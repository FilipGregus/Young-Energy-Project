from machine import Pin, I2C, sleep, Timer, PWM
import ssd1306
from bme680 import *




red_led =PWM( Pin(27), freq=2000, duty_u16 = 0)
green_led =PWM( Pin(25), freq=2000, duty_u16 = 0)
blue_led =PWM( Pin(32), freq=2000, duty_u16 = 0)

# using default address 0x3C
i2c = I2C(-1, Pin(22), Pin(21))
display = ssd1306.SSD1306_I2C(64, 48, i2c)

bme = BME680_I2C(i2c)

displayOn = False
displayState = 1
displayChanged = False

timerStarted = False

#display.line(0, 0, 63, 47, 1) 
#display.show()
#display.poweroff() 



def move(pin):
    sleep(10)
    if not pin.value(): return
    
    global displayOn
    displayOn = True
    
def changeDisplayMode(t):
    
    global displayState, displayChanged
    
    if displayState < 4:
        displayState += 1
        displayChanged = True
    else:
        displayState = 1
        shutDownDisplay()
    
        
def printOnDisplay(bmeVals):
    global displayState, display
    
    display.fill(0)
    if displayState == 1:
        display.text("{:.2f}".format(bmeVals.temperature)+"°C", 0, 0, 1)
        display.show()
    elif displayState == 2:
        display.text("{:.2f}".format(bmeVals.humidity)+"%", 0, 0, 1)
        display.show()
    elif displayState == 3:
        display.text("{}".format(bmeVals.gas), 0, 0, 1)
        display.show()
    elif displayState == 4:
        display.text("{:.1f}".format(bmeVals.pressure)+"hPa", 0, 0, 1)
        display.show()            
        

def shutDownDisplay():
    global displayOn, timerStarted, timer, display
    displayOn = False
    timerStarted = False
    timer.deinit()
    display.poweroff()
    
def normalize(value, min_val, max_val):
    return (value - min_val) / (max_val - min_val)

def calculate_iaq(norm_gas, norm_humidity, norm_temperature):      
    norm_gas = normalize(norm_gas, 500, 50000)
    norm_humidity = normalize(norm_humidity, 30, 60)  # Optimálne hodnoty vlhkosti
    norm_temperature = normalize(norm_temperature, 18, 28)
    
    iaq = (0.5 * norm_gas) + (0.25 * norm_humidity) + (0.25 * norm_temperature)
    iaq_index = iaq * 500
    return iaq_index
    

def indicateOnLed(vals):    
    print(calculate_iaq(vals.gas, vals.humidity, vals.temperature))
    
    #rozdelnie na stupne
    
def turnOffLed():
    global red_led, green_led, blue_led
    
    red_led.duty_u16(0)
    green_led.duty_u16(0)
    blue_led.duty_u16(0)


pir = Pin(0, Pin.IN)
pir.irq(handler = move, trigger = Pin.IRQ_RISING)
move(pir)
timer = Timer(-1)
    

while True:
    bmeVals = bme    
  
    if displayOn:
        indicateOnLed(bmeVals)
        if not timerStarted:
            print("a")
            display.poweron()
            timer.init(callback = changeDisplayMode, period = 5000)
            timerStarted = True
            displayChanged = True
        if displayChanged:            
            printOnDisplay(bmeVals)
            displayChanged = False            
    else:
        turnOffLed()
        
    if not timerStarted:
        sleep(10)
    