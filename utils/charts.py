
import plotly.graph_objects as go
import pandas as pd

def create_advanced_chart(df, symbol):
    """
    Create an interactive candlestick chart with indicators
    """
    if df.empty:
        return go.Figure()

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ))

    # EMA Lines
    if 'EMA12' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA12'], line=dict(color='orange', width=1), name='EMA12'))
    if 'EMA26' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA26'], line=dict(color='blue', width=1), name='EMA26'))
    if 'EMA200' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], line=dict(color='red', width=2), name='EMA200'))

    # Layout updates
    fig.update_layout(
        title=f"กราฟรายวัน {symbol}",
        yaxis_title='ราคา (บาท)',
        xaxis_rangeslider_visible=False,
        height=600,
        template='plotly_dark'
    )
    
    return fig

def create_rsi_chart(df):
    """
    Create a separate chart for RSI
    """
    if df.empty or 'RSI' not in df.columns:
        return go.Figure()
        
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple', width=2), name='RSI'))
    
    # Overbought/Oversold lines
    fig.add_hline(y=70, line_dash="dash", line_color="red")
    fig.add_hline(y=30, line_dash="dash", line_color="green")
    
    fig.update_layout(
        title="ดัชนี RSI (14)",
        yaxis_title="RSI",
        height=300,
        template='plotly_dark',
        yaxis=dict(range=[0, 100])
    )
    return fig
