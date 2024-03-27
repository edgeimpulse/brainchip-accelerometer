'''
acquires a fix number of accelerometer samples and stores them to csv files on disk
need to have the adxl34x acceleromter connected
need to have the pwm connecto the the gpio as described in code
'''


import time
import board
import busio
import adafruit_adxl34x
import os
import pandas as pd
import sys
import RPi.GPIO as GPIO
import threading
import argparse

num_of_samples = 0
data = []
previous_time = 0
accumulated_time = 0

adafruit_adxl34x.DataRate.RATE_3200_HZ
i2c = busio.I2C(board.SCL, board.SDA)
accelerometer = adafruit_adxl34x.ADXL345(i2c)

GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(18, GPIO.OUT)
p = GPIO.PWM(18, 100)

def data_acq_callback(channel):
    global num_of_samples
    global data
    global previous_time
    global accumulated_time

    if done_collecting.is_set() == False:
        accel = accelerometer.acceleration
        if num_of_samples == 0:
            ts = 0
            accumulated_time = ts
            previous_time = 0
        else:
            current_time = previous_time + 10
            ts = (current_time - previous_time)
            accumulated_time = accumulated_time + ts
            previous_time = current_time 

        data_dict = {'timestamp':accumulated_time, 'accX':accel[0], 'accY':accel[1], 'accZ':accel[2]}
        data.append(data_dict)

        num_of_samples = num_of_samples + 1
    
    if num_of_samples == 100:
        done_collecting.set()
        num_of_samples = 0

def help():
    print('python3 accel-hw-timed-fixed-dt.py <folder-name>')

def main(argv):
    global data

    parser = argparse.ArgumentParser(description='acquire accel data to csv file')
    parser.add_argument('output_dir', type=str,
                        help='The dir to output the accel data to')

    args = parser.parse_args()

    #create a folder if it doesn't exist
    #if the folder exists error out
    os.makedirs(args.output_dir)
    os.chdir(args.output_dir)

    number_of_files = 0

    while number_of_files != 300:   
        p.start(50)
        #wait for data collection to finish
        done_collecting.wait()
        p.stop()
        done_collecting.clear()

        #write to a file
        i = 0
        while os.path.exists(args.output_dir + "-" + str(i) + ".csv"):
            i = i + 1

        with open(args.output_dir + "-" + str(i) + ".csv", "w") as f:
            df = pd.DataFrame(data)
            df.to_csv(f, index=False, header=True)
            f.write("\n")
 
        data = []       
        number_of_files = number_of_files + 1

    p.stop()

if __name__ == '__main__':
    done_collecting = threading.Event()
    done_collecting.clear()

    GPIO.add_event_detect(16, GPIO.RISING, 
        callback=data_acq_callback, bouncetime=10)

    #send args to main function
    main(sys.argv[1:])
    GPIO.cleanup()
    sys.exit(0)    
