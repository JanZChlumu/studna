from machine import Pin, SPI, Timer, PWM, UART
from utime import sleep
import time
import ujson  # JSON pro ukládání strukturovaných dat
import uos
from rotary_irq_rp2 import RotaryIRQ
import lcd12864_spi
from lcd12864_spi import LCD12864_SPI
import Calibri10CZ  as F10_FONT
import Calibri12CZ  as F12_FONT
import Calibri16CZ as F16_FONT
import Calibri24CZ as F24_FONT
import Calibri36CZ as F36_FONT
import Calibri80CZ as F80_FONT

semaphore = 1  # Binární semafor (1 = volný, 0 = obsazený)

def acquire_semaphore():
    """Pokud je semafor volný (1), nastavíme ho na obsazený (0) a vrátíme True."""
    global semaphore
    if semaphore == 1:
        semaphore = 0
        return True
    return False

def release_semaphore():
    """Uvolní semafor (nastaví na 1)."""
    global semaphore
    semaphore = 1

FILE_CONFIG = "config.json"
FILE_HISTORY = "hist_data.json"

# Definice viceurovnoveho menu
menu = {
    "Setting menu": ["Hladiny"      , "Zobrazení"       , "Info"            , "Zpět..."],
    "Hladiny":      ["Min"          , "Max"             , "Posun reference" , "Zpět..."],
    "Zobrazení":    ["Graf historie", "LCD jas"         , "LCD kontrast"    , "Zpět..."],
    "Info":         ["Hist. maxima" , "RESET Historie"  , "Průměruj vzorky" , "Zpět..."]
}
# testovací konfigurace pro emulovanou EEPROM
test_config_data = {"Min":             {"val": 20, "rotmax": 100, "rotstep" : 1, "unit": "cm"},
                    "Max":             {"val": 40, "rotmax": 200, "rotstep" : 1, "unit": "cm"},
                    "Posun reference": {"val": 0, "rotmax": 220, "rotstep" : 1, "unit": "mm", "rotmin" : -220},
                    "Graf historie":   {"val": 0, "rotmax": 2, "rotstep" : 1, "unit": "hodin"},
                    "LCD jas":         {"val": 2, "rotmax": 10, "rotstep" : 1},
                    "LCD kontrast":    {"val": 4, "rotmax": 30, "rotstep" : 2},
                    "RESET Historie":  {"val": 0, "rotmax": 3, "rotstep" : 1},
                    "Průměruj vzorky":   {"val": 1, "rotmax": 7, "rotstep" : 1, "rotmin" : 1, "unit" : "vzorky"}} 

do_action = None # jméno probíhající akce
selected_text = "" # na tento text ukazuje šipka v menu "->"
action_tmp_file__rmax = None  # dočasná hodnota z konfiguračního souboru, vyžadují některé akce
action_tmp_file__unit = None  # dočasná hodnota z konfiguračního souboru, vyžadují některé akce

graph_data = {"8h": [], "16h": [], "32h": [], "counter": 0}
home_screens_show_data = {"dist_cm": -1, "percent": -1, "error": None}

current_menu = "Setting menu"
selected_action = 0

# Seznam položek menu
home_screens_list = ["Home_%", "Home_cm", "Home_graf"]
ActualHomeScreen = home_screens_list[0] 

hist_data_shadow = {"min": 0, "max": 0}

def save_file(file_name, data):
    try:
        with open(file_name, "w") as f:
            ujson.dump(data, f)
            print("File saved")
    except OSError:
        print("Error saving config")        

def load_file(file_name):
    try:
        with open(file_name, "r") as f:
            print(f"File loaded {file_name}")
            return ujson.load(f)
    except OSError:
        print("File not found")
        return None  # Soubor neexistuje

#print("!!!!!!! test confguration !!!!!!!!!")
#save_file(FILE_CONFIG, test_config_data)    #TOdo remove later

file_ram_shadow_data = {}

