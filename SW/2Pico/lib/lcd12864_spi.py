"""
LCD12864_SPI v 0.2.3

LCD12864_SPI is a FrameBuffer based MicroPython driver for the graphical
LiquidCrystal LCD12864 display (also known as st7920).
 
Connection: SPI
Color: 1-bit monochrome
Controllers: Esp8266, Esp32, RP2

Project path: https://github.com/r2d2-arduino/micropython-lcd12864
MIT License

Author: Arthur Derkach 
  
LCD -> ESP32 / ESP8266
--------------
GND -> GND
VCC -> 5V
V0
RS  -> CS_PIN
R/W -> D7 GPIO13 MOSI
E   -> D5 GPIO14 SCK
DB0
..
DB7
PSB -> GND or LOW
NC
RST -> RST_PIN or HI
VOUT
BLA -> 3.3-5V
BLK -> GND
"""

from micropython import const
from machine import Pin
from time import sleep_us
from framebuf import FrameBuffer, MONO_HMSB, MONO_HLSB

LCD_CLS          = const(0x01)
LCD_HOME         = const(0x02)
LCD_ADDR_INC     = const(0x06)
LCD_DISPLAY_ON   = const(0x0C)
LCD_DISPLAY_OFF  = const(0x08)
LCD_CURSOR_ON    = const(0x0E)
LCD_CURSOR_BLINK = const(0x0F)
LCD_ENTRY_MODE   = const(0x04) # +0..3
LCD_SHIFT_CTRL   = const(0x10) # : 10, 14, 18, 1C
SET_CGRAM_ADDR   = const(0x40) # +0..3F
SET_DDRAM_ADDR   = const(0x80) # +0..3F  

LCD_BASIC        = const(0x30)
LCD_EXTEND       = const(0x34)
LCD_GFXMODE      = const(0x36)
LCD_TXTMODE      = const(0x34)
LCD_STANDBY      = const(0x01)
LCD_ADDR         = const(0x80)
LCD_COMMAND      = const(0xF8)
LCD_DATA         = const(0xFA)

LCD_WIDTH  = const(128)
LCD_HEIGHT = const(64)

