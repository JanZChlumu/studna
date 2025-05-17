# Studna
Projekt se skládá ze 2 nezávislých částí
## Ochrana domácí vodárny
Do studny je umístěn hladinový spínač, který vybaví při kriticky nízké hladině. Odpojí 3 fázovou domácí vodárnu, aby se systém nezavzdušnil a čerpadlo neshořelo. [Schema v rozvaděči](./HW/Silnoproud_ochrana_cerpadla/darling_ochrana.pdf)

## Měření výšky hladiny
Motivace: Do studny byl při rekonstrukci zaveden UTP kabel.
Snaha byla o levné řešení, které v případě nefunkčnosti bude možné snadno upgradovat na "profi drahé" řešení :)
Použít levné čidlo, které komunikuje přes RS485 se zobrazovacím LCD modulem.

## Zobrazovací a řídicí jednotka 
Základní bloky:
- modul 485
- Raspberry Pico
- LCD 128x64 pix

[celkové schema](./HW/kicad/lcd/lcd.pdf)

### Ultrazvukové čidlo
Waterproof Ultrasonic Module JSN-SR04T

#### Použitý mód
Mode 3: Mode=120K (or short M2 bit directly) UART controlled output
The UART controlled output method outputs the measured distance value (hexadecimal number)
according to the UART communication format. In this method, the trigger command oX55 signal
needs to be added to the RX
pin. The module measures once every time the command is received. The foot outputs the measured
distance value. The command trigger cycle should be greater than 60ms