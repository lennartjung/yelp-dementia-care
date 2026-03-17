#!/usr/bin/env python3
import pyaudio
import numpy as np

p = pyaudio.PyAudio()
stream = p.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    input_device_index=14,
    frames_per_buffer=1024
)

print("Recording for 3 seconds - SPEAK NOW!")
frames = []
for i in range(0, int(16000 / 1024 * 3)):
    data = stream.read(1024)
    frames.append(data)

stream.close()
p.terminate()

audio = np.frombuffer(b''.join(frames), dtype=np.int16)
rms = np.sqrt(np.mean(audio**2))
normalized = rms / 32768.0
print(f"\nLevel: {normalized:.6f}")
print(f"Threshold: 0.004")
if normalized > 0.004:
    print("✓ Above threshold - should work")
else:
    print(f"✗ Too low - suggest threshold: {max(0.001, normalized * 1.5):.6f}")
