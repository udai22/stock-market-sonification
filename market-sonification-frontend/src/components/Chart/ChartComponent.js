// src/components/Chart/ChartComponent.js
import React, { useEffect, useRef, useState } from 'react';
import { createChart, CrosshairMode } from 'lightweight-charts';

/**
 * Renders a candlestick chart using TradingView's Lightweight Charts.
 * @param {Array} data - The historical price data to display.
 * @param {Object} latestData - The latest market data.
 */
const ChartComponent = ({ data, latestData }) => {
  const chartContainerRef = useRef();
  const chartRef = useRef();
  const [candleSeries, setCandleSeries] = useState(null);

  useEffect(() => {
    const handleResize = () => {
      if (chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
      layout: {
        backgroundColor: '#253248',
        textColor: 'rgba(255, 255, 255, 0.9)',
      },
      grid: {
        vertLines: { color: 'rgba(197, 203, 206, 0.5)' },
        horzLines: { color: 'rgba(197, 203, 206, 0.5)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: 'rgba(197, 203, 206, 0.8)',
      },
      timeScale: {
        borderColor: 'rgba(197, 203, 206, 0.8)',
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#4bffb5',
      downColor: '#ff4976',
      borderDownColor: '#ff4976',
      borderUpColor: '#4bffb5',
      wickDownColor: '#838ca1',
      wickUpColor: '#838ca1',
    });

    setCandleSeries(candleSeries);
    chartRef.current = chart;

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (candleSeries && data.length > 0) {
      const formattedData = data.map(item => ({
        time: item.time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close
      }));
      candleSeries.setData(formattedData);
    }
  }, [candleSeries, data]);

  useEffect(() => {
    if (candleSeries && latestData && latestData.timestamp) {
      const updatedData = {
        time: latestData.timestamp / 1000, // Convert to seconds
        open: latestData.open,
        high: latestData.high,
        low: latestData.low,
        close: latestData.close
      };
      candleSeries.update(updatedData);
    }
  }, [candleSeries, latestData]);

  return <div ref={chartContainerRef} />;
};

export default ChartComponent;