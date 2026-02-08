import streamlit as st
import pandas as pd
import time
from services.bitkub_service import BitkubService
from services.line_messaging import LineMessagingService  # New Service
from utils.indicators import calculate_indicators, check_signals
from utils.charts import create_advanced_chart, create_rsi_chart

import threading
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Bitkub Crypto Monitor",
    page_icon="📈",
    layout="wide"
)

# Initialize Services
bitkub = BitkubService()

# Initialize LINE Messaging Service (Singleton)
@st.cache_resource
def get_line_service():
    return LineMessagingService()

line_service = get_line_service()

# --- Background Monitor (Singleton) ---
class BackgroundMonitor:
    def __init__(self, line_service):
        self.line_service = line_service
        self.is_running = False
        self.last_alert_dict = {} # Thread-safe alert history
        self.symbols = ['BTC_THB', 'ETH_THB', 'SCRT_THB', 'POW_THB', 'SPEC_THB'] # Sync with main list if possible, or pass in
        self.thread = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print("Background Monitor Started!")

    def _run(self):
        while self.is_running:
            try:
                messages = []
                pending_updates = {}
                
                # 1. Loop through symbols
                for sym in self.symbols:
                    # Default Timeframe 1h for background monitoring
                    timeframe = "1h" 
                    try:
                        # Fetch Candles for Signals
                        df = bitkub.get_candles(sym, timeframe=timeframe)
                        
                        # Fetch Ticker for % Change
                        ticker = bitkub.get_ticker(sym)
                        percent_change = 0.0
                        if ticker and isinstance(ticker, list) and len(ticker) > 0:
                            percent_change = float(ticker[0].get('percent_change', 0))
                        
                        if not df.empty:
                            df = calculate_indicators(df)
                            sigs = check_signals(df)
                            
                            if sigs:
                                # Check duplicate alert
                                state_key = f"{sym}_{timeframe}_{df.index[-1]}"
                                if self.last_alert_dict.get(sym) != state_key:
                                    last_price = df['close'].iloc[-1]
                                    
                                    # Determine Action
                                    action = "เฝ้าระวัง"
                                    has_buy = any("สัญญาณซื้อ" in s or "แนวโน้มขาขึ้น" in s for s in sigs)
                                    has_sell = any("สัญญาณขาย" in s or "แนวโน้มขาลง" in s for s in sigs)
                                    if has_buy and not has_sell:
                                        action = "ซื้อ"
                                    elif has_sell and not has_buy:
                                        action = "ขาย"
                                    elif has_buy and has_sell:
                                        action = "ระมัดระวัง (Mixed)"
                                        
                                    # Format Message
                                    short_sym = sym.replace("_THB", "")
                                    change_sign = "+" if percent_change >= 0 else ""
                                    
                                    msg = f"🪙 {short_sym}: {last_price:,.2f} ({change_sign}{percent_change:.2f}%)\n"
                                    msg += f" - analyze : {action}\n"
                                    
                                    # Format specific alerts
                                    for s in sigs:
                                        icon = "🔸" # Default
                                        if "ซื้อ" in s or "ขาขึ้น" in s:
                                            icon = "🟢"
                                        elif "ขาย" in s or "ขาลง" in s:
                                            icon = "🔴"
                                        
                                        msg += f"  {icon} **แจ้งเตือน: {s}**\n"
                                    
                                    messages.append(msg)
                                    pending_updates[sym] = state_key
                    except Exception as e:
                        print(f"Bg Error {sym}: {e}")
                
                # 2. Send Batch Alert
                if messages and self.line_service:
                    full_msg = "🔔 สรุปราคา Crypto\n\n" + "\n".join(messages)
                    if self.line_service.send_message(full_msg):
                        print(f"Sent Batch Alert: {len(messages)} symbols")
                        self.last_alert_dict.update(pending_updates)

                # 3. Sleep for 60 seconds
                time.sleep(60)
                
            except Exception as e:
                print(f"Background Loop Error: {e}")
                time.sleep(60)

