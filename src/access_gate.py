#!/usr/bin/env python3
"""
PIN-gesicherte Zugangsschranke mit Raspberry Pi 4.

Funktionen:
- IR-Fernbedienung fuer PIN-Eingabe und Admin-Tasten
- HC-SR04-Ultraschall-Abstandsmessung
- Servo-Schrankarm
- 16x2 LCD mit PCF8574-I2C-Adapter
- rote/gruene LED
- Buzzer
- lokale Weboberflaeche mit Status und Steuerbefehlen
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import queue
import signal
import socketserver
import sys
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

try:
    import RPi.GPIO as GPIO
except ImportError:  # pragma: no cover - nur fuer Syntaxpruefung ausserhalb des Pi
    GPIO = None

try:
    import smbus
except ImportError:  # pragma: no cover
    try:
        import smbus2 as smbus
    except ImportError:
        smbus = None


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "access_gate.log"


class GateState(str, Enum):
    CLOSED = "GESCHLOSSEN"
    OPENING = "OEFFNET"
    OPEN = "OFFEN"
    CLOSING = "SCHLIESST"
    ALARM = "ALARM"


@dataclass
class Pins:
    servo: int = 18
    ir_receiver: int = 4
    ultrasonic_trigger: int = 17
    ultrasonic_echo: int = 5
    red_led: int = 23
    green_led: int = 24
    button: int = 27
    buzzer: int = 22


@dataclass
class ServoConfig:
    closed_duty_cycle: float = 2.5
    open_duty_cycle: float = 7.2
    pwm_hz: int = 50
    move_seconds: float = 0.7


@dataclass
class LcdConfig:
    enabled: bool = True
    i2c_bus: int = 1
    address: int = 0x27
    columns: int = 16
    rows: int = 2


@dataclass
class UltrasonicConfig:
    enabled: bool = True
    warning_distance_cm: float = 80.0
    max_distance_cm: float = 300.0
    sample_interval_seconds: float = 0.35
    echo_timeout_seconds: float = 0.025
    auto_open_cooldown_seconds: float = 1.0


@dataclass
class ButtonConfig:
    active_low: bool = True
    pull: str = "up"


@dataclass
class IrConfig:
    enabled: bool = True
    pulse_timeout_seconds: float = 0.08
    repeat_cooldown_seconds: float = 0.25
    open_button: str = "ch_plus"
    close_button: str = "ch_minus"
    delete_button: str = "prev"
    mute_button: str = "eq"
    lock_button: str = "power"
    confirm_button: str = "play"
    button_codes: dict[str, int] = field(
        default_factory=lambda: {
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
    )


@dataclass
class AppConfig:
    pin_code: str = "1234"
    auto_close_seconds: int = 5
    max_wrong_pins: int = 3
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    pins: Pins = field(default_factory=Pins)
    servo: ServoConfig = field(default_factory=ServoConfig)
    lcd: LcdConfig = field(default_factory=LcdConfig)
    ultrasonic: UltrasonicConfig = field(default_factory=UltrasonicConfig)
    button: ButtonConfig = field(default_factory=ButtonConfig)
    ir: IrConfig = field(default_factory=IrConfig)


@dataclass
class Status:
    state: GateState = GateState.CLOSED
    locked: bool = False
    alarm_muted: bool = False
    object_detected: bool = False
    distance_cm: Optional[float] = None
    entered_pin_masked: str = ""
    wrong_attempts: int = 0
    countdown: int = 0
    last_event: str = "System startet"
    last_ir_button: str = ""
    last_update: str = ""


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def dataclass_from_dict(cls, data: dict[str, object]):
    allowed = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in data.items() if key in allowed})


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        config = AppConfig()
        path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
        return config

    raw = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(
        pin_code=str(raw.get("pin_code", "1234")),
        auto_close_seconds=int(raw.get("auto_close_seconds", 5)),
        max_wrong_pins=int(raw.get("max_wrong_pins", 3)),
        web_host=str(raw.get("web_host", "0.0.0.0")),
        web_port=int(raw.get("web_port", 8080)),
        pins=dataclass_from_dict(Pins, raw.get("pins", {})),
        servo=dataclass_from_dict(ServoConfig, raw.get("servo", {})),
        lcd=dataclass_from_dict(LcdConfig, raw.get("lcd", {})),
        ultrasonic=dataclass_from_dict(UltrasonicConfig, raw.get("ultrasonic", {})),
        button=dataclass_from_dict(ButtonConfig, raw.get("button", {})),
        ir=dataclass_from_dict(IrConfig, raw.get("ir", {})),
    )


class LcdDisplay:
    ENABLE = 0b00000100
    BACKLIGHT = 0b00001000
    REGISTER_SELECT = 0b00000001

    def __init__(self, config: LcdConfig):
        self.config = config
        self.available = False
        self.bus = None

        if not config.enabled:
            return
        if smbus is None:
            logging.warning("smbus/smbus2 nicht verfuegbar, LCD deaktiviert")
            return

        try:
            self.bus = smbus.SMBus(config.i2c_bus)
            self._init_lcd()
            self.available = True
        except Exception as exc:
            logging.warning("LCD konnte nicht initialisiert werden: %s", exc)

    def _write_byte(self, data: int) -> None:
        assert self.bus is not None
        self.bus.write_byte(self.config.address, data | self.BACKLIGHT)

    def _pulse_enable(self, data: int) -> None:
        self._write_byte(data | self.ENABLE)
        time.sleep(0.0005)
        self._write_byte(data & ~self.ENABLE)
        time.sleep(0.0001)

    def _write4(self, data: int) -> None:
        self._write_byte(data)
        self._pulse_enable(data)

    def _send(self, value: int, mode: int = 0) -> None:
        high = mode | (value & 0xF0)
        low = mode | ((value << 4) & 0xF0)
        self._write4(high)
        self._write4(low)

    def _command(self, value: int) -> None:
        self._send(value, 0)
        time.sleep(0.002)

    def _init_lcd(self) -> None:
        time.sleep(0.05)
        self._write4(0x30)
        time.sleep(0.005)
        self._write4(0x30)
        time.sleep(0.005)
        self._write4(0x30)
        time.sleep(0.005)
        self._write4(0x20)
        self._command(0x28)
        self._command(0x0C)
        self._command(0x06)
        self.clear()

    def clear(self) -> None:
        if self.available:
            self._command(0x01)

    def show(self, line1: str, line2: str = "") -> None:
        if not self.available:
            return

        lines = [line1[: self.config.columns], line2[: self.config.columns]]
        addresses = [0x80, 0xC0]
        for index, text in enumerate(lines[: self.config.rows]):
            self._command(addresses[index])
            padded = text.ljust(self.config.columns)
            for char in padded:
                self._send(ord(char), self.REGISTER_SELECT)


class Hardware:
    def __init__(self, config: AppConfig):
        if GPIO is None:
            raise RuntimeError("RPi.GPIO ist nicht installiert. Dieses Programm muss auf dem Raspberry Pi laufen.")

        self.config = config
        self.servo_pwm = None
        self.buzzer_pwm = None
        self.lcd = LcdDisplay(config.lcd)

    def setup(self) -> None:
        pins = self.config.pins
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(pins.red_led, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pins.green_led, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pins.buzzer, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pins.servo, GPIO.OUT)
        GPIO.setup(pins.ultrasonic_trigger, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pins.ultrasonic_echo, GPIO.IN)
        GPIO.setup(pins.ir_receiver, GPIO.IN)
        button_pull = GPIO.PUD_UP if self.config.button.pull == "up" else GPIO.PUD_DOWN
        GPIO.setup(pins.button, GPIO.IN, pull_up_down=button_pull)

        self.servo_pwm = GPIO.PWM(pins.servo, self.config.servo.pwm_hz)
        self.servo_pwm.start(0)
        self.buzzer_pwm = GPIO.PWM(pins.buzzer, 1500)
        self.buzzer_pwm.start(0)

    def cleanup(self) -> None:
        try:
            if self.servo_pwm is not None:
                self.servo_pwm.ChangeDutyCycle(0)
                self.servo_pwm.stop()
            if self.buzzer_pwm is not None:
                self.buzzer_pwm.ChangeDutyCycle(0)
                self.buzzer_pwm.stop()
            GPIO.cleanup()
        except Exception:
            logging.exception("GPIO-Cleanup fehlgeschlagen")

    def set_leds(self, red: bool, green: bool) -> None:
        GPIO.output(self.config.pins.red_led, GPIO.HIGH if red else GPIO.LOW)
        GPIO.output(self.config.pins.green_led, GPIO.HIGH if green else GPIO.LOW)

    def move_servo(self, duty_cycle: float) -> None:
        assert self.servo_pwm is not None
        self.servo_pwm.ChangeDutyCycle(duty_cycle)
        time.sleep(self.config.servo.move_seconds)
        self.servo_pwm.ChangeDutyCycle(0)

    def open_gate(self) -> None:
        self.move_servo(self.config.servo.open_duty_cycle)

    def close_gate(self) -> None:
        self.move_servo(self.config.servo.closed_duty_cycle)

    def beep(self, count: int = 1, duration: float = 0.08, pause: float = 0.08, frequency: int = 1800) -> None:
        assert self.buzzer_pwm is not None
        for _ in range(count):
            self.buzzer_pwm.ChangeFrequency(frequency)
            self.buzzer_pwm.ChangeDutyCycle(50)
            time.sleep(duration)
            self.buzzer_pwm.ChangeDutyCycle(0)
            time.sleep(pause)

    def alarm_beep(self) -> None:
        self.beep(count=3, duration=0.12, pause=0.07, frequency=2300)

    def read_button_pressed(self) -> bool:
        pressed_level = GPIO.LOW if self.config.button.active_low else GPIO.HIGH
        return GPIO.input(self.config.pins.button) == pressed_level

    def measure_distance_cm(self) -> Optional[float]:
        if not self.config.ultrasonic.enabled:
            return None

        pins = self.config.pins
        timeout = self.config.ultrasonic.echo_timeout_seconds

        GPIO.output(pins.ultrasonic_trigger, GPIO.LOW)
        time.sleep(0.000002)
        GPIO.output(pins.ultrasonic_trigger, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(pins.ultrasonic_trigger, GPIO.LOW)

        wait_start = time.monotonic()
        while GPIO.input(pins.ultrasonic_echo) == GPIO.LOW:
            if time.monotonic() - wait_start > timeout:
                return None

        pulse_start = time.monotonic()
        while GPIO.input(pins.ultrasonic_echo) == GPIO.HIGH:
            if time.monotonic() - pulse_start > timeout:
                return None

        pulse_duration = time.monotonic() - pulse_start
        distance_cm = pulse_duration * 34300 / 2
        if distance_cm <= 0 or distance_cm > self.config.ultrasonic.max_distance_cm:
            return None
        return round(distance_cm, 1)

    def show_lcd(self, line1: str, line2: str = "") -> None:
        self.lcd.show(line1, line2)


class NecIrReader(threading.Thread):
    def __init__(self, pin: int, callback: Callable[[int], None], config: IrConfig, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.pin = pin
        self.callback = callback
        self.config = config
        self.stop_event = stop_event
        self.last_code = 0
        self.last_time = 0.0

    def run(self) -> None:
        if GPIO is None or not self.config.enabled:
            return

        while not self.stop_event.is_set():
            code = self._read_code()
            if code is None:
                continue
            now = time.monotonic()
            if code == self.last_code and now - self.last_time < self.config.repeat_cooldown_seconds:
                continue
            self.last_code = code
            self.last_time = now
            self.callback(code)

    def _wait_for_level(self, level: int, timeout: float) -> Optional[float]:
        start = time.monotonic()
        while GPIO.input(self.pin) != level:
            if time.monotonic() - start > timeout or self.stop_event.is_set():
                return None
        reached = time.monotonic()
        while GPIO.input(self.pin) == level:
            if time.monotonic() - reached > timeout or self.stop_event.is_set():
                return None
        return time.monotonic() - reached

    def _read_code(self) -> Optional[int]:
        low_duration = self._wait_for_level(GPIO.LOW, self.config.pulse_timeout_seconds)
        if low_duration is None or not 0.006 <= low_duration <= 0.012:
            return None

        high_duration = self._wait_for_level(GPIO.HIGH, self.config.pulse_timeout_seconds)
        if high_duration is None:
            return None
        if 0.0018 <= high_duration <= 0.0028:
            return self.last_code if self.last_code else None
        if not 0.0035 <= high_duration <= 0.006:
            return None

        bits: list[int] = []
        for _ in range(32):
            low = self._wait_for_level(GPIO.LOW, self.config.pulse_timeout_seconds)
            high = self._wait_for_level(GPIO.HIGH, self.config.pulse_timeout_seconds)
            if low is None or high is None:
                return None
            bits.append(1 if high > 0.001 else 0)

        value = 0
        for index, bit in enumerate(bits):
            value |= bit << index

        address = value & 0xFF
        address_inv = (value >> 8) & 0xFF
        command = (value >> 16) & 0xFF
        command_inv = (value >> 24) & 0xFF

        if (address ^ address_inv) != 0xFF or (command ^ command_inv) != 0xFF:
            return None

        return (address_inv << 16) | (command << 8) | command_inv


class AccessGateApp:
    def __init__(self, config: AppConfig):
        self.config = config
        self.hardware = Hardware(config)
        self.status = Status(last_update=self._now())
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.ir_name_by_code = {code: name for name, code in config.ir.button_codes.items()}
        self.ir_reader = NecIrReader(config.pins.ir_receiver, self._queue_ir_code, config.ir, self.stop_event)
        self.web_server: Optional[socketserver.ThreadingTCPServer] = None
        self.last_auto_open_at = 0.0

    def _now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _set_event(self, message: str) -> None:
        self.status.last_event = message
        self.status.last_update = self._now()
        logging.info(message)

    def _queue_ir_code(self, code: int) -> None:
        button = self.ir_name_by_code.get(code, f"unknown:{code:06X}")
        self.events.put(("ir", button))

    def start(self) -> None:
        self.hardware.setup()
        self.hardware.close_gate()
        self.hardware.set_leds(red=True, green=False)
        self.hardware.show_lcd("PIN-Schranke", "geschlossen")
        self._set_event("System bereit")

        self.ir_reader.start()
        threading.Thread(target=self._sensor_loop, daemon=True).start()
        threading.Thread(target=self._button_loop, daemon=True).start()
        self._start_web_server()

        try:
            while not self.stop_event.is_set():
                try:
                    kind, value = self.events.get(timeout=0.2)
                except queue.Empty:
                    continue
                if kind == "ir":
                    self.handle_ir_button(value)
                elif kind == "button":
                    self.toggle_gate(source="Taster")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self.stop_event.set()
        if self.web_server is not None:
            self.web_server.shutdown()
            self.web_server.server_close()
        self.hardware.show_lcd("System", "gestoppt")
        self.hardware.cleanup()

    def _sensor_loop(self) -> None:
        while not self.stop_event.is_set():
            distance_cm = self.hardware.measure_distance_cm()
            object_detected = (
                distance_cm is not None
                and distance_cm <= self.config.ultrasonic.warning_distance_cm
            )

            with self.lock:
                self.status.distance_cm = distance_cm
                self.status.object_detected = object_detected
                state = self.status.state
                locked = self.status.locked

            if object_detected:
                self._handle_distance_detection(distance_cm, state, locked)
            time.sleep(self.config.ultrasonic.sample_interval_seconds)

    def _button_loop(self) -> None:
        pressed_at = 0.0
        while not self.stop_event.is_set():
            if self.hardware.read_button_pressed():
                now = time.monotonic()
                if now - pressed_at > 0.8:
                    self.events.put(("button", "toggle"))
                    pressed_at = now
            time.sleep(0.05)

    def _start_web_server(self) -> None:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: object) -> None:
                logging.debug("Web: " + fmt, *args)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._send_html(app.render_page())
                elif parsed.path == "/api/status":
                    self._send_json(app.status_snapshot())
                elif parsed.path == "/action":
                    params = parse_qs(parsed.query)
                    action = params.get("name", [""])[0]
                    app.handle_web_action(action)
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", "/")
                    self.end_headers()
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def _send_html(self, body: str) -> None:
                data = body.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_json(self, payload: dict[str, object]) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.web_server = socketserver.ThreadingTCPServer((self.config.web_host, self.config.web_port), Handler)
        threading.Thread(target=self.web_server.serve_forever, daemon=True).start()
        logging.info("Weboberflaeche: http://%s:%s", self.config.web_host, self.config.web_port)

    def status_snapshot(self) -> dict[str, object]:
        with self.lock:
            data = asdict(self.status)
            data["state"] = self.status.state.value
            data["distance_display"] = "n/a" if self.status.distance_cm is None else f"{self.status.distance_cm:.1f}"
            return data

    def render_page(self) -> str:
        status = self.status_snapshot()
        escaped = {key: html.escape(str(value)) for key, value in status.items()}
        return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="2">
  <title>PIN-Zugangsschranke</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; background: #111827; color: #f9fafb; }}
    main {{ max-width: 780px; margin: auto; }}
    .card {{ background: #1f2937; border-radius: 14px; padding: 1rem 1.25rem; margin: 1rem 0; }}
    .state {{ font-size: 2.2rem; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; }}
    a.button {{ display: block; text-align: center; padding: .8rem; border-radius: 10px; color: #111827; background: #93c5fd; text-decoration: none; font-weight: 700; }}
    a.warn {{ background: #fca5a5; }}
    a.ok {{ background: #86efac; }}
    small {{ color: #cbd5e1; }}
  </style>
</head>
<body>
<main>
  <h1>PIN-Zugangsschranke</h1>
  <section class="card">
    <div class="state">{escaped["state"]}</div>
    <p>{escaped["last_event"]}</p>
    <small>Letztes Update: {escaped["last_update"]}</small>
  </section>
  <section class="card grid">
    <div>Objekt erkannt: <strong>{escaped["object_detected"]}</strong></div>
    <div>Abstand: <strong>{escaped["distance_display"]} cm</strong></div>
    <div>Sperrmodus: <strong>{escaped["locked"]}</strong></div>
    <div>Fehlversuche: <strong>{escaped["wrong_attempts"]}</strong></div>
    <div>Countdown: <strong>{escaped["countdown"]}</strong></div>
    <div>Letzte IR-Taste: <strong>{escaped["last_ir_button"]}</strong></div>
    <div>PIN: <strong>{escaped["entered_pin_masked"]}</strong></div>
  </section>
  <section class="card grid">
    <a class="button ok" href="/action?name=open">Öffnen</a>
    <a class="button" href="/action?name=close">Schließen</a>
    <a class="button warn" href="/action?name=lock">Sperrmodus umschalten</a>
    <a class="button" href="/action?name=mute">Alarm stumm</a>
  </section>
</main>
</body>
</html>"""

    def handle_web_action(self, action: str) -> None:
        if action == "open":
            self.open_gate(source="Web")
        elif action == "close":
            self.close_gate(source="Web")
        elif action == "lock":
            self.toggle_lock(source="Web")
        elif action == "mute":
            self.mute_alarm(source="Web")

    def handle_ir_button(self, button: str) -> None:
        with self.lock:
            self.status.last_ir_button = button

        if button.startswith("unknown:"):
            self.unknown_ir(button)
            return

        if button.isdigit():
            self.add_pin_digit(button)
            return

        if button == self.config.ir.delete_button:
            self.delete_pin_digit()
        elif button == self.config.ir.confirm_button:
            self.confirm_pin()
        elif button == self.config.ir.mute_button:
            self.mute_alarm(source="IR")
        elif button == self.config.ir.lock_button:
            self.toggle_lock(source="IR")
        elif button == self.config.ir.open_button:
            self.open_gate(source="IR")
        elif button == self.config.ir.close_button:
            self.close_gate(source="IR")
        else:
            self._set_event(f"IR-Taste ohne Funktion: {button}")

    def add_pin_digit(self, digit: str) -> None:
        with self.lock:
            if len(self.status.entered_pin_masked) >= len(self.config.pin_code):
                return
            raw_pin = getattr(self.status, "_raw_pin", "")
            raw_pin += digit
            setattr(self.status, "_raw_pin", raw_pin)
            self.status.entered_pin_masked = "*" * len(raw_pin)
            self._set_event("PIN-Ziffer eingegeben")
            self.hardware.show_lcd("PIN eingeben", self.status.entered_pin_masked)

    def delete_pin_digit(self) -> None:
        with self.lock:
            raw_pin = getattr(self.status, "_raw_pin", "")
            raw_pin = raw_pin[:-1]
            setattr(self.status, "_raw_pin", raw_pin)
            self.status.entered_pin_masked = "*" * len(raw_pin)
            self._set_event("PIN-Ziffer geloescht")
            self.hardware.show_lcd("PIN eingeben", self.status.entered_pin_masked)

    def confirm_pin(self) -> None:
        with self.lock:
            raw_pin = getattr(self.status, "_raw_pin", "")
            setattr(self.status, "_raw_pin", "")
            self.status.entered_pin_masked = ""

        if raw_pin == self.config.pin_code:
            with self.lock:
                self.status.wrong_attempts = 0
                self.status.alarm_muted = False
            self._set_event("PIN korrekt")
            self.hardware.beep(1)
            self.open_gate(source="PIN")
        else:
            self.wrong_pin()

    def wrong_pin(self) -> None:
        with self.lock:
            self.status.wrong_attempts += 1
            attempts = self.status.wrong_attempts
            max_attempts = self.config.max_wrong_pins

        self.hardware.beep(2, frequency=900)
        if attempts >= max_attempts:
            self.trigger_alarm("Zu viele falsche PINs")
        else:
            self._set_event(f"Falscher PIN ({attempts}/{max_attempts})")
            self.hardware.show_lcd("Falscher PIN", f"{attempts}/{max_attempts}")

    def unknown_ir(self, button: str) -> None:
        self._set_event(f"Unbekannter IR-Code: {button}")
        self.hardware.show_lcd("Unbekannter", "IR-Code")
        self.hardware.beep(3, duration=0.05, frequency=700)

    def toggle_gate(self, source: str) -> None:
        with self.lock:
            state = self.status.state
            if state == GateState.ALARM:
                self.status.state = GateState.CLOSED
                self.status.alarm_muted = True
                state = GateState.CLOSED

        if state in {GateState.OPEN, GateState.OPENING}:
            self.close_gate(source=source)
        elif state in {GateState.CLOSED, GateState.CLOSING}:
            self.open_gate(source=source)

    def open_gate(self, source: str) -> None:
        with self.lock:
            if self.status.state in {GateState.OPEN, GateState.OPENING}:
                return
            self.status.state = GateState.OPENING
            self.status.alarm_muted = False
            self._set_event(f"Schranke oeffnet ({source})")

        self.hardware.show_lcd("OEFFNET...", source)
        self.hardware.set_leds(red=True, green=True)
        self.hardware.beep(1)
        self.hardware.open_gate()

        with self.lock:
            self.status.state = GateState.OPEN
            self._set_event("Schranke offen")

        self.hardware.set_leds(red=False, green=True)
        self.hardware.show_lcd("Schranke offen", "Auto-close")
        threading.Thread(target=self._auto_close_countdown, daemon=True).start()

    def close_gate(self, source: str) -> None:
        with self.lock:
            if self.status.state in {GateState.CLOSED, GateState.CLOSING}:
                return
            self.status.state = GateState.CLOSING
            self.status.countdown = 0
            self._set_event(f"Schranke schliesst ({source})")

        self.hardware.show_lcd("SCHLIESST...", source)
        self.hardware.set_leds(red=True, green=True)
        self.hardware.beep(2)
        self.hardware.close_gate()

        with self.lock:
            self.status.state = GateState.CLOSED
            self._set_event("Schranke geschlossen")

        self.hardware.set_leds(red=True, green=False)
        self.hardware.show_lcd("Geschlossen", "PIN eingeben")

    def _auto_close_countdown(self) -> None:
        for remaining in range(self.config.auto_close_seconds, 0, -1):
            with self.lock:
                if self.status.state != GateState.OPEN:
                    self.status.countdown = 0
                    return
                self.status.countdown = remaining
            self.hardware.show_lcd("Schliesst in", f"{remaining} Sekunden")
            time.sleep(1)
        self.close_gate(source="Auto")

    def toggle_lock(self, source: str) -> None:
        with self.lock:
            self.status.locked = not self.status.locked
            locked = self.status.locked
            self._set_event(f"Sperrmodus {'aktiv' if locked else 'inaktiv'} ({source})")

        self.hardware.beep(1 if locked else 2, frequency=1200)
        self.hardware.show_lcd("Sperrmodus", "AKTIV" if locked else "INAKTIV")

    def mute_alarm(self, source: str) -> None:
        with self.lock:
            self.status.alarm_muted = True
            if self.status.state == GateState.ALARM:
                self.status.state = GateState.CLOSED
            self._set_event(f"Alarm stumm ({source})")

        self.hardware.set_leds(red=True, green=False)
        self.hardware.show_lcd("Alarm", "stumm")

    def trigger_alarm(self, reason: str) -> None:
        with self.lock:
            self.status.state = GateState.ALARM
            self._set_event(f"Alarm: {reason}")

        self.hardware.set_leds(red=True, green=False)
        self.hardware.show_lcd("ALARM", reason[:16])
        if not self.status.alarm_muted:
            self.hardware.alarm_beep()

    def _handle_distance_detection(self, distance_cm: Optional[float], state: GateState, locked: bool) -> None:
        distance_text = "n/a" if distance_cm is None else f"{distance_cm:.1f} cm"
        now = time.monotonic()

        if locked:
            self._set_event(f"Objekt erkannt im Sperrmodus: {distance_text}")
            self.hardware.show_lcd(f"Abstand {distance_text}"[:16], "Gesperrt")
            return

        if state == GateState.CLOSED and now - self.last_auto_open_at >= self.config.ultrasonic.auto_open_cooldown_seconds:
            self.last_auto_open_at = now
            self._set_event(f"Objekt erkannt: {distance_text}, oeffne Schranke")
            self.hardware.show_lcd(f"Abstand {distance_text}"[:16], "Oeffne...")
            self.open_gate(source="Abstand")


def main() -> int:
    parser = argparse.ArgumentParser(description="PIN-gesicherte Zugangsschranke")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    setup_logging()
    config = load_config(args.config)
    app = AccessGateApp(config)

    def stop_handler(signum: int, frame: object) -> None:
        del signum, frame
        app.stop_event.set()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    try:
        app.start()
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
