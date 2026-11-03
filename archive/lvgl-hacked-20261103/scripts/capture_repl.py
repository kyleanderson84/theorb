#!/usr/bin/env python3
import sys, time, os
try:
    import serial
except ImportError:
    print("pyserial not installed. Run: pip install pyserial")
    sys.exit(1)

PORT = '/dev/ttyACM0'
BAUD   = 115200
LOG    = 'repl_output.txt'
RUN_SEC = 30

def main():
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(3)
    ser.read(200)
    ser.write(b'\r\n')
    time.sleep(0.5)

    with open(LOG, 'w') as out:
        start = time.time()
        last_send = start
        while time.time() - start < RUN_SEC:
            data = ser.read(256)
            if data:
                out.write(data.decode('utf-8', errors='replace'))
                out.flush()
            if time.time() - last_send > 1.0:
                ser.write(b'\r\n')
                last_send = time.time()
        out.write("\n=== REPL session end ===\n")
    ser.close()
    print(f"Log written to {LOG}")

if __name__ == '__main__':
    main()