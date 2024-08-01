// src/components/AudioControl/AudioControlComponent.js
import React, { useState, useCallback } from 'react';
import { Button, Slider, IconButton } from '@material-ui/core';
import { PlayArrow, Pause, VolumeUp, VolumeOff } from '@material-ui/icons';

/**
 * Renders audio controls for playing and adjusting market sonification.
 * @param {boolean} isPlaying - Indicates whether playback is currently active.
 * @param {Function} onPlaybackStart - Callback function when playback starts.
 * @param {Function} onPlaybackStop - Callback function when playback stops.
 */
const AudioControlComponent = ({ isPlaying, onPlaybackStart, onPlaybackStop }) => {
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  const togglePlay = useCallback(() => {
    if (isPlaying) {
      onPlaybackStop();
    } else {
      onPlaybackStart();
    }
  }, [isPlaying, onPlaybackStart, onPlaybackStop]);

  const handleVolumeChange = useCallback((event, newValue) => {
    setVolume(newValue);
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted(!isMuted);
  }, [isMuted]);

  return (
    <div className="audio-control">
      <Button onClick={togglePlay}>
        {isPlaying ? <Pause /> : <PlayArrow />}
      </Button>
      <Slider value={volume} onChange={handleVolumeChange} min={0} max={1} step={0.01} />
      <IconButton onClick={toggleMute}>
        {isMuted ? <VolumeOff /> : <VolumeUp />}
      </IconButton>
    </div>
  );
};

export default AudioControlComponent;