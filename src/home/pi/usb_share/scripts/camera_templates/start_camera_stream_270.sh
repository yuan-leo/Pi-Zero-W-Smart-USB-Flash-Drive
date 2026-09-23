#!/bin/bash

/usr/local/bin/mjpg_streamer -o "output_http.so -l 127.0.0.1 -p 8080 -n" -i "input_raspicam.so -x 320 -y 240 -fps 5 -rot 270"&
