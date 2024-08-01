"""
market_data_service.py

This module provides a robust market data fetching, caching, and analysis service.
It utilizes a two-tier caching system with Redis for fast, short-term access
and local file storage for long-term persistence. The service is designed
to minimize API calls, optimize data retrieval, and handle errors gracefully.
It also includes technical indicators calculation.

Dependencies:
- databento
- redis
- pandas
- talipp

Environment variables:
- REDIS_HOST: Redis server host (default: localhost)
- REDIS_PORT: Redis server port (default: 6379)
- REDIS_PASSWORD: Redis server password (optional)
- LOCAL_STORAGE_PATH: Path for local file storage
- DATABENTO_API_KEY: Databento API key
"""

import os
import logging
import hashlib
import pickle
import gzip
from datetime import datetime, timedelta
from typing import Tuple, List, Any, Optional, Generator

import databento as db
import redis
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from talipp.indicators import EMA, Ichimoku, RSI, ATR
from talipp.ohlcv import OHLCV
from databento_dbn import FIXED_PRICE_SCALE, UNDEF_PRICE, BidAskPair

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
LOCAL_STORAGE_PATH = os.getenv('LOCAL_STORAGE_PATH', 'Backend/MarketDataStored')
DATABENTO_API_KEY = os.getenv('DATABENTO_API_KEY', "db-higLgmW3Hwqx6pAFiUSDayssT3HRj")

# Ensure local storage directory exists
os.makedirs(LOCAL_STORAGE_PATH, exist_ok=True)

# Initialize Redis client
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        #password=REDIS_PASSWORD,
        decode_responses=False,
        socket_timeout=5,
    )
    redis_client.ping()  # Test connection
except redis.ConnectionError:
    logger.error("Failed to connect to Redis. Ensure Redis is running and credentials are correct.")
    redis_client = None

# Initialize Databento client
databento_client = db.Historical(DATABENTO_API_KEY)

def generate_cache_key(symbol: str, start_time: str, end_time: str) -> str:
    """Generate a unique cache key based on the query parameters."""
    return hashlib.md5(f"{symbol}:{start_time}:{end_time}".encode()).hexdigest()

def get_cached_data(symbol: str, start_time: str, end_time: str) -> Optional[List[dict]]:
    """
    Attempt to retrieve cached data from Redis or local storage.
    
    Args:
        symbol (str): The market symbol.
        start_time (str): The start time of the data range.
        end_time (str): The end time of the data range.
    
    Returns:
        Optional[List[dict]]: Cached data if found, None otherwise.
    """
    cache_key = generate_cache_key(symbol, start_time, end_time)
    
    # Try Redis first
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Cache hit in Redis for {symbol}")
                return pickle.loads(cached_data)
        except redis.RedisError as e:
            logger.error(f"Redis error: {e}")
    
    # If not in Redis, try local storage
    file_path = os.path.join(LOCAL_STORAGE_PATH, f"{cache_key}.pickle.gz")
    if os.path.exists(file_path):
        try:
            with gzip.open(file_path, 'rb') as f:
                data = pickle.load(f)
            logger.info(f"Cache hit in local storage for {symbol}")
            # Store in Redis for faster future access
            if redis_client:
                redis_client.setex(cache_key, timedelta(hours=24), pickle.dumps(data))
            return data
        except Exception as e:
            logger.error(f"Error reading from local storage: {e}")
    
    logger.info(f"Cache miss for {symbol}")
    return None

