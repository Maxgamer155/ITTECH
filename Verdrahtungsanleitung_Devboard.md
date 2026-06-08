# Verdrahtungsanleitung mit Raspberry-Pi-Devboard

Diese Anleitung ist für ein typisches Raspberry-Pi-Devboard / GPIO-Breakout gedacht, bei dem die Anschlüsse mit Namen wie `GPIO17`, `GPIO18`, `3V3`, `5V`, `GND`, `SDA` und `SCL` beschriftet sind.

Wenn euer Devboard andere Bezeichnungen hat, zählt die Raspberry-Pi-Pin-Nummer aus der Tabelle als Fallback.

## 1. Grundregeln vor dem Anschließen

- Raspberry Pi vor dem Umstecken ausschalten.
- GPIO-Pins vertragen nur `3.3V`, niemals `5V` auf einen GPIO-Eingang geben.
- Alle Bauteile müssen eine gemeinsame Masse haben: `GND` vom Pi, Servo-Netzteil und Sensoren verbinden.
- LEDs immer mit Vorwiderstand verwenden, z. B. `220 Ω` bis `330 Ω`.
- Servo nicht aus einem GPIO-Pin versorgen. GPIO liefert nur das Signal.
- Beim LCD zuerst `3V3` testen. Wenn es nur mit `5V` funktioniert, SDA/SCL nur mit Level-Shifter verwenden.

## 2. Übersicht der Devboard-Anschlüsse

| Funktion | Devboard-Beschriftung | Pi-Pin |
|---|---|---:|
| 3,3 V Versorgung | `3V3` / `3.3V` | Pin 1 oder 17 |
| 5 V Versorgung | `5V` | Pin 2 oder 4 |
| Masse | `GND` | z. B. Pin 6, 9, 14 |
| I²C Daten | `SDA` / `GPIO2` | Pin 3 |
| I²C Takt | `SCL` / `GPIO3` | Pin 5 |
| IR-Empfänger Signal | `GPIO4` | Pin 7 |
| PIR-Sensor Signal | `GPIO17` | Pin 11 |
| Servo Signal | `GPIO18` | Pin 12 |
| Buzzer Signal | `GPIO22` | Pin 15 |
| rote LED | `GPIO23` | Pin 16 |
| grüne LED | `GPIO24` | Pin 18 |
| Taster | `GPIO27` | Pin 13 |

## 3. LCD anschließen

Das LCD hat auf dem I²C-Adapter vier Pins:

| LCD-Pin | Devboard-Anschluss | Hinweis |
|---|---|---|
| `GND` | `GND` | Masse |
| `VCC` | zuerst `3V3` | sicherer für Pi-GPIOs |
| `SDA` | `SDA` oder `GPIO2` | I²C-Daten |
| `SCL` | `SCL` oder `GPIO3` | I²C-Takt |

Falls das LCD mit `3V3` nichts anzeigt:

1. Kontrast-Poti auf der Rückseite langsam drehen.
2. I²C-Adresse mit `i2cdetect -y 1` prüfen.
3. Erst danach `5V` testen, aber SDA/SCL dann nur mit Level-Shifter verwenden.

## 4. IR-Empfänger anschließen

Der IR-Empfänger hat meistens drei Pins: `S`, `+`, `-` oder `OUT`, `VCC`, `GND`.

| IR-Pin | Devboard-Anschluss | Hinweis |
|---|---|---|
| `S` / `OUT` | `GPIO4` | Signal der Fernbedienung |
| `+` / `VCC` | `3V3` | nicht 5 V verwenden |
| `-` / `GND` | `GND` | Masse |

Danach könnt ihr Codes mit folgendem Programm testen:

```bash
python3 src/scan_ir_codes.py
```

## 5. PIR-Bewegungssensor anschließen

Der PIR-Sensor hat meistens drei Pins: `VCC`, `OUT`, `GND`.

| PIR-Pin | Devboard-Anschluss | Hinweis |
|---|---|---|
| `VCC` | `5V` | viele PIR-Module brauchen 5 V |
| `OUT` | `GPIO17` | Bewegungssignal |
| `GND` | `GND` | Masse |

Nach dem Einschalten braucht der PIR-Sensor oft 30 bis 60 Sekunden Aufwärmzeit. In dieser Zeit kann er unzuverlässig auslösen.

## 6. Servo anschließen

Der SG90-Servo hat drei Kabel:

| Servo-Kabel | Bedeutung | Anschluss |
|---|---|---|
| braun/schwarz | `GND` | `GND` am Devboard und Servo-Netzteil |
| rot | `5V` | externe 5-V-Versorgung empfohlen |
| orange/gelb | Signal | `GPIO18` |

Wenn ihr den Servo kurz testet, kann er manchmal direkt mit `5V` vom Pi laufen. Für eine Vorführung ist eine externe 5-V-Versorgung stabiler.

