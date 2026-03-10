from machine import Pin, SPI, PWM, Timer
from time import sleep
from ili9341 import Display, color565
from xglcd_font import XglcdFont
from xpt2046 import Touch
import network
import urequests


# ============================================================================
# CONSTANTS
# ============================================================================
CYAN = color565(0, 255, 255)
BLACK = color565(0, 0, 0)

# Global font variable (loaded once)
_font_cache = None


# ============================================================================
# HARDWARE SETUP
# ============================================================================
def display_setup(display_width, display_height, rotation=0, touch_handler=None):
    """
    Set up the display and backlight and touch screen.
    
    Args:
        display_width: Display width
        display_height: Display height
        rotation: Display rotation (0, 90, 180, 270, default: 0)
        touch_handler: Touch handler function
    
    Returns:
        tuple: (display, backlight, touch) objects
    """
    # Set up SPI for TFT display
    display_spi = SPI(1, baudrate=60000000, sck=Pin(14), mosi=Pin(13))
    
    # Set up display (rst must be a different pin from cs)
    display = Display(
        display_spi,
        dc=Pin(2),
        cs=Pin(15),
        rst=Pin(16),
        width=display_width,
        height=display_height,
        rotation=rotation,
    )
    
    # Set up backlight with PWM for brightness control
    backlight = PWM(Pin(21), freq=1000, duty=0)
    
    # Set up touch screen (SPI2 for XPT2046)
    touchscreen_spi = SPI(2, baudrate=1000000, sck=Pin(25), mosi=Pin(32), miso=Pin(39))
    touch = Touch(touchscreen_spi, cs=Pin(33), int_pin=Pin(36), int_handler=touch_handler, width=display_width, height=display_height)
    
    return display, backlight, touch


def set_backlight_brightness(backlight, brightness):
    """
    Set the backlight brightness level.
    
    Args:
        backlight: PWM backlight object
        brightness: Brightness level (0-100, where 0 is off and 100 is maximum)
    """
    brightness = max(0, min(100, brightness))
    
    if brightness == 0:
        backlight.duty(0)
    else:
        duty = int((brightness / 100.0) * 1023)
        backlight.duty(duty)


def connect_wifi(ssid, password):
    """
    Connect to WiFi network.
    Resets STA interface first to avoid "Wifi Internal State Error" after soft reboot.
    
    Args:
        ssid: WiFi network name
        password: WiFi password
    
    Returns:
        bool: True if connected, False otherwise
    """
    wlan = network.WLAN(network.STA_IF)
    # Clean state: off then on (avoids ESP32 internal state error after reboot)
    wlan.active(False)
    sleep(0.2)
    wlan.active(True)
    sleep(0.5)

    if not wlan.isconnected():
        print(f'Connecting to {ssid}...')
        try:
            wlan.connect(ssid, password)
        except OSError as e:
            print('WiFi connect error:', e)
            return False

        # Wait for connection (max 10 seconds)
        for _ in range(20):
            if wlan.isconnected():
                break
            sleep(0.5)
    
    if wlan.isconnected():
        print(f'WiFi connected! IP: {wlan.ifconfig()[0]}')
        return True
    else:
        print('WiFi connection failed')
        return False


def check_wifi_connected():
    """Check if WiFi is connected."""
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()


def get_font():
    """Load and cache the font for reuse."""
    global _font_cache
    if _font_cache is None:
        print('Loading Unispace font (12x24)...')
        _font_cache = XglcdFont('Unispace12x24.c', 12, 24)
    return _font_cache


def display_loading(display, message="Loading...", color=CYAN):
    """
    Show a centered message on black background.
    """
    try:
        font = XglcdFont('Unispace12x24.c', 12, 24)
    except Exception:
        font = None
    display.clear(BLACK)
    if font:
        x = max(0, (display.width - len(message) * font.width) // 2)
        y = max(0, (display.height - font.height) // 2)
        display.draw_text(x, y, message, font, color, BLACK)

def display_image(display, image_path):
    """
    Display an image on the display.
    """
    display.draw_image(image_path)