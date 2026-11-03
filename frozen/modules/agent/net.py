# agent/net.py — Network cascade + HTTP transport for the AI supervisor.
#
# Implements the connection cascade from the design doc:
#   1. Preferred / known WPA2 networks (config/known_nets.json)
#   2. Any open network (authmode OPEN) -> TLS-only upstream
#   3. Give up gracefully (never hang, log the failure)
#
# Uses synchronous sockets wrapped so the supervisor can drive them from its
# asyncio loop without blocking the GUI for long. All upstream calls default to
# HTTPS; plain HTTP is refused unless allow_insecure is explicitly set.

import network
import time
import socket
import ssl
import ujson as json

try:
    import urequests  # provided by frozen bundle-networking
except ImportError:
    urequests = None

KNOWN_NETS = "config/known_nets.json"


def _load_known():
    try:
        with open(KNOWN_NETS) as f:
            return json.load(f)
    except Exception:
        return {}


class Net:
    def __init__(self, timeout=8):
        self.wlan = network.WLAN(network.STA_IF)
        self.timeout = timeout
        self.connected = False
        self.ssid = None
        self.last_error = None

    def _connect(self, ssid, pw):
        w = self.wlan
        if not w.active():
            w.active(True)
        try:
            w.disconnect()
        except Exception:
            pass
        try:
            w.connect(ssid, pw)
        except Exception as e:
            self.last_error = "connect:%s" % e
            return False
        t0 = time.time()
        while not w.isconnected():
            if time.time() - t0 > self.timeout:
                self.last_error = "timeout:%s" % ssid
                return False
            time.sleep_ms(150)
        self.connected = True
        self.ssid = ssid
        self.last_error = None
        return True

    def connect(self):
        """Run the cascade. Returns True on any successful link."""
        known = _load_known()
        try:
            scan = self.wlan.scan()  # (ssid, bssid, ch, rssi, authmode, hidden)
        except Exception as e:
            self.last_error = "scan:%s" % e
            return False

        seen = set()
        # 1. Known networks first, strongest RSSI first
        candidates = []
        for s in scan:
            try:
                ssid = s[0].decode() if isinstance(s[0], bytes) else s[0]
            except Exception:
                continue
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            candidates.append((s[3], ssid, s[4]))
        candidates.sort(reverse=True)

        for rssi, ssid, auth in candidates:
            if ssid in known:
                pw = known[ssid]
                if self._connect(ssid, pw):
                    return True

        # 2. Open networks (authmode 0), strongest first, TLS enforced upstream
        for rssi, ssid, auth in candidates:
            if auth == 0:
                if self._connect(ssid, ""):
                    return True

        self.last_error = self.last_error or "no-known-or-open"
        return False

    def request(self, method, url, body=None, headers=None, allow_insecure=False):
        """Minimal HTTP(S) request. Returns (status, bytes) or (None, error)."""
        if url.startswith("http://") and not allow_insecure:
            return None, "insecure-url-refused"
        if urequests is not None:
            try:
                r = urequests.request(method, url, data=body, headers=headers or {})
                data = r.content
                status = r.status_code
                r.close()
                return status, data
            except Exception as e:
                return None, "req:%s" % e
        # Fallback raw socket (no chunked decode) for simple endpoints
        return self._raw_request(method, url, body, headers, allow_insecure)

    def _raw_request(self, method, url, body, headers, allow_insecure):
        try:
            if url.startswith("https://"):
                host, _, rest = url[8:].partition("/")
                port = 443
                sock = socket.socket()
                sock.settimeout(self.timeout)
                sock = ssl.wrap_socket(sock, server_hostname=host.split(":")[0])
            else:
                host, _, rest = url[7:].partition("/")
                port = 80
                sock = socket.socket()
                sock.settimeout(self.timeout)
            if ":" in host:
                host, p = host.split(":")
                port = int(p)
            sock.connect(socket.getaddrinfo(host, port)[0][-1])
            path = "/" + rest
            req = "%s %s HTTP/1.0\r\nHost: %s\r\n" % (method, path, host)
            for k, v in (headers or {}).items():
                req += "%s: %s\r\n" % (k, v)
            if body:
                req += "Content-Length: %d\r\n" % len(body)
            req += "\r\n"
            sock.send(req.encode())
            if body:
                sock.send(body)
            chunks = []
            while True:
                d = sock.recv(512)
                if not d:
                    break
                chunks.append(d)
            sock.close()
            raw = b"".join(chunks)
            head, _, payload = raw.partition(b"\r\n\r\n")
            status = int(head.split(b" ")[1])
            return status, payload
        except Exception as e:
            return None, "raw:%s" % e

    def close(self):
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        self.connected = False
