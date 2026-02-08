
import sys
import os

# Add current directory to path so we can import services/utils
sys.path.append(os.path.join(os.getcwd(), 'monitor'))

from services.bitkub_service import BitkubService
from utils.indicators import calculate_indicators, check_signals

def main():
    print("--- Starting Verification ---")
    
    bitkub = BitkubService()
    
    # 1. Test Get Symbols
    print("\n1. Testing Get Symbols...")
    symbols = bitkub.get_symbols()
    if symbols:
        print(f"✅ Success. Found {len(symbols)} symbols. Example: {symbols[0]['symbol']}")
        test_symbol = symbols[0]['symbol']
    else:
        print("❌ Failed to fetch symbols.")
        test_symbol = 'BTC_THB'

    # 2. Test Get Ticker
    print(f"\n2. Testing Get Ticker for {test_symbol}...")
    ticker = bitkub.get_ticker(test_symbol)
    if ticker:
        print("✅ Success. Ticker data received.")
    else:
        print("❌ Failed to fetch ticker.")

    # 3. Test Get Candles (1D)
    print(f"\n3. Testing Get Candles for {test_symbol} (1D)...")
    # Use fixed timestamp to ensure we get data regardless of system time skew
    # Jan 1 2023 to Feb 1 2024 (13 months) to ensure enough data for EMA200
    start_ts = 1672531200 # Jan 1 2023
    end_ts = 1706745600   # Feb 1 2024
    
    print("Testing with symbol from API (e.g. THB_BTC):")
    df = bitkub.get_candles(test_symbol, timeframe='1D', start_timestamp=start_ts, end_timestamp=end_ts)
    
    if df.empty:
        print("❌ Failed with API symbol. Trying inverted symbol...")
        # Try inverting
        if "THB_" in test_symbol:
            inv_symbol = f"{test_symbol.split('_')[1]}_THB"
        else:
            inv_symbol = test_symbol
            
        print(f"Testing with inverted symbol {inv_symbol}...")
        df = bitkub.get_candles(inv_symbol, timeframe='1D', start_timestamp=start_ts, end_timestamp=end_ts)
        
    if not df.empty:
        print(f"✅ Success. Received {len(df)} candles.")
        print(df.head(2))
        
        # 4. Test Indicators
        print("\n4. Testing Indicator Calculation...")
        df_ind = calculate_indicators(df)
        cols = df_ind.columns
        if 'RSI' in cols and 'EMA200' in cols:
            print("✅ Success. RSI and EMA columns added.")
            print(f"Last RSI: {df_ind['RSI'].iloc[-1]}")
        else:
            print("❌ Failed to calculate indicators.")
            
        # 5. Test Signals
        print("\n5. Testing Signal Detection...")
        signals = check_signals(df_ind)
        if signals:
            print(f"ℹ️ Signals detected: {signals}")
        else:
            print("ℹ️ No signals detected (this is normal if market is quiet).")
            
    else:
        print("❌ Failed to fetch candles.")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    main()
