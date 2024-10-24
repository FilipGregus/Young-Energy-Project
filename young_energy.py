#
# This code was made by: Filip Greguš, Andreas Nosál
#
# Project for: Young Energy Europe AHK Slowakei
# Date: 19 october 2024
#
# This code is under: The GNU General Public License v3.0

from machine import Pin, I2C, Timer, PWM, ADC, deepsleep, freq, RTC
import ssd1306, esp32
from bme680 import *
from time import time, ticks_diff, ticks_ms, sleep_ms
import sys
import esp32


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

adc = ADC(Pin(34))
adc.atten(ADC.ATTN_11DB)
adc.width(ADC.WIDTH_12BIT)

displayOn = False
displayState = 1
displayChanged = False
timerStarted = False
measureCount = -1

def move(pin):
    sleep_ms(10)
    if not pin.value(): return
    
    global displayOn
    displayOn = True

pir = Pin(0, Pin.IN)
pir.irq(handler = move, trigger = Pin.IRQ_RISING)
move(pir)

# Lithium battery voltage parameters
MAX_BATTERY_VOLTAGE = 4.1
MIN_BATTERY_VOLTAGE = 2.5
VOLTAGE_DIVIDER_RATIO = 2

freq(80000000);

rtc = RTC()


def offLed():
    global red_led, green_led, blue_led
    red_led.duty_u16(0)
    green_led.duty_u16(0)
    blue_led.duty_u16(0)


def save_to_nvs(measureCount, min_gas, max_gas, timestamp, uptime_run, gas, iaq):
    rtc.memory(f"{measureCount},{min_gas},{max_gas},{timestamp},{uptime_run},{gas},{iaq}")


def load_from_nvs():
    data = rtc.memory()
    print(data)
    if data:
        try:
            measureCount, min_gas, max_gas, timestamp, uptime_run, gas, iaq = map(int, data.decode().split(','))
            return measureCount, min_gas, max_gas, timestamp, uptime_run, gas, iaq
        except:
            return -1, 1_000_000_000, 0, 0, 0, 0, 0  # Default values if parsing fails
    return -1, 1_000_000_000, 0, 0, 0, 0, 0  # Default values if no data found


