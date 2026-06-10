# PIN-gesicherte Zugangsschranke

Dieses Projekt steuert eine kleine Zugangsschranke mit einem Raspberry Pi 4. Die Schranke wird mit einer IR-Fernbedienung per PIN freigegeben, ein Servo bewegt den Schrankenarm, ein HC-SR04-Ultraschallsensor misst den Abstand vor der Schranke, ein 16x2-LCD zeigt Statusmeldungen, LEDs zeigen den Zustand und ein Buzzer gibt Rückmeldungen.

## Hardware

- Raspberry Pi 4
- 16x2 LCD mit I²C-Adapter, meist `PCF8574`
- IR-Empfänger mit 3 Pins
- IR-Fernbedienung
- HC-SR04 Ultraschallsensor
- SG90 Micro Servo
- aktiver oder passiver Buzzer
- rote LED mit Vorwiderstand
- grüne LED mit Vorwiderstand
- Taster
- Breadboard und Jumperkabel

## Anschlussplan

Eine ausführliche Schritt-für-Schritt-Anleitung für euer Devboard liegt in `Verdrahtungsanleitung_Devboard.md`.

| Bauteil | Pin am Bauteil | Raspberry Pi |
|---|---|---|
| LCD | `GND` | `GND`, z. B. Pin 6 |
| LCD | `VCC` | zuerst `3.3V`, Pin 1 oder 17 |
| LCD | `SDA` | `GPIO2 / SDA`, Pin 3 |
| LCD | `SCL` | `GPIO3 / SCL`, Pin 5 |
| IR-Empfänger | `VCC` | `3.3V`, Pin 1 |
| IR-Empfänger | `GND` | `GND`, z. B. Pin 9 |
| IR-Empfänger | `OUT/S` | `GPIO4`, Pin 7 |
| HC-SR04 | `VCC` | `5V`, Pin 2 oder 4 |
| HC-SR04 | `GND` | `GND`, z. B. Pin 14 |
| HC-SR04 | `Trig` | `GPIO17`, Pin 11 |
| HC-SR04 | `Echo` | Spannungsteiler → `GPIO5`, Pin 29 |
| Servo | Signal, meist orange/gelb | `GPIO18`, Pin 12 |
| Servo | Plus, meist rot | externe `5V` empfohlen |
| Servo | Minus, meist braun/schwarz | gemeinsame Masse mit Pi |
| Buzzer | Plus | `GPIO22`, Pin 15 |
| Buzzer | Minus | `GND` |
| rote LED | Anode über Widerstand | `GPIO23`, Pin 16 |
| rote LED | Kathode | `GND` |
| grüne LED | Anode über Widerstand | `GPIO24`, Pin 18 |
| grüne LED | Kathode | `GND` |
| Taster | Seite 1 | `GPIO27`, Pin 13 |
| Taster | Seite 2 | `GND` |

Wichtig: Der Raspberry Pi verträgt an GPIO-Pins nur `3.3V`. Deshalb den IR-Empfänger mit `3.3V` betreiben. Das `Echo`-Signal des HC-SR04 ist bei 5-V-Versorgung ebenfalls `5V` und darf nicht direkt an den Pi. Nutzt dafür einen Spannungsteiler, z. B. `1 kΩ` von `Echo` zu `GPIO5` und `2 kΩ` von `GPIO5` zu `GND`. Das LCD zuerst mit `3.3V` testen. Wenn es nur mit `5V` zuverlässig arbeitet, sollte für SDA/SCL ein Level-Shifter verwendet werden, weil viele I²C-LCD-Adapter Pull-ups nach VCC haben. Beim Servo eine externe `5V`-Versorgung verwenden, wenn der Servo zittert oder der Pi instabil wird. Die Masse der externen Versorgung muss mit `GND` des Pi verbunden sein.

## Software vorbereiten

Auf dem Raspberry Pi:

```bash
sudo raspi-config
```

Dann aktivieren:

