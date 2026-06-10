# Projektdokumentation: PIN-gesicherte Zugangsschranke

## Deckblatt

**Projektidee:** Automatische Zugangsschranke mit IR-Fernbedienung und Abstandssensor  
**Fach / Lernfeld:** IT-Technik, Lernfeld 7  
**Gruppe:** TODO: Namen der Gruppenmitglieder eintragen  
**Abgabedatum:** TODO: Datum eintragen  

## Inhaltsverzeichnis

1. Projektbeschreibung
2. Soll-Anforderungen
3. Verwendete Hardware
4. Funktionsprinzip
5. GPIO-Anschlusstabelle
6. Software-Funktionen
7. Bedienkonzept
8. Ablauf der Steuerung
9. Tests
10. Probleme und Lösungsansätze
11. Erweiterungsmöglichkeiten
12. LCD-Anzeigen

## 1. Projektbeschreibung

In diesem Projekt wird eine kleine Zugangsschranke mit einem Raspberry Pi 4 realisiert. Die Schranke wird durch einen Servo-Motor bewegt. Ein HC-SR04-Ultraschallsensor misst den Abstand vor der Schranke. Erkennt der Sensor ein Objekt innerhalb der eingestellten Entfernung, öffnet die Schranke automatisch. Zusätzlich kann die Schranke über eine Infrarot-Fernbedienung und einen lokalen Taster gesteuert werden.

Ein 16x2-LCD zeigt Statusmeldungen wie `PIN eingeben`, `Schranke offen`, `Falscher PIN` oder `ALARM` an. Eine rote und eine grüne LED zeigen den Zustand optisch. Ein Buzzer gibt Rückmeldungen und Alarmsignale aus. Zusätzlich stellt der Raspberry Pi eine Webseite bereit, über die der aktuelle Zustand kontrolliert und die Schranke gesteuert werden kann.

Die fiktive Situation ist eine kleine Parkplatz-, Lager- oder Sicherheitszufahrt. Nähert sich ein Fahrzeug oder eine Person der Schranke, zeigt das LCD den Abstand und öffnet die Schranke. Nach einem Countdown schließt sie automatisch. Wenn der Abstandssensor danach weiterhin ein Objekt erkennt, öffnet die Schranke erneut statt in den Alarmzustand zu gehen.

## 2. Soll-Anforderungen

### Pflichtanforderungen

- Die Schranke startet im Zustand **geschlossen**.
- Der HC-SR04 misst den Abstand vor der Schranke.
- Die IR-Fernbedienung wird zur PIN-Eingabe und manuellen Steuerung verwendet.
- Der richtige PIN-Code öffnet die Schranke.
- Ein erkanntes Objekt unterhalb der Abstandsschwelle öffnet die Schranke automatisch.
- Der Servo bewegt den Schrankenarm zwischen geschlossen und offen.
- Eine rote LED leuchtet bei geschlossener Schranke.
- Eine grüne LED leuchtet bei geöffneter Schranke.
- Ein Taster dient als manuelle lokale Bedienung.
- Das LCD zeigt den aktuellen Zustand und Bedienhinweise.
- Der Buzzer gibt akustische Rückmeldungen.
- Nach mehreren falschen PIN-Eingaben wird ein Alarm ausgelöst.

### Erweiterte Anforderungen

- Die Schranke schließt nach einem Countdown automatisch.
- Ein Sperrmodus kann per Fernbedienung aktiviert werden.
- Im Sperrmodus öffnet die Abstandserkennung nicht automatisch.
- Ein Webinterface zeigt den aktuellen Zustand an.
- Über das Webinterface können Öffnen, Schließen, Sperrmodus und Alarm-Stummschaltung ausgelöst werden.
- Ereignisse werden in einer Log-Datei gespeichert.

## 3. Verwendete Hardware

- Raspberry Pi 4
- Breadboard
- Jumperkabel
- IR-Empfänger mit 3 Pins
- IR-Fernbedienung
- HC-SR04 Ultraschallsensor
- SG90 Micro Servo
- 16x2 LCD mit I²C-Adapter, vermutlich `PCF8574`
- rote LED
- grüne LED
- Widerstände für LEDs, z. B. 220 Ω bis 330 Ω
- Taster
- Buzzer / Piezo-Speaker
- optional externe 5-V-Versorgung für den Servo

## 4. Funktionsprinzip

Der Raspberry Pi überwacht dauerhaft den HC-SR04-Ultraschallsensor, den IR-Empfänger und den Taster. Misst der Ultraschallsensor einen Abstand unterhalb der Warnschwelle, zeigt das LCD den Abstand und öffnet die Schranke automatisch. Der Nutzer kann alternativ einen PIN über die IR-Fernbedienung eingeben oder die Schranke mit dem Taster öffnen und schließen. Nach einem Countdown schließt die Schranke automatisch wieder.

