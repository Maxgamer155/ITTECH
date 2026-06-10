#!/usr/bin/env python3
"""
Test-Weboberflaeche fuer einen IR-Transmitter am Raspberry Pi.

Hardware:
- IR-Transmitter DAT/S -> GPIO26 / Pin 37
- IR-Transmitter VCC   -> 3.3V oder 5V je nach Modul
- IR-Transmitter GND   -> GND

Start:
python3 src/test_ir_transmitter.py

Web:
http://<PI-IP>:8090
"""

from __future__ import annotations

import argparse
import html
import signal
import socketserver
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO ist nicht installiert. Dieses Script muss auf dem Raspberry Pi laufen.")
    raise SystemExit(1)


DEFAULT_GPIO = 26
DEFAULT_PORT = 8090
DEFAULT_CARRIER_HZ = 38_000
DEFAULT_DUTY_CYCLE = 33

BUTTON_CODES: dict[str, int] = {
    "power": 0xFFA25D,
    "ch": 0xFF629D,
    "ch_plus": 0xFFE21D,
    "prev": 0xFF22DD,
    "next": 0xFF02FD,
    "play": 0xFFC23D,
    "vol_minus": 0xFFE01F,
    "vol_plus": 0xFFA857,
    "eq": 0xFF906F,
    "0": 0xFF6897,
    "100_plus": 0xFF9867,
    "200_plus": 0xFFB04F,
    "1": 0xFF30CF,
    "2": 0xFF18E7,
    "3": 0xFF7A85,
    "4": 0xFF10EF,
    "5": 0xFF38C7,
    "6": 0xFF5AA5,
    "7": 0xFF42BD,
    "8": 0xFF4AB5,
    "9": 0xFF52AD,
}


def parse_code(value: str) -> int:
    cleaned = value.strip().lower().replace("_", "")
    if cleaned.startswith("0x"):
        return int(cleaned, 16)
    if any(char in "abcdef" for char in cleaned):
        return int(cleaned, 16)
    return int(cleaned, 10)


class IrTransmitter:
    def __init__(self, gpio_pin: int, carrier_hz: int, duty_cycle: int):
        self.gpio_pin = gpio_pin
        self.carrier_hz = carrier_hz
        self.duty_cycle = duty_cycle
        self.pwm = None
        self.lock = threading.Lock()

    def setup(self) -> None:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.gpio_pin, GPIO.OUT, initial=GPIO.LOW)
        self.pwm = GPIO.PWM(self.gpio_pin, self.carrier_hz)
        self.pwm.start(0)

    def cleanup(self) -> None:
        if self.pwm is not None:
            self.pwm.ChangeDutyCycle(0)
            self.pwm.stop()
        GPIO.cleanup(self.gpio_pin)

    def carrier_on(self) -> None:
        assert self.pwm is not None
        self.pwm.ChangeDutyCycle(self.duty_cycle)

    def carrier_off(self) -> None:
        assert self.pwm is not None
        self.pwm.ChangeDutyCycle(0)

    def mark(self, seconds: float) -> None:
        self.carrier_on()
        time.sleep(seconds)

    def space(self, seconds: float) -> None:
        self.carrier_off()
        time.sleep(seconds)

    def send_remote_code(self, remote_code: int, repeats: int = 1) -> None:
        command = (remote_code >> 8) & 0xFF
        command_inverse = remote_code & 0xFF
        self.send_nec(address=0x00, command=command, command_inverse=command_inverse, repeats=repeats)

    def send_nec(self, address: int, command: int, command_inverse: int | None = None, repeats: int = 1) -> None:
        address &= 0xFF
        command &= 0xFF
        address_inverse = address ^ 0xFF
        if command_inverse is None:
            command_inverse = command ^ 0xFF
        command_inverse &= 0xFF
        frame = address | (address_inverse << 8) | (command << 16) | (command_inverse << 24)

        with self.lock:
            for index in range(max(1, repeats)):
                self.send_frame(frame)
                if index + 1 < repeats:
                    self.space(0.08)
            self.carrier_off()

    def send_frame(self, frame: int) -> None:
        self.mark(0.009)
        self.space(0.0045)

        for bit_index in range(32):
            bit = (frame >> bit_index) & 1
            self.mark(0.000562)
            self.space(0.001687 if bit else 0.000562)

        self.mark(0.000562)
        self.space(0.02)


