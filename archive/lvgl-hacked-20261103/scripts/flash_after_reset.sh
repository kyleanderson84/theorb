#!/bin/bash
# Flash the custom ESP32-S3 build the moment the board is reachable.
# Handles both: app mode (PID 4001, trigger bootloader via REPL) and
# download mode (PID 1001, flash directly).
LOG=/home/kyle_dude/theorb/flash_after_reset.log
BUILD=/home/kyle_dude/theorb/micropython/ports/esp32/build-ESP32_GENERIC_S3-SPIRAM_OCT
echo "FLASH_WATCHER start $(date)" > $LOG

wait_for_pid() {
  local want=$1 t0=$2
  while true; do
    PID=$(for d in /sys/bus/usb/devices/*/; do
      v=$(cat $d/idVendor 2>/dev/null); [ "$v" = "303a" ] && cat $d/idProduct 2>/dev/null
    done | head -1)
    [ "$PID" = "$want" ] && return 0
    [ $((SECONDS - t0)) -gt 30 ] && return 1
    sleep 0.5
  done
}

while true; do
  PORT=$(ls /dev/ttyACM* 2>/dev/null | head -1)
  [ -z "$PORT" ] && { sleep 1; continue; }
  PID=$(for d in /sys/bus/usb/devices/*/; do
    v=$(cat $d/idVendor 2>/dev/null); [ "$v" = "303a" ] && cat $d/idProduct 2>/dev/null
  done | head -1)
  echo "$(date +%T) port=$PORT pid=$PID" >> $LOG

  if [ "$PID" = "4001" ]; then
    echo "$(date +%T) APP MODE - trying machine.bootloader()" >> $LOG
    /home/kyle_dude/theorb/.venv/bin/python - <<PYEOF >> $LOG 2>&1
import serial, time
s = serial.Serial(port="$PORT", baudrate=115200, timeout=0.5, write_timeout=1)
s.dtr=False; s.rts=False
time.sleep(1)
s.reset_input_buffer()
s.write(b'\r\n'); time.sleep(0.5); s.read(2000)
s.write(b'machine.bootloader()\r\n')
s.flush()
s.close()
print("bootloader cmd sent")
PYEOF
    sleep 2
    wait_for_pid 1001 0 && echo "$(date +%T) chip in download mode" >> $LOG
  fi

  # Re-scan for download mode port
  PORT=$(ls /dev/ttyACM* 2>/dev/null | head -1)
  PID=$(for d in /sys/bus/usb/devices/*/; do
    v=$(cat $d/idVendor 2>/dev/null); [ "$v" = "303a" ] && cat $d/idProduct 2>/dev/null
  done | head -1)
  if [ "$PID" = "1001" ]; then
    echo "$(date +%T) DOWNLOAD MODE - flashing $PORT" >> $LOG
    esptool --chip esp32s3 -p $PORT --before no-reset --after hard-reset write-flash \
      --flash-mode dio --flash-freq 80m --flash-size 16MB \
      0x0 $BUILD/bootloader/bootloader.bin \
      0x8000 $BUILD/partition_table/partition-table.bin \
      0x10000 $BUILD/micropython.bin >> $LOG 2>&1
    rc=$?
    echo "$(date +%T) FLASH_DONE rc=$rc" >> $LOG
    exit $rc
  fi

  sleep 1
done
