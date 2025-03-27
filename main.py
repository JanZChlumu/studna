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
max_records = 128  # Počet měření za posledních 6 hodin -> uložit každé 12 měření á 15 sec.

pwmLCD = PWM(Pin(10))
pwmLCD.freq(1000) # PWM 1kHz

spi = SPI( 0, baudrate = 1_000_000, polarity = 1, phase = 1 )
lcd = LCD12864_SPI( spi = spi, cs_pin = 15, rst_pin = 4, rotation = 1 )
lcd.clear()
UpdateLCD = False
BlockMenu = False

# Inicializace rotačního enkodéru
rot = RotaryIRQ(pin_num_clk=6, pin_num_dt=7, min_val=0, max_val=5, reverse=False, range_mode=RotaryIRQ.RANGE_WRAP, pull_up=True)
#RotaryLastVal = 100

"""
ROTARY def set(self, value=None, min_val=None, incr=None,
            max_val=None, reverse=None, range_mode=None):
"""

# Inicializace tlačítka potvrzení
button = Pin(14, Pin.IN, Pin.PULL_UP)
button_debounce_time_ms = 13
button_debounce_timer = Timer(-1) # -1 means SW timer 

led = Pin("LED", Pin.OUT)

def rotary_reset_and_set_to_max(value):
    global RotaryLastVal
    rot.reset()
    rot.set(max_val = value)
    RotaryLastVal = value
    print(f"Rotary reset & set to max {rot.get_max_val()}")    

# Seznam položek menu
home_screens = ["Home 0", "Home 1", "Home 2", "Setting screen" ]
ActualScreen = home_screens[0]
rotary_reset_and_set_to_max(len(home_screens) - 2) # note posledni prvek nesmi byt otacenim dosazitelny

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
HAPTIC Timer call cyclic
"""
def haptic(timer):    
    global RotaryLastVal, UpdateLCD, ActualScreen    
    _val = rot.value()
    if RotaryLastVal != _val:
        RotaryLastVal = _val
        UpdateLCD = True
        print(f"Rotary value {RotaryLastVal}")
        if ActualScreen != "Setting menu":
            ActualScreen = home_screens[RotaryLastVal]


hapticTimer = Timer(-1)
hapticTimer.init(period=19, mode=Timer.PERIODIC, callback=haptic) 

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

tim = Timer(-1)
tim.init(period=997, mode=Timer.PERIODIC, callback=task1)


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
        lcd.fill(0)
        lcd.set_font(BIG_FONT)
        lcd.set_text_wrap()
        lcd.text("Home screen", 0, 0)
        lcd.draw_text(str(screen_id), 0, 0)
        lcd.show()                        
        UpdateLCD = False
        print(f"Home {screen_id}")

pwmLCD.duty_u16(15000)


# Definice viceurovnoveho menu
menu = {
    "Setting menu": ["Polozka 1", "Polozka 2", "Polozka 3", "Zpet"],
    "Polozka 1": ["Akce 1 1", "Zpet"],
    "Polozka 2": ["Akce 2 1", "Akce 2 2", "Zpet"],
    "Polozka 3": ["Akce 3 1", "Akce 3 2", "Akce 3 3" , "Zpet"]
}

current_menu = "Setting menu"
selected_action = 0

def draw_menu():        
    global UpdateLCD
    """ Vykresli aktualni menu na LCD """
    lcd.clear()
    lcd.text(current_menu, 0, 0, 1)
    
    for i, item in enumerate(menu[current_menu]):
        prefix = "-> " if i == selected_action else "   "
        lcd.text(prefix + item, 0, 10 + i * 10, 1)

    lcd.show()
    UpdateLCD = False

def navigate_menu():
    """ Posune kurzor nahoru nebo dolu v menu """
    global selected_action
    if UpdateLCD:
        selected_action = RotaryLastVal #(selected_index + direction) % len(menu[current_menu][:-1])
        draw_menu()
        print("Setting menu")

def check_button(_):  
    global current_menu, selected_action, BlockMenu, UpdateLCD, ActualScreen
    if button.value() == 0:
    
        UpdateLCD = True

        if ActualScreen != "Setting screen":
            # entry into setting menu
            ActualScreen = "Setting screen"
            current_menu = "Setting menu"
            selected_action = 0
            rotary_reset_and_set_to_max(len(menu[current_menu]) - 1)
            draw_menu()
        else: #je v menu
            selected_item = menu[current_menu][selected_action]       
            if selected_item == "Zpet":
                current_menu = "Setting menu"
                rotary_reset_and_set_to_max(len(menu[current_menu]) - 1)
                selected_action = 0
                draw_menu()
            elif selected_item in menu:  # Pokud existuje podmenu
                current_menu = selected_item
                rotary_reset_and_set_to_max(len(menu[current_menu]) - 1)
                selected_action = 0
                draw_menu()
            elif menu[current_menu] == "Setting menu" and selected_action == menu[current_menu].index("Zpet"):
                # navrat zpet na screeny
                ActualScreen = home_screens[0]
                rotary_reset_and_set_to_max(len(home_screens) - 2)
            else:            
                print("Entry into action")

def button_isr(pin):
    global button_debounce_timer
    button_debounce_timer.init(mode=Timer.ONE_SHOT, period=button_debounce_time_ms, callback=check_button)

# Nastaveni preruseni
button.irq(trigger=Pin.IRQ_FALLING, handler=button_isr)

# Zobrazeni menu pri startu
#draw_menu()

# Hlavni smycka
while True:    
    if ActualScreen == "Home 0":        
        draw_screens(home_screens.index(ActualScreen))
    elif ActualScreen == "Home 1":        
        draw_screens(home_screens.index(ActualScreen))
    elif ActualScreen == "Home 2":
        draw_screens(home_screens.index(ActualScreen))        
    elif ActualScreen == "Setting screen":        
        navigate_menu()
        #TODO tady vsechny akce!!
    else:
        print("Error actual screen") 
    time.sleep(0.5)        

"""
    if UpdateLCD:
        if BlockMenu:        
            rot.set(max_val = menu[current_menu][-1])
            print(f"Rotary set max value {menu[current_menu][-1]}")
            navigate_menu(RotaryLastVal)
        else:
            selected_item = menu[current_menu][selected_index]
            # tohle nefunguje po startu
            if selected_item == "Akce 1 1":
                draw_bar(50)
        
        UpdateLCD = False            
    #if not button.value():  # Kontrola stisknuti tlacitka
    #    select_item()
    time.sleep(0.1)  # Debounce
"""