Wichtig bei externer Versorgung:

- Plus vom Netzteil an rotes Servo-Kabel.
- Minus vom Netzteil an Servo-GND.
- Minus vom Netzteil zusätzlich mit `GND` vom Pi verbinden.
- Servo-Signalkabel bleibt an `GPIO18`.

## 7. Buzzer anschließen

| Buzzer-Pin | Devboard-Anschluss | Hinweis |
|---|---|---|
| `+` | `GPIO22` | Signal |
| `-` | `GND` | Masse |

Wenn der Buzzer sehr laut oder instabil ist, kann ein kleiner Vorwiderstand sinnvoll sein. Bei vielen Funduino-Buzzern funktioniert der direkte Anschluss aber für kurze Signaltöne.

## 8. LEDs anschließen

### Rote LED

| LED-Seite | Anschluss |
|---|---|
| langes Bein / Anode | über `220 Ω` bis `330 Ω` an `GPIO23` |
| kurzes Bein / Kathode | `GND` |

### Grüne LED

| LED-Seite | Anschluss |
|---|---|
| langes Bein / Anode | über `220 Ω` bis `330 Ω` an `GPIO24` |
| kurzes Bein / Kathode | `GND` |

Wenn eine LED nicht leuchtet, ist sie wahrscheinlich falsch herum eingesteckt oder der falsche GPIO wurde verwendet.

## 9. Taster anschließen

Der Taster wird gegen Masse geschaltet. Das Programm nutzt den internen Pull-up-Widerstand des Raspberry Pi.

| Taster-Seite | Devboard-Anschluss |
|---|---|
| Seite 1 | `GPIO27` |
| Seite 2 | `GND` |

Bei einem 4-poligen Taster liegen jeweils zwei gegenüberliegende Pins intern zusammen. Wenn der Taster dauerhaft als gedrückt erkannt wird, um 90 Grad drehen oder andere Pins verwenden.

## 10. Komplette Anschlussliste

| Bauteil | Bauteil-Pin | Devboard | Pi-Pin |
|---|---|---|---:|
| LCD | `GND` | `GND` | 6 |
| LCD | `VCC` | `3V3` | 1 |
| LCD | `SDA` | `SDA` / `GPIO2` | 3 |
| LCD | `SCL` | `SCL` / `GPIO3` | 5 |
| IR-Empfänger | `OUT/S` | `GPIO4` | 7 |
| IR-Empfänger | `VCC/+` | `3V3` | 1 |
| IR-Empfänger | `GND/-` | `GND` | 9 |
| PIR | `VCC` | `5V` | 2 |
| PIR | `OUT` | `GPIO17` | 11 |
| PIR | `GND` | `GND` | 14 |
| Servo | Signal | `GPIO18` | 12 |
| Servo | Plus | externe `5V` | - |
| Servo | Minus | `GND` | 6 |
| Buzzer | `+` | `GPIO22` | 15 |
| Buzzer | `-` | `GND` | 20 |
| rote LED | Anode mit Widerstand | `GPIO23` | 16 |
| rote LED | Kathode | `GND` | 25 |
| grüne LED | Anode mit Widerstand | `GPIO24` | 18 |
| grüne LED | Kathode | `GND` | 30 |
| Taster | Seite 1 | `GPIO27` | 13 |
| Taster | Seite 2 | `GND` | 34 |

## 11. Empfohlene Reihenfolge beim Aufbau

1. Pi ausschalten.
2. LCD anschließen.
3. Pi starten und LCD mit `i2cdetect -y 1` prüfen.
4. IR-Empfänger anschließen und Fernbedienung mit `src/scan_ir_codes.py` testen.
5. LEDs anschließen und mit dem Hauptprogramm prüfen.
6. Buzzer anschließen.
7. PIR-Sensor anschließen und nach Aufwärmzeit testen.
8. Servo zuletzt anschließen, idealerweise mit externer 5-V-Versorgung.
9. Hauptprogramm starten:

```bash
python3 src/access_gate.py
```

10. Webinterface öffnen:

```text
http://<IP-DES-RASPBERRY-PI>:8080
```

## 12. Häufige Fehler

| Fehler | Ursache | Lösung |
|---|---|---|
| Pi startet neu, wenn Servo fährt | Servo zieht zu viel Strom | externe 5-V-Versorgung verwenden |
| LCD zeigt nur blaue Fläche | Kontrast falsch | Poti am I²C-Adapter drehen |
| LCD wird nicht gefunden | I²C aus oder falsche Verkabelung | `raspi-config`, SDA/SCL prüfen |
| IR reagiert nicht | VCC/GND/OUT vertauscht | Pinbeschriftung am Modul prüfen |
| PIR löst immer aus | Aufwärmzeit oder Empfindlichkeit | warten, Potis einstellen |
| Taster reagiert invertiert | falsch gesteckt | Taster drehen oder Pins wechseln |
