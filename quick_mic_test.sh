#!/bin/bash
# Quick microphone level test

echo "=== Quick Microphone Test ==="
echo ""

# Check if yelp is running
YELP_RUNNING=$(ps aux | grep python | grep yelp_complete.py | grep -v grep)
if [ -n "$YELP_RUNNING" ]; then
    echo "⚠ Warning: yelp_complete.py is currently running!"
    echo "Stop it first: pkill -f yelp_complete.py"
    echo ""
fi

echo "Recording 3 seconds... SPEAK NOW!"
arecord -D hw:1,0 -f S16_LE -r 48000 -c 2 -d 3 /tmp/quick_test.wav 2>/dev/null

echo ""
echo "Analyzing audio level..."
python3 << 'EOF'
import wave
import numpy as np

try:
    with wave.open('/tmp/quick_test.wav', 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        audio_np = np.frombuffer(frames, dtype=np.int16)

        if wf.getnchannels() == 2:
            audio_np = audio_np.reshape(-1, 2).mean(axis=1)

        rms = np.sqrt(np.mean(audio_np**2))
        normalized_rms = rms / 32768.0

        print(f"Current audio level: {normalized_rms:.4f}")
        print(f"Threshold in script: 0.004")
        print("")

        if normalized_rms > 0.004:
            print(f"✓ ABOVE threshold - should be detected")
        else:
            print(f"✗ BELOW threshold - will NOT be detected")
            print(f"  Need to speak louder or lower threshold to: {normalized_rms * 1.5:.4f}")
except Exception as e:
    print(f"Error: {e}")
EOF

echo ""
echo "Playing back your recording..."
aplay /tmp/quick_test.wav 2>/dev/null

rm /tmp/quick_test.wav
