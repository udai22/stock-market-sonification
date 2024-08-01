// src/components/MarketData/MarketDataComponent.js
import React from 'react';
import { Paper, Typography, Grid } from '@material-ui/core';

/**
 * Displays current market data.
 * @param {Object} data - The current market data.
 */
const MarketDataComponent = ({ data }) => {
  const calculateChange = () => {
    if (data.open && data.close) {
      return ((data.close - data.open) / data.open * 100).toFixed(2);
    }
    return 'N/A';
  };

  return (
    <Paper className="market-data" style={{ padding: '1rem' }}>
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Typography variant="h6">{data.symbol || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography>Price: ${data.close?.toFixed(2) || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography>Change: {calculateChange()}%</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography>Volume: {data.volume?.toLocaleString() || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography>Time: {new Date(data.timestamp / 1e6).toLocaleTimeString()}</Typography>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default MarketDataComponent;