def read_adc(adc, count=50):
    values = []
    for i in range(count):
        values.append(adc.read_uv())
    
    average = sum(values) / count / 1_000_000

    values.sort()
    median = values[count // 2] / 1_000_000
    
    third_count = count // 3
    average_middle = sum(values[third_count : 2*third_count]) / third_count / 1_000_000
    
    return (average, average_middle, median)

def get_battery_percentage(voltage):
    voltage *= VOLTAGE_DIVIDER_RATIO
    if voltage > MAX_BATTERY_VOLTAGE:
        return 100
    elif voltage < MIN_BATTERY_VOLTAGE:
        return 0
    else:
        return int(((voltage - MIN_BATTERY_VOLTAGE) / (MAX_BATTERY_VOLTAGE - MIN_BATTERY_VOLTAGE)) * 100)

def warning():
    global red_led, buzzer    
    buzzer.init(freq = 2000, duty_u16 = 0)
    offLed()
    
    for duty in (2**15, 0, 2**15, 0):
        red_led.duty_u16(duty)
        buzzer.duty_u16(duty)
        sleep_ms(1000)
    
    if measureCount > 5:
        indicateOnLed(iaq)
        
def getTimeSeconds(rtc):
    current_timestamp = rtc.datetime()
    seconds = current_timestamp[6] + (current_timestamp[5] * 60 + current_timestamp[4] *3600)
    return seconds

if not i2c_ok:
    warning()
    sys.exit()

gas = 0
iaq = 0
min_gas = 1_000_000_000
max_gas = 0

measureCount, min_gas, max_gas, last_logged_time, uptime_run, gas, iaq = load_from_nvs()

uptime_run += getTimeSeconds(rtc) - uptime_run

if not displayOn and uptime_run < 30:
    deepsleep(2500)
    

temperature = bme.temperature
pressure = bme.pressure
humidity = bme.humidity
gas = gas / 100
iaq = iaq / 100

if (getTimeSeconds(rtc) - last_logged_time) > 120:
    measureCount = -1
    min_gas = 1_000_000_000  # Reset the gas calibration values
    max_gas = 0
    uptime_run = 0


def normalize_with_midpoint(value, min_val, mid_val, max_val):
    if value < mid_val:
        norm_value = (value - mid_val) / (mid_val - min_val)
    else:
        norm_value = (value - mid_val) / (max_val - mid_val)
    
    return max(-1, min(norm_value, 1))  # Orezanie do rozsahu -1 až 1


def calculate_iaq(gas, humidity, temperature):    
    norm_humidity = normalize_with_midpoint(humidity, 30, 45, 60)  # Optimálna vlhkosť 45%
    norm_temperature = normalize_with_midpoint(temperature, 18, 23, 28)  # Optimálna teplota 23°C
    
    abs_humidity = abs(norm_humidity)
    abs_temperature = abs(norm_temperature)
    
    iaq = (0.5 * gas) + (0.25 * abs_humidity) + (0.25 * abs_temperature)
    iaq_index = iaq * 500  # Škálovanie na rozsah 0 - 500
    
    return iaq_index

def gasAlogorithm():
    global bme, temperature, pressure, humidity, gas, iaq
    global measureCount, min_gas, max_gas

    temperature = bme.temperature
    measured_gas = bme.gas
    pressure = bme.pressure
    humidity = bme.humidity
    
    print("nameralo sa", measured_gas)

    measureCount += 1

    # Update the min/max gas values
    if measureCount > 3:
        if measured_gas > max_gas:
            max_gas = measured_gas
        elif measured_gas < min_gas:
            min_gas = measured_gas
        gas = ((measured_gas - min_gas) / (max_gas - min_gas))

    # Calculate IAQ if enough measurements have been taken
    if measureCount > 5:
        iaq = calculate_iaq(1 - gas, humidity, temperature)


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
        green_led.duty_u16(2**8)
    else:
        red_led.duty_u16(2**15)          

    
def changeDisplayMode(t):
    
    global displayState, displayChanged, measureCount
    
    if displayState < 5:
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
        battery_voltage = read_adc(adc)[1]
        battery_percentage = get_battery_percentage(battery_voltage)
        display.text("Baterka", 0, 0, 1)
        display.text(f"{battery_percentage}%", 0, 25, 1)
        display.show()

        # Battery low warning
        if battery_percentage <= 10:
            display.text("Pozor", 0, 40, 1)
            display.show()
            warning()
            
    elif displayState == 5:
        if measureCount < 5:
            display.text("Prebieha", 0, 0, 1)
            display.text("priprava", 0, 20, 1)
            display.text(f"{round(150 - uptime_run - (measureCount * 30))}s", 0, 40, 1)
            display.show()
        else:
            display.text("VOC", 0, 0, 1)
            display.text("{:.2f}".format(100 *(iaq / 500))+"%", 0, 25, 1)
            display.text("{:.1f}".format(round(iaq))+"ppm", 0, 40, 1)
            display.show()
        

def shutDownDisplay():
    global displayOn, timerStarted, timer, display
    displayOn = False
    timerStarted = False
    timer.deinit()
    display.poweroff()    


timer = Timer(-1)

while True:
    start = getTimeSeconds(rtc)
    
    if uptime_run >= 30:
        uptime_run = uptime_run % 30
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
        uptime_run += getTimeSeconds(rtc) - start
        
        save_to_nvs(measureCount, min_gas, max_gas, getTimeSeconds(rtc), uptime_run +
                    (start - last_logged_time), int(gas * 100), int(iaq * 100))
        deepsleep(2500)
