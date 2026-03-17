#!/bin/bash
# Create a static 1 second silence file

echo "Creating 1 second silence file (stereo for Jabra)..."

# Create 1 second of silence at 16000 Hz stereo (for Jabra Speak2 55 output)
ffmpeg -f lavfi -i anullsrc=r=16000:cl=stereo -t 1.0 -c:a pcm_s16le /home/ljung/yelp/silence_1s.wav -y

echo "Done! Created /home/ljung/yelp/silence_1s.wav"
ls -lh /home/ljung/yelp/silence_1s.wav
