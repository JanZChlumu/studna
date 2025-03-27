from machine import Pin, SPI, Timer, PWM, UART
from utime import sleep
import time
from rotary_irq_rp2 import RotaryIRQ
import lcd12864_spi
from lcd12864_spi import LCD12864_SPI
import ArialRoundedMT_70pix as BIG_FONT

# Inicializace UART1 pro Raspberry Pi Pico 
uart1 = UART(1, baudrate=9600, tx=Pin(8), rx=Pin(9))  # Nastav piny dle zapojení

distances = []
times = []
max_records = 128  # Počet měření za posledních 6 hodin -> uložit každé 12 měření á 15 sec.

pwmLCD = PWM(Pin(10))
pwmLCD.freq(1000) # PWM 1kHz

spi = SPI( 0, baudrate = 1_000_000, polarity = 1, phase = 1 )
lcd = LCD12864_SPI( spi = spi, cs_pin = 15, rst_pin = 4, rotation = 1 )
lcd.clear()
UpdateLCD = False


# Inicializace rotačního enkodéru
rot = RotaryIRQ(pin_num_clk=6, pin_num_dt=7, min_val=0, max_val=5, reverse=False, range_mode=RotaryIRQ.RANGE_WRAP, pull_up=True)
rot.set(value=0)
# nahrazuje init
RotaryLastVal = 100

"""
ROTARY def set(self, value=None, min_val=None, incr=None,
            max_val=None, reverse=None, range_mode=None):
"""

# Inicializace tlačítka potvrzení
button = Pin(14, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)

# Seznam položek menu
menu_items = ["Polozka 1", "Polozka 2", "Polozka 3", "Polozka 4", "Polozka 5"]
submenus = ["Submenu 1", "Submenu 2", "Submenu 3", "Submenu 4", "Submenu 5"]
current_index = 0
in_submenu = False


def map_value(x, in_min, in_max, out_min, out_max):
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def get_distance():
    uart1.write(b'\x55')  # Odeslání příkazu pro vyčtení dat
    time.sleep(0.05)    
    if uart1.any() >= 4:
        start_byte = uart1.read(1)
        if start_byte == b'\xff':
            data = uart1.read(3)
            if data and len(data) == 3:
                h_data, l_data, checksum = data
                distance = (h_data << 8) + l_data
                if ((255 + h_data + l_data) & 0xFF) != checksum:
                    print("Invalid result")
                    return None
                else:
                    #print(f"Distance [mm]: {distance}")
                    return distance
    return None

def draw_graph():
    lcd.clear()
    lcd.text("Min:", 0, 0, 1)
    lcd.text("Max:", 0, 10, 1)    
    #print("distances", len(distances))
    
    if len(distances) > 0:
        min_distance = min(distances)
        max_distance = max(distances)
        range_distance = max_distance - min_distance
        
        lcd.text(str(min_distance), 35, 0, 1)
        lcd.text(str(max_distance), 35, 10, 1)
        
        # Prevent division by zero if all distances are the same
        if range_distance == 0:
            scale = 63
        else:
            scale = 63 / range_distance

        for i in range(1, len(distances)):
            x1 = int((i - 1) * 128 / max_records)
            y1 = 63 - int((distances[i - 1] - min_distance) * scale)
            x2 = int(i * 128 / max_records)
            y2 = 63 - int((distances[i] - min_distance) * scale)
            lcd.line(x1, y1, x2, y2, 1)    
    lcd.show()

"""
HAPTIC Timer
"""
def haptic(timer):
    global RotaryLastVal, UpdateLCD
    _val = rot.value()
    if RotaryLastVal != _val:
        RotaryLastVal = _val
        UpdateLCD = True
        print(f"Rotary value {RotaryLastVal}")
        
hapticTimer = Timer()
hapticTimer.init(period=20, mode=Timer.PERIODIC, callback=haptic) 

def task1(timer):    
    global UpdateLCD
    led.toggle()
    distance = get_distance()    
    if distance is not None:        
        distances.append(distance)
            
        if len(distances) > max_records:
            distances.pop(0)
    #UpdateLCD = True
    #draw_graph()            

tim = Timer()
tim.init(period=1000, mode=Timer.PERIODIC, callback=task1)


