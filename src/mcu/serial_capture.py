#!/usr/bin/env python3
"""Capture the serial console of the XAI firmware until its '#' end marker.

For boards on the bench (NUCLEO-L476RG through the ST-LINK virtual COM port).
Flash firmware/xai_nucleo-l476rg.bin first (copy it to the ST-LINK USB drive),
start this script, then press RESET so the log starts at boot.

    python -m mcu.serial_capture /dev/ttyACM0 results/mcu/xai-nucleo-l476rg/raw.log

The pqm4 libopencm3 HAL used by the STM32 build prints at 38400 baud.
Needs pyserial.
"""
import argparse
import sys
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("port", help="serial port, e.g. /dev/ttyACM0 or COM5")
    ap.add_argument("out", help="raw log to write")
    ap.add_argument("--baud", type=int, default=38400)
    ap.add_argument("--timeout", type=float, default=3600,
                    help="give up after this many seconds without the end marker")
    a = ap.parse_args()
    import serial

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    buf = ""
    with serial.Serial(a.port, a.baud, timeout=1) as ser, open(out, "w") as f:
        print(f"{a.port} @ {a.baud}: press RESET on the board", file=sys.stderr)
        while time.time() - t0 < a.timeout:
            chunk = ser.read(256).decode("ascii", errors="replace")
            if not chunk:
                continue
            f.write(chunk)
            f.flush()
            sys.stdout.write(chunk)
            buf = (buf + chunk)[-4096:]
            if any(line.strip() == "#" for line in buf.splitlines()):
                print(f"\nend marker received -> {out}", file=sys.stderr)
                return 0
    print(f"timeout without end marker -> {out}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
