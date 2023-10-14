import os
import sys, getopt
import signal
import time
from edge_impulse_linux.runner import ImpulseRunner
import io
import time
import board
import busio
import adafruit_adxl34x
import os
import pandas as pd
import numpy as np

import time
import board
import busio
import adafruit_adxl34x
import os
import pandas as pd
import sys
import RPi.GPIO as GPIO
import threading

from akida import devices

runner = None

num_of_samples = 0
data = []
previous_time = 0
accumulated_time = 0
number_of_files = 0
accel0 = []
accel1 = []
accel2 = []
features = []


adafruit_adxl34x.DataRate.RATE_3200_HZ
adafruit_adxl34x.Range.RANGE_16_G
i2c = busio.I2C(board.SCL, board.SDA)
accelerometer = adafruit_adxl34x.ADXL345(i2c)


GPIO.setmode(GPIO.BCM)
GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.setup(18, GPIO.OUT)
p = GPIO.PWM(18, 100)

def akida_model_inference(model, processed_features):

    scaling_factor = 15 / np.max(processed_features)
    # Convert to uint8
    processed_features_uint8 = np.uint8(processed_features * scaling_factor)

    # Reshape to model input shape
    input_shape = (1,) + tuple(model.input_shape)  # Assuming model.input_shape returns (39,)
    inputs = processed_features_uint8.reshape(input_shape)

    # Perform inference
    device = devices()[0]
    model.map(device)
    # model.summary()
    results = model.predict(inputs)
    return results

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

        data.append(accel[0])
        data.append(accel[1])
        data.append(accel[2])

        num_of_samples = num_of_samples + 1
    
    if num_of_samples == 100:
        done_collecting.set()
        num_of_samples = 0


def signal_handler(sig, frame):
    print('Interrupted')
    p.stop()
    GPIO.cleanup()

    if (runner):
        runner.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def help():
    print('python3 claa-hw-time.py <path-to-akida-model.fbz>')

def main(argv):
    try:
        opts, args = getopt.getopt(argv, "h", ["--help"])
    except getopt.GetoptError:
        help()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            help()
            sys.exit()

    if len(args) != 1:
        print(len(args))
        help()
        sys.exit(2)

    model = args[0]

    p.start(50)
    #wait for data collection to finish
    done_collecting.wait()
    p.stop()
    done_collecting.clear()

    features = data

    print(len(features))

    print(features)

    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)

    print('MODEL: ' + modelfile)

    #add pythong dsp code
    processed_features = np.array([0.1467, 0.2941, 1.3105, 2.0280, 2.8643, 1.5801, 1.5660, 1.4363, 1.3001, 1.1117, 1.1817, 1.2346, 0.6545, 0.0479, 0.5384, 0.6327, 1.4070, 0.5814, 2.4727, 2.2234, 2.1496, 2.2316, 1.7698, 2.1855, 2.2644, 1.6087, 0.0852, 0.3664, 0.4464, 1.1865, 0.8909, 2.2625, 1.9151, 1.8818, 1.6190, 1.6399, 1.7571, 1.6380, 1.3321])
    akida_model = akida.Model(modelfile)

    predictions = akida_model_inference(akida_model, processed_features)

if __name__ == '__main__':

    done_collecting = threading.Event()
    done_collecting.clear()

    GPIO.add_event_detect(16, GPIO.RISING, 
        callback=data_acq_callback, bouncetime=10)

    main(sys.argv[1:])
