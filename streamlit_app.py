import streamlit as st
import pandas as pd
import io
import json
import os
import requests
import datetime
import time
from collections import defaultdict, deque
from openpyxl import Workbook
from main import read_csv_with_header_row3, normalize_transaction, fifo_profit_loss

st.set_page_config(page_title="Crypto Tracker & Market Monitor", layout="wide")

def get_sparkline(prices, color="#43A047"):
    if not prices or len(prices) < 2: return ""
    min_p, max_p = min(prices), max(prices)
    range_p = max_p - min_p if max_p > min_p else 1
    
    width, height = 100, 30
    points = []
    for i, p in enumerate(prices):
        x = (i / (len(prices) - 1)) * width
        y = height - ((p - min_p) / range_p) * height
        points.append(f"{x},{y}")
    
    polyline = " ".join(points)
    return f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
        <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M 0,{height} {" ".join([f"L {p}" for p in points])} L {width},{height} Z" fill="{color}" fill-opacity="0.1" />
    </svg>
    """

def get_safety_window(time_str):
    try:
        dt = datetime.datetime.strptime(time_str, "%H:%M")
        end = (dt + datetime.timedelta(minutes=15)).strftime("%H:%M")
        return f"{time_str} - {end}"
    except:
        return time_str

# --- NAVIGATION ---
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to", [" Market Monitor", "💰 FIFO & Tax Summary"])

def show_fifo_page():
    st.title("💰 Crypto FIFO Profit/Loss Tracker")
    
    # Folder Path (Relative for portability)
    folder_path = "report"
    all_transactions = []

    # Process Folder Automatically
    if os.path.isdir(folder_path):
        from main import collect_all_csv
        if 'data_loaded' not in st.session_state:
            with st.spinner(f"Scanning subfolders in {folder_path}..."):
                txns = collect_all_csv(folder_path)
                st.session_state['all_txns'] = txns
                st.session_state['data_loaded'] = True
        
        all_transactions = st.session_state.get('all_txns', [])
    else:
        st.error(f"❌ Folder not found: {folder_path}")

    if all_transactions:
        normalized = [normalize_transaction(t) for t in all_transactions]
        
        # --- CALCULATIONS ---
        df_raw = pd.DataFrame(normalized)
        df_raw['created_date'] = pd.to_datetime(df_raw['created_date'], errors='coerce')
        df_raw['year'] = df_raw['created_date'].dt.year
        
        def fifo_tax_summary(transactions):
            by_currency = defaultdict(list)
            for t in transactions:
                if t["currency"]:
                    by_currency[t["currency"]].append(t)
            yearly_results = defaultdict(lambda: defaultdict(float))
            for coin, txns in by_currency.items():
                txns.sort(key=lambda x: x["created_date"])
                buy_queue = deque()
                for t in txns:
                    side = t["side"].lower()
                    amount = t["amount"]
                    price = t["thb_exec_price"]
                    try:
                        txn_date = pd.to_datetime(t["created_date"])
                        txn_year = txn_date.year
                    except:
                        txn_year = 0
                    if side == "buy":
                        buy_queue.append({"amount": amount, "price": price})
                    elif side == "sell":
                        sell_amount = amount
                        sell_price = price
                        while sell_amount > 0 and buy_queue:
                            buy_lot = buy_queue[0]
                            qty_used = min(sell_amount, buy_lot["amount"])
                            cost_basis = qty_used * buy_lot["price"]
                            proceeds = qty_used * sell_price
                            profit = proceeds - cost_basis
                            yearly_results[txn_year][coin] += profit
                            buy_lot["amount"] -= qty_used
                            if buy_lot["amount"] <= 0:
                                buy_queue.popleft()
                            sell_amount -= qty_used
            return yearly_results

        tax_summary = fifo_tax_summary(normalized)
        profit_data = fifo_profit_loss(normalized)
        total_profit = sum(profit_data.values())

        # --- TOP SUMMARY SECTION ---
        st.subheader("📑 Tax Reporting Dashboard (ยื่นภาษี ภ.ง.ด.)")
        
        if tax_summary:
            years = sorted(tax_summary.keys(), reverse=True)
            col_sel, col_empty = st.columns([1, 2])
            selected_year = col_sel.selectbox("เลือกปีที่ต้องการดูสรุปภาษี:", years)
            
            year_data = tax_summary[selected_year]
            year_total_profit = sum(year_data.values())
            
            c1, c2, c3 = st.columns(3)
            c1.metric(f"กำไรสุทธิในปี {selected_year}", f"{year_total_profit:,.2f} THB")
            c2.metric("เหรียญที่ขาย (ปีนี้)", len(year_data))
            c3.metric("กำไรสะสมทั้งหมด (FIFO)", f"{total_profit:,.2f} THB")
            
            with st.expander(f"📁 ดูรายละเอียดกำไรรายเหรียญ ปี {selected_year}", expanded=True):
                year_df = pd.DataFrame(list(year_data.items()), columns=["Currency", "Realized Profit (THB)"])
                year_df = year_df[year_df["Realized Profit (THB)"] != 0].sort_values(by="Realized Profit (THB)", ascending=False)
                st.table(year_df)
            
            st.caption("⚠️ หมายเหตุ: ข้อมูลภาษีใช้เกณฑ์กำไรที่เกิดขึ้นจริง (Realized Profit) ตามปีปฏิทินที่ขาย")
        
        st.divider()

        # --- DETAILED DATA SECTION ---
        st.subheader("📊 Transaction Overview")
        st.dataframe(df_raw, width="stretch")
        
        col_l, col_r = st.columns(2)
        with col_l:
            with st.expander("📂 View breakdown by Source (Files/Folders)"):
                source_counts = df_raw['source'].value_counts().reset_index()
                source_counts.columns = ['Source Path', 'Transaction Count']
                st.table(source_counts)
        
        with col_r:
            with st.expander("📈 Overall Profit Summary (All Time)"):
                profit_overall_df = pd.DataFrame(list(profit_data.items()), columns=["Currency", "Total Profit (THB)"])
                st.table(profit_overall_df)

        # --- EXPORT SECTION ---
        st.subheader("📥 Export Results")
        json_str = json.dumps(normalized, ensure_ascii=False, indent=2)
        st.download_button(label="Download Transactions (JSON)", data=json_str, file_name="transactions.json", mime="application/json", key="dl_json")
        
        output = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Profit Summary"
        ws.append(["Currency", "Net Profit (THB)"])
        for coin, curr_profit in profit_data.items():
            ws.append([coin, curr_profit])
        ws.append([])
        ws.append(["Total", total_profit])
        wb.save(output)
        st.download_button(label="Download Profit Summary (Excel)", data=output.getvalue(), file_name="profit_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_excel")
    else:
        st.warning("No transactions found in the report folder. Please check your source files.")

def show_monitor_page():
    st.markdown("""
        <style>
        .main-header { font-size: 2.5rem; font-weight: 700; color: #1E88E5; margin-bottom: 0.5rem; }
        .sub-header { font-size: 1.2rem; color: #546E7A; margin-bottom: 2rem; }
        .card { 
            padding: 1.5rem; border-radius: 10px; border: 1px solid #E0E0E0; 
            background-color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 1rem;
        }
        .metric-label { font-size: 0.9rem; color: #757575; font-weight: 500; }
        .metric-value { font-size: 1.4rem; font-weight: 700; color: #212121; }
        .peak-time { color: #43A047; font-weight: 600; }
        .bottom-time { color: #E53935; font-weight: 600; }
        
        .ticker-card {
            background: white; padding: 10px; border-radius: 8px; 
            border-left: 4px solid #1E88E5; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 5px; /* Added margin-bottom for spacing */
        }
        .day-card {
            text-align: center; padding: 10px; border: 1px solid #EEE; 
            border-radius: 8px; background: #F9F9F9; margin-bottom: 5px;
        }
        
        /* Professional Ticker Layout */
        .ticker-container {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 10px 0;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .ticker-header {
            display: flex;
            padding: 5px 15px;
            font-size: 0.75rem;
            color: #777;
            font-weight: 500;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .ticker-row {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            gap: 12px;
        }
        .ticker-row:last-child { border-bottom: none; }
        
        .ticker-coin-info { display: flex; align-items: center; gap: 12px; width: 150px; }
        .ticker-logo { width: 32px; height: 32px; border-radius: 50%; }
        .ticker-symbol { font-weight: 700; font-size: 1.1rem; color: #FFF; }
        .ticker-volume { font-size: 0.75rem; color: #777; margin-top: 2px; }
        
        .ticker-sparkline-box { flex: 1; height: 30px; display: flex; align-items: center; justify-content: center; opacity: 0.8; }
        .ticker-price-box { width: 140px; text-align: right; }
        .ticker-last-price { font-weight: 700; font-size: 1.15rem; color: #FFF; }
        .ticker-pct { font-size: 0.85rem; font-weight: 600; margin-top: 2px; }
        
        @media (max-width: 768px) {
            .ticker-coin-info { width: 110px; gap: 8px; }
            .ticker-logo { width: 28px; height: 28px; }
            .ticker-symbol { font-size: 1rem; }
            .ticker-sparkline-box { min-width: 60px; }
            .ticker-price-box { width: 110px; }
            .ticker-last-price { font-size: 1rem; }
            .ticker-header { display: none; }
            .ticker-row { padding: 12px 10px; gap: 8px; }
        }
        
        /* Playbook Styles - Frosted Glass (Weather App Style) */
        .playbook-container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 10px;
            margin-bottom: 20px;
        }
        .playbook-row {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            gap: 15px;
        }
        .playbook-row:last-child { border-bottom: none; }
        
        .playbook-day { width: 60px; font-weight: 700; font-size: 1.1rem; }
        .playbook-icon { width: 30px; text-align: center; font-size: 1.4rem; }
        .playbook-price { width: 80px; text-align: left; font-weight: 600; font-size: 1rem; color: #90A4AE; }
        .playbook-range { flex: 1; height: 4px; background: rgba(255,255,255,0.1); border-radius: 10px; position: relative; margin: 0 10px; }
        .playbook-range-fill { 
            position: absolute; height: 100%; border-radius: 10px;
            background: linear-gradient(90deg, #E53935, #43A047); 
        }
        .playbook-target { width: 90px; text-align: right; font-weight: 700; font-size: 1.15rem; color: #FFFFFF; }
        
        @media (max-width: 768px) {
            .playbook-day { width: 45px; font-size: 1rem; }
            .playbook-icon { width: 25px; font-size: 1.2rem; }
            .playbook-price { width: 60px; font-size: 0.9rem; }
            .playbook-target { width: 75px; font-size: 1rem; }
            .playbook-row { padding: 10px 10px; gap: 8px; }
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-header">📈 Market Insight Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Advanced Pattern Analysis & Real-time Market Monitoring</div>', unsafe_allow_html=True)

    symbols = ['BTC_THB', 'ETH_THB', 'SCRT_THB', 'POW_THB', 'SPEC_THB']
    ticker_url = "https://api.bitkub.com/api/v3/market/ticker"
    
    # Initialize Session State
    if 'monitor_data_v2_loaded' not in st.session_state:
        st.session_state.update({
            'monitor_data_v2_loaded': False,
            'ticker_res': {},
            'monitor_data_v2': [],
            'minute_data_v2_loaded': False,
            'minute_data_v2': [],
            'dow_patterns': {}, # Day of Week (Monday-Sunday) patterns
            'dow_data_loaded': False
        })

    # Sidebar Tools
    with st.sidebar:
        st.divider()
        if st.button("🔄 Force Refresh Market Data", use_container_width=True, type="primary"):
            st.session_state['monitor_data_v2_loaded'] = False
            st.session_state['minute_data_v2_loaded'] = False
            st.session_state['dow_data_loaded'] = False
            st.rerun()

    # --- Data Acquisition ---
    if not st.session_state['monitor_data_v2_loaded'] or not st.session_state['dow_data_loaded']:
        try:
            ticker_data_list = requests.get(ticker_url).json()
            st.session_state['ticker_res'] = {item['symbol']: item for item in ticker_data_list}
            
            end_ts = int(time.time())
            start_ts_1y = end_ts - (1 * 365 * 24 * 60 * 60)
            if not st.session_state['monitor_data_v2_loaded']:
                # Monthly/Day History (1 Year) - Resolution 1D
                fetched_mon = []
                with st.spinner("Analyzing 1-Year Market Patterns (Daily)..."):
                    for sym in symbols:
                        h_url = f"https://api.bitkub.com/tradingview/history?symbol={sym}&resolution=1D&from={start_ts_1y}&to={end_ts}"
                        res = requests.get(h_url).json()
                        if res.get('s') == 'ok':
                            h_df = pd.DataFrame({'t': res['t'], 'h': res['h'], 'l': res['l'], 'c': res['c']}) # Added 'c' for close
                            h_df['date'] = pd.to_datetime(h_df['t'], unit='s')
                            h_df['month'] = h_df['date'].dt.strftime('%Y-%m')
                            for month, group in h_df.groupby('month'):
                                max_row = group.loc[group['h'].idxmax()]
                                min_row = group.loc[group['l'].idxmin()]
                                fetched_mon.append({
                                    'Symbol': sym.replace("THB_", ""), 'Month': month,
                                    'High': max_row['h'], 'Date High': max_row['date'].strftime('%Y-%m-%d'), 'Day High': max_row['date'].day,
                                    'Low': min_row['l'], 'Date Low': min_row['date'].strftime('%Y-%m-%d'), 'Day Low': min_row['date'].day
                                })
                st.session_state['monitor_data_v2'] = fetched_mon
                st.session_state['monitor_data_v2_loaded'] = True
        except Exception as e:
            st.error(f"Error fetching historical data: {e}")

    # Minute Data Acquisition (30 Days) - resolution 1
    if not st.session_state['minute_data_v2_loaded']:
        try:
            end_ts = int(time.time())
            start_ts = end_ts - (30 * 24 * 60 * 60)
            fetched_min = []
            with st.spinner("Analyzing Minute-Level Tactical Patterns..."):
                for sym in symbols:
                    h_url = f"https://api.bitkub.com/tradingview/history?symbol={sym}&resolution=1&from={start_ts}&to={end_ts}"
                    res = requests.get(h_url).json()
                    if res.get('s') == 'ok':
                        m_df = pd.DataFrame({'t': res['t'], 'h': res['h'], 'l': res['l'], 'c': res['c'], 'v': res.get('v', [0]*len(res['t']))}) # Added 'c' for close
                        m_df['dt'] = pd.to_datetime(m_df['t'], unit='s', utc=True).dt.tz_convert('Asia/Bangkok')
                        m_df['date'] = m_df['dt'].dt.date
                        m_df['time'] = m_df['dt'].dt.strftime('%H:%M')
                        m_df['volume'] = m_df['v']
                        m_df['Close'] = m_df['c'] # Ensure 'Close' column exists for sparkline
                        for date, group in m_df.groupby('date'):
                            max_r = group.loc[group['h'].idxmax()]
                            min_r = group.loc[group['l'].idxmin()]
                            fetched_min.append({
                                'Symbol': sym.replace("THB_", ""), 'Date': date, 'DayName': m_df[m_df['date']==date]['dt'].iloc[0].day_name(),
                                'High': max_r['h'], 'Time High': max_r['time'], 'Vol at High': max_r['v'],
                                'Low': min_r['l'], 'Time Low': min_r['time'], 'Vol at Low': min_r['v'],
                                'Close': group['c'].iloc[-1] # Add last close price for the day
                            })
            
            st.session_state['minute_data_v2'] = fetched_min
            
            # Generate Day-of-Week patterns from minute data for maximum precision
            df_min = pd.DataFrame(fetched_min)
            
            # Get latest prices for normalization
            ticker_list = requests.get("https://api.bitkub.com/api/v3/market/ticker").json()
            curr_prices = {item['symbol'].replace("_THB", "").replace("THB_", ""): float(item['last']) for item in ticker_list}


            dow_map = {}
            for sym in df_min['Symbol'].unique():
                s_df = df_min[df_min['Symbol'] == sym].sort_values('Date').copy()
                c_price = curr_prices.get(sym, s_df['High'].iloc[-1])
                
                # Calculate daily returns for all dates to get day-specific trends
                s_df['MidPrice'] = (s_df['High'] + s_df['Low']) / 2
                s_df['DailyReturn'] = s_df['MidPrice'].pct_change()
                
                daily_drift = s_df['DailyReturn'].mean() if not s_df['DailyReturn'].dropna().empty else 0
                
                # Helper to cluster into 15-min buckets
                def get_bucket(t_str):
                    h, m = map(int, t_str.split(':'))
                    return f"{h:02d}:{(m // 15) * 15:02d}"
                
                s_df = s_df.copy()
                s_df['Bucket High'] = s_df['Time High'].apply(get_bucket)
                s_df['Bucket Low'] = s_df['Time Low'].apply(get_bucket)
                
                # Calculate Daily Normalization Factors
                # ratio = value / daily_avg_price
                s_df['DailyAvg'] = s_df.groupby('Date')[['High', 'Low']].transform('mean').mean(axis=1)
                s_df['HighRatio'] = s_df['High'] / s_df['DailyAvg']
                s_df['LowRatio'] = s_df['Low'] / s_df['DailyAvg']
                
                patterns = {}
                for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                    d_df = s_df[s_df['DayName'] == d]
                    if not d_df.empty:
                        # Find Mode Bucket
                        peak_bucket = d_df['Bucket High'].mode()[0]
                        bottom_bucket = d_df['Bucket Low'].mode()[0]
                        
                        # Confidence Score based on Bucket frequency
                        conf_peak = (d_df['Bucket High'] == peak_bucket).sum() / len(d_df) * 100
                        conf_bottom = (d_df['Bucket Low'] == bottom_bucket).sum() / len(d_df) * 100
                        
                        # Day-specific trend (average return for this day of the week)
                        day_trend = d_df['DailyReturn'].mean() if not d_df['DailyReturn'].dropna().empty else daily_drift
                        
                        # --- VOLUME-WEIGHTED PRICE TARGETS ---
                        peak_rows = d_df[d_df['Bucket High'] == peak_bucket]
                        bottom_rows = d_df[d_df['Bucket Low'] == bottom_bucket]
                        
                        # Use Volume at High/Low as weights
                        def get_weighted_ratio(rows, ratio_col, vol_col):
                            total_vol = rows[vol_col].sum()
                            if total_vol > 0:
                                return (rows[ratio_col] * rows[vol_col]).sum() / total_vol
                            return rows[ratio_col].mean()

                        h_ratio_weighted = get_weighted_ratio(peak_rows, 'HighRatio', 'Vol at High')
                        l_ratio_weighted = get_weighted_ratio(bottom_rows, 'LowRatio', 'Vol at Low')
                        
                        avg_h = c_price * h_ratio_weighted
                        max_h = c_price * peak_rows['HighRatio'].max()
                        
                        avg_l = c_price * l_ratio_weighted
                        min_l = c_price * bottom_rows['LowRatio'].min()
                        
                        profit_pct = ((avg_h - avg_l) / avg_l) * 100 if avg_l > 0 else 0
                        patterns[d] = {
                            'Peak': peak_bucket,
                            'Bottom': bottom_bucket,
                            'Avg High': avg_h,
                            'Max High': max_h,
                            'Avg Low': avg_l,
                            'Min Low': min_l,
                            'Conf Peak': conf_peak,
                            'Conf Bottom': conf_bottom,
                            'Profit Pct': profit_pct,
                            'High Ratio': h_ratio_weighted,
                            'Low Ratio': l_ratio_weighted,
                            'Trend': day_trend
                        }
                dow_map[sym] = {
                    'patterns': patterns,
                    'daily_drift': daily_drift
                }
            
            st.session_state['dow_patterns'] = dow_map
            st.session_state['minute_data_v2_loaded'] = True
            st.session_state['dow_data_loaded'] = True
        except Exception as e:
            st.error(f"Error fetching minute data: {e}")

    # --- UI Rendering ---
    ticker_res = st.session_state.get('ticker_res', {})
    
    # --- Weekly Trading Playbook (Day-of-Week) --- WEATHER APP STYLE
    st.markdown('<div class="main-header" style="font-size: 1.8rem; border-bottom: 2px solid #1E88E5; margin-bottom: 1rem;">📅 Weekly Trading Playbook</div>', unsafe_allow_html=True)
    
    mon_df = pd.DataFrame(st.session_state['monitor_data_v2']) if st.session_state['monitor_data_v2'] else pd.DataFrame()
    min_df = pd.DataFrame(st.session_state['minute_data_v2']) if st.session_state['minute_data_v2'] else pd.DataFrame()
    dow_patterns = st.session_state.get('dow_patterns', {})

    if dow_patterns:
        playbook_symbols = list(dow_patterns.keys())
        default_index = 0
        if "SPEC_THB" in playbook_symbols:
            default_index = playbook_symbols.index("SPEC_THB")
        elif "SPEC" in playbook_symbols:
            default_index = playbook_symbols.index("SPEC")

        selected_sym = st.selectbox("Select Currency for Daily Guide", playbook_symbols, index=default_index)
        symbol_data = dow_patterns.get(selected_sym, {})
        patterns_data = symbol_data.get('patterns', {})
        
        days_full = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_th_short = {'Monday':'จ.', 'Tuesday':'อ.', 'Wednesday':'พ.', 'Thursday':'พฤ.', 'Friday':'ศ.', 'Saturday':'ส.', 'Sunday':'อา.'}
        
        today_idx = datetime.date.today().weekday()
        days_sorted = days_full[today_idx:] + days_full[:today_idx]
        
        # Start Playbook Glass Container
        playbook_html = '<div class="playbook-container">'
        
        for i_offset, day in enumerate(days_sorted):
            p = patterns_data.get(day, {'Trend': 0, 'Low Ratio': 0.95, 'High Ratio': 1.05, 'Peak': '12:00', 'Bottom': '00:00'})
            drift = p.get('Trend', symbol_data.get('daily_drift', 0))
            
            # Trading Icons
            icon = "📈"
            if drift > 0.02: icon = "🚀"
            elif drift > 0: icon = "📈"
            elif drift > -0.02: icon = "📉"
            else: icon = "🐻"
            
            # Forecast
            today = datetime.date.today()
            forecast_date = today + datetime.timedelta(days=i_offset)
            c_price = float(ticker_res.get(selected_sym.replace("THB_", "")+"_THB", {}).get('last', 0))
            if c_price == 0: c_price = p.get('Avg High', 1)
            
            forecast_base = c_price * (1 + drift * i_offset)
            f_low = forecast_base * p['Low Ratio']
            f_high = forecast_base * p['High Ratio']
            
            # Range Bar Calc
            range_min = forecast_base * 0.9
            range_max = forecast_base * 1.1
            
            fill_left = ((f_low - range_min) / (range_max - range_min)) * 100
            fill_width = ((f_high - f_low) / (range_max - range_min)) * 100
            
            fill_left = max(0, min(90, fill_left))
            fill_width = max(5, min(100 - fill_left, fill_width))
            
            day_label = "วันนี้" if i_offset == 0 else day_th_short[day]
            
            playbook_html += f'<div class="playbook-row"><div class="playbook-day">{day_label}</div><div class="playbook-icon">{icon}</div><div class="playbook-price">{f_low:,.2f}</div><div class="playbook-range"><div class="playbook-range-fill" style="left: {fill_left}%; width: {fill_width}%;"></div></div><div class="playbook-target">{f_high:,.2f}</div></div>'
        
        playbook_html += '</div>'
        st.markdown(playbook_html, unsafe_allow_html=True)
        st.info("💡 **Tip**: แผนภาพแสดงช่วงราคาสูง-ต่ำที่คาดการณ์ตามสถิติรายวัน (อ้างอิงราคาปัจจุบัน + Trend)")
    else:
        st.info("Playbook is being generated...")

    # --- Real-time Ticker --- EXCHANGE STYLE
    ticker_res = st.session_state.get('ticker_res', {})
    min_df = pd.DataFrame(st.session_state['minute_data_v2']) if st.session_state['minute_data_v2'] else pd.DataFrame()
    
    ticker_html = """
    <div class="ticker-container">
        <div class="ticker-header">
            <div style="width: 150px">สินทรัพย์ / ปริมาณ (THB)</div>
            <div style="flex: 1; text-align: center">กราฟ 24 ชม.</div>
            <div style="width: 140px; text-align: right">ราคาล่าสุด / % 24 ชม.</div>
        </div>
    """
    
    # Common bitkub logo base
    logo_base = "https://static.bitkubstatic.com/static/images/icons/{}.png"
    
    for sym in symbols:
        if sym in ticker_res:
            data = ticker_res[sym]
            coin_only = sym.split('_')[0]
            pct = float(data['percent_change'])
            color = "#43A047" if pct >= 0 else "#E53935"
            volume = float(data.get('base_volume', 0)) * float(data['last']) # Approximate volume in THB
            vol_str = f"{volume/1e6:,.2f}M" if volume >= 1e6 else f"{volume/1e3:,.2f}K"
            
            # Sparkline
            spark_html = ""
            if not min_df.empty and coin_only in min_df['Symbol'].values: # Use coin_only for symbol matching
                s_min = min_df[min_df['Symbol'] == coin_only].tail(24) # Last 24 points
                prices = s_min['Close'].tolist()
                spark_html = get_sparkline(prices, color)
            
            ticker_html += f"""
            <div class="ticker-row">
                <div class="ticker-coin-info">
                    <img src="{logo_base.format(coin_only)}" class="ticker-logo" onerror="this.src='https://www.bitkub.com/static/images/icons/default.png'">
                    <div>
                        <div class="ticker-symbol">{coin_only}<span style="font-size:0.7rem; color:#666">/THB</span></div>
                        <div class="ticker-volume">ปริมาณ: {vol_str}</div>
                    </div>
                </div>
                <div class="ticker-sparkline-box">
                    {spark_html}
                </div>
                <div class="ticker-price-box">
                    <div class="ticker-last-price">{float(data['last']):,.2f}</div>
                    <div class="ticker-pct" style="color: {color}">{"+" if pct > 0 else ""}{pct}%</div>
                </div>
            </div>
            """
            
    ticker_html += "</div>"
    st.markdown(ticker_html, unsafe_allow_html=True)
    
    main_tabs = st.tabs(["💎 Strategic Overview", "🕒 Daily Detail", "📊 Historical Logs"])
    
    with main_tabs[0]:
        st.subheader("✨ Tactical High/Low Patterns")
        st.markdown("""
            สรุปสถิติเพื่อหาจังหวะเทรด:
            - **วันที่ (Day)**: วิเคราะห์จากสถิติรอบ **1 ปี**
            - **เวลา (Time)**: วิเคราะห์แนวโน้มล่าสุดรอบ **1 อาทิตย์** (แม่นยำระดับนาที)
        """)
        
        if not mon_df.empty and not min_df.empty:
            # Filter for last 7 days for Time patterns
            last_7_days = sorted(min_df['Date'].unique(), reverse=True)[:7]
            min_7d_df = min_df[min_df['Date'].isin(last_7_days)]
            
            for sym in sorted(mon_df['Symbol'].unique()):
                s_mon = mon_df[mon_df['Symbol'] == sym]
                s_min_7d = min_7d_df[min_7d_df['Symbol'] == sym]
                
                # Day pattern (1 year)
                high_day = s_mon['Day High'].mode()[0] if not s_mon.empty else "N/A"
                low_day = s_mon['Day Low'].mode()[0] if not s_mon.empty else "N/A"
                
                # Time pattern (1 week minute-level)
                high_time = s_min_7d['Time High'].mode()[0] if not s_min_7d.empty else "N/A"
                low_time = s_min_7d['Time Low'].mode()[0] if not s_min_7d.empty else "N/A"
                
                with st.container():
                    col1, col2, col3 = st.columns([1, 2, 2])
                    with col1:
                        st.markdown(f"### {sym}")
                    with col2:
                        st.markdown(f"""
                            <div class="card">
                                <span class="metric-label">📈 Peak Forecast</span><br/>
                                <span class="metric-value">วันที่ {high_day}</span> 
                                <span class="peak-time">@ {high_time}</span>
                                <div style="font-size:0.7rem; color:#999">Day: 1Y | Time: 7D Minute</div>
                            </div>
                        """, unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"""
                            <div class="card">
                                <span class="metric-label">📉 Bottom Forecast</span><br/>
                                <span class="metric-value">วันที่ {low_day}</span> 
                                <span class="bottom-time">@ {low_time}</span>
                                <div style="font-size:0.7rem; color:#999">Day: 1Y | Time: 7D Minute</div>
                            </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Generating insights (Analyzing historical data)...")


    with main_tabs[1]:
        st.subheader("�🕒 Minute-Level Time Distribution")
        if not min_df.empty:
            min_df['Hour'] = min_df['Time High'].apply(lambda x: int(x.split(':')[0]))
            c1, c2 = st.columns(2)
            with c1:
                st.write("📈 Hourly Peak Distribution")
                st.bar_chart(min_df['Hour'].value_counts().sort_index())
            with c2:
                st.write("📉 Hourly Bottom Distribution")
                min_df['Hour Low'] = min_df['Time Low'].apply(lambda x: int(x.split(':')[0]))
                st.bar_chart(min_df['Hour Low'].value_counts().sort_index())
            
            st.divider()
            st.subheader("📊 Recent Daily Tracker")
            dates = sorted(min_df['Date'].unique(), reverse=True)[:7]
            for d in dates:
                with st.expander(f"Data for {d.strftime('%Y-%m-%d')}"):
                    d_data = min_df[min_df['Date'] == d]
                    rows = []
                    for _, r in d_data.iterrows():
                        rows.append({
                            'Symbol': r['Symbol'],
                            'Highest (Time)': f"{r['High']:,.2f} ({r['Time High']})",
                            'Lowest (Time)': f"{r['Low']:,.2f} ({r['Time Low']})"
                        })
                    st.table(pd.DataFrame(rows))
        else:
            st.info("No distribution data.")

    with main_tabs[2]:
        st.subheader("📜 Historical Log Archive")
        if not mon_df.empty:
            sel_sym = st.selectbox("Filter History by Symbol", sorted(mon_df['Symbol'].unique()))
            s_hist = mon_df[mon_df['Symbol'] == sel_sym].sort_values('Month', ascending=False)
            st.table(s_hist[['Month', 'High', 'Date High', 'Low', 'Date Low']])










# Render Page
if page == "💰 FIFO & Tax Summary":
    show_fifo_page()
else:
    show_monitor_page()

