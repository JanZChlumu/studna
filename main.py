from machine import Pin, SPI, Timer, PWM, UART
from utime import sleep
import time
import ujson  # JSON pro ukládání strukturovaných dat
import uos
from rotary_irq_rp2 import RotaryIRQ
import lcd12864_spi
from lcd12864_spi import LCD12864_SPI
import Calibri10CZ  as F10_FONT
import Calibri16CZ as F16_FONT
import Calibri24CZ as F24_FONT
import Calibri36CZ as F36_FONT
import Calibri80CZ as F80_FONT

FILENAME = "config.json"

def save_config(data):
    try:
        with open(FILENAME, "w") as f:
            ujson.dump(data, f)
            print("File saved")
    except OSError:
        print("Error saving config")        

def load_config():
    try:
        with open(FILENAME, "r") as f:
            print("File loaded")
            return ujson.load(f)
    except OSError:
        print("File not found")
        return None  # Soubor neexistuje

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

# Inicializace rotačního enkodéru
rot = RotaryIRQ(pin_num_clk=6, pin_num_dt=7, min_val=0, max_val=5, reverse=False, range_mode=RotaryIRQ.RANGE_WRAP, pull_up=True)
"""
ROTARY def set(self, value=None, min_val=None, incr=None, max_val=None, reverse=None, range_mode=None):
"""

# Inicializace tlačítka potvrzení
button = Pin(14, Pin.IN, Pin.PULL_UP)
button_debounce_time_ms = 21
button_debounce_timer = Timer(-1) # -1 means SW timer 

led = Pin("LED", Pin.OUT)

def rotary_menu_reset_and_set_to_max(value):
    global RotaryPlausibleVal
    rot.reset() # = set(value = 0) #toto neni vhodne pro Akce
    rot.set(max_val = value, incr = 1)
    RotaryPlausibleVal = value #zabrání překreslení LCD
    #toto pridej global selected_action = 0
    print(f"Rotary reset & set to max {rot.get_max_val()}")    

# Definice viceurovnoveho menu
menu = {
    "Setting menu": ["Hladiny", "Zobrazení", "Info", "Zpět..."],
    "Hladiny":      ["Min" , "Max", "Zpět..."],
    "Zobrazení":    ["Graf historie", "LCD jas", "LCD kontrast", "Zpět..."],
    "Info":         ["Hist. maxima" , "Ulož test. CFG", "Zpět..."]
}
# testovací konfigurace pro emulovanou EEPROM
test_config_data = {"Min":            {"val": 21, "rotmax": 20, "rotstep" : 1, "unit": "cm"},
                    "Max":            {"val": 21, "rotmax": 20, "rotstep" : 1, "unit": "cm"},
                    "Graf historie":  {"val": 2, "rotmax": 24, "rotstep" : 8},
                    "LCD jas":        {"val": 2, "rotmax": 10, "rotstep" : 1},
                    "LCD kontrast":   {"val": 2, "rotmax": 5, "rotstep" : 1},
                    "Hist. maxima":   {"Min": 70, "Max": 123, "unit": "cm"}} 
               
#action_list = {"Min" : 11, "LCD jas" : 22, "Hist. maxima" : 33}
do_action = None
selected_text = ""
file_action_value = None
file_action_rmax = None
file_action_unit = None

current_menu = "Setting menu"
selected_action = 0

# Seznam položek menu
home_screens_list = ["Home_%", "Home_cm", "Home_graf"]
ActualHomeScreen = home_screens_list[0] 
rotary_menu_reset_and_set_to_max(len(home_screens_list) - 1)

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
    global RotaryPlausibleVal, UpdateLCD, ActualHomeScreen    
    _val = rot.value()
    if RotaryPlausibleVal != _val:
        RotaryPlausibleVal = _val
        UpdateLCD = True
        print(f"Rotary value {RotaryPlausibleVal} | max {rot.get_max_val()}")
        if ActualHomeScreen is not None:
            ActualHomeScreen = home_screens_list[RotaryPlausibleVal]


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

