import numpy as np
import pyaudio
import wave

SAMPLE_RATE = 44100
CHANNELS = 1
FORMAT = pyaudio.paFloat32

def generate_sine_wave(frequency, duration, amplitude=1.0):
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    return amplitude * np.sin(2 * np.pi * frequency * t)

def normalize_value(value, min_val, max_val):
    return (value - min_val) / (max_val - min_val)

def map_to_frequency(normalized_value, min_freq, max_freq):
    return min_freq + normalized_value * (max_freq - min_freq)

class AudioPlayer:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=SAMPLE_RATE,
                                  output=True)

    def play(self, audio_data):
        self.stream.write(audio_data.astype(np.float32).tobytes())

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

def save_audio(filename, audio_data):
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.astype(np.float32).tobytes())