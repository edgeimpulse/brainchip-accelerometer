import os
import sys, getopt
import signal
import time
import io

#for i2c, gpio, pwms
import board
import busio
import adafruit_adxl34x
import os
import pandas as pd
import numpy as np
import RPi.GPIO as GPIO
import threading

#for model running
import akida
import scipy

#for dsp code
from spectral_analysis import generate_features
import numpy as np


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

# takes in raw features from the accel in format [x,y,z,x,y,z,etc]
def dsp(features):

    processed_features = []

    # Parameters for generate_features

    ## The first section are parameters that apply for any DSP block
    # Version of the implementation.  If you want the latest, look into parameters.json, and use the value of latestImplementationVersion
    implementation_version = 4 # 4 is latest versions
    draw_graphs = False # For testing from script, disable graphing to improve speed

    # This is where you want to paste in your test sample.  This can be taken from studio
    #  For example, the below sample is from https://studio.edgeimpulse.com/public/223682/latest/classification#load-sample-269491318
    #  It was copied by clicking on the copy icon next to "Raw features"
    #  It is 3 axis accelerometer data, with 62.5Hz sampling frequency
    #  Data should be formatted as a single flat list, regardless of the number of axes/channels
    raw_data = np.array(features)

    axes = ['x', 'y', 'z'] # Axes names.  Can be any labels, but the length naturally must match the number of channels in raw data
    sampling_freq = 100 # Sampling frequency of the data.  Ignored for images

    # Below here are parameters that are specific to the spectral analysis DSP block. These are set to the defaults
    scale_axes = 1 # Scale your data if desired
    input_decimation_ratio = 1 # Decimation ratio.  See /spectral_analysis/paramters.json:31 for valid ratios
    filter_type = 'none' # Filter type.  String : low, high, or none
    filter_cutoff = 0 # Cutoff frequency if filtering is chosen.  Ignored if filter_type is 'none'
    filter_order = 0 # Filter order.  Ignored if filter_type is 'none'.  2, 4, 6, or 8 is valid otherwise
    analysis_type = 'FFT' # Analysis type.  String : FFT, wavelet

    # The following parameters only apply to FFT analysis type.  Even if you choose wavelet analysis, these parameters still need dummy values
    fft_length = 16 # Size of FFT to perform.  Should be power of 2 >-= 16 and <= 4096

    # Deprecated parameters.  Only applies to version 1, maintained for backwards compatibility
    spectral_peaks_count = 0 # Deprecated parameter.  Only applies to version 1, maintained for backwards compatibility
    spectral_peaks_threshold = 0 # Deprecated parameter.  Only applies to version 1, maintained for backwards compatibility
    spectral_power_edges = "0" # Deprecated parameter.  Only applies to version 1, maintained for backwards compatibility

    # Current FFT parameters
    do_log = True # Take the log of the spectral powers from the FFT frames
    do_fft_overlap = True # Overlap FFT frames by 50%.  If false, no overlap
    extra_low_freq = False # This will decimate the input window by 10 and perform another FFT on the decimated window.
                        # This is useful to extract low frequency data.  The features will be appended to the normal FFT features

    # These parameters only apply to Wavelet analysis type.  Even if you choose FFT analysis, these parameters still need dummy values
    wavelet_level = 1 # Level of wavelet decomposition
    wavelet = "" # Wavelet kernel to use


    output = generate_features(implementation_version, draw_graphs, raw_data, axes, sampling_freq, scale_axes, input_decimation_ratio,
                        filter_type, filter_cutoff, filter_order, analysis_type, fft_length, spectral_peaks_count,
                        spectral_peaks_threshold, spectral_power_edges, do_log, do_fft_overlap,
                        wavelet_level, wavelet, extra_low_freq)

    # Return dictionary, as defined in code
        # return {
        #     'features': List of output features
        #     'graphs': Dictionary of graphs
        #     'labels': Names of the features
        #     'fft_used': Array showing which FFT sizes were used.  Helpful for optimzing embedded DSP code
        #     'output_config': information useful for correctly configuring the learn block in Studio
        # }

    print(f'Processed features are: ')
    #print('Feature name, value')
    idx = 0
    for axis in axes:
        #print(f'\nFeatures for axis: {axis}')
        for label in output['labels']:
            #print(f'{label: <40}: {output["features"][idx]}')
            processed_features.append(output["features"][idx])
    

    print(processed_features)
    print(type(processed_features))
    
    processed_features_np = np.array(processed_features)
    print(type(processed_features_np))

    return processed_features


def akida_model_inference(model, processed_features):

    scaling_factor = 15 / np.max(processed_features)
    # Convert to uint8
    processed_features_uint8 = np.uint8(processed_features * scaling_factor)

    # Reshape to model input shape
    input_shape = (1,) + tuple(model.input_shape)  # Assuming model.input_shape returns (39,)
    inputs = processed_features_uint8.reshape(input_shape)

    # Perform inference
    device = akida.devices()[0]
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
    dir_path = os.path.dirname(os.path.realpath(__file__))
    modelfile = os.path.join(dir_path, model)
    #print('MODEL: ' + modelfile)

    #start pws
    p.start(50)
    #wait for data collection to finish
    done_collecting.wait()
    p.stop()
    done_collecting.clear()

    features = data
    #print(len(features))
    #print(features)

    #run the dsp
    processed_features = dsp(features)

    #run the model on akida
    akida_model = akida.Model(modelfile)
    predictions = akida_model_inference(akida_model, processed_features)

    print(predictions)
    print("softmaxed:", scipy.special.softmax(predictions))

if __name__ == '__main__':

    #startup the thread
    done_collecting = threading.Event()
    done_collecting.clear()

    #set the gpio pin input to trigger an interrupt
    GPIO.add_event_detect(16, GPIO.RISING, 
        callback=data_acq_callback, bouncetime=10)

    #send args to main function
    main(sys.argv[1:])
