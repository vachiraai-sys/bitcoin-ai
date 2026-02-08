
import pandas as pd
import pandas_ta as ta

def calculate_indicators(df):
    """
    Calculate technical indicators using pandas_ta
    df: DataFrame with 'close' column
    """
    if df.empty:
        return df

    # RSI (14)
    df['RSI'] = df.ta.rsi(length=14)

    # MACD (12, 26, 9)
    # macd method returns a DataFrame with columns: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # EMA (12, 26, 200)
    # Check if we have enough data to avoid errors
    if len(df) >= 12:
        df['EMA12'] = df.ta.ema(length=12)
    if len(df) >= 26:
        df['EMA26'] = df.ta.ema(length=26)
    if len(df) >= 200:
        df['EMA200'] = df.ta.ema(length=200)
    else:
        # Fill with NaN if not enough data, or just don't calculate
        df['EMA200'] = pd.Series([None] * len(df), index=df.index)

    return df

def check_signals(df):
    """
    Check for buy/sell signals based on the latest data
    Returns a list of signal strings
    """
    if df.empty or len(df) < 2:
        return []

    signals = []
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    # RSI Signals
    if last_row['RSI'] < 30:
        signals.append("RSI ต่ำกว่า 30 (Oversold - สัญญาณซื้อ)")
    elif last_row['RSI'] > 70:
        signals.append("RSI สูงกว่า 70 (Overbought - สัญญาณขาย)")

    # EMA Crossover (Golden Cross / Death Cross)
    # Check if EMA12 crosses EMA26
    if prev_row['EMA12'] < prev_row['EMA26'] and last_row['EMA12'] > last_row['EMA26']:
        signals.append("EMA Golden Cross (12 ตัด 26 ขึ้น - สัญญาณซื้อ)")
    elif prev_row['EMA12'] > prev_row['EMA26'] and last_row['EMA12'] < last_row['EMA26']:
        signals.append("EMA Death Cross (12 ตัด 26 ลง - สัญญาณขาย)")
    
    # Check price relative to EMA200 (Trend Filter)
    if 'EMA200' in df.columns and pd.notna(last_row['EMA200']):
        if last_row['close'] > last_row['EMA200']:
           signals.append("ราคาอยู่เหนือ EMA200 (แนวโน้มขาขึ้น)")
        elif last_row['close'] < last_row['EMA200']:
           signals.append("ราคาอยู่ต่ำกว่า EMA200 (แนวโน้มขาลง)")

    return signals