def draw_set_value(desc, value, unit = None):
    """ Draw a value on the display
    Args:
    desc (str): Description of the value
    value (int): Value to be displayed
    """
    global UpdateLCD
    if UpdateLCD:
        lcd.clear()
        lcd.set_font(F16_FONT)
        lcd.set_text_wrap()
        if unit is not None:
            text = str(value) + unit
        else:
            text = str(value)
        lcd.draw_text("Nastav " + desc, 0, 0)
        lcd.set_font(F36_FONT)
        lcd.draw_text(text, 15, 20)
        lcd.show()
        UpdateLCD = False

def draw_bar(fill_percentage):
    """ Draw a horizontal bar with adjustable fill
    Args:
    fill_percentage (int): Fill level from 0 to 100
    """
    global UpdateLCD
    if UpdateLCD:        
        print(fill_percentage)
        #lcd.clear()
        lcd.set_font(F24_FONT)
        lcd.set_text_wrap()        
        lcd.draw_text("Nastav jas", 0, 0)
        bar_width = 100
        bar_height = 15
        x_start = 14
        y_start = 25
        filled_width = int((fill_percentage / 100) * bar_width)    
        # Draw bar border
        lcd.rect(x_start, y_start, bar_width, bar_height, 1)    
        # clear - rewrite by white color
        lcd.fill_rect(x_start+1, y_start+1, bar_width-2, bar_height-2, 0)    
        # Draw filled portion
        lcd.fill_rect(x_start, y_start, filled_width, bar_height, 1)    
        lcd.show()
        UpdateLCD = False

def draw_testingFonts():
    global UpdateLCD
    if UpdateLCD:
        lcd.fill(0)
        lcd.set_font(F16_FONT)
        lcd.set_text_wrap()        
        lcd.draw_text("Historická data %ěščřžýá∑∞", 0, 0)
        lcd.show()                        
        UpdateLCD = False        

def draw_screens(screen_id):    
    global UpdateLCD
    if UpdateLCD:          
        lcd.fill(0)
        lcd.set_font(F80_FONT)
        #lcd.set_text_wrap()
        lcd.text(home_screens_list[screen_id], 0, 0)
        lcd.draw_text(str(screen_id) + "3%", 0, -10)
        lcd.show()                        
        UpdateLCD = False
        print(f"Home {screen_id}")

pwmLCD.duty_u16(15000)

def draw_menu():        
    global UpdateLCD
    #print("draw_menu")
    """ Vykresli aktualni menu na LCD """
    lcd.clear()
    lcd.set_font(F16_FONT)
    lcd.draw_text(current_menu, 0, 0)

    for i, item in enumerate(menu[current_menu]):
        prefix = "-> " if i == selected_action else "   "
        lcd.draw_text(prefix + item, 0, 12 + i * 12)

    lcd.show()
    UpdateLCD = False

def navigate_menu():
    """ Posune kurzor nahoru nebo dolu v menu """
    global selected_action
    if UpdateLCD:
        print("navigate_menu")
        selected_action = RotaryPlausibleVal
        draw_menu()

def entry_action(action):
    global do_action, file_action_value, file_action_unit, file_action_rmax
    if action == "Ulož test. CFG":
        save_config(test_config_data)    #TOdo remove later
        print("TEST TEST TEST Save config")
        return            
    cfg = load_config()
    if cfg is None:
        print("Error loading config")
        do_action = None
        rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1) #reset to menu
    else:
        lcd.clear()
        #print(f"\n\n entry action | loaded cfg {cfg}.")
        try:
            file_action_rmax = cfg[action]["rotmax"]
            step = cfg[action]["rotstep"]
            file_action_value = cfg[action]["val"]
            rot.set(value = file_action_value, max_val = file_action_rmax, incr = step) # nastaveni max a krok
            RotaryPlausibleVal = file_action_value
            print(f"entry action {action} | file load: file_action_value {file_action_value}, rmax {file_action_rmax}, step {step}.")
            if "unit" in cfg[action]:
                file_action_unit = cfg[action]["unit"]
            else:
                file_action_unit = None
        except OSError:
            print("Klic neni nenalezen") # pouzij defaultni hodnoty z menu
            file_action_rmax = len(menu[current_menu]) - 1        
            rotary_menu_reset_and_set_to_max(file_action_rmax)
            file_action_value = None    
        
        do_action = action
        print(f"Entry action {action}. Rotary max {rot.get_max_val()}") 