def draw_bar(fill_percentage):
    """ Draw a horizontal bar with adjustable fill
    Args:
    fill_percentage (int): Fill level from 0 to 100
    """
    print(fill_percentage)
    #lcd.clear()
    bar_width = 100
    bar_height = 15
    x_start = 14
    y_start = 25
    filled_width = int((fill_percentage / 100) * bar_width)    
    # Draw bar border
    lcd.rect(x_start, y_start, bar_width, bar_height, 1)    
    # clear
    lcd.fill_rect(x_start+1, y_start+1, bar_width-2, bar_height-2, 0)    
    # Draw filled portion
    lcd.fill_rect(x_start, y_start, filled_width, bar_height, 1)    
    lcd.show()

def draw_screens(screen_id):    
    global UpdateLCD
    if UpdateLCD:  
        if screen_id == 0:                    
            lcd.fill(0)
            lcd.set_font(BIG_FONT)
            lcd.set_text_wrap()
            lcd.text("Default 8x8 font", 0, 0)
            lcd.draw_text("92%", 0, 0)
            lcd.show()                
        elif screen_id == 1:
            draw_graph()
        else:       
            print("error screen id")
        UpdateLCD = False        


pwmLCD.duty_u16(25000)

# Definice viceurovnoveho menu
menu = {
    "Hlavni menu": ["Polozka 1", "Polozka 2", "Polozka 3", 2],
    "Polozka 1": ["Akce 1 1", "Zpet", 1],
    "Polozka 2": ["Akce 2 1", "Akce 2 2", "Zpet", 2],
    "Polozka 3": ["Akce 3 1", "Akce 3 2", "Akce 3 3" , "Zpet", 3]
}

current_menu = "Hlavni menu"
selected_index = 0

def draw_menu():        
    global UpdateLCD
    """ Vykresli aktualni menu na LCD """
    lcd.clear()
    lcd.text(current_menu, 0, 0, 1)
    
    for i, item in enumerate(menu[current_menu][:-1]):
        prefix = "-> " if i == selected_index else "   "
        lcd.text(prefix + item, 0, 10 + i * 10, 1)

    lcd.show()
    UpdateLCD = False

def navigate_menu(direction):
    """ Posune kurzor nahoru nebo dolu v menu """
    global selected_index
    selected_index = direction #(selected_index + direction) % len(menu[current_menu][:-1])
    draw_menu()

def select_item(pin):
    """ Potvrdi vyber v menu """
    global current_menu, selected_index

    selected_item = menu[current_menu][selected_index]
    
    if selected_item == "Zpet":
        current_menu = "Hlavni menu"
        rot.set(value=0)
    elif selected_item in menu:  # Pokud existuje podmenu
        current_menu = selected_item
        rot.set(value=0)
    
    selected_index = 0
    draw_menu()


# Nastaveni preruseni
button.irq(trigger=Pin.IRQ_FALLING, handler=select_item)

# Zobrazeni menu pri startu
draw_menu()

# Hlavni smycka pro polling rotary enkoderu
while True:
    
    if UpdateLCD:
        rot.set(max_val = menu[current_menu][-1])
        print(f"Rotary set max value {menu[current_menu][-1]}")
        navigate_menu(RotaryLastVal)
        UpdateLCD = False            
    #if not button.value():  # Kontrola stisknuti tlacitka
    #    select_item()
    time.sleep(0.1)  # Debounce

"""
# Hlavní smyčka
#draw_menu(current_index)
while True:
    #draw_screens(RotaryLastVal)
        
    
    navigate_menu(RotaryLastVal)
    
    #val = rot.value()
    #draw_bar(map_value(val, 0, 25, 0, 100))            
    #pwm_map = map_value(val, 0, 25, 0, 65535)       
        
    time.sleep(0.2)
"""

"""
    if not in_submenu:
        if val != RotaryLastVal:
            current_index = val
            draw_menu(current_index)
            RotaryLastVal = val
        if button.value() == 0:
            in_submenu = True
            draw_submenu(current_index)
            time.sleep(0.1)  # Debounce
    else:
        if button.value() == 0:
            in_submenu = False
            draw_menu(current_index)
            time.sleep(0.3)  # Debounce
"""            