Bei falscher PIN-Eingabe wird die Anzahl der Fehlversuche erhöht. Nach drei falschen Eingaben wechselt das System in den Alarmzustand. Der Buzzer piept, die rote LED bleibt aktiv und das LCD zeigt `ALARM`.

## 5. GPIO-Anschlusstabelle

| Bauteil | Pin am Bauteil | Raspberry Pi | Hinweis |
|---|---|---|---|
| LCD | `GND` | `GND`, z. B. Pin 6 | gemeinsame Masse |
| LCD | `VCC` | zuerst `3.3V`, Pin 1 oder 17 | bei 5 V Level-Shifter für I²C nutzen |
| LCD | `SDA` | `GPIO2 / SDA`, Pin 3 | I²C-Daten |
| LCD | `SCL` | `GPIO3 / SCL`, Pin 5 | I²C-Takt |
| IR-Empfänger | `VCC` | `3.3V`, Pin 1 | GPIO-sicher betreiben |
| IR-Empfänger | `GND` | `GND`, z. B. Pin 9 | gemeinsame Masse |
| IR-Empfänger | `OUT/S` | `GPIO4`, Pin 7 | IR-Daten |
| HC-SR04 | `VCC` | `5V`, Pin 2 oder 4 | Sensorversorgung |
| HC-SR04 | `GND` | `GND`, z. B. Pin 14 | gemeinsame Masse |
| HC-SR04 | `Trig` | `GPIO17`, Pin 11 | Ultraschall auslösen |
| HC-SR04 | `Echo` | Spannungsteiler → `GPIO5`, Pin 29 | Echo ist sonst 5 V |
| Servo | Signal | `GPIO18`, Pin 12 | PWM-Ausgang |
| Servo | Plus | externe `5V` empfohlen | Pi-5V nur für kurze Tests |
| Servo | Minus | `GND` | gemeinsame Masse notwendig |
| Buzzer | Plus | `GPIO22`, Pin 15 | Ton-Ausgang |
| Buzzer | Minus | `GND` | gemeinsame Masse |
| rote LED | Anode über Widerstand | `GPIO23`, Pin 16 | geschlossen / Alarm |
| rote LED | Kathode | `GND` | Vorwiderstand verwenden |
| grüne LED | Anode über Widerstand | `GPIO24`, Pin 18 | offen |
| grüne LED | Kathode | `GND` | Vorwiderstand verwenden |
| Taster | Seite 1 | `GPIO27`, Pin 13 | interner Pull-up |
| Taster | Seite 2 | `GND` | Tastendruck zieht auf GND |

Wichtig: GPIO-Pins am Raspberry Pi sind nur 3,3-V-tolerant. Das `Echo`-Signal des HC-SR04 liegt bei 5-V-Versorgung ebenfalls bei 5 V und muss per Spannungsteiler auf ungefähr 3,3 V reduziert werden. Das LCD sollte zuerst mit 3,3 V getestet werden. Falls das LCD nur mit 5 V funktioniert, sollte für SDA und SCL ein Level-Shifter verwendet werden, weil viele I²C-Adapter Pull-up-Widerstände nach VCC besitzen. Der Servo sollte nicht aus einem GPIO-Pin versorgt werden. Falls eine externe Servo-Versorgung verwendet wird, muss deren Masse mit `GND` des Raspberry Pi verbunden werden.

## 6. Software-Funktionen

- Zustandsmaschine mit `GESCHLOSSEN`, `OEFFNET`, `OFFEN`, `SCHLIESST`, `ALARM`
- PIN-Eingabe über IR-Fernbedienung
- automatische Schließung nach 5 Sekunden
- Abstandsmessung mit HC-SR04
- automatische Öffnung bei Abstand unter `80 cm`
- erneutes Öffnen, wenn nach dem Schließen weiterhin ein Objekt erkannt wird
- Sperrmodus ohne automatische Öffnung
- Fehlversuchszähler für falsche PINs
- Buzzer-Signale für Öffnen, Schließen, Fehler und Alarm
- LCD-Ausgabe für Status und Bedienhinweise
- Webinterface auf Port `8080`
- JSON-Status-Endpunkt `/api/status`
- Log-Datei `access_gate.log`
- Konfiguration über `config.json`

## 7. Bedienkonzept

| Eingabe | Funktion |
|---|---|
| Zahlen `0` bis `9` | PIN eingeben |
| `Play/Pause` | PIN bestätigen |
| `Prev` | letzte PIN-Ziffer löschen |
| `CH+` | Schranke manuell öffnen |
| `CH-` | Schranke manuell schließen |
| `Power` | Sperrmodus ein/aus |
| `EQ` | Alarm stummschalten |
| Taster | Schranke lokal öffnen/schließen |
| Webbutton `Öffnen` | Schranke über Browser öffnen |
| Webbutton `Schließen` | Schranke über Browser schließen |

Standard-PIN: `1234`

Der lokale Taster schaltet standardmäßig `GPIO27` gegen `GND`. Falls ein Devboard-Taster gegen `3.3V` schaltet, wird dies in `config.json` über `button.active_low` und `button.pull` angepasst.

