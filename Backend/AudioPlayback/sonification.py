import sys
import os
import time
import logging
from datetime import datetime
import numpy as np
import pyaudio
import wave

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add necessary paths
try:
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    market_path = os.path.join(backend_path, 'Market')
    sys.path.extend([backend_path, market_path])
    from Market.MarketDataDisplayScript_Optimized import main_ohlcv
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Audio constants
SAMPLE_RATE = 44100
CHANNELS = 1
FORMAT = pyaudio.paFloat32
MIN_FREQ = 220  # A3
MAX_FREQ = 880  # A5
BEAT_DURATION = 0.125  # 125ms (sixteenth note at 120 BPM)
BEAT_PATTERN = [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0]  # Mozart-inspired

class AudioPlayer:
    """Handles real-time audio playback and recording."""

    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=SAMPLE_RATE,
                                  output=True)

    def play(self, audio_data):
        """Play audio data in real-time."""
        try:
            self.stream.write(audio_data.astype(np.float32).tobytes())
        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    def close(self):
        """Close the audio stream and terminate PyAudio."""
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

def generate_sine_wave(frequency, duration, amplitude=1.0):
    """Generate a sine wave of given frequency, duration, and amplitude."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    return amplitude * np.sin(2 * np.pi * frequency * t)

def normalize_value(value, min_val, max_val):
    """Normalize a value to the range [0, 1]."""
    return (value - min_val) / (max_val - min_val) if max_val > min_val else 0

def map_to_frequency(normalized_value, min_freq, max_freq):
    """Map a normalized value to a frequency range."""
    return min_freq + normalized_value * (max_freq - min_freq)

def sonify_data(data, beat_index):
    """Convert market data to audio based on sonification rules."""
    try:
        # Price change to frequency (Chapter 2: Polarity)
        price_change = (data['close'] - data['open']) / data['open'] if data['open'] != 0 else 0
        norm_price_change = normalize_value(price_change, -0.05, 0.05)  # Assume max 5% change
        frequency = map_to_frequency(norm_price_change, MIN_FREQ, MAX_FREQ)

        # Volume to amplitude (Chapter 15: Scaling)
        norm_volume = normalize_value(data['volume'], 0, data['volume'] * 2)  # Dynamic scaling
        amplitude = norm_volume * 0.5 + 0.5  # Ensure some minimal amplitude

        # Generate base sine wave
        audio = generate_sine_wave(frequency, BEAT_DURATION, amplitude)

        # Apply beat pattern (Chapter 13: Auditory Icons and Earcons)
        audio *= BEAT_PATTERN[beat_index]

        # Add harmonics based on RSI (Chapter 3: Stream-based Sonification)
        if data['rsi'] is not None:
            if data['rsi'] > 70 or data['rsi'] < 30:
                harmonic = generate_sine_wave(frequency * 2, BEAT_DURATION, amplitude * 0.3)
                audio += harmonic
            if data['rsi'] > 80 or data['rsi'] < 20:
                harmonic = generate_sine_wave(frequency * 3, BEAT_DURATION, amplitude * 0.2)
                audio += harmonic

        return audio
    except Exception as e:
        logger.error(f"Error in sonify_data: {e}")
        return np.zeros(int(SAMPLE_RATE * BEAT_DURATION))

def save_audio(filename, audio_data):
    """Save audio data to a WAV file."""
    try:
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_data.astype(np.float32).tobytes())
        logger.info(f"Audio saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving audio: {e}")

def format_value(value):
    """Format a value for logging, handling None values."""
    return f"{value:.2f}" if value is not None else "N/A"

def main():
    """Main function to run the sonification process."""
    audio_player = AudioPlayer()
    beat_index = 0
    start_time = None
    all_audio_data = np.array([])

    try:
        for data in main_ohlcv():
            if start_time is None:
                start_time = datetime.fromtimestamp(data['timestamp'] / 1e9)
            
            current_time = datetime.fromtimestamp(data['timestamp'] / 1e9)
            elapsed_time = current_time - start_time
            
            # Simulate real-time playback
            time.sleep(max(0, elapsed_time.total_seconds() - (datetime.now() - start_time).total_seconds()))

            audio_data = sonify_data(data, beat_index)
            audio_player.play(audio_data)
            all_audio_data = np.concatenate((all_audio_data, audio_data))

            beat_index = (beat_index + 1) % len(BEAT_PATTERN)

            # Log market data and indicators
            logger.info(f"Timestamp: {current_time}, Close: {format_value(data['close'])}, Volume: {data['volume']}")
            logger.info(f"EMA9: {format_value(data['ema_9'])}, EMA26: {format_value(data['ema_26'])}, EMA52: {format_value(data['ema_52'])}")
            logger.info(f"RSI: {format_value(data['rsi'])}, ATR: {format_value(data['atr'])}")
            logger.info("Ichimoku Cloud:")
            logger.info(f"  Base Line: {format_value(data['ichimoku_base_line'])}")
            logger.info(f"  Conversion Line: {format_value(data['ichimoku_conversion_line'])}")
            logger.info(f"  Lagging Line: {format_value(data['ichimoku_lagging_line'])}")
            logger.info(f"  Leading Fast Line: {format_value(data['ichimoku_cloud_leading_fast_line'])}")
            logger.info(f"  Leading Slow Line: {format_value(data['ichimoku_cloud_leading_slow_line'])}")
            logger.info("-" * 50)

    except KeyboardInterrupt:
        logger.info("Stopping playback...")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        audio_player.close()
        save_audio("market_sonification.wav", all_audio_data)

if __name__ == "__main__":
    main()  
