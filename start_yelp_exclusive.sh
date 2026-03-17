#!/bin/bash
# Start yelp with exclusive microphone access and audio tests

echo "=== Starting Yelp with Exclusive Microphone Access ==="
echo ""

# 1. Kill any existing yelp processes
echo "1. Stopping any running yelp processes..."
pkill -9 -f yelp_complete.py 2>/dev/null
sleep 1

# 2. Check if anything else is using the H2n microphone
echo "2. Checking for other processes using H2n..."
MIC_USERS=$(lsof /dev/snd/pcmC1D0c 2>/dev/null | grep -v "COMMAND" | wc -l)

if [ "$MIC_USERS" -gt 0 ]; then
    echo "⚠ Warning: Other processes are using the H2n microphone:"
    lsof /dev/snd/pcmC1D0c 2>/dev/null
    echo ""
    echo "Kill them? (y/n)"
    read -r answer
    if [ "$answer" = "y" ]; then
        lsof -t /dev/snd/pcmC1D0c 2>/dev/null | xargs kill -9 2>/dev/null
        echo "Processes killed."
        sleep 1
    fi
fi

# 3. Test audio output (speaker)
echo ""
echo "3. Testing audio output..."
echo "Unmuting and setting volume to 100%..."
amixer set Master 100% unmute >/dev/null 2>&1
amixer set PCM 100% unmute >/dev/null 2>&1

echo "Checking audio output..."
# Just verify volume is unmuted, no sound test

MASTER_VOL=$(amixer get Master | grep -o '\[on\]' | head -1)
if [ "$MASTER_VOL" = "[on]" ]; then
    echo "✓ Audio output is unmuted and ready"
else
    echo "✗ Warning: Master volume might be muted"
fi

# 4. Test microphone input
echo ""
echo "4. Testing microphone input..."
echo "Recording 3 seconds - SPEAK NOW (say 'hallo')..."
arecord -D hw:1,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/startup_test.wav 2>/dev/null

# Analyze audio level
cd /home/ljung/yelp
source venv/bin/activate

AUDIO_LEVEL=$(python3 << 'EOF'
import wave
import numpy as np
try:
    with wave.open('/tmp/startup_test.wav', 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        audio_np = np.frombuffer(frames, dtype=np.int16)
        if wf.getnchannels() == 2:
            audio_np = audio_np.reshape(-1, 2).mean(axis=1)
        rms = np.sqrt(np.mean(audio_np**2))
        normalized_rms = rms / 32768.0
        print(f"{normalized_rms:.4f}")
except:
    print("0.0000")
EOF
)

echo "Microphone level: $AUDIO_LEVEL (threshold: 0.0005)"

if (( $(echo "$AUDIO_LEVEL > 0.0005" | bc -l) )); then
    echo "✓ Microphone input is working"
else
    echo "⚠ Warning: Microphone level is low - speak louder or adjust threshold"
fi

rm /tmp/startup_test.wav 2>/dev/null

# 5. Start yelp
echo ""
echo "5. Starting yelp..."
echo "Press Ctrl+C to stop"
echo "========================================"
echo ""
python yelp_complete.py

# When script exits (Ctrl+C), clean up
echo ""
echo "Cleaning up..."
pkill -9 -f yelp_complete.py 2>/dev/null