def set_cached_data(symbol: str, start_time: str, end_time: str, data: List[dict]) -> None:
    """
    Store data in both Redis and local storage.
    
    Args:
        symbol (str): The market symbol.
        start_time (str): The start time of the data range.
        end_time (str): The end time of the data range.
        data (List[dict]): The data to be cached.
    """
    cache_key = generate_cache_key(symbol, start_time, end_time)
    
    # Store in Redis
    if redis_client:
        try:
            redis_client.setex(cache_key, timedelta(hours=24), pickle.dumps(data))
        except redis.RedisError as e:
            logger.error(f"Failed to store data in Redis: {e}")
    
    # Store in local storage
    file_path = os.path.join(LOCAL_STORAGE_PATH, f"{cache_key}.pickle.gz")
    try:
        with gzip.open(file_path, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to store data in local storage: {e}")

def get_market_data(dataset: str, symbol: str, start_time: str, end_time: str, schema: str) -> List[dict]:
    """
    Fetch market data, using cache if available, otherwise querying the Databento API.
    
    Args:
        dataset (str): The dataset to query.
        symbol (str): The market symbol.
        start_time (str): The start time of the data range.
        end_time (str): The end time of the data range.
        schema (str): The data schema to use.
    
    Returns:
        List[dict]: A list of dictionaries containing the market data.
    """
    cached_data = get_cached_data(symbol, start_time, end_time)
    if cached_data:
        return cached_data

    try:
        data = databento_client.timeseries.get_range(
            dataset=dataset,
            symbols=symbol,
            start=start_time,
            end=end_time,
            schema=schema
        )
        
        # Convert data to a serializable format
        serializable_data = [
            {
                'ts_event': item.ts_event,
                'instrument_id': item.instrument_id,
                'open': item.open,
                'high': item.high,
                'low': item.low,
                'close': item.close,
                'volume': item.volume,
            }
            for item in data
        ]
        
        set_cached_data(symbol, start_time, end_time, serializable_data)
        
        return serializable_data
    except Exception as e:
        logger.error(f"Error fetching data from Databento API: {e}")
        raise

def market_data_generator_ohlcv(symbol: str, start_time: str, end_time: str, schema: str) -> Generator[Tuple[str, float, float, float, float, int, int], None, None]:
    """
    Generate OHLCV data for a given symbol and time range.
    
    Args:
        symbol (str): The market symbol.
        start_time (str): The start time of the data range.
        end_time (str): The end time of the data range.
        schema (str): The data schema to use.
    
    Yields:
        Tuple[str, float, float, float, float, int, int]: Symbol, open, high, low, close, volume, timestamp
    """
    data = get_market_data("XNAS.ITCH", symbol, start_time, end_time, schema)

    for item in data:
        yield (
            symbol,
            item['open'] / FIXED_PRICE_SCALE,
            item['high'] / FIXED_PRICE_SCALE,
            item['low'] / FIXED_PRICE_SCALE,
            item['close'] / FIXED_PRICE_SCALE,
            item['volume'],
            item['ts_event']
        )

def market_data_generator_mbo(symbol: str, start_time: str, end_time: str) -> Generator[Tuple[float, float, float, float, int, int], None, None]:
    """
    Generate MBO (Market by Order) data for a given symbol and time range.
    
    Args:
        symbol (str): The market symbol.
        start_time (str): The start time of the data range.
        end_time (str): The end time of the data range.
    
    Yields:
        Tuple[float, float, float, float, int, int]: Best bid price, best offer price, mid price, weighted mid price, best bid size, best offer size
    """
    data = get_market_data("XNAS.ITCH", symbol, start_time, end_time, "mbo")
    market = db.OrderBook()

    for item in data:
        mbo = db.MBOMsg(**item)
        market.apply(mbo)
        if mbo.flags & db.RecordFlags.F_LAST:
            best_bid, best_offer = market.aggregated_bbo(mbo.instrument_id)
            best_bid_price = best_bid.price if best_bid is not None else 0
            best_offer_price = best_offer.price if best_offer is not None else 0

            best_bid_price /= FIXED_PRICE_SCALE
            best_offer_price /= FIXED_PRICE_SCALE

            if (best_bid_price + best_offer_price) == 0:
                continue

            best_bid_size = best_bid.size if best_bid is not None else 0
            best_offer_size = best_offer.size if best_offer is not None else 0

            mid = (best_bid_price + best_offer_price) / 2 if best_bid and best_offer else 0
            weighted_mid = (best_bid_size * best_bid_price + best_offer_size * best_offer_price) / (best_bid_size + best_offer_size) if (best_bid_size + best_offer_size) > 0 else 0
            yield best_bid_price, best_offer_price, mid, weighted_mid, best_bid_size, best_offer_size

def main_ohlcv() -> Generator[dict, None, None]:
    """
    Main function to generate OHLCV data with technical indicators.
    
    Yields:
        dict: A dictionary containing OHLCV data and technical indicators.
    """
    # Initialize technical indicators
    ema_9 = EMA(9)
    ema_26 = EMA(26)
    ema_52 = EMA(52)
    ichimoku = Ichimoku(kijun_period=26, tenkan_period=9, chikou_lag_period=26, senkou_slow_period=52, senkou_lookup_period=26)
    rsi = RSI(14)
    atr = ATR(14)

    # Store OHLCV values
    ohlcv_values = []

    for symbol, open_price, high_price, low_price, close_price, volume, timestamp in market_data_generator_ohlcv("SPY", "2024-07-30T14:00:00", "2024-07-30T16:00:00", "ohlcv-1s"):
        ohlcv = OHLCV(open=open_price, high=high_price, low=low_price, close=close_price, volume=volume, time=datetime.fromtimestamp(timestamp / 1e9))
        ohlcv_values.append(ohlcv)

        # Update indicators
        ema_9.add(ohlcv.close)
        ema_26.add(ohlcv.close)
        ema_52.add(ohlcv.close)
        ichimoku.add(ohlcv)
        rsi.add(ohlcv.close)
        atr.add(ohlcv)

        indicator_values = {
            'symbol': symbol,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume,
            'timestamp': timestamp,
            'ema_9': ema_9[-1] if len(ema_9) > 0 else None,
            'ema_26': ema_26[-1] if len(ema_26) > 0 else None,
            'ema_52': ema_52[-1] if len(ema_52) > 0 else None,
            'rsi': rsi[-1] if len(rsi) > 0 else None,
            'atr': atr[-1] if len(atr) > 0 else None
        }

        if len(ichimoku) > 0:
            ichimoku_val = ichimoku[-1]
            indicator_values.update({
                'ichimoku_base_line': ichimoku_val.base_line,
                'ichimoku_conversion_line': ichimoku_val.conversion_line,
                'ichimoku_lagging_line': ichimoku_val.lagging_line,
                'ichimoku_cloud_leading_fast_line': ichimoku_val.cloud_leading_fast_line,
                'ichimoku_cloud_leading_slow_line': ichimoku_val.cloud_leading_slow_line
            })

        yield indicator_values

def cleanup_old_cache_files(max_age_days: int = 30) -> None:
    """
    Remove cache files older than the specified number of days.
    
    Args:
        max_age_days (int): The maximum age of cache files in days (default: 30).
    """
    current_time = datetime.now()
    for filename in os.listdir(LOCAL_STORAGE_PATH):
        file_path = os.path.join(LOCAL_STORAGE_PATH, filename)
        file_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        if (current_time - file_modified_time).days > max_age_days:
            try:
                os.remove(file_path)
                logger.info(f"Removed old cache file: {filename}")
            except OSError as e:
                logger.error(f"Error deleting old cache file {filename}: {e}")

if __name__ == "__main__":
    for indicator_values in main_ohlcv():
        logging.info(indicator_values)
    
    # Clean up old cache files
    #cleanup_old_cache_files()