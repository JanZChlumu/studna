
Příklad vygenerování fontu

SET pismo="c:\Windows\Fonts\CALIBRI.TTF"
c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 16 Calibri16CZ.py -k czech

Note: parametr "-k czech" použije z fontu CALIBRI.TTF jen ty znaky, které jsou v souboru "czech". Tím se uspoří velikost výstupního Calibri16CZ.py souboru.
