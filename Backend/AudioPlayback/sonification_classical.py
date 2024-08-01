import pygame
import pygame.midi
import time
import mido
from mido import Message, MidiFile, MidiTrack

# Initialize pygame and midi
pygame.init()
pygame.midi.init()

# Set up MIDI output
port = pygame.midi.get_default_output_id()
midi_out = pygame.midi.Output(port, 0)

# Mozart Sonata No. 16 in C major, K. 545 (first few measures)
MOZART_THEME = [
    # Right hand (melody)
    [(60, 64, 67), (72, 76), 72, 71, 72, 74, 76, 77, 76, 74, 72, 71, 72, 69, 67],
    # Left hand (accompaniment)
    [60, 64, 60, 64, 60, 64, 60, 64, 60, 64, 60, 64, 60, 64, 60]
]

# Note durations (in beats)
DURATIONS = [1, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5, 0.5, 0.25, 0.25, 0.25, 0.25, 0.5, 0.5, 1]

# Dynamics
VELOCITIES = {
    'p': 60,
    'mp': 80,
    'f': 100,
    'sf': 120
}

def play_note(note, duration, velocity):
    if isinstance(note, tuple):  # Chord
        for n in note:
            midi_out.note_on(n, velocity)
    else:  # Single note
        midi_out.note_on(note, velocity)
    
    time.sleep(duration * 60 / 140)  # Sleep for the note duration (at 140 BPM)
    
    if isinstance(note, tuple):  # Chord
        for n in note:
            midi_out.note_off(n, 0)
    else:  # Single note
        midi_out.note_off(note, 0)

def play_mozart_theme():
    for rh_note, lh_note, duration in zip(MOZART_THEME[0], MOZART_THEME[1], DURATIONS):
        # Play right hand (melody)
        play_note(rh_note, duration, VELOCITIES['mp'])
        
        # Play left hand (accompaniment)
        play_note(lh_note, duration, VELOCITIES['p'])

def create_midi_file():
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(Message('program_change', program=0, time=0))  # Piano sound

    current_time = 0
    for rh_note, lh_note, duration in zip(MOZART_THEME[0], MOZART_THEME[1], DURATIONS):
        # Right hand (melody)
        if isinstance(rh_note, tuple):  # Chord
            for n in rh_note:
                track.append(Message('note_on', note=n, velocity=VELOCITIES['mp'], time=current_time))
                current_time = 0
        else:  # Single note
            track.append(Message('note_on', note=rh_note, velocity=VELOCITIES['mp'], time=current_time))
        
        # Left hand (accompaniment)
        track.append(Message('note_on', note=lh_note, velocity=VELOCITIES['p'], time=current_time))
        current_time = 0

        # Note off messages
        ticks_duration = int(duration * mid.ticks_per_beat)
        if isinstance(rh_note, tuple):  # Chord
            for n in rh_note:
                track.append(Message('note_off', note=n, velocity=0, time=ticks_duration))
                ticks_duration = 0
        else:  # Single note
            track.append(Message('note_off', note=rh_note, velocity=0, time=ticks_duration))
        
        track.append(Message('note_off', note=lh_note, velocity=0, time=ticks_duration))
        current_time = 0

    mid.save('mozart_sonata_16.mid')

if __name__ == "__main__":
    try:
        print("Playing Mozart's Piano Sonata No. 16 in C major (K. 545)...")
        play_mozart_theme()
        create_midi_file()
        print("MIDI file 'mozart_sonata_16.mid' created.")
    except KeyboardInterrupt:
        print("\nPlayback stopped.")
    finally:
        del midi_out
        pygame.midi.quit()