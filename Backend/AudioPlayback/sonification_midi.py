import sys
import os
import time
import logging
from datetime import datetime
import numpy as np
import fluidsynth
from mido import Message, MidiFile, MidiTrack

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
MIN_FREQ = 60  # C4
MAX_FREQ = 84  # C6
BEAT_DURATION = 0.25  # Quarter note at 120 BPM
BEAT_PATTERN = [1, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5, 0.5, 1]  # Mozart-inspired

# Initialize FluidSynth
fs = fluidsynth.Synth()
fs.start(driver='coreaudio')  # Use 'alsa' for Linux, 'coreaudio' for macOS, or 'dsound' for Windows
sfid = fs.sfload("/Users/udaikhattar/Desktop/Development/AudioSpy/Steinway_D__SC55_Style_.sf2")  # Load a SoundFont (update the path)
fs.program_select(0, sfid, 0, 0)  # Select a piano sound

class AudioPlayer:
    """Handles real-time audio playback."""

    def play(self, note, duration, velocity):
        """Play a note using FluidSynth."""
        try:
            fs.noteon(0, note, velocity)
            time.sleep(duration)
            fs.noteoff(0, note)
        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    def close(self):
        """Close FluidSynth."""
        fs.delete()

def normalize_value(value, min_val, max_val):
    """Normalize a value to the range [0, 1]."""
    return (value - min_val) / (max_val - min_val) if max_val > min_val else 0

def map_to_note(normalized_value, min_note, max_note):
    """Map a normalized value to a MIDI note range."""
    return int(min_note + normalized_value * (max_note - min_note))

def sonify_data(data, beat_index):
    """Convert market data to audio based on sonification rules."""
    try:
        # Price change to note (Chapter 2: Polarity)
        price_change = (data['close'] - data['open']) / data['open'] if data['open'] != 0 else 0
        norm_price_change = normalize_value(price_change, -0.05, 0.05)  # Assume max 5% change
        note = map_to_note(norm_price_change, MIN_FREQ, MAX_FREQ)

        # Volume to velocity (Chapter 15: Scaling)
        norm_volume = normalize_value(data['volume'], 0, data['volume'] * 2)  # Dynamic scaling
        velocity = int(norm_volume * 40 + 60)  # Ensure some minimal velocity

        # Apply beat pattern (Chapter 13: Auditory Icons and Earcons)
        duration = BEAT_PATTERN[beat_index] * BEAT_DURATION

        # Add harmonics based on RSI (Chapter 3: Stream-based Sonification)
        if data['rsi'] is not None:
            if data['rsi'] > 70 or data['rsi'] < 30:
                harmonic_note = note + 12  # Octave higher
                velocity_harmonic = int(velocity * 0.7)  # Softer harmonic
            if data['rsi'] > 80 or data['rsi'] < 20:
                harmonic_note_2 = note + 19  # Fifth above the octave
                velocity_harmonic_2 = int(velocity * 0.5)  # Even softer harmonic

        return note, duration, velocity, harmonic_note, velocity_harmonic, harmonic_note_2, velocity_harmonic_2
    except Exception as e:
        logger.error(f"Error in sonify_data: {e}")
        return None

def save_midi(filename, notes):
    """Save notes to a MIDI file."""
    try:
        mid = MidiFile()
        track = MidiTrack()
        mid.tracks.append(track)

        track.append(Message('program_change', program=0, time=0))  # Piano sound

        current_time = 0
        for note, duration, velocity in notes:
            ticks_duration = int(duration * mid.ticks_per_beat)
            track.append(Message('note_on', note=note, velocity=velocity, time=current_time))
            track.append(Message('note_off', note=note, velocity=0, time=ticks_duration))
            current_time = 0  # Reset time after each event

        mid.save(filename)
        logger.info(f"MIDI file saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving MIDI: {e}")

def format_value(value):
    """Format a value for logging, handling None values."""
    return f"{value:.2f}" if value is not None else "N/A"

def main():
    """Main function to run the sonification process."""
    audio_player = AudioPlayer()
    beat_index = 0
    start_time = None
    notes = []

    try:
        for data in main_ohlcv():
            if start_time is None:
                start_time = datetime.fromtimestamp(data['timestamp'] / 1e9)
            
            current_time = datetime.fromtimestamp(data['timestamp'] / 1e9)
            elapsed_time = current_time - start_time
            
            # Simulate real-time playback
            time.sleep(max(0, elapsed_time.total_seconds() - (datetime.now() - start_time).total_seconds()))

            sonification_data = sonify_data(data, beat_index)
            if sonification_data is not None:
                note, duration, velocity, harmonic_note, velocity_harmonic, harmonic_note_2, velocity_harmonic_2 = sonification_data
                audio_player.play(note, duration, velocity)
                notes.append((note, duration, velocity))
                if harmonic_note is not None:
                    audio_player.play(harmonic_note, duration, velocity_harmonic)
                    notes.append((harmonic_note, duration, velocity_harmonic))
                if harmonic_note_2 is not None:
                    audio_player.play(harmonic_note_2, duration, velocity_harmonic_2)
                    notes.append((harmonic_note_2, duration, velocity_harmonic_2))

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
        save_midi("market_sonification.mid", notes)

if __name__ == "__main__":
    main()