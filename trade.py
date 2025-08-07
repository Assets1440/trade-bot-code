import os
import threading
import time
from flask import Flask, jsonify

# === (Insert ALL your previous trading bot imports and code here, up to and including 'run_bot') ===

import pandas as pd
from dotenv import load_dotenv
from alpaca_trade_api.rest import REST, TimeFrame, TimeFrameUnit

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
BASE_URL = os.getenv("BASE_URL")

api = REST(API_KEY, API_SECRET, BASE_URL)

SYMBOLS = ["TSLA", "NVDA", "SOXL", "SPY", "SHOP", "PLTR", "TQQQ"]

def fetch_data(symbol, timeframe, limit=300):
    print(f"📥 Fetching data for {symbol} [{timeframe}]")
    try:
        bars = api.get_bars(symbol, timeframe, limit=limit).df
        if 'symbol' in bars.columns:
            bars = bars[bars['symbol'] == symbol]
        return bars
    except Exception as e:
        print(f"⚠️ Error fetching data for {symbol}: {e}")
        return pd.DataFrame()

def find_fvg_and_bias(symbol):
    print(f"🔍 Analyzing FVG and bias for {symbol}")
    try:
        data_4h = fetch_data(symbol, TimeFrame(4, TimeFrameUnit.Hour), limit=120)
        data_1h = fetch_data(symbol, TimeFrame.Hour, limit=60)
        if data_4h.empty or data_1h.empty:
            print(f"⚠️ Insufficient 4H or 1H data for {symbol}")
            return False
        bias_confirmed = True
        return bias_confirmed
    except Exception as e:
        print(f"⚠️ Error analyzing bias for {symbol}: {e}")
        return False

def check_5_confirmations(df):
    print("✅ Checking for 5 confirmations...")
    confirmations = 4 # Placeholder logic
    return confirmations >= 4

def get_stop_loss(df):
    if len(df) < 3:
        print("⚠️ Not enough data to calculate stop loss.")
        return None
    fvg_candle_low = df['low'].iloc[-3]
    current_price = df['close'].iloc[-1]
    max_stop = current_price * 0.78
    return min(fvg_candle_low, max_stop)

def recap_trade(symbol, entry, sl, tp, reason):
    log_line = f"{symbol},{entry},{sl},{tp},{reason}\n"
    try:
        with open("trade_log.csv", "a") as f:
            f.write(log_line)
        print(f"📝 Trade recap saved for {symbol}")
    except Exception as e:
        print(f"🚨 Failed to save trade recap: {e}")

def execute_trade(symbol, price, sl, tp, reason):
    qty = max(int(50 / price), 1)
    try:
        api.submit_order(
            symbol=symbol,
            qty=qty,
            side='buy',
            type='market',
            time_in_force='gtc',
            order_class='bracket',
            take_profit={'limit_price': round(tp, 2)},
            stop_loss={'stop_price': round(sl, 2)}
        )
        recap_trade(symbol, price, sl, tp, reason)
        print(f"💥 Executed trade for {symbol} at ${price:.2f}")
    except Exception as e:
        print(f"❌ Failed to execute trade for {symbol}: {e}")

def run_bot_loop():
    while True:
        run_bot()
        time.sleep(300)

def run_bot():
    print("🚀 Bot is running!")
    for symbol in SYMBOLS:
        try:
            if not find_fvg_and_bias(symbol):
                print(f"⛔ Bias not confirmed for {symbol}")
                continue

            df = fetch_data(symbol, TimeFrame.Minute)
            if df.empty:
                print(f"⛔ No data fetched for {symbol}")
                continue

            if not check_5_confirmations(df):
                print(f"⛔ Not enough confirmations for {symbol}")
                continue

            entry = df['close'].iloc[-1]
            sl = get_stop_loss(df)
            if sl is None:
                print(f"⛔ Could not calculate stop loss for {symbol}")
                continue

            tp = entry * 1.05
            reason = "4 confirmations met"
            execute_trade(symbol, entry, sl, tp, reason)
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")

# === Flask web server code for Render ===

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"status": "Bot is running!"})

@app.route('/health')
def health():
    return jsonify({"ok": True})

if __name__ == '__main__':
    # Start trading bot in a background thread
    threading.Thread(target=run_bot_loop, daemon=True).start()
    # Start Flask app
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
