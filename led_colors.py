from bme680 import *
from machine import I2C, Pin, PWM
from time import sleep

red_led = PWM(Pin(27), freq=2000, duty_u16=0)
green_led =PWM(Pin(25), freq=2000, duty_u16=2**14)
blue_led = Pin(32, Pin.OUT)

sleep(5)

red_led = PWM(Pin(27), freq=2000, duty_u16=0)
green_led =PWM(Pin(25), freq=2000, duty_u16=0)

def red():
    global red_led
    red_led.duty_u16(2**15)
    
def orange():
    red_led = PWM(Pin(27), freq=2000, duty_u16=2**15)
    green_led =PWM(Pin(25), freq=2000, duty_u16=2**10)
    
def yellow():
    red_led = PWM(Pin(27), freq=2000, duty_u16=2**15)
    green_led =PWM(Pin(25), freq=2000, duty_u16=2**12)
    
def green():
    green_led =PWM(Pin(25), freq=2000, duty_u16=2**14)
    

    