def load_cfg_to_shadow_ram(file_data):
    global file_ram_shadow_data
    print("load_cfg_for_home_screens")
    if file_ram_shadow_data is None:
        file_ram_shadow_data = {"Min": 0, "Max": 0, "GraphHrs": 0, "ReferenceShift": 0}
    if file_data is not None:
        try:
            file_ram_shadow_data["Min"] = file_data["Min"]["val"]
            file_ram_shadow_data["Max"] = file_data["Max"]["val"]
            file_ram_shadow_data["GraphHrs"] = file_data["Graf historie"]["val"]
            file_ram_shadow_data["ReferenceShift"] = file_data["Posun reference"]["val"]
            file_ram_shadow_data["AvgNo"] = file_data["Průměruj vzorky"]["val"]
            file_ram_shadow_data["LCD jas"] = file_data["LCD jas"]["val"]
            file_ram_shadow_data["LCD jas max"] = file_data["LCD jas"]["rotmax"]            
            file_ram_shadow_data["LCD kontrast"] = file_data["LCD kontrast"]["val"]
            file_ram_shadow_data["LCD kontrast max"] = file_data["LCD kontrast"]["rotmax"]
        except OSError:
            print("load_cfg_for_home_screens | no key found")
 
load_cfg_to_shadow_ram(load_file(FILE_CONFIG))

def load_history_info(file_data):
    global hist_data_shadow    
    print("load_history_info")
    if hist_data_shadow is None:
        hist_data_shadow = {"min": 0, "max": 0}
    if file_data is None:
        # Pokud soubor neexistuje, vytvoř nový
        file_data = {"min_vody": 0, "max_vody": 0}
        save_file(FILE_HISTORY, file_data)
        hist_data_shadow["min"] = 0
        hist_data_shadow["max"] = 0
    else:
        try:
            hist_data_shadow["min"] = file_data["min_vody"]
            hist_data_shadow["max"] = file_data["max_vody"]
        except OSError:
            print("load_history_info | no key found")
    
load_history_info(load_file(FILE_HISTORY)) #INIT

def save_history_info():
    global hist_data_shadow
    if hist_data_shadow is not None:
        _file_data = load_file(FILE_HISTORY)
        if _file_data is None:
            # Pokud soubor neexistuje, vytvoř nový
            _file_data = {"min_vody" : hist_data_shadow["min"], "max_vody" : hist_data_shadow["max"]}
        else:
            _file_data["min_vody"] = hist_data_shadow["min"]
            _file_data["max_vody"] = hist_data_shadow["max"]
        save_file(FILE_HISTORY, _file_data)
        print("History saved")
    
def update_history_data(distance):
    global hist_data_shadow
    if distance is not None:
        _update = False
        if hist_data_shadow["min"] == 0 or distance < hist_data_shadow["min"]:
            hist_data_shadow["min"] = distance
            _update = True
        if hist_data_shadow["max"] == 0 or distance > hist_data_shadow["max"]:
            hist_data_shadow["max"] = distance
            _update = True        
        if _update:
            save_history_info()
            print(f"History updated min {hist_data_shadow['min']} max {hist_data_shadow['max']}")

# Inicializace UART1 pro Raspberry Pi Pico 
uart1 = UART(1, baudrate=9600, tx=Pin(8), rx=Pin(9))  # Nastav piny dle zapojení

distances = []
max_records = 128  # Počet měření za posledních 6 hodin -> uložit každé 12 měření á 15 sec.

pwmLCD = PWM(Pin(10))
pwmLCD.freq(1000) # PWM 1kHz

pwmContrast = PWM(Pin(11))
pwmContrast.freq(1000) # PWM 1kHz
MIN_PWM_CONTRAST = 0
MAX_PWM_CONTRAST = 65535

spi = SPI( 0, baudrate = 1_000_000, polarity = 1, phase = 1 )
lcd = LCD12864_SPI( spi = spi, cs_pin = 20, rst_pin = 21, rotation = 0 )
lcd.clear()
UpdateLCD = False

# Inicializace rotačního enkodéru
rot = RotaryIRQ(pin_num_clk=6, pin_num_dt=7, min_val=0, max_val=5, reverse=True, range_mode=RotaryIRQ.RANGE_WRAP, pull_up=True)

