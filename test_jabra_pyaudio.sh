#!/bin/bash
# Test if PyAudio can record from Jabra via PulseAudio

cd /home/ljung/yelp
source venv/bin/activate

python3 test_jabra_pyaudio.py
