# Crypto Tracker & Market Monitor 📈💰

A Streamlit application for tracking cryptocurrency market patterns and calculating FIFO-based profit/loss for tax reporting.

## 🌟 Features

### 1. 📈 Market Insight Dashboard
- **Real-time Ticker**: Monitor latest prices for BTC, ETH, SCRT, POW, and SPEC.
- **Weekly Trading Playbook**: Statistical analysis of Peak/Bottom patterns by day of week.
- **Tactical Patterns**: High/Low forecasts based on 1-year historical data and 7-day minute-level analysis.
- **Minute-Level Distribution**: Hourly analysis of price movements.

### 2. 💰 FIFO & Tax Summary
- **FIFO Calculation**: Automatic profit/loss calculation using the First-In-First-Out method.
- **Tax Reporting**: Yearly summary of realized profits for tax filing (ภ.ง.ด.).
- **Data Export**: Download results in JSON or Excel format.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Active internet connection (for Bitkub API)

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Place your transaction CSV files in the `report/` folder.

### Running the App

```bash
streamlit run streamlit_app.py
```

## 📁 Project Structure

- `streamlit_app.py`: Main application interface.
- `main.py`: Core logic for CSV processing and FIFO calculations.
- `report/`: (Ignored) Folder for input transaction files.
- `backup/`: (Ignored) Folder for local backups.
- `requirements.txt`: Python dependencies.

## 📝 Note
This application uses the Bitkub V3 API for real-time and historical market data.
