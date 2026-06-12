# Normnaher Schaltplan

Datei: `Schaltplan_normnah.svg`

Der Schaltplan zeigt die elektrische Verschaltung des Schrankenprojekts als normnahe Funktionsschaltung. Er ist keine Breadboard-Steckskizze.

## Enthaltene Baugruppen

- Raspberry Pi 4 GPIO-Header
- LCD 16x2 mit I²C-Adapter
- IR-Empfänger
- HC-SR04 Ultraschallsensor
- SG90 Servo
- Buzzer
- rote LED mit Vorwiderstand
- grüne LED mit Vorwiderstand
- Taster gegen GND
- Spannungsteiler für HC-SR04 `Echo`

Der separate IR-Transmitter ist bewusst nicht enthalten.

## Wichtige Anschlüsse

| Funktion | GPIO / Pin | Hinweis |
|---|---:|---|
| LCD SDA | `GPIO2 / Pin 3` | I²C-Daten |
| LCD SCL | `GPIO3 / Pin 5` | I²C-Takt |
| IR-Empfänger OUT | `GPIO4 / Pin 7` | IR-Daten |
| HC-SR04 Trig | `GPIO17 / Pin 11` | Ausgang zum Sensor |
| HC-SR04 Echo | `GPIO5 / Pin 29` | nur über Spannungsteiler |
| Servo Signal | `GPIO18 / Pin 12` | PWM |
| Buzzer | `GPIO22 / Pin 15` | Signal |
| rote LED | `GPIO23 / Pin 16` | über Vorwiderstand |
| grüne LED | `GPIO24 / Pin 18` | über Vorwiderstand |
| Taster | `GPIO27 / Pin 13` | gegen GND, interner Pull-up |

## Schutzbeschaltung

Der HC-SR04 arbeitet mit `5 V`. Sein `Echo`-Pin liefert deshalb ebenfalls ca. `5 V`. Der Raspberry Pi verträgt an GPIO-Eingängen aber nur `3,3 V`.

Spannungsteiler:

```text
HC-SR04 Echo --- R1 1 kΩ --- GPIO5 --- R2 2 kΩ --- GND
```

## Hinweise zur Normdarstellung

- Widerstände sind als Rechtecksymbole dargestellt.
- Baugruppen sind als beschriftete Funktionsblöcke dargestellt.
- Versorgungsschienen sind getrennt als `+3,3 V`, `+5 V` und `GND` geführt.
- GPIOs sind mit BCM-Nummer und physischer Pin-Nummer beschriftet.
