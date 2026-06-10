#!/usr/bin/env python3
"""
Isolierter Test fuer den HC-SR04 Ultraschallsensor.

Standard-Pins passend zum Schrankenprojekt:
- Trig: GPIO17 / Pin 11
- Echo: GPIO5 / Pin 29, nur ueber Spannungsteiler anschliessen
"""

from __future__ import annotations

import argparse
import statistics
import time

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO ist nicht installiert. Dieses Script muss auf dem Raspberry Pi laufen.")
    raise SystemExit(1)


SPEED_OF_SOUND_CM_PER_SECOND = 34300


def measure_distance_cm(trigger_pin: int, echo_pin: int, timeout_seconds: float) -> tuple[float | None, str]:
    GPIO.output(trigger_pin, GPIO.LOW)
    time.sleep(0.000002)
    GPIO.output(trigger_pin, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(trigger_pin, GPIO.LOW)

    wait_start = time.monotonic()
    while GPIO.input(echo_pin) == GPIO.LOW:
        if time.monotonic() - wait_start > timeout_seconds:
            return None, "timeout: Echo wurde nicht HIGH"

    pulse_start = time.monotonic()
    while GPIO.input(echo_pin) == GPIO.HIGH:
        if time.monotonic() - pulse_start > timeout_seconds:
            return None, "timeout: Echo blieb zu lange HIGH"

    pulse_duration = time.monotonic() - pulse_start
    distance_cm = pulse_duration * SPEED_OF_SOUND_CM_PER_SECOND / 2
    return round(distance_cm, 1), "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="HC-SR04 Ultraschallsensor testen")
    parser.add_argument("--trigger", type=int, default=17, help="BCM-GPIO fuer Trig, Standard: 17")
    parser.add_argument("--echo", type=int, default=5, help="BCM-GPIO fuer Echo, Standard: 5")
    parser.add_argument("--interval", type=float, default=0.5, help="Pause zwischen Messungen")
    parser.add_argument("--timeout", type=float, default=0.025, help="Echo-Timeout in Sekunden")
    parser.add_argument("--samples", type=int, default=0, help="Anzahl Messungen, 0 = endlos")
    args = parser.parse_args()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(args.trigger, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(args.echo, GPIO.IN)

    print("HC-SR04 Test gestartet")
    print(f"Trig: GPIO{args.trigger}")
    print(f"Echo: GPIO{args.echo}  ACHTUNG: Echo nur ueber Spannungsteiler an den Pi anschliessen")
    print("Abbruch mit Strg+C")

    valid_measurements: list[float] = []
    measurement_count = 0

    try:
        while args.samples <= 0 or measurement_count < args.samples:
            measurement_count += 1
            distance_cm, status = measure_distance_cm(args.trigger, args.echo, args.timeout)
            if distance_cm is None:
                print(f"{measurement_count:04d}: {status}")
            else:
                valid_measurements.append(distance_cm)
                if len(valid_measurements) > 10:
                    valid_measurements.pop(0)
                average = statistics.mean(valid_measurements)
                print(f"{measurement_count:04d}: {distance_cm:6.1f} cm   Mittelwert(<=10): {average:6.1f} cm")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nTest beendet")
    finally:
        GPIO.output(args.trigger, GPIO.LOW)
        GPIO.cleanup((args.trigger, args.echo))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