## 8. Ablauf der Steuerung

1. Programm startet.
2. GPIO, Servo, LCD, IR-Empfänger, HC-SR04 und Webserver werden initialisiert.
3. Schranke fährt in die geschlossene Position.
4. LCD zeigt `PIN-Schranke` und `geschlossen`.
5. Der HC-SR04 misst ein Objekt innerhalb der Warnschwelle.
6. LCD zeigt den Abstand und `Oeffne...`.
7. Servo fährt die Schranke auf.
8. Alternativ kann der Nutzer per Fernbedienung oder Taster öffnen/schließen.
9. Grüne LED leuchtet, rote LED geht aus.
10. LCD zeigt Countdown zum automatischen Schließen.
11. Nach Ablauf des Countdowns fährt der Servo die Schranke zu.
12. Bei falschem PIN wird der Fehlversuchszähler erhöht.
13. Nach drei falschen PINs wird Alarm ausgelöst. Der Abstandssensor löst keinen Alarm aus.

## 9. Tests

| Testfall | Erwartetes Ergebnis | Ergebnis |
|---|---|---|
| Programmstart | Schranke geschlossen, rote LED an, LCD zeigt Status | TODO |
| Objekt unter 80 cm | LCD zeigt Abstand und Schranke öffnet automatisch | TODO |
| richtiger PIN | Servo öffnet, grüne LED an, Buzzer piept | TODO |
| falscher PIN | Fehleranzeige, Fehlversuchszähler steigt | TODO |
| 3 falsche PINs | Alarmzustand, Buzzer warnt | TODO |
| `EQ` drücken | Alarm wird stummgeschaltet | TODO |
| `Power` drücken | Sperrmodus wechselt | TODO |
| Annäherung im Sperrmodus | Schranke bleibt geschlossen, LCD zeigt `Gesperrt` | TODO |
| Webinterface öffnen | Status wird im Browser angezeigt | TODO |
| Webbutton schließen | Servo fährt zu | TODO |

## 10. Probleme und Lösungsansätze

| Problem | Mögliche Ursache | Lösungsansatz |
|---|---|---|
| LCD bleibt leer | I²C deaktiviert, falsche Adresse, Kontrast falsch | `raspi-config`, `i2cdetect -y 1`, Potentiometer drehen |
| Servo zittert | Stromversorgung zu schwach | externe 5-V-Versorgung nutzen |
| IR wird nicht erkannt | falscher Pin, falsche Pinbelegung, andere Codes | `src/scan_ir_codes.py` verwenden |
| Abstand ist immer `n/a` | Trigger/Echo falsch angeschlossen oder Echo ohne Spannungsteiler | Verdrahtung und Widerstände prüfen |
| Abstand springt stark | Sensor misst schräg oder Objekt reflektiert schlecht | Sensor gerade ausrichten, feste Fläche testen |
| Buzzer klingt falsch | aktiver/passiver Buzzer unterschiedlich | Frequenz oder Ansteuerung anpassen |
| Webseite nicht erreichbar | falsche IP oder Port | `http://<Pi-IP>:8080` verwenden |

## 11. Erweiterungsmöglichkeiten

- PIN im Webinterface ändern.
- Statusverlauf im Webinterface anzeigen.
- MQTT-Nachricht bei Alarm senden.
- Display-Menü für mehrere Benutzer-PINs.
- Buzzer-Melodie für erfolgreiche Freigabe.
- Mechanischer Schrankenarm aus Pappe oder Holz.

## 12. LCD-Anzeigen

| Situation | Zeile 1 | Zeile 2 |
|---|---|---|
| Programmstart | `PIN-Schranke` | `geschlossen` |
| geschlossen | `Geschlossen` | `PIN eingeben` |
| Objekt unter 80 cm | `Abstand xx.x cm` | `Oeffne...` |
| PIN-Eingabe | `PIN eingeben` | verdeckte PIN, z. B. `****` |
| falscher PIN | `Falscher PIN` | Fehlversuche, z. B. `1/3` |
| Schranke öffnet | `OEFFNET...` | Auslöser, z. B. `PIN` |
| Schranke offen | `Schliesst in` | Countdown, z. B. `5 Sekunden` |
| Schranke schließt | `SCHLIESST...` | Auslöser, z. B. `Auto` |
| Alarm | `ALARM` | Grund, z. B. falsche PINs |
| unbekannter IR-Code | `Unbekannter` | `IR-Code` |

## Dateien im Projekt

- `src/access_gate.py`: Hauptprogramm
- `src/scan_ir_codes.py`: Hilfsprogramm zum Auslesen der Fernbedienungscodes
- `config.json`: Pinbelegung, PIN-Code und Hardware-Konfiguration
- `README.md`: Aufbau- und Startanleitung
- `access_gate.log`: wird beim Programmstart automatisch angelegt