# Inicializace tlačítka potvrzení
button = Pin(14, Pin.IN, Pin.PULL_UP)
button_debounce_time_ms = 21
button_debounce_timer = Timer(-1) # -1 means SW timer 

led = Pin("LED", Pin.OUT)

def rotary_menu_reset_and_set_to_max(value):
    global RotaryPlausibleVal
    rot.reset() # = set(value = 0) #toto neni vhodne pro Akce
    rot.set(max_val = value, incr = 1, min_val = 0)
    RotaryPlausibleVal = value #zabrání překreslení LCD
    #toto pridej global selected_action = 0
    print(f"Rotary reset & set to max {rot.get_max_val()}")    

rotary_menu_reset_and_set_to_max(len(home_screens_list) - 1)

def map_value(x, in_min, in_max, out_min, out_max):
    mapped_value = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    print(f"map_value -> {x} | {in_min} {in_max} | {out_min} {out_max} | -> {mapped_value}")
    return int(mapped_value)    

def measure_ultrasonic():
    if not acquire_semaphore():  
        return None  # Pokud je semafor obsazený, měření neproběhne

    uart1.write(b'\x55')  # Odeslání příkazu pro měření
    time.sleep(0.05)  # Krátká pauza (2 ms)

    distance = None
    if uart1.any() >= 4:
        start_byte = uart1.read(1)
        if start_byte == b'\xff':
            data = uart1.read(3)
            if data and len(data) == 3:
                h_data, l_data, checksum = data
                result = (h_data << 8) + l_data
                if ((255 + h_data + l_data) & 0xFF) == checksum:
                    distance = result
                else:
                    print("Invalid result")
                    led.toggle()
                    led.toggle()
                    led.toggle()
    print(f"measure_ultrasonic {distance}")    
    release_semaphore()  # Uvolnění semaforu po dokončení
    return distance

def get_distance():    
    # average samples
    if file_ram_shadow_data.get("AvgNo", 1) > 1:                
        distances = []
        for i in range(file_ram_shadow_data["AvgNo"]):
            dist_mm = measure_ultrasonic()
            if dist_mm is not None:
                #dist_mm = file_ram_shadow_data["ReferenceShift"] - dist_mm
                if dist_mm < 0:
                    home_screens_show_data["error"] = "Uprav ref. hladinu"
                distances.append(dist_mm)
        if len(distances) > 0:
            avg = sum(distances) / len(distances)
            print(f"get_distance_AVG | dist_mm {distances} | avg {avg}")
            return avg
    else:
        # no average samples
        return measure_ultrasonic()
       
   

def draw_home_graph_hrs():
    global UpdateLCD, home_screens_show_data
    if UpdateLCD:
        lcd.fill(0)    
        map_hours = {0: "8h", 1: "16h", 2: "32h"}
        _hr = file_ram_shadow_data["GraphHrs"]
        if _hr in map_hours: 
            distances = graph_data[map_hours[_hr]]

            if len(distances) > 0:                
                min_distance = min(distances)
                max_distance = max(distances)                                
                range_distance = max_distance - min_distance                                                
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
                # write over graph
                lcd.set_font(F12_FONT)
                lcd.draw_text("Max:" + str(max_distance/10) + "cm", 5, 10, center_x=True, clear_background=True)
                lcd.draw_text( map_hours[_hr] , 105, 25, clear_background=True)    
                lcd.draw_text("Min: " + str(min_distance/10) + "cm", 5, 42, center_x=True, clear_background=True)
            else:
                lcd.text("Nejsou data pro ", 5, 20, 1)
                lcd.text( " " + map_hours[_hr] + " graf ", 25, 30, 1)
        else:
            print("Invalid key in map_hours")                    
        if home_screens_show_data.get("error", "NoError") != "NoError":
            lcd.set_font(F12_FONT)
            lcd.draw_text(str(home_screens_show_data["error"]), 30, 0, center_x=True, clear_background=True)
            home_screens_show_data["error"] = None
        lcd.show()
        UpdateLCD = False