class LCD12864_SPI( FrameBuffer ):
    def __init__( self, spi, cs_pin, rst_pin = None, rotation = 0 ):
        """ Constructor
        Args
        spi  (object): SPI
        cs   (object): CS pin (Chip Select)
        rotation (int): Display rotation 0 = 0 degrees, 1 = 180 degrees
        """ 
        self.spi = spi
        self.cs  = Pin( cs_pin, Pin.OUT, value = 0 )
        
        if (rst_pin):
            Pin( rst_pin, Pin.OUT, value = 1 )
        # Other properties
        self.height = LCD_HEIGHT
        self.width  = LCD_WIDTH
        
        self._rotation = rotation
        self.font = None
        self.text_wrap = False
        
        #order of bites in buffer depending of screen position
        fb_format = MONO_HLSB
        if (rotation == 1):
            fb_format = MONO_HMSB
            
        # Buffer initialization
        self.buffsize = LCD_WIDTH * LCD_HEIGHT // 8
        self.buffer = bytearray( self.buffsize )
        super().__init__( self.buffer, self.width, self.height, fb_format )

        self.init()

    def init(self):
        """ Initialize the LCD controler """
        self.cs.value( 1 )
    
        self.write_command( LCD_BASIC ) # basic instruction set
        self.write_command( LCD_CLS ) #clear
        sleep_us(50) #wait for clearing
        
        self.write_command( LCD_ADDR_INC )
        self.write_command( LCD_DISPLAY_ON ) # display on
           
        self.cs.value( 0 )

    def clear( self ):
        """ Clear display """
        self.cs.value( 1 )
        self.write_command( LCD_BASIC )
        self.write_command( LCD_CLS ) #clear
        sleep_us(50)

        # Clear framebuffer
        for i in range(len(self.buffer)):
            self.buffer[i] = 0

        self.cs.value( 0 ) 
        
    def write_command( self, cmd ):
        """ Sending a command to the display
        Args
        cmd (int): Command number, example: 0x2E
        """        
        self.spi.write( bytearray( [ LCD_COMMAND, cmd & 0xF0, (cmd & 0x0F) << 4] ) )
        
    def write_data( self, data ):
        """ Sending data to the display
        Args
        cmd (int): Command number, example: 0x2E
        """        
        self.spi.write( bytearray( [ LCD_DATA, data & 0xF0, (data & 0x0F) << 4] ) )

    def set_font(self, font):
        """ Set font for text
        Args
        font (module): Font module generated by font_to_py.py
        """
        self.font = font
        
    def set_text_wrap(self, on = True):
        """ Set text wrapping """
        self.text_wrap = bool(on)

    def draw_text(self, text, x, y, color=1, center_x=False, clear_background=False):
        """ Draw text on display
        Args
        text (str): Text to display
        x (int): Start X position (ignored if center_x is True)
        y (int): Start Y position
        color (int): Color of the text
        center_x (bool): Whether to center the text in the x-axis
        clear_background (bool): Whether to clear the background before drawing text
        """
        x_start = x
        screen_width = self.width

        font = self.font
        wrap = self.text_wrap

        if font is None:
            print("Font not set")
            return False

        # Calculate total text width if centering is enabled
        if center_x:
            total_width = sum(font.get_ch(char)[2] for char in text)
            x_start = (screen_width - total_width) // 2

        # Clear background if requested
        if clear_background:
            total_width = sum(font.get_ch(char)[2] for char in text)
            text_height = font.get_ch(text[0])[1] if text else 0
            self.fill_rect(x_start, y, total_width, text_height, 0)

        for char in text:
            glyph = font.get_ch(char)
            glyph_height = glyph[1]
            glyph_width = glyph[2]

            if char == " ":  # double size for space
                x_start += glyph_width

            if wrap and (x_start + glyph_width > screen_width):  # End of row
                x_start = x
                y += glyph_height

            self.draw_bitmap(glyph, x_start, y, color)
            x_start += glyph_width

    def draw_bitmap(self, bitmap, x, y, color = 1):
        """ Draw a bitmap on display
        Args
        bitmap (bytes): Bitmap data
        x      (int): Start X position
        y      (int): Start Y position
        color  (int): Color 0 or 1
        """        
        fb = FrameBuffer(bytearray(bitmap[0]), bitmap[2], bitmap[1], MONO_HLSB)
        self.blit(fb, x, y, 1 - color)        
              
        
    def show( self ):
        ''' Send FrameBuffer to lcd '''
        #Set text mode
        self.cs.value( 1 )
        self.write_command( LCD_GFXMODE )
        
        buffsize = self.buffsize
        rotation = self._rotation
        buffer = memoryview( self.buffer )
        row_buffer = bytearray( 3 * 16 )
        
        for y in range(64):
            x_addr = LCD_ADDR
            y_addr = LCD_ADDR + y
                
            if y > 31:
                x_addr += 8
                y_addr -= 32
            
            #Set addres position            
            self.spi.write( bytearray( [ LCD_COMMAND, y_addr & 0xF0, (y_addr & 0x0F) << 4,
                                         LCD_COMMAND, x_addr & 0xF0, (x_addr & 0x0F) << 4 ] ) )
            y_offset = y * 16
            
            #Send buffer to display
            for x in range(16):
                pos = y_offset + x
                if ( rotation == 1 ):
                    pos = buffsize - 1 - pos
                    
                data = buffer[pos]
                
                x_offset = x * 3
                row_buffer[x_offset    ] = LCD_DATA 
                row_buffer[x_offset + 1] = data & 0xF0
                row_buffer[x_offset + 2] = (data & 0x0F) << 4

            self.spi.write( row_buffer )

        self.cs.value( 0 )
