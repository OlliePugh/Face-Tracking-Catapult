import pigpio
import time
from threading import Thread
import numpy as np
import cv2
from picamera import PiCamera
from picamera.array import PiRGBArray

def get_center(x,y,w,h):
    x_center = x+(w/2)
    y_center = y+(h/2)
    return (x_center, y_center)

def get_distance(width):
    width_at_1m = 50
    return 2
    return width_at_1m/width  # returns the distance in meters

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)

class Catapult(pigpio.pi):
    def __init__(self, x_pin, height_pin, fire_pin, loaded_pos = 1900, max_height_freq=1150 ,x_offset=0, x_damp=1, x_invert=False, fire_invert=False):
        super().__init__()  # instantiate the pi object
        self.x_pin = x_pin
        self.height_pin = height_pin
        self.fire_pin = fire_pin

        self.x_pos = 0  # center the turret (-1 - > 1)
        self.x_offset = x_offset
        self.x_damp = x_damp
        self.x_invert = x_invert

        self.height = 0  # 0 being closest to the pivot 1 being the furthers away
        self.max_height_freq = max_height_freq

        self.tracking = True

        self.firing = False
        self.firing_enabled = False
        self.loaded_pos = loaded_pos

        self.fire_invert = fire_invert

        self.set_mode(x_pin, pigpio.OUTPUT)
        self.set_mode(height_pin, pigpio.OUTPUT)
        self.set_mode(fire_pin, pigpio.OUTPUT)

        self.set_servo_pulsewidth(self.height_pin, 1000)  # set the position of the servo
        self.set_servo_pulsewidth(self.fire_pin, loaded_pos)  # set the position of the servo

        self.thread_exit = False  # flag to stop the thread

        self.thread = Thread(target=self.position_management, daemon=True)  # create the thread
        self.thread.start()  # start the thread

        print("Starting Position Thread")

    def position_management(self):  # a function to move the table to the target pos
        while not self.thread_exit: # while the thread is not exiting

            modded_x_pos = self.x_pos + self.x_offset  # get the raw x position and apply the offset

            modded_x_pos = clamp(modded_x_pos, -1, 1)  # ensure thats it within the acceptable range after applying the offset

            modded_x_pos *= self.x_damp  # apply the dampening

            if self.x_invert:
                modded_x_pos *= -1

            x_freq = ((((modded_x_pos)+1)/2)*1000)+1000
            y_freq = (self.height*self.max_height_freq) + 1000
            self.set_servo_pulsewidth(self.x_pin, x_freq)  # set the position of the servo
            self.set_servo_pulsewidth(self.height_pin, y_freq)  # set the position of the servo

            if self.firing_enabled:
                if not self.firing:
                    self.set_servo_pulsewidth(self.fire_pin, 1000)  # set the position of the servo
                else:
                    self.fire()
            else:
                self.set_servo_pulsewidth(self.fire_pin, self.loaded_pos)  # set the position of the servo

            time.sleep(0.02)  # wait the 20ms analog frequency

    def set_pos(self, x_pos):
        if x_pos > 1 or x_pos < -1:
            print(pos, "is not a valid value (-1->1)")
            return

        self.x_pos = x_pos

    def stop(self):
        self.thread_exit = True  # stop the thread that moves the servo
        super().stop()

    def fire(self):
        self.firing = False
        self.set_servo_pulsewidth(self.fire_pin, self.loaded_pos)  # set the position of the servo
        time.sleep(0.5)
        print("no firing procedure created yet")

#if __name__ == "__main__":
    #my_turret = Catapult(17,12)
    #while True:
        #my_turret.x_pos = -1