def draw_graph():
    lcd.fill(0)
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

#update homescreens
def task1(timer):    
    global UpdateLCD, home_screens_show_data
    #led.toggle()
    #TODO always check limit - save water level
    dist_mm = get_distance()
    if dist_mm is not None:            
        #dist_mm = file_ram_shadow_data["ReferenceShift"] - dist_mm
        update_history_data(dist_mm) #update history data

        if ActualHomeScreen in home_screens_list:
            _dist_cm = round(float(dist_mm / 10), 2)
            _percent = int((((dist_mm/10) - file_ram_shadow_data["Min"]) * 100)/file_ram_shadow_data["Max"])
            home_screens_show_data = {"dist_cm": _dist_cm, "percent": _percent}
            print(f"task1 | dist_cm {_dist_cm} | percent {_percent} | actual_home_screen {ActualHomeScreen}")
            UpdateLCD = True    

tim = Timer(-1)
tim.init(period=2*1000, mode=Timer.PERIODIC, callback=task1)

def updateGraphData(_):
    global graph_data
    print("updateGraphData")
    _dist = get_distance()
    _arrray_max = 128
    if _dist is not None:
        #8h store
        graph_data["8h"].append(_dist)
        if len(graph_data["8h"]) > _arrray_max:
            graph_data["8h"].pop(0)
        print("updateGraphData | data 8h", graph_data["8h"]) #TODO tohle ukaze cely list!
        # 16h store
        if graph_data["counter"] % 2 == 0:
            graph_data["16h"].append(_dist)
            if len(graph_data["16h"]) > _arrray_max:    
                graph_data["16h"].pop(0)
            print("updateGraphData | data 16h", graph_data["16h"])
        # 32h store
        if graph_data["counter"] % 4 == 0:
            graph_data["32h"].append(_dist)
            if len(graph_data["32h"]) > _arrray_max:    
                graph_data["32h"].pop(0)
            print("updateGraphData | data 32h", graph_data["32h"])
    graph_data["counter"] += 1

"""
Historie pro grafy se ukládá jen v ram. LCD má rozlišení 128x64 pixelů, takže max 128 bodů uložíme pro každý graf.
Pro 8h graf uložíme hodnotu každých 225 sec, pro 16h graf každých 450 sec a pro 32h graf každých 900 sec.
"""
timStoreGraph = Timer(-1)
timStoreGraph.init(period=1000*225, mode=Timer.PERIODIC, callback=updateGraphData)
#timStoreGraph.init(period=2500, mode=Timer.PERIODIC, callback=updateGraphData)

def draw_action_set_value(desc, value, unit = None):
    """ Draw a value on the display
    Args:
    desc (str): Description of the value
    value (int): Value to be displayed
    """
    global UpdateLCD
    if UpdateLCD:
        lcd.fill(0)
        lcd.set_font(F16_FONT)
        lcd.set_text_wrap()
        if unit is not None:
            text = str(value) + unit
        else:
            text = str(value)
        lcd.draw_text(desc, 0, 0)
        lcd.set_font(F36_FONT)
        lcd.draw_text(text, 5, 20, center_x=True)
        lcd.show()
        UpdateLCD = False

def draw_action_reset_history(desc, value):
    _map = {0 : "Ne", 1 : "Možná?", 2 : "Ano", 3 : "Možná?"}
    draw_action_set_value(desc, _map[value])

def draw_action_graph_time_base(desc, value, unit = None):
    try:
        map_hours = {0: 8, 1: 16, 2: 32}
    except KeyError:
        value = 0  # Default value if key is not found        
        print("Invalid key in map_hours")
    draw_action_set_value(desc, map_hours[value], unit)

def draw_action_bar(text_desc, fill_percentage):
    """ Draw a horizontal bar with adjustable fill
    Args:
    fill_percentage (int): Fill level from 0 to 100
    """
    global UpdateLCD
    if UpdateLCD:        
        print(fill_percentage)
        #lcd.fill(0)
        lcd.set_font(F24_FONT)
        lcd.set_text_wrap()        
        lcd.draw_text(text_desc, 0, 0)        
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

