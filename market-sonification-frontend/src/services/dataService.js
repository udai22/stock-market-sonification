// src/services/dataService.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

/**
 * Fetches historical market data from the server.
 * @returns {Promise<Array>} A promise that resolves to an array of historical data.
 */
export const fetchHistoricalData = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/main_ohlcv`);
    return response.data.map(item => ({
      time: item.timestamp / 1000, // Convert nanoseconds to seconds
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume
    }));
  } catch (error) {
    console.error('Error fetching historical data:', error);
    return [];
  }
};

/**
 * Fetches the latest market data from the server.
 * @returns {Promise<Object>} A promise that resolves to the latest market data.
 */
export const fetchLatestMarketData = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/latest_market_data`);
    return response.data;
  } catch (error) {
    console.error('Error fetching latest market data:', error);
    return null;
  }
};