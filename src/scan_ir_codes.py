#!/usr/bin/env python3
"""
IR-Codes der Fernbedienung auslesen.

Start auf dem Raspberry Pi:
python3 src/scan_ir_codes.py
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from access_gate import IrConfig, NecIrReader  # noqa: E402

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO ist nicht installiert. Dieses Script muss auf dem Raspberry Pi laufen.")
    raise SystemExit(1)


IR_PIN = 4
stop_event = threading.Event()


def print_code(code: int) -> None:
    print(f"Code: hex=0x{code:06X}, dezimal={code}")


def stop(signum: int, frame: object) -> None:
    del signum, frame
    stop_event.set()


def main() -> int:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_PIN, GPIO.IN)

    print(f"IR-Scanner gestartet. OUT/S am IR-Empfaenger muss an GPIO{IR_PIN} liegen.")
    print("Tasten auf der Fernbedienung druecken. Abbruch mit Strg+C.")

    reader = NecIrReader(IR_PIN, print_code, IrConfig(), stop_event)
    reader.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        GPIO.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