def draw_action_info_history_extrems():
    global UpdateLCD    
    if UpdateLCD:
        lcd.fill(0)
        lcd.set_font(F16_FONT)
        lcd.set_text_wrap()
        lcd.draw_text("Historické extrémy", 0, 0)        
        lcd.draw_text("Min : " + str(hist_data_shadow["min"]/1000) + " m", 0, 20)
        lcd.draw_text("Max : " + str(hist_data_shadow["max"]/1000) + " m", 0, 30)
        lcd.draw_text("Ø z " + str(file_ram_shadow_data["AvgNo"]) + " vzorků", 0, 50)
        lcd.show()                        
        UpdateLCD = False
        print("draw_history_maximums")

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

def draw_home_screen_cm():
    global UpdateLCD, home_screens_show_data
    if UpdateLCD:
        lcd.fill(0)        
        lcd.set_font(F16_FONT)        
        lcd.draw_text("Výška hladiny", 0, 0, center_x=True)
        lcd.set_font(F36_FONT)        
        lcd.draw_text(str(home_screens_show_data["dist_cm"]) + "cm", 0, 15, center_x=True)                
        if home_screens_show_data.get("error", "NoError") != "NoError":
            print(f"error {home_screens_show_data["error"]}")
            lcd.set_font(F12_FONT)
            lcd.draw_text(str(home_screens_show_data["error"]), 30, 0, center_x=True, clear_background=True)
            home_screens_show_data["error"] = None
        lcd.show()                        
        UpdateLCD = False
        

def draw_home_screen_percent():
    global UpdateLCD, home_screens_show_data
    if UpdateLCD:
        lcd.fill(0)        
        lcd.set_font(F16_FONT)        
        lcd.draw_text("V zásobě %", 5, -2, center_x=True)
        lcd.set_font(F80_FONT)        
        lcd.draw_text(str(home_screens_show_data["percent"]), 0, -2, center_x=True)        
        if home_screens_show_data.get("error", "NoError") != "NoError":
            lcd.set_font(F16_FONT)
            lcd.draw_text(str(home_screens_show_data["error"]), 30, 0, center_x=True, clear_background=True)
            home_screens_show_data["error"] = None
        lcd.show()
        UpdateLCD = False


pwmLCD.duty_u16(map_value(file_ram_shadow_data["LCD jas"], 0, file_ram_shadow_data["LCD jas max"], 0, 65535)) # 0-100%
pwmContrast.duty_u16(map_value(file_ram_shadow_data["LCD kontrast"], 0, file_ram_shadow_data["LCD kontrast max"], MIN_PWM_CONTRAST, MAX_PWM_CONTRAST)) # 0-100%

def draw_menu():        
    global UpdateLCD
    #print("draw_menu")
    """ Vykresli aktualni menu na LCD """
    lcd.fill(0)
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
    global do_action, action_tmp_file__unit, action_tmp_file__rmax, RotaryPlausibleVal, UpdateLCD
    
    # načti z konfiguračního souboru
    cfg = load_file(FILE_CONFIG)
    if cfg is None:
        print("Error loading config")
        do_action = None
        rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1) #reset to menu
    else:
        lcd.clear()
        UpdateLCD = True        
        try:
            if action in cfg:
                action_tmp_file__rmax = cfg[action]["rotmax"]
                _val = cfg[action]["val"]
                _step = cfg[action]["rotstep"]

                RotaryPlausibleVal = _val
                rot.set(value = _val, max_val = action_tmp_file__rmax, incr = _step)
                print(f"entry action {action} | file load: val {_val}, rmax {action_tmp_file__rmax}, step {_step}.")
                
                # non standard keys...
                if "unit" in cfg[action]:
                    action_tmp_file__unit = cfg[action]["unit"]
                else:
                    action_tmp_file__unit = None
                if "rotmin" in cfg[action]:
                    rot.set(min_val = cfg[action]["rotmin"])
        except OSError:
            print("Klic neni nenalezen") # pouzij defaultni hodnoty z menu
            action_tmp_file__rmax = len(menu[current_menu]) - 1        
            rotary_menu_reset_and_set_to_max(action_tmp_file__rmax)            
        
        do_action = action
        print(f"Entry action {action}. Rotary max {rot.get_max_val()}") 


