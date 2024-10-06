from machine import Pin, I2C, Timer, PWM
import ssd1306
from bme680 import *
from time import time, ticks_diff, ticks_ms, sleep_ms
import sys


i2c_ok = False

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
try:
    bme = BME680_I2C(i2c)
    display = ssd1306.SSD1306_I2C(64, 48, i2c)
    i2c_ok = True
except:
    i2c_ok = False
    


red_led = PWM(Pin(27), freq=2000, duty_u16=0)
green_led = PWM(Pin(25), freq=2000, duty_u16=0)
blue_led = PWM(Pin(32), freq=2000, duty_u16=0)

buzzer = PWM(Pin(33))
buzzer.deinit()

def warning():
    global red_led, buzzer    
    buzzer.init(freq = 2000, duty_u16 = 0)
    
    for duty in (2**15,0,2**15,0):
        red_led.duty_u16(duty)
        buzzer.duty_u16(duty)
        sleep_ms(1000)


if not i2c_ok:
    warning()
    sys.exit()
    
displayOn = False
displayState = 1
displayChanged = False

timerStarted = False

measureCount = -1

temperature = bme.temperature
pressure = bme.pressure
humidity = bme.humidity
gas = 0
iaq = 0

min_gas = 1_000_000_000
max_gas = 0

#display.line(0, 0, 63, 47, 1) 
#display.show()
#display.poweroff()

def normalize_with_midpoint(value, min_val, mid_val, max_val):
    if value < mid_val:
        norm_value = (value - mid_val) / (mid_val - min_val)
    else:
        norm_value = (value - mid_val) / (max_val - mid_val)
    
    return max(-1, min(norm_value, 1))  # Orezanie do rozsahu -1 až 1


def calculate_iaq(gas, humidity, temperature):    
    # Normalizácia hodnôt s optimálnym bodom (stred = 0)      
    norm_humidity = normalize_with_midpoint(humidity, 30, 45, 60)  # Optimálna vlhkosť 45%
    
    norm_temperature = normalize_with_midpoint(temperature, 18, 23, 28)  # Optimálna teplota 23°C
    
    # Absolútne odchýlky od optimálnych hodnôt (čím bližšie k 0, tým lepšie)    
    abs_humidity = abs(norm_humidity)
    abs_temperature = abs(norm_temperature)
    
    # Výpočet IAQ indexu s váhami (čím väčšia odchýlka, tým horší index)
    iaq = (0.5 * gas) + (0.25 * abs_humidity) + (0.25 * abs_temperature)
    iaq_index = iaq * 500  # Škálovanie na rozsah 0 - 500
    
    return iaq_index

def gasAlogorithm():
    global bme
    global temperature, pressure, humidity, gas, iaq
    global measureCount
    global min_gas, max_gas
    
    temperature = bme.temperature
    measured_gas = bme.gas
    pressure = bme.pressure
    humidity = bme.humidity
    
    measureCount += 1
    
    if measureCount > 3:
        if measured_gas > max_gas:
            max_gas = measured_gas
        elif measured_gas < min_gas:
            min_gas = measured_gas          
        gas = ((measured_gas-min_gas)/(max_gas-min_gas))        
    
    if measureCount > 5:        
        iaq = calculate_iaq(1-gas, humidity, temperature)
    
def offLed():
    global red_led, green_led, blue_led
    red_led.duty_u16(0)
    green_led.duty_u16(0)
    blue_led.duty_u16(0)


def indicateOnLed(iaq):    
    global red_led, green_led, blue_led
    offLed()
    
    if iaq < 100:
        green_led.duty_u16(2**14)
    elif iaq < 200:
        red_led.duty_u16(2**15)
        green_led.duty_u16(2**12)
    elif iaq < 300:
        red_led.duty_u16(2**15)
        green_led.duty_u16(2**10)
    else:
        red_led.duty_u16(2**15)          


def move(pin):
    sleep_ms(10)
    if not pin.value(): return
    
    global displayOn
    displayOn = True
    
def changeDisplayMode(t):
    
    global displayState, displayChanged, measureCount
    
    if displayState == 3 and measureCount < 5:
        offLed()
        displayState = 1
        shutDownDisplay()    
    elif displayState < 4:
        displayState += 1
        displayChanged = True
    else:
        offLed()
        displayState = 1
        shutDownDisplay()
    
        
def printOnDisplay():
    global displayState, display
    global temperature, pressure, humidity, gas
    
    display.fill(0)
    if displayState == 1:
        display.text("Teplota", 0, 0, 1)
        display.text("{:.2f}".format(temperature)+"'C", 0, 25, 1)        
        display.show()
    elif displayState == 2:
        display.text("Vlchkost", 0, 0, 1)
        display.text("{:.2f}".format(humidity)+"%", 0, 25, 1)
        display.show()    
    elif displayState == 3:
        display.text("Tlak", 0, 0, 1)
        display.text("{:.0f}".format(pressure)+"hPa", 0, 25, 1)
        display.show()
    elif displayState == 4:
        display.text("VOC", 0, 0, 1)
        display.text("{:.2f}".format(100-(gas*100))+"%", 0, 25, 1)
        display.show()
        

def shutDownDisplay():
    global displayOn, timerStarted, timer, display
    displayOn = False
    timerStarted = False
    timer.deinit()
    display.poweroff()    


pir = Pin(0, Pin.IN)
pir.irq(handler = move, trigger = Pin.IRQ_RISING)
move(pir)
timer = Timer(-1)
    
startTick = ticks_ms()

while True:    
    if ticks_diff(ticks_ms(), startTick) > 60000:
        startTick = ticks_ms()
        gasAlogorithm()  
            
    if displayOn:
        if not timerStarted:           
            if measureCount > 5:
                if measureCount > 15 and iaq > 400:
                    warning()
                indicateOnLed(iaq)
            display.poweron()
            timer.init(callback = changeDisplayMode, period = 5000)
            timerStarted = True
            displayChanged = True
        if displayChanged:            
            printOnDisplay()
            displayChanged = False
        
    if not timerStarted:
        sleep_ms(100)
