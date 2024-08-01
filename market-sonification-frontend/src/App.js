import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CssBaseline, Container, Grid } from '@material-ui/core';
import ChartComponent from './components/Chart/ChartComponent';
import AudioControlComponent from './components/AudioControl/AudioControlComponent';
import MarketDataComponent from './components/MarketData/MarketDataComponent';
import { connectWebSocket, sendWebSocketMessage } from './services/websocketService';
import { fetchHistoricalData } from './services/dataService';

const SOUNDFONT_PATH = "/Users/udaikhattar/Desktop/Development/AudioSpy/Steinway_D__SC55_Style_.sf2";

function App() {
  const [marketData, setMarketData] = useState(null);
  const [historicalData, setHistoricalData] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const webSocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const soundfontRef = useRef(null);

  const handleMarketUpdate = useCallback((data) => {
    if (data.type === 'market_update') {
      setMarketData(data.market_data);
      if (isPlaying) {
        playSonification(data.audio_info);
      }
    }
  }, [isPlaying]);

  useEffect(() => {
    const initializeAudioContext = async () => {
      if (window.AudioContext || window.webkitAudioContext) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      } else {
        console.error('Web Audio API is not supported in this browser.');
      }
    };

    initializeAudioContext();
  }, []);

  useEffect(() => {
    const loadSoundfont = async () => {
      if (audioContextRef.current) {
        const response = await fetch(SOUNDFONT_PATH);
        const arrayBuffer = await response.arrayBuffer();
        soundfontRef.current = await audioContextRef.current.decodeAudioData(arrayBuffer);
      }
    };

    loadSoundfont();

    const socket = connectWebSocket(handleMarketUpdate);
    webSocketRef.current = socket;

    fetchHistoricalData().then(setHistoricalData);

    return () => {
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
    };
  }, [handleMarketUpdate]);

  const playSonification = useCallback((audioInfo) => {
    if (!soundfontRef.current || !audioContextRef.current) return;

    const { notes, duration } = audioInfo;
    const currentTime = audioContextRef.current.currentTime;

    notes.forEach(([note, velocity]) => {
      const source = audioContextRef.current.createBufferSource();
      source.buffer = soundfontRef.current;
      
      const gainNode = audioContextRef.current.createGain();
      gainNode.gain.setValueAtTime(velocity / 127, currentTime);
      
      source.connect(gainNode);
      gainNode.connect(audioContextRef.current.destination);
      
      source.playbackRate.value = 2 ** ((note - 60) / 12);
      source.start(currentTime);
      source.stop(currentTime + duration);
    });
  }, []);

  const handlePlaybackStart = useCallback(() => {
    setIsPlaying(true);
    sendWebSocketMessage(webSocketRef.current, { type: 'playback_control', action: 'start' });
  }, []);

  const handlePlaybackStop = useCallback(() => {
    setIsPlaying(false);
    sendWebSocketMessage(webSocketRef.current, { type: 'playback_control', action: 'stop' });
  }, []);

  return (
    <Container>
      <CssBaseline />
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <ChartComponent data={historicalData} latestData={marketData} />
        </Grid>
        <Grid item xs={12} md={8}>
          {marketData && <MarketDataComponent data={marketData} />}
        </Grid>
        <Grid item xs={12} md={4}>
          <AudioControlComponent
            isPlaying={isPlaying}
            onPlaybackStart={handlePlaybackStart}
            onPlaybackStop={handlePlaybackStop}
          />
        </Grid>
      </Grid>
    </Container>
  );
}

export default App;