def leave_action(action, rot_val, rot_max):
    global UpdateLCD, do_action, file_action_value, file_action_unit, file_action_rmax
    
    rot.set(value = rot_val, max_val = rot_max, incr = 1)
    do_action = None
    UpdateLCD = True
    # ulož novou hodnotu
    cfg = load_config()
    if cfg is not None: # redundantni check bylo overeno v entry_action
        cfg[action]["val"] = RotaryPlausibleVal 
        save_config(cfg)  # Uložení změněné hodnoty do souboru
        print(f"Leave action {action} | stored file_action_value {RotaryPlausibleVal} ")
    else:
        print("Leave action | Error loading config")
    #clean variables
    file_action_value = None
    file_action_unit = None
    file_action_rmax = None

def check_button(_):  
    global current_menu, selected_action, UpdateLCD, ActualHomeScreen, selected_text
    if button.value() == 0:    
        UpdateLCD = True
        print(f"-> BTN ActualHomeScreen {ActualHomeScreen} | cur_menu {current_menu} | sel_action {selected_action} ")
        if ActualHomeScreen is not None:
            # entry into setting menu            
            ActualHomeScreen = None
            current_menu = "Setting menu"
            selected_action = 0
            rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1)
            
        else: #jsme v menu selection
            if do_action is None:            
                print("BTN  Menu selection")
                selected_text = menu[current_menu][selected_action]       
                if selected_text == "Zpět...":
                    if current_menu == "Setting menu":  #leave menu
                        print("naaaaaaaaaaaavrat")
                        ActualHomeScreen = "Home_%"
                        rotary_menu_reset_and_set_to_max(len(home_screens_list) - 1)
                    else:
                        current_menu = "Setting menu"
                        rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1)
                        selected_action = 0
                        
                elif selected_text in menu:  # Pokud existuje podmenu
                    current_menu = selected_text
                    rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1)
                    selected_action = 0 #delete ??? vsude???
            
                else:            
                    print("BTN Entry into action")
                    entry_action(selected_text)
            else:
                print("BTN  Leave Action")                
                _rot_last_in_menu = selected_action
                _rot_max = len(menu[current_menu]) - 1
                leave_action(selected_text, _rot_last_in_menu, _rot_max)

        print(f"<- BTN ActualHomeScreen {ActualHomeScreen} | cur_menu {current_menu} | sel_action {selected_action} | UpdateLCD {UpdateLCD}.")                

def button_isr(pin):
    global button_debounce_timer
    button_debounce_timer.init(mode=Timer.ONE_SHOT, period=button_debounce_time_ms, callback=check_button)
# Nastaveni preruseni
button.irq(trigger=Pin.IRQ_FALLING, handler=button_isr)


# Hlavni smycka
while True:    
    #print(f"while act screen {ActualScreen}")
    if ActualHomeScreen == "Home_%":        
        draw_screens(home_screens_list.index(ActualHomeScreen))
    elif ActualHomeScreen == "Home_cm":        
        draw_screens(home_screens_list.index(ActualHomeScreen))
    elif ActualHomeScreen == "Home_graf":
        draw_screens(home_screens_list.index(ActualHomeScreen))        
    elif ActualHomeScreen is None:        
        if do_action is None:
            navigate_menu()
        else:        
            #TODO tady vsechny akce!!
            if do_action == "Max":
                draw_set_value(do_action, RotaryPlausibleVal, file_action_unit)    
            elif do_action == "LCD jas":
                map_val = map_value(RotaryPlausibleVal, 0, file_action_rmax, 0, 100)
                draw_bar(map_val)            
            elif do_action == "Hist. maxima":
                draw_testingFonts()
            elif do_action == "Ulož test. CFG":
                save_config(test_config_data)    
            else: 
                print("While doesn't have action handler")
                do_action = None
                rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1)
                UpdateLCD = True
    else:
        print("Error actual screen") 
    time.sleep(0.1)
