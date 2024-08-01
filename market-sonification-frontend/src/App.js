import React, { useState, useEffect, useCallback, useRef } from 'react';
import { CssBaseline, Container, Grid } from '@material-ui/core';
import ChartComponent from './components/Chart/ChartComponent';
import AudioControlComponent from './components/AudioControl/AudioControlComponent';
import MarketDataComponent from './components/MarketData/MarketDataComponent';
import { connectWebSocket, sendWebSocketMessage } from './services/websocketService';
import { fetchHistoricalData } from './services/dataService';

function App() {
  const [marketData, setMarketData] = useState({});
  const [historicalData, setHistoricalData] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const webSocketRef = useRef(null);
  const audioContextRef = useRef(null);

  const handleMarketUpdate = useCallback((data) => {
    if (data.type === 'market_update') {
      setMarketData(prevData => ({...prevData, ...data.delta_data}));
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
    const connectAndListen = () => {
      const socket = connectWebSocket(handleMarketUpdate);
      webSocketRef.current = socket;

      socket.onclose = () => {
        console.log('WebSocket closed. Reconnecting...');
        setTimeout(connectAndListen, 5000);
      };
    };

    connectAndListen();
    fetchHistoricalData().then(setHistoricalData);

    return () => {
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
    };
  }, [handleMarketUpdate]);

  const playSonification = useCallback((audioInfo) => {
    if (!audioContextRef.current) return;

    const { notes, duration } = audioInfo;
    const currentTime = audioContextRef.current.currentTime;

    notes.forEach(([note, velocity]) => {
      const oscillator = audioContextRef.current.createOscillator();
      const gainNode = audioContextRef.current.createGain();

      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(midiToFrequency(note), currentTime);
      
      gainNode.gain.setValueAtTime(velocity / 127, currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.00001, currentTime + duration);
      
      oscillator.connect(gainNode);
      gainNode.connect(audioContextRef.current.destination);
      
      oscillator.start(currentTime);
      oscillator.stop(currentTime + duration);
    });
  }, []);

  const midiToFrequency = (midiNote) => {
    return 440 * Math.pow(2, (midiNote - 69) / 12);
  };

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