- `Interface Options` → `I2C` → aktivieren

Abhängigkeiten:

```bash
sudo apt update
sudo apt install -y python3-rpi.gpio python3-smbus i2c-tools
```

LCD-Adresse prüfen:

```bash
i2cdetect -y 1
```

Typische Adressen sind `0x27` oder `0x3F`. In `config.json` ist aktuell `39` eingetragen, das entspricht `0x27`.

## Start

```bash
python3 src/access_gate.py
```

Weboberfläche:

```text
http://<IP-DES-RASPBERRY-PI>:8080
```

Beispiel lokal auf dem Pi:

```text
http://localhost:8080
```

## Bedienung

| Taste | Funktion |
|---|---|
| `0` bis `9` | PIN eingeben |
| `Play/Pause` | PIN bestätigen |
| `Prev` | letzte PIN-Ziffer löschen |
| `CH+` | Schranke manuell öffnen |
| `CH-` | Schranke manuell schließen |
| `Power` | Sperrmodus ein/aus |
| `EQ` | Alarm stummschalten |
| Taster am Breadboard | Schranke öffnen/schließen |

Standard-PIN:

```text
1234
```

Die PIN kann in `config.json` geändert werden.

Der Taster ist standardmäßig als Verbindung von `GPIO27` nach `GND` konfiguriert. Falls euer Devboard-Taster stattdessen nach `3.3V` schaltet, setzt in `config.json` bei `button` die Werte auf `"active_low": false` und `"pull": "down"`.

## Funktionen

- PIN-Eingabe über IR-Fernbedienung
- automatische Schließung nach Countdown
- Abstandsmessung mit HC-SR04
- automatische Öffnung bei Objekt unter `80 cm`
- erneutes Öffnen, falls nach dem Schließen noch ein Objekt erkannt wird
- Board-Taster toggelt die Schranke auf/zu, auch wenn vorher ein Alarm aktiv war
- Alarm nach 3 falschen PINs
- LCD-Statusanzeige
- LED-Anzeige für offen/geschlossen
- Buzzer-Signale für Bedienung und Alarm
- Webinterface mit Status und Steuerknöpfen
- Log-Datei `access_gate.log`

## LCD-Anzeigen

| Situation | Zeile 1 | Zeile 2 |
|---|---|---|
| Programmstart | `PIN-Schranke` | `geschlossen` |
| geschlossen | `Geschlossen` | `PIN eingeben` |
| Objekt unter 80 cm | `Abstand xx.x cm` | `Oeffne...` |
| PIN-Eingabe | `PIN eingeben` | `*`, `**`, `***`, `****` |
| falscher PIN | `Falscher PIN` | z. B. `1/3` |
| Schranke öffnet | `OEFFNET...` | Auslöser, z. B. `PIN` |
| Schranke offen | `Schliesst in` | z. B. `5 Sekunden` |
| Schranke schließt | `SCHLIESST...` | Auslöser, z. B. `Auto` |
| Alarm | `ALARM` | z. B. nach 3 falschen PINs |
| unbekannte IR-Taste | `Unbekannter` | `IR-Code` |

## Fehlersuche

- LCD bleibt leer: I²C aktivieren, Adresse mit `i2cdetect -y 1` prüfen, Potentiometer am LCD-Adapter drehen.
- Servo zittert: externe `5V`-Versorgung verwenden und gemeinsame Masse herstellen.
- Fernbedienung reagiert nicht: IR-Empfänger-Pinbelegung prüfen, `VCC` an `3.3V`, `OUT` an `GPIO4`.
- Abstand ist immer `n/a`: `Trig`/`Echo` prüfen, Spannungsteiler prüfen, Sensor gerade ausrichten.
- Abstand springt stark: Sensor auf feste Fläche ausrichten, Kabel prüfen, Messbereich unter `300 cm` halten.
- Weboberfläche nicht erreichbar: IP-Adresse des Pi prüfen und Port `8080` verwenden.
