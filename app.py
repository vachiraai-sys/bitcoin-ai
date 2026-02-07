import streamlit as st
import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime

# --- 1. Page Configuration & Custom CSS (Orange Theme) ---
st.set_page_config(
    page_title="Bitkub Trading Signals",
    page_icon="🍊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Orange Theme CSS
st.markdown("""
<style>
    /* Primary Color Accents */
    :root {
        --primary-color: #FF9F1C;
        --secondary-color: #FF5733;
        --background-color: #1E1E1E;
        --text-color: #FFFFFF;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #FF9F1C !important;
    }
    
    /* Buttons */
    div.stButton > button {
        background-color: #FF9F1C;
        color: white;
        border: none;
        border-radius: 5px;
        font-weight: bold;
    }
    div.stButton > button:hover {
        background-color: #FF5733;
        color: white;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #FF9F1C;
        font-weight: bold;
    }
    [data-testid="stMetricLabel"] {
        color: #E0E0E0;
    }
    
    /* Dataframes */
    [data-testid="stDataFrame"] {
        border: 1px solid #333;
    }
    
    /* Signal Badges */
    .signal-buy {
        background-color: #28a745;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
    }
    .signal-sell {
        background-color: #dc3545;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
    }
    .signal-wait {
        background-color: #6c757d;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-weight: bold;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. Configuration & Constants ---
SYMBOLS = [
    "SPEC_THB",
    "BTC_THB",
    "ETH_THB",
    "SCRT_THB",
    "POW_THB"
]

TIMEFRAME_MAPPING = {
    "1 Hour": "60",
    "1 Day": "1D"
}

API_BASE_URL = "https://api.bitkub.com"

# --- 3. Data Fetching Functions ---
@st.cache_data(ttl=30)  # Cache ticker data for 30 seconds
def get_ticker_data():
    """Fetches real-time ticker data from Bitkub API V3."""
    try:
        url = f"{API_BASE_URL}/api/v3/market/ticker"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # V3 returns a list of objects. Convert to dict for easier lookup.
        ticker_dict = {
            item['symbol']: {
                'last': float(item['last']),
                'percentChange': float(item['percent_change'])
            } for item in data
        }
        return ticker_dict
    except Exception as e:
        st.error(f"Error fetching ticker data: {e}")
        return None

@st.cache_data(ttl=60)  # Cache candles for 1 minute
def get_candles(symbol, timeframe_minutes):
    """Fetches OHLC data (candles) from Bitkub API (TradingView endpoint)."""
    try:
        # Calculate timestamps (Bitkub needs 'from' and 'to' in seconds)
        now = int(time.time())
        # Calculate numeric resolution for timestamp calculation
        res_int = 1440 if timeframe_minutes == '1D' else int(timeframe_minutes)
        start = now - (200 * res_int * 60)
        
        # NOTE: Bitkub uses a TradingView-style endpoint for candles
        # Endpoint: https://api.bitkub.com/tradingview/history
        url = f"{API_BASE_URL}/tradingview/history"
        
        params = {
            "symbol": symbol,
            "resolution": timeframe_minutes,
            "from": start,
            "to": now
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('s') != 'ok':
            return None
            
        # Convert to DataFrame
        # Bitkub TV structure: { "t": [], "o": [], "h": [], "l": [], "c": [], "v": [], "s": "ok" }
        df = pd.DataFrame({
            "timestamp": data['t'],
            "open": data['o'],
            "high": data['h'],
            "low": data['l'],
            "close": data['c'],
            "volume": data['v']
        })
        
        # Convert timestamp to datetime and close to float
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        return df
        
    except Exception as e:
        st.error(f"Error fetching candles for {symbol}: {e}")
        return None

# --- 4. Technical Analysis & Signal Logic ---
def analyze_market(df):
    """Calculates RSI, Bollinger Bands and determines trading signal."""
    if df is None or len(df) < 20:
        return None, "INSUFFICIENT_DATA"
    
    # Work on a copy to avoid modifying cached data and naming conflicts
    df = df.copy()
    
    # Calculate RSI (14)
    df.ta.rsi(length=14, append=True)
    
    # Calculate Bollinger Bands (20, 2)
    df.ta.bbands(length=20, std=2, append=True)
    
    # Column names can vary by system (e.g., BBL_20_2.0 vs BBL_20_2.0_2.0)
    # Use robust matching to find RSI and BB columns
    rsi_col = next((c for c in df.columns if c.startswith('RSI_14')), 'RSI_14')
    lower_band_col = next((c for c in df.columns if c.startswith('BBL_20')), 'BBL_20_2.0')
    upper_band_col = next((c for c in df.columns if c.startswith('BBU_20')), 'BBU_20_2.0')
    
    # Get latest row
    latest = df.iloc[-1]
    
    # Signal Logic
    signal = "NEUTRAL"
    reason = ""
    
    if rsi_col not in df.columns or lower_band_col not in df.columns:
        signal = "WAIT (Calc)"
    elif pd.isna(latest[rsi_col]) or pd.isna(latest[lower_band_col]):
        signal = "WAIT (Calc)"
    elif latest[rsi_col] < 30 and latest['close'] <= latest[lower_band_col]:
        signal = "BUY"
        reason = f"RSI({latest[rsi_col]:.1f}) < 30 & Price <= LowBB"
    elif latest[rsi_col] > 70 and latest['close'] >= latest[upper_band_col]:
        signal = "SELL"
        reason = f"RSI({latest[rsi_col]:.1f}) > 70 & Price >= UpBB"
    else:
        signal = "NEUTRAL"
    
    return df, signal

# --- 5. Main Dashboard Display ---
def main():
    st.title("🍊 Bitkub Crypto Trading Dashboard")
    st.markdown("Monitor prices and signals for specific coins using **RSI + Bollinger Bands** strategy.")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        timeframe_name = st.selectbox("Select Timeframe", list(TIMEFRAME_MAPPING.keys()), index=1)
        timeframe_val = TIMEFRAME_MAPPING[timeframe_name]
        
        if st.button("Refresh Data", use_container_width=True):
            st.rerun()
            
        st.info(f"**Strategy:**\n\n🟢 **BUY**: RSI < 30 & Price touches Lower Band\n\n🔴 **SELL**: RSI > 70 & Price touches Upper Band")
        st.markdown("---")
        st.markdown(f"**Current Time:** {datetime.now().strftime('%H:%M:%S')}")

    # Main Data Fetching
    with st.spinner("Fetching data from Bitkub API..."):
        ticker_data = get_ticker_data()
    
    if not ticker_data:
        st.error("Failed to load ticker data.")
        return

    # Dashboard Grid
    st.subheader(f"Market Overview ({timeframe_name})")
    
    cols = st.columns(len(SYMBOLS)) # Responsive columns
    
    # Store detailed data for the second section
    analysis_results = {}
    
    # Iterate through symbols to display cards
    for idx, symbol in enumerate(SYMBOLS):
        
        # Ticker Info
        if symbol not in ticker_data:
            with cols[idx % 3]: # Simple wrap logic if screen is small, though st.columns handles it
                st.warning(f"{symbol}: No Data")
            continue
            
        ticker = ticker_data[symbol]
        last_price = ticker['last']
        change_pct = ticker['percentChange']
        
        # Technical Analysis
        df = get_candles(symbol, timeframe_val)
        analyzed_df, signal = analyze_market(df)
        analysis_results[symbol] = (analyzed_df, signal)
        
        # Custom Card UI
        with cols[idx]:
            # Get display name (e.g., BTC from BTC_THB)
            display_name = symbol.split('_')[0]
            
            st.markdown(f"""
            <div style="background-color: #2D2D2D; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #444;">
                <h3 style="margin:0; color: #FF9F1C;">{display_name}</h3>
                <p style="font-size: 0.8em; color: #888;">{symbol}</p>
                <h2 style="margin:10px 0;">฿{last_price:,.2f}</h2>
                <p style="color: {'#28a745' if change_pct >= 0 else '#dc3545'}; font-size: 1.1em; font-weight: bold;">
                    {change_pct:+.2f}%
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Signal Badge
            if signal == "BUY":
                st.markdown(f'<div class="signal-buy">BUY SIGNAL</div>', unsafe_allow_html=True)
            elif signal == "SELL":
                st.markdown(f'<div class="signal-sell">SELL SIGNAL</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="signal-wait">{signal}</div>', unsafe_allow_html=True)
                
    st.markdown("---")

    # Detailed View
    st.subheader("Detailed Analysis")
    
    selected_symbol = st.selectbox("Select Coin for details", SYMBOLS)
    
    if selected_symbol in analysis_results:
        df, signal = analysis_results[selected_symbol]
        
        if df is not None:
            # Find column names dynamically
            rsi_col = next((c for c in df.columns if c.startswith('RSI_14')), 'RSI_14')
            lower_band_col = next((c for c in df.columns if c.startswith('BBL_20')), 'BBL_20_2.0')
            upper_band_col = next((c for c in df.columns if c.startswith('BBU_20')), 'BBU_20_2.0')

            # Show latest Indicator values
            latest = df.iloc[-1]
            rsi = latest.get(rsi_col, 0)
            upper = latest.get(upper_band_col, 0)
            lower = latest.get(lower_band_col, 0)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("RSI (14)", f"{rsi:.2f}")
            with c2:
                st.metric("Upper Band", f"{upper:,.2f}")
            with c3:
                st.metric("Lower Band", f"{lower:,.2f}")
                
            # Chart (Simple Streamlit Line Chart for Price & Bands)
            st.markdown("#### Price Action & Bollinger Bands")
            chart_data = df[['datetime', 'close', upper_band_col, lower_band_col]].copy()
            chart_data.set_index('datetime', inplace=True)
            st.line_chart(chart_data)
            
            # Raw Data
            with st.expander("View Raw Data"):
                st.dataframe(df.sort_values(by='datetime', ascending=False).head(50))
                
        else:
            st.write("No historical data available for analysis.")

if __name__ == "__main__":
    main()
