import databento as db
from .OrderBook import Market
from datetime import datetime
from collections import deque
from talipp.indicators import EMA, Ichimoku, RSI, ATR
from talipp.ohlcv import OHLCV
import logging
from databento_dbn import FIXED_PRICE_SCALE, UNDEF_PRICE, BidAskPair


# Configure logging
logging.basicConfig(level=logging.INFO)

def get_market_data(dataset, symbol, start_time, end_time, schema, client):
    data = client.timeseries.get_range(
        dataset=dataset,
        symbols=symbol,
        start=start_time,
        end=end_time,
        schema=schema
    )

    instrument_map = db.common.symbology.InstrumentMap()
    instrument_map.insert_metadata(data.metadata)
    return data, instrument_map

def market_data_generator_ohlcv(symbol, start_time, end_time, client, schema):
    data, instrument_map = get_market_data("XNAS.ITCH", symbol, start_time, end_time, schema, client)

    for ohlcv in data:
        resolved_symbol = instrument_map.resolve(ohlcv.instrument_id, ohlcv.pretty_ts_event.date()) or ""
        yield resolved_symbol, ohlcv.open / FIXED_PRICE_SCALE, ohlcv.high / FIXED_PRICE_SCALE, ohlcv.low / FIXED_PRICE_SCALE, ohlcv.close / FIXED_PRICE_SCALE, ohlcv.volume, ohlcv.ts_event

def market_data_generator_mbo(symbol, start_time, end_time, client):
    data, instrument_map = get_market_data("XNAS.ITCH", symbol, start_time, end_time, "mbo", client)
    market = Market()

    for mbo in data:
        market.apply(mbo)
        if mbo.flags & db.RecordFlags.F_LAST:
            resolved_symbol = instrument_map.resolve(mbo.instrument_id, mbo.pretty_ts_recv.date()) or ""
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

def main_ohlcv():
    client = db.Historical("db-higLgmW3Hwqx6pAFiUSDayssT3HRj")

    # Initialize technical indicators
    ema_9 = EMA(9)
    ema_26 = EMA(26)
    ema_52 = EMA(52)
    ichimoku = Ichimoku(kijun_period=26, tenkan_period=9, chikou_lag_period=26, senkou_slow_period=52, senkou_lookup_period=26)
    rsi = RSI(14)
    atr = ATR(14)

    # Store OHLCV values
    ohlcv_values = []

    for symbol, open_price, high_price, low_price, close_price, volume, timestamp in market_data_generator_ohlcv("SPY", "2024-05-22T14:00:00", "2024-05-22T15:00:00", client, "ohlcv-1s"):
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

if __name__ == "__main__":
    for indicator_values in main_ohlcv():
        logging.info(indicator_values)
