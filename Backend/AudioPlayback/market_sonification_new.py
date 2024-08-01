"""
market_sonification.py

This module provides a real-time market data sonification system designed for integration
with a production web application. It fetches market data, processes it, and converts it
into musical output, saving as MIDI and WAV files while streaming data via WebSocket.

The system fetches market data, sonifies it in real-time, and provides multiple output formats
for flexible integration with web applications and audio systems.

Dependencies:
- fluidsynth
- mido
- numpy
- websockets
- asyncio
- scipy
- market_data_service (custom module for fetching market data)

Environment variables:
- SOUNDFONT_PATH: Path to the SoundFont file for FluidSynth
- WEBSOCKET_HOST: Host for the WebSocket server (default: localhost)
- WEBSOCKET_PORT: Port for the WebSocket server (default: 8765)
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any
import json

import numpy as np
import fluidsynth
from mido import Message, MidiFile, MidiTrack
import asyncio
import websockets
import scipy.io.wavfile as wavfile

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add necessary paths
try:
    backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    market_path = os.path.join(backend_path, 'Market')
    sys.path.extend([backend_path, market_path])
    from Market.market_data_service import main_ohlcv
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

# Constants
SAMPLE_RATE = 44100
CHANNELS = 1
MIN_FREQ = 60  # C4
MAX_FREQ = 84  # C6
BEAT_DURATION = 0.25  # Quarter note at 120 BPM
BEAT_PATTERN = [1, 0.5, 0.5, 0.5, 0.5, 1, 0.5, 0.5]  # More varied rhythm
SOUNDFONT_PATH = "/Users/udaikhattar/Desktop/Development/AudioSpy/Steinway_D__SC55_Style_.sf2"
WEBSOCKET_HOST = os.getenv('WEBSOCKET_HOST', 'localhost')
WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', 8765))

class AudioPlayer:
    """Handles real-time audio playback using FluidSynth."""

    def __init__(self):
        self.synth = fluidsynth.Synth()
        self.synth.start(driver='coreaudio')  # Use 'alsa' for Linux, 'coreaudio' for macOS, or 'dsound' for Windows
        self.sfid = self.synth.sfload(SOUNDFONT_PATH)
        self.synth.program_select(0, self.sfid, 0, 0)  # Select a piano sound

    def play(self, notes: List[Tuple[int, int]], duration: float):
        """
        Play a collection of notes simultaneously.

        Args:
            notes (List[Tuple[int, int]]): List of (note, velocity) tuples.
            duration (float): Duration to play the notes.
        """
        try:
            for note, velocity in notes:
                self.synth.noteon(0, note, velocity)
            time.sleep(duration)
            for note, _ in notes:
                self.synth.noteoff(0, note)
        except Exception as e:
            logger.error(f"Error playing audio: {e}")

    def close(self):
        """Close FluidSynth."""
        self.synth.delete()

class MarketSonifier:
    """Handles the sonification of market data and streaming of data/audio information."""

    def __init__(self):
        self.audio_player = AudioPlayer()
        self.connected_clients = set()
        self.last_sent_data = None
        self.running = True

    async def register(self, websocket):
        """Register a new WebSocket client."""
        self.connected_clients.add(websocket)

    async def unregister(self, websocket):
        """Unregister a WebSocket client."""
        self.connected_clients.remove(websocket)

    async def broadcast(self, message):
        """Broadcast a message to all connected WebSocket clients."""
        for websocket in self.connected_clients.copy():
            try:
                await websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                await self.unregister(websocket)

    @staticmethod
    def normalize_value(value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to the range [0, 1]."""
        return (value - min_val) / (max_val - min_val) if max_val > min_val else 0

    @staticmethod
    def map_to_note(normalized_value: float, min_note: int, max_note: int) -> int:
        """Map a normalized value to a MIDI note range."""
        return int(min_note + normalized_value * (max_note - min_note))

    def sonify_data(self, data: dict, beat_index: int) -> Tuple[List[Tuple[int, int]], float]:
        """
        Convert market data to audio parameters based on sonification rules.

        Args:
            data (dict): Market data dictionary.
            beat_index (int): Current position in the beat pattern.

        Returns:
            Tuple[List[Tuple[int, int]], float]: List of (note, velocity) tuples and note duration.
        """
        try:
            # Price change to melody note
            price_change = (data['close'] - data['open']) / data['open'] if data['open'] != 0 else 0
            norm_price_change = self.normalize_value(price_change, -0.05, 0.05)
            melody_note = self.map_to_note(norm_price_change, MIN_FREQ, MAX_FREQ)

            # Volume to velocity
            norm_volume = self.normalize_value(data['volume'], 0, data['volume'] * 2)
            melody_velocity = int(norm_volume * 40 + 60)

            duration = BEAT_PATTERN[beat_index] * BEAT_DURATION

            notes = [(melody_note, melody_velocity)]

            # RSI to chord
            if data.get('rsi'):
                if data['rsi'] > 70:
                    chord_notes = [melody_note + 4, melody_note + 7]  # Major chord
                elif data['rsi'] < 30:
                    chord_notes = [melody_note + 3, melody_note + 7]  # Minor chord
                else:
                    chord_notes = []
                chord_velocity = int(melody_velocity * 0.7)
                notes.extend((note, chord_velocity) for note in chord_notes)

            # Ichimoku Cloud to harmony
            if data.get('ichimoku_cloud_leading_fast_line') and data.get('ichimoku_cloud_leading_slow_line'):
                harmony_note = melody_note + 2 if data['ichimoku_cloud_leading_fast_line'] > data['ichimoku_cloud_leading_slow_line'] else melody_note - 2
                harmony_velocity = int(melody_velocity * 0.6)
                notes.append((harmony_note, harmony_velocity))

            return notes, duration

        except Exception as e:
            logger.error(f"Error in sonify_data: {e}")
            return [(MIN_FREQ, 60)], BEAT_DURATION  # Default note if error occurs

    async def handle_websocket(self, websocket, path):
        await self.register(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                if data['type'] == 'playback_control':
                    if data['action'] == 'start':
                        self.running = True
                    elif data['action'] == 'stop':
                        self.running = False
        finally:
            await self.unregister(websocket)

    def calculate_delta(self, new_data):
        """Calculate the delta between the new data and the last sent data."""
        if not self.last_sent_data:
            self.last_sent_data = new_data
            return new_data

        delta = {}
        for key, value in new_data.items():
            if key not in self.last_sent_data or value != self.last_sent_data[key]:
                delta[key] = value

        self.last_sent_data = new_data
        return delta if delta else None

    async def run(self):
        """Main execution loop for the market sonification."""
        server = await websockets.serve(
            self.handle_websocket, WEBSOCKET_HOST, WEBSOCKET_PORT
        )

        beat_index = 0
        start_time = None
        midi_notes = []

        while True:
            try:
                logger.info("Starting market data retrieval...")
                data_generator = main_ohlcv()
                logger.info("Market data generator initialized.")

                for data in data_generator:
                    if not self.running:
                        await asyncio.sleep(1)
                        continue

                    logger.debug(f"Received market data: {data}")
                    if start_time is None:
                        start_time = datetime.fromtimestamp(data['timestamp'] / 1e9)

                    current_time = datetime.fromtimestamp(data['timestamp'] / 1e9)
                    elapsed_time = current_time - start_time

                    # Simulate real-time playback
                    await asyncio.sleep(max(0, elapsed_time.total_seconds() - (datetime.now() - start_time).total_seconds()))

                    delta_data = self.calculate_delta(data)
                    if delta_data:
                        notes, duration = self.sonify_data(delta_data, beat_index)
                        logger.debug(f"Sonified data: notes={notes}, duration={duration}")
                        self.audio_player.play(notes, duration)
                        midi_notes.append((notes, duration))

                        # Prepare audio information for streaming
                        audio_info = {
                            "notes": [[note, velocity] for note, velocity in notes],
                            "duration": duration,
                            "beat_index": beat_index
                        }

                        # Stream data and audio information
                        await self.broadcast({"type": "market_update", "delta_data": delta_data, "audio_info": audio_info})

                    beat_index = (beat_index + 1) % len(BEAT_PATTERN)

                    self.log_market_data(data, current_time)

                # If we've gone through all data, reset and start over
                start_time = None
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"An error occurred in run method: {e}")
                await asyncio.sleep(5)  # Wait a bit before retrying

        self.save_midi_and_wav("market_sonification", midi_notes)
        await server.wait_closed()

    @staticmethod
    def log_market_data(data: dict, timestamp: datetime):
        """Log market data and indicators."""
        logger.info(f"Timestamp: {timestamp}, Close: {data.get('close', 'N/A')}, Volume: {data.get('volume', 'N/A')}")
        logger.info(f"EMA9: {data.get('ema_9', 'N/A')}, EMA26: {data.get('ema_26', 'N/A')}, EMA52: {data.get('ema_52', 'N/A')}")
        logger.info(f"RSI: {data.get('rsi', 'N/A')}, ATR: {data.get('atr', 'N/A')}")
        logger.info("Ichimoku Cloud:")
        logger.info(f"  Base Line: {data.get('ichimoku_base_line', 'N/A')}")
        logger.info(f"  Conversion Line: {data.get('ichimoku_conversion_line', 'N/A')}")
        logger.info(f"  Lagging Line: {data.get('ichimoku_lagging_line', 'N/A')}")
        logger.info(f"  Leading Fast Line: {data.get('ichimoku_cloud_leading_fast_line', 'N/A')}")
        logger.info(f"  Leading Slow Line: {data.get('ichimoku_cloud_leading_slow_line', 'N/A')}")
        logger.info("-" * 50)

    @staticmethod
    def save_midi_and_wav(filename: str, notes: List[Tuple[List[Tuple[int, int]], float]]):
        """
        Save notes to both MIDI and WAV files.

        Args:
            filename (str): Output file name (without extension).
            notes (List[Tuple[List[Tuple[int, int]], float]]): List of (notes, duration) tuples.
        """
        try:
            # Save MIDI
            mid = MidiFile()
            track = MidiTrack()
            mid.tracks.append(track)

            track.append(Message('program_change', program=0, time=0))  # Piano sound

            current_time = 0
            for note_list, duration in notes:
                ticks_duration = int(duration * mid.ticks_per_beat)
                for note, velocity in note_list:
                    track.append(Message('note_on', note=note, velocity=velocity, time=current_time))
                    current_time = 0
                for note, _ in note_list:
                    track.append(Message('note_off', note=note, velocity=0, time=ticks_duration))
                    ticks_duration = 0

            midi_filename = f"{filename}.mid"
            mid.save(midi_filename)
            logger.info(f"MIDI file saved to {midi_filename}")

            # Generate WAV
            sample_rate = 44100  # Standard sample rate
            t = 0  # Current time
            audio_data = []

            for note_list, duration in notes:
                chunk_samples = int(duration * sample_rate)
                chunk = np.zeros(chunk_samples)

                for note, velocity in note_list:
                    frequency = 440 * (2 ** ((note - 69) / 12))  # Convert MIDI note to frequency
                    t_array = np.linspace(t, t + duration, chunk_samples, False)
                    note_data = np.sin(2 * np.pi * frequency * t_array) * (velocity / 127)
                    chunk += note_data

                audio_data.extend(chunk)
                t += duration

            audio_data = np.array(audio_data)
            audio_data = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)

            wav_filename = f"{filename}.wav"
            wavfile.write(wav_filename, sample_rate, audio_data)
            logger.info(f"WAV file saved to {wav_filename}")

        except Exception as e:
            logger.error(f"Error saving MIDI and WAV: {e}")

if __name__ == "__main__":
    sonifier = MarketSonifier()
    asyncio.run(sonifier.run())