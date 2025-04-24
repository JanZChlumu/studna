


# Ultra sonic sensor
Used
Mode 3: Mode=120K (or short M2 bit directly) UART controlled output
The UART controlled output method outputs the measured distance value (hexadecimal number)
according to the UART communication format. In this method, the trigger command oX55 signal
needs to be added to the RX
pin. The module measures once every time the command is received. The foot outputs the measured
distance value. The command trigger cycle should be greater than 60ms