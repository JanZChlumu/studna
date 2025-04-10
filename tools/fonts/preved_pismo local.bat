@echo off

SET pismo="c:\Windows\Fonts\CALIBRI.TTF"

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 10 Calibri10CZ.py -k czech

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 12 Calibri12CZ.py -k czech

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 16 Calibri16CZ.py -k czech

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 24 Calibri24CZ.py -k czech

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 36 Calibri36CZ.py -k czech

c:\Users\Z004NBWP\tools\thonny-4.1.7-windows-portable\python.exe c:\Users\Z004NBWP\Git\MicroPythonTest\.not2Pico\micropython-lcd12864-main\tools\font_to_py.py -x %pismo% 80 Calibri80CZ.py -k czech

echo Hotovo!
pause