@st.cache_resource
def start_background_monitor(_line_service):
    if _line_service:
        monitor = BackgroundMonitor(_line_service)
        monitor.start()
        return monitor
    return None

# Start the background monitor immediately
if line_service:
    start_background_monitor(line_service)


def main():
    st.set_page_config(page_title="Bitkub Monitor", layout="wide")
    st.title("📈 Bitkub Crypto Monitor (ระบบติดตามแนวโน้มรายวัน)")

    # Sidebar
    st.sidebar.header("การตั้งค่า")
    
    # Custom Symbol List
    symbol_list = ['BTC_THB', 'ETH_THB', 'SCRT_THB', 'POW_THB', 'SPEC_THB']
    
    # Default to SPEC_THB
    default_symbol = 'SPEC_THB'
    default_idx = symbol_list.index(default_symbol) if default_symbol in symbol_list else 0
    
    selected_symbol = st.sidebar.selectbox("เลือกเหรียญ", symbol_list, index=default_idx)
    timeframe = st.sidebar.selectbox("ช่วงเวลา (Timeframe)", ["15m", "1h", "4h", "1D"], index=1) # Default 1h

    # Refresh Button
    if st.sidebar.button("รีเฟรชข้อมูล"):
        st.rerun()

    # Toggle Recent Trades to save bandwidth
    show_trades = st.sidebar.checkbox("แสดงการซื้อขายล่าสุด", value=False)


    # Main Content
    
    # Main Content
    
    # 1. Global Signal Dashboard (Responsive Layout)
    st.subheader(f"สถานะเหรียญ ({timeframe})")
    
    # Custom CSS for Responsive Grid
    # Custom CSS for Responsive Grid
    st.markdown("""
<style>
.signal-container {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    justify-content: center; /* Center on large screens, or flex-start */
}
.signal-card {
    flex: 1 1 200px; /* Grow, shrink, min-width 200px */
    padding: 15px;
    border-radius: 10px;
    color: white;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}
.signal-card:hover {
    transform: translateY(-5px);
}
.signal-card h4 {
    margin: 0;
    margin-bottom: 5px;
    font-size: 1.2rem;
    color: white;
}
.signal-card .price {
    font-size: 1.5rem;
    font-weight: bold;
    margin-bottom: 5px;
}
.signal-card .status {
    font-size: 0.9rem;
}
/* HTML Details/Summary Styling */
details > summary {
    list-style: none;
    cursor: pointer;
    font-size: 0.8rem;
    opacity: 0.8;
    margin-top: 5px;
}
details > summary::-webkit-details-marker {
    display: none;
}
</style>
""", unsafe_allow_html=True)

    # Dictionaries to store data for later use
    data_cache = {}
    
    # Prepare HTML strings
    cards_html = []
    
    # Batch Alert Storage
    batch_messages = []
    pending_alert_updates = {}
    
    # Progress bar (optional, might be distracting if fast, keeping it minimal)
    # progress_bar = st.progress(0)

    for i, sym in enumerate(symbol_list):
        try:
            # Fetch data (Sync loop, could be slow if many symbols but 5 is fine)
            df = bitkub.get_candles(sym, timeframe=timeframe)
            
            if not df.empty:
                df = calculate_indicators(df)
                data_cache[sym] = df
                
                last_price = df['close'].iloc[-1]
                sigs = check_signals(df)
                
                # Determine Color & Content
                box_color = "#262730" # Default Dark
                border_style = "1px solid #4e4e4e"
                status_icon = "✅"
                status_text = "ปกติ"
                details_html = ""

                if sigs:
                    border_style = "none"
                    has_buy = any("สัญญาณซื้อ" in s or "แนวโน้มขาขึ้น" in s for s in sigs)
                    has_sell = any("สัญญาณขาย" in s or "แนวโน้มขาลง" in s for s in sigs)
                    
                    if has_buy and not has_sell:
                        box_color = "#28a745" # Green
                    elif has_sell and not has_buy:
                        box_color = "#ff4b4b" # Red
                    elif has_buy and has_sell:
                        box_color = "#ffa726" # Orange
                    else:
                        box_color = "#ff4b4b" # Fallback Red
                    
                    status_icon = "⚠️"
                    status_text = f"{len(sigs)} สัญญาณ"
                    
                    # Create details list
                    list_items = "".join([f"<li style='text-align:left;'>{s}</li>" for s in sigs])
                    details_html = f"""
<details>
    <summary>▼ รายละเอียด</summary>
    <ul style="font-size: 0.8rem; padding-left: 20px; margin: 5px 0;">
        {list_items}
    </ul>
</details>
"""
                    
                # Construct HTML Card
                card = f"""
<div class="signal-card" style="background-color: {box_color}; border: {border_style};">
    <h4>{sym}</h4>
    <div class="price">{last_price:,.2f}</div>
    <div class="status">{status_icon} {status_text}</div>
    {details_html}
</div>
"""
                cards_html.append(card)
                
            else:
                # Error/No Data Card
                cards_html.append(f"""
<div class="signal-card" style="background-color: #333; border: 1px dashed red;">
    <h4>{sym}</h4>
    <div>No Data</div>
</div>
""")

        except Exception as e:
            print(f"Error scanning {sym}: {e}")
            cards_html.append(f"""
<div class="signal-card" style="background-color: #333;">
    <h4>{sym}</h4>
    <div>Error</div>
</div>
""")

    # Render CSS Grid
    if cards_html:
        st.markdown(f"""
<div class="signal-container">
{''.join(cards_html)}
</div>
""", unsafe_allow_html=True)
    
    st.markdown("---") # Separator

    # 3. Visualization for Selected Symbol
    col1, col2 = st.columns([3, 1])

    with col1:
        # Ticker Info
        ticker = bitkub.get_ticker(selected_symbol)
        if ticker and selected_symbol in ticker:
            data = ticker[selected_symbol]
            last_price = data['last']
            percent_change = data['percentChange']
            
            st.metric(
                label=f"ราคาล่าสุด {selected_symbol}",
                value=f"{last_price:,.2f} บาท",
                delta=f"{percent_change}%"
            )
        
        # Use cached data if available, else fetch (should be in cache)
        df = data_cache.get(selected_symbol)
        
        if df is None or df.empty:
             with st.spinner("กำลังดึงข้อมูลย้อนหลัง..."):
                df = bitkub.get_candles(selected_symbol, timeframe=timeframe)
                if not df.empty:
                    df = calculate_indicators(df)
        
        if df is not None and not df.empty:
            # Charts
            st.subheader("กราฟราคา & EMA (Price Action)")
            fig_price = create_advanced_chart(df, selected_symbol)
            st.plotly_chart(fig_price, width="stretch")
            
            st.subheader("ดัชนี RSI")
            fig_rsi = create_rsi_chart(df)
            st.plotly_chart(fig_rsi, width="stretch")
        else:
            st.warning("ไม่มีข้อมูลย้อนหลัง")

    with col2:
        if show_trades:
            st.subheader("การซื้อขายล่าสุด")
            trades = bitkub.get_recent_trades(selected_symbol)
            if trades:
                # Format trade data
                trade_data = []
                for t in trades[:15]: # Show last 15
                    trade_data.append({
                        "เวลา": datetime.fromtimestamp(t[0]).strftime('%H:%M:%S'),
                        "ราคา": f"{t[1]:,.2f}",
                        "จำนวน": f"{t[2]:.4f}",
                        "ประเภท": t[3].upper() # BUY/SELL
                    })
                st.table(pd.DataFrame(trade_data))
            else:
                st.write("ไม่มีข้อมูลการซื้อขายล่าสุด")
        else:
            st.info("💡 ปิดการแสดงผลการซื้อขายล่าสุด (ช่วยลดการใช้เน็ต)")

    # Auto Refresh Logic
    st.sidebar.markdown("---")
    if st.sidebar.checkbox("อัปเดตอัตโนมัติ (ทุก 1 นาที)", value=True):
        time.sleep(60)
        st.rerun()

if __name__ == "__main__":
    from datetime import datetime
    import time
    main()