class WebApp:
    def __init__(self, transmitter: IrTransmitter, port: int, repeats: int):
        self.transmitter = transmitter
        self.port = port
        self.repeats = repeats
        self.last_message = "Bereit"
        self.server: socketserver.ThreadingTCPServer | None = None

    def start(self) -> None:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: object) -> None:
                del fmt, args

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self.send_html(app.render())
                    return
                if parsed.path == "/send":
                    app.handle_send(parse_qs(parsed.query))
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.end_headers()
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def send_html(self, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = socketserver.ThreadingTCPServer(("0.0.0.0", self.port), Handler)
        self.server.serve_forever()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    def handle_send(self, params: dict[str, list[str]]) -> None:
        try:
            button = params.get("button", [""])[0]
            custom_code = params.get("code", [""])[0]

            if button:
                code = BUTTON_CODES[button]
                label = button
            else:
                code = parse_code(custom_code)
                label = custom_code

            self.transmitter.send_remote_code(code, repeats=self.repeats)
            self.last_message = f"Gesendet: {label} / 0x{code:06X}"
        except Exception as exc:
            self.last_message = f"Fehler: {exc}"

    def render(self) -> str:
        buttons = "".join(
            f'<a class="btn" href="/send?button={html.escape(name)}">{html.escape(name)}</a>'
            for name in BUTTON_CODES
        )
        message = html.escape(self.last_message)
        return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IR Transmitter Test</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 1.5rem; background: #111827; color: #f9fafb; }}
    main {{ max-width: 720px; margin: auto; }}
    .card {{ background: #1f2937; border-radius: 14px; padding: 1rem; margin: 1rem 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: .5rem; }}
    .btn, button {{ display: block; padding: .75rem; border-radius: 10px; background: #93c5fd; color: #111827; text-align: center; text-decoration: none; font-weight: 700; border: 0; }}
    input {{ width: 100%; box-sizing: border-box; padding: .75rem; border-radius: 10px; border: 0; margin: .4rem 0; }}
    small {{ color: #cbd5e1; }}
  </style>
</head>
<body>
<main>
  <h1>IR Transmitter Test</h1>
  <section class="card">
    <p><strong>{message}</strong></p>
    <small>Signal: GPIO{self.transmitter.gpio_pin} / Pin 37, Web-Port: {self.port}</small>
  </section>
  <section class="card">
    <h2>Tasten</h2>
    <div class="grid">{buttons}</div>
  </section>
  <section class="card">
    <h2>Eigenen Code senden</h2>
    <form action="/send" method="get">
      <input name="code" placeholder="z. B. 0xFFA25D oder 16753245" required>
      <button type="submit">Senden</button>
    </form>
  </section>
</main>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="IR-Transmitter-Test mit Weboberflaeche")
    parser.add_argument("--gpio", type=int, default=DEFAULT_GPIO, help="BCM-GPIO, Standard: 26")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Web-Port, Standard: 8090")
    parser.add_argument("--repeats", type=int, default=1, help="Sende-Wiederholungen")
    parser.add_argument("--send", help="Code direkt senden, z. B. 0xFFA25D")
    parser.add_argument("--button", help="Bekannte Taste direkt senden, z. B. play oder 1")
    args = parser.parse_args()

    transmitter = IrTransmitter(args.gpio, DEFAULT_CARRIER_HZ, DEFAULT_DUTY_CYCLE)
    transmitter.setup()

    stop_event = threading.Event()

    def stop(signum: int, frame: object) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        if args.button:
            transmitter.send_remote_code(BUTTON_CODES[args.button], repeats=args.repeats)
            print(f"Gesendet: {args.button}")
            return 0

        if args.send:
            code = parse_code(args.send)
            transmitter.send_remote_code(code, repeats=args.repeats)
            print(f"Gesendet: 0x{code:06X}")
            return 0

        app = WebApp(transmitter, args.port, args.repeats)
        print(f"IR-Transmitter-Webinterface: http://0.0.0.0:{args.port}")
        web_thread = threading.Thread(target=app.start, daemon=True)
        web_thread.start()

        while not stop_event.is_set():
            time.sleep(0.2)

        app.stop()
    finally:
        transmitter.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
