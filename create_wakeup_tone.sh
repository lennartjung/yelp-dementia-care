#!/bin/bash
# Create a gentle wake-up tone for the speaker (very quiet)

echo "Creating speaker wake-up file..."

# Generate a very quiet 100Hz tone for 0.3 seconds, then silence for 1.7 seconds
# Total: 2 seconds with guaranteed speaker activation
ffmpeg -f lavfi -i "sine=frequency=100:duration=0.3" -af "volume=0.05" -ar 16000 -ac 2 /home/ljung/yelp/wakeup.wav -y
ffmpeg -f lavfi -i anullsrc=r=16000:cl=stereo -t 1.7 /home/ljung/yelp/silence_short.wav -y

# Concatenate: wakeup tone + silence
ffmpeg -i /home/ljung/yelp/wakeup.wav -i /home/ljung/yelp/silence_short.wav -filter_complex '[0:a][1:a]concat=n=2:v=0:a=1' -y /home/ljung/yelp/speaker_init.wav

# Cleanup temp files
rm /home/ljung/yelp/wakeup.wav /home/ljung/yelp/silence_short.wav

echo "Created /home/ljung/yelp/speaker_init.wav"
