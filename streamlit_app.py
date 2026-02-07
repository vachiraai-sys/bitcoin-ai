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

def get_safety_window(time_str, minutes=15):
    try:
        dt = datetime.datetime.strptime(time_str, "%H:%M")
        end = (dt + datetime.timedelta(minutes=minutes)).strftime("%H:%M")
        return f"{time_str} - {end}"
    except:
        return time_str

# --- NAVIGATION ---
st.sidebar.title("🧭 Navigation")
page = st.sidebar.radio("Go to", ["� Market Monitor", "�💰 FIFO & Tax Summary"])

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
        }
        .day-card {
            text-align: center; padding: 10px; border: 1px solid #EEE; 
            border-radius: 8px; background: #F9F9F9; margin-bottom: 5px;
        }
        
        /* Dark Theme Support */
        @media (prefers-color-scheme: dark) {
            .card {
                background-color: #1E1E1E;
                border-color: #333333;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
            .metric-label { color: #BBBBBB; }
            .metric-value { color: #FFFFFF; }
            .ticker-card {
                background: #1E1E1E;
                box-shadow: 0 1px 3px rgba(0,0,0,0.3);
            }
            .day-card {
                background: #2D2D2D;
                border-color: #444444;
                color: #EEEEEE;
            }
            .sub-header { color: #90A4AE; }
            .day-card .day-label { color: #64B5F6 !important; }
        }
        .profit-badge {
            background: #E8F5E9; color: #2E7D32; padding: 2px 6px; 
            border-radius: 4px; font-size: 0.7rem; font-weight: 700;
        }
        .conf-badge {
            font-size: 0.6rem; color: #9E9E9E; font-weight: 500;
        }
        
        /* Tablet (iPad) Optimizations */
        @media (min-width: 769px) and (max-width: 1024px) {
            .main-header { font-size: 2.2rem; }
            .sub-header { font-size: 1.1rem; margin-bottom: 1.5rem; }
            .card { padding: 1.2rem; }
            .metric-value { font-size: 1.2rem; }
            .day-card { padding: 8px; font-size: 0.9rem; }
            .day-card .day-label { font-size: 1rem; }
            .price-section { font-size: 0.8rem; }
        }

        /* Mobile Optimizations */
        @media (max-width: 768px) {
            .main-header { font-size: 1.8rem; }
            .sub-header { font-size: 1rem; margin-bottom: 1rem; }
            .card { padding: 1rem; margin-bottom: 0.5rem; }
            .metric-value { font-size: 1.1rem; }
            .metric-label { font-size: 0.8rem; }
            .ticker-card { padding: 8px; }
            .day-card { 
                padding: 10px; display: flex; justify-content: space-between; 
                align-items: center; text-align: left; 
            }
            .day-card hr { display: none; }
            .day-card .day-label { width: 70px; font-weight: 700; color: #1E88E5; flex-shrink: 0; }
            .day-card .price-section { flex: 1; text-align: right; }
            .profit-badge { font-size: 0.6rem; padding: 1px 4px; }
            .conf-badge { font-size: 0.55rem; }
            .stTabs [data-baseweb="tab-list"] { gap: 10px; }
            .stTabs [data-baseweb="tab"] { padding: 5px 10px; }
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
                            h_df = pd.DataFrame({'t': res['t'], 'h': res['h'], 'l': res['l']})
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
                        m_df = pd.DataFrame({'t': res['t'], 'h': res['h'], 'l': res['l'], 'v': res.get('v', [0]*len(res['t']))})
                        m_df['dt'] = pd.to_datetime(m_df['t'], unit='s', utc=True).dt.tz_convert('Asia/Bangkok')
                        m_df['date'] = m_df['dt'].dt.date
                        m_df['time'] = m_df['dt'].dt.strftime('%H:%M')
                        m_df['volume'] = m_df['v']
                        for date, group in m_df.groupby('date'):
                            max_r = group.loc[group['h'].idxmax()]
                            min_r = group.loc[group['l'].idxmin()]
                            fetched_min.append({
                                'Symbol': sym.replace("THB_", ""), 'Date': date, 'DayName': m_df[m_df['date']==date]['dt'].iloc[0].day_name(),
                                'High': max_r['h'], 'Time High': max_r['time'], 'Vol at High': max_r['v'],
                                'Low': min_r['l'], 'Time Low': min_r['time'], 'Vol at Low': min_r['v']
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
    
    # --- Weekly Trading Playbook (Day-of-Week) --- MOVED TO TOP
    st.markdown('<div class="main-header" style="font-size: 1.8rem; border-bottom: 2px solid #1E88E5; margin-bottom: 1rem;">📅 Weekly Trading Playbook (Day-of-Week)</div>', unsafe_allow_html=True)
    
    mon_df = pd.DataFrame(st.session_state['monitor_data_v2']) if st.session_state['monitor_data_v2'] else pd.DataFrame()
    min_df = pd.DataFrame(st.session_state['minute_data_v2']) if st.session_state['minute_data_v2'] else pd.DataFrame()
    dow_patterns = st.session_state.get('dow_patterns', {})

    if dow_patterns:
        # Auto-select SPEC (index 4 in symbols if using symbols, or find index in list)
        playbook_symbols = list(dow_patterns.keys())
        default_index = 0
        if "SPEC_THB" in playbook_symbols:
            default_index = playbook_symbols.index("SPEC_THB")
        elif "SPEC" in playbook_symbols:
            default_index = playbook_symbols.index("SPEC")

        selected_sym = st.selectbox("Select Currency for Daily Guide", playbook_symbols, index=default_index)
        patterns = dow_patterns[selected_sym]
        
        cols = st.columns(7)
        days_full = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Reorder days to start from today (today is index 0 in this new list)
        today_idx = datetime.date.today().weekday()
        days = days_full[today_idx:] + days_full[:today_idx]
        
        day_th = {'Monday':'จันทร์', 'Tuesday':'อังคาร', 'Wednesday':'พุธ', 'Thursday':'พฤหัส', 'Friday':'ศุกร์', 'Saturday':'เสาร์', 'Sunday':'อาทิตย์'}
        
        for i_offset, day in enumerate(days):
            with cols[i_offset]:
                # i here is the original index for forecast calculation
                original_idx = days_full.index(day)
                symbol_data = dow_patterns.get(selected_sym, {})
                patterns_day = symbol_data.get('patterns', {})
                
                p = patterns_day.get(day, {'Peak': 'N/A', 'Bottom': 'N/A', 'Avg High': 0, 'Max High': 0, 'Avg Low': 0, 'Min Low': 0, 'Conf Peak': 0, 'Conf Bottom': 0, 'Profit Pct': 0, 'High Ratio': 0, 'Low Ratio': 0, 'Trend': 0})
                drift = p.get('Trend', symbol_data.get('daily_drift', 0))
                
                # --- FORWARD LOOKING FORECAST ---
                today = datetime.date.today()
                # Use i_offset to calculate days ahead (0 for today, 1 for tomorrow, etc.)
                days_ahead = i_offset
                # Wait, if i_offset is 0, it's today. But the original code had:
                # days_ahead = (original_idx - today.weekday() + 7) % 7
                # if days_ahead == 0: days_ahead = 7
                # We want the *next* occurrence if it's in the past, but since we start from today,
                # i_offset 0 is today, i_offset 1 is tomorrow, etc.
                
                forecast_date = today + datetime.timedelta(days=days_ahead)
                
                c_price = ticker_res.get(selected_sym.replace("THB_", "")+"_THB", {}).get('last', p['Avg High'])
                forecast_base = float(c_price) * (1 + drift * days_ahead)
                
                f_high = forecast_base * p['High Ratio']
                f_low = forecast_base * p['Low Ratio']
                
                st.markdown(f"""
                    <div class="day-card" style="position:relative; border-top: 3px solid #1E88E5">
                        <div class="day-label" style="font-size:0.8rem">
                            {day_th[day]}<br/>
                            <span style="font-size:0.65rem; color:#666">{forecast_date.strftime('%d %b')}</span>
                        </div>
                        <hr style="margin:5px 0"/>
                        <div class="price-section">
                            <span style="font-size:0.6rem; color:#43A047; font-weight:700">🔮 Forecast High ({get_safety_window(p['Peak'])})</span><br/>
                            <span style="font-size:1.0rem; font-weight:700; color:#2E7D32">{f_high:,.2f}</span>
                        </div>
                        <div class="price-section">
                            <span style="font-size:0.6rem; color:#E53935; font-weight:700">🔮 Forecast Low ({get_safety_window(p['Bottom'])})</span><br/>
                            <span style="font-size:1.0rem; font-weight:700; color:#C62828">{f_low:,.2f}</span>
                        </div>
                        <div style="font-size:0.55rem; color:#999; margin-top:5px">
                            Trend: {drift*100:+.2f}%/day
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.info("💡 **Tip**: ใช้ข้อมูลนี้เพื่อดูว่าโดยปกติแล้วในแต่ละวัน ราคาของเหรียญนี้มักจะพุ่งหรือดิ่งในช่วงเวลาใด เพื่อวางแผนการเข้าซื้อ/ขายล่วงหน้า")
    else:
        st.info("Playbook is being generated...")

    st.divider()
    st.subheader("⚡ Real-time Ticker")
    t_cols = st.columns(len(symbols))
    for i, sym in enumerate(symbols):
        if sym in ticker_res:
            data = ticker_res[sym]
            color = "#43A047" if float(data['percent_change']) >= 0 else "#E53935"
            with t_cols[i]:
                st.markdown(f"""
                    <div class="ticker-card" style="border-left-color: {color}">
                        <div style="font-size:0.7rem; color:#666">{sym.replace("_THB", "")}</div>
                        <div style="font-size:1.1rem; font-weight:700">{float(data['last']):,.2f}</div>
                        <div style="font-size:0.7rem; color:{color}">{data['percent_change']}%</div>
                    </div>
                """, unsafe_allow_html=True)

    st.divider()
    
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