def leave_action(store_action, restore_rot_val, restore_rot_max):
    global UpdateLCD, do_action, action_tmp_file__unit, action_tmp_file__rmax
    
    UpdateLCD = True
    _store_config = True

    if do_action == "RESET Historie":
        if RotaryPlausibleVal == 2:  # _map = {0 : "Ne", 1 : "Možná?", 2 : "Ano", 3 : "Možná?"}            
            _store_config = False
            do_action = None
            hist_data_shadow["min"] = 0
            hist_data_shadow["max"] = 0
            save_history_info()
            load_history_info(load_file(FILE_HISTORY)) #INIT
            print("History reset!!!")
            return
    
    rot.set(value = restore_rot_val, max_val = restore_rot_max, incr = 1, min_val = 0)    
    do_action = None    
    #clean temp action variables    
    action_tmp_file__unit = None
    action_tmp_file__rmax = None
    
    if _store_config:
        # save new value to config file
        cfg = load_file(FILE_CONFIG)
        if cfg is not None: # redundantni check bylo overeno v entry_action
            if store_action in cfg:
                cfg[store_action]["val"] = RotaryPlausibleVal
                save_file(FILE_CONFIG, cfg)  # Uložení změněné hodnoty do souboru
                print(f"Leave action {store_action} | stored RotVal {RotaryPlausibleVal} ")
            else:
                print("Leave action | Witout storage")        
        load_cfg_to_shadow_ram(load_file(FILE_CONFIG)) #update shadow ram
    

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
                    print(f"BTN Entry into action {selected_text}")
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
        draw_home_screen_percent()
        #draw_screens(home_screens_list.index(ActualHomeScreen))
    elif ActualHomeScreen == "Home_cm":        
        draw_home_screen_cm()
        #draw_screens(home_screens_list.index(ActualHomeScreen))
    elif ActualHomeScreen == "Home_graf":
        draw_home_graph_hrs()
        #draw_screens(home_screens_list.index(ActualHomeScreen))        
    elif ActualHomeScreen is None:        
        if do_action is None:
            navigate_menu()
        else:        
            #ALL actions HERE
            if do_action == "Max" or \
               do_action == "Min" or \
               do_action == "Posun reference" or \
               do_action == "Průměruj vzorky":
                draw_action_set_value(do_action, RotaryPlausibleVal, action_tmp_file__unit)    
            elif do_action == "LCD jas":                 
                map_val = map_value(RotaryPlausibleVal, 0, action_tmp_file__rmax, 0, 100)
                draw_action_bar(do_action, map_val)
                pwmLCD.duty_u16(map_value(RotaryPlausibleVal, 0, action_tmp_file__rmax, 0, 65535))
            elif do_action == "LCD kontrast":    
                map_val = map_value(RotaryPlausibleVal, 0, action_tmp_file__rmax, 0, 100)
                draw_action_bar(do_action, map_val)
                pwmContrast.duty_u16(map_value(RotaryPlausibleVal, 0, action_tmp_file__rmax, MIN_PWM_CONTRAST, MAX_PWM_CONTRAST))            
            elif do_action == "Hist. maxima":
                draw_action_info_history_extrems()                            
            elif do_action == "Graf historie":
                draw_action_graph_time_base(do_action, RotaryPlausibleVal, action_tmp_file__unit)
            elif do_action == "RESET Historie":
                draw_action_reset_history(do_action, RotaryPlausibleVal)
            else: 
                print("While doesn't have action handler")
                do_action = None
                rotary_menu_reset_and_set_to_max(len(menu[current_menu]) - 1)
                UpdateLCD = True
    else:
        print("Error actual screen") 
    time.sleep(0.2)
