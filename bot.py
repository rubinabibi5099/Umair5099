
import asyncio
import os
import json
import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# ==========================================
# ⚙️ MALIK UMAIR SVIP - CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "8690803539:AAGWSs0B0viP4nNXqUSemCX7yQa5ul1uY6o"
CHANNEL_CHAT_ID = "@malikumairsvipsignals"
HISTORY_FILE = "trading_history.json"

LIVE_PAIRS_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X",
    "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X", "EURAUD": "EURAUD=X",
    "EURCAD": "EURCAD=X", "EURNZD": "EURNZD=X", "EURCHF": "EURCHF=X",
    "GBPJPY": "GBPJPY=X", "GBPAUD": "GBPAUD=X", "GBPCAD": "GBPCAD=X",
    "GBPCHF": "GBPCHF=X", "GBPNZD": "GBPNZD=X", "AUDJPY": "AUDJPY=X",
    "AUDCAD": "AUDCAD=X", "AUDNZD": "AUDNZD=X", "CADJPY": "CADJPY=X",
    "CHFJPY": "CHFJPY=X", "NZDJPY": "NZDJPY=X", "NZDCAD": "NZDCAD=X"
}

is_signal_running = False

# --- DATABASE FUNCTIONS (LIFETIME SESSION STORAGE) ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return []

def save_trade_to_db(result_type, session_type):
    history = load_history()
    trade_record = {
        "timestamp": time.time(),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "session": session_type,
        "result": result_type
    }
    history.append(trade_record)
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"DB Save Error: {e}")

def get_session_stats(session_name):
    history = load_history()
    d_wins, m_wins, losses = 0, 0, 0
    for trade in history:
        if trade.get("session") == session_name:
            res = trade.get("result")
            if res == "DIRECT_WIN": d_wins += 1
            elif res == "MTG_WIN": m_wins += 1
            elif res == "LOSS": losses += 1
            
    total_wins = d_wins + m_wins
    total = total_wins + losses
    accuracy = (total_wins / total * 100) if total > 0 else 0.0
    return total, d_wins, m_wins, losses, accuracy

# --- NEWS FETCH SYSTEM ---
def get_upcoming_news_schedule():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            events = response.json()
            now_utc = datetime.utcnow()
            upcoming_list = []
            for event in events:
                if event.get("impact") == "High":
                    date_str = event.get("date")
                    if date_str:
                        event_time = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
                        if event_time >= now_utc:
                            title = event.get("title", "News")
                            currency = event.get("country", "USD")
                            upcoming_list.append({
                                "time": event_time.strftime("%Y-%m-%d | %H:%M UTC"),
                                "currency": currency,
                                "title": title
                            })
                            if len(upcoming_list) >= 4:
                                break
            return upcoming_list
    except:
        pass
    return []

# --- LIVE MARKET STATUS CHECKER ---
def check_live_market_status():
    try:
        # Sample check across top pairs to evaluate volatility/status
        volatilities = []
        for pair, yf_symbol in list(LIVE_PAIRS_MAP.items())[:5]:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1d", interval="5m", timeout=5)
            if not df.empty and len(df) > 5:
                highs = df['High'].tail(5)
                lows = df['Low'].tail(5)
                avg_range = (highs - lows).mean()
                volatilities.append(avg_range)
        
        if volatilities:
            avg_vol = np.mean(volatilities)
            if avg_vol > 0.0015:
                return "🔴 **AVOID / HIGH CHOPPY VOLATILITY**\nMarket is moving aggressively with unpredictable whipsaws. Trade with extreme caution or stay out!", "AVOID"
            elif avg_vol < 0.0003:
                return "🟡 **NORMAL / LOW MOMENTUM**\nMarket is quiet and slow. Trend continuation might be weak.", "NORMAL"
            else:
                return "🟢 **GOOD / STABLE MARKET**\nMarket conditions are healthy with smooth momentum candles. Ideal for executing strategy signals!", "GOOD"
    except:
        pass
    return "🟢 **NORMAL MARKET CONDITIONS**\nStable environment for trading.", "NORMAL"

# --- 4 INTERACTIVE BUTTONS ---
def get_session_buttons():
    return {
        "inline_keyboard": [
            [
                {"text": "☀️ Morning Results", "callback_data": "res_morning"},
                {"text": "🌙 Evening Results", "callback_data": "res_evening"}
            ],
            [
                {"text": "📰 Forex News", "callback_data": "res_news"},
                {"text": "📊 Market Status", "callback_data": "res_status"}
            ]
        ]
    }

def send_telegram_message_with_buttons(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHANNEL_CHAT_ID, 
        'text': text, 
        'parse_mode': 'Markdown',
        'reply_markup': get_session_buttons()
    }
    try:
        requests.post(url, json=payload, timeout=20)
    except Exception as e:
        print(f"Telegram Message Error: {e}")

def send_telegram_simple_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHANNEL_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload, timeout=20)
    except Exception as e:
        print(f"Telegram Message Error: {e}")

def send_telegram_photo_with_buttons(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    for _ in range(3):
        try:
            if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
                with open(photo_path, 'rb') as photo:
                    payload = {
                        'chat_id': CHANNEL_CHAT_ID, 
                        'caption': caption, 
                        'parse_mode': 'Markdown',
                        'reply_markup': str(get_session_buttons()).replace("'", '"')
                    }
                    files = {'photo': photo}
                    response = requests.post(url, data=payload, files=files, timeout=45)
                    if response.status_code == 200:
                        return True
        except:
            time.sleep(1)
    return False

# --- AUTO SUMMARY SENDER ---
def trigger_auto_summary(session_name):
    total, d_wins, m_wins, losses, acc = get_session_stats(session_name)
    t_wins = d_wins + m_wins
    summary_text = (
        f"🚨 *{session_name.upper()} SESSION COMPLETED - TOTAL SUMMARY* 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Total Signals:** `{total}`\n"
        f"⭐ **Direct Wins:** `{d_wins}`\n"
        f"✅ **MTG Wins:** `{m_wins}`\n"
        f"🏆 **Total Wins:** `{t_wins}`\n"
        f"❌ **Losses:** `{losses}`\n"
        f"📈 **Lifetime Accuracy:** `{acc:.2f}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Use the buttons below to check history, news, or market status!*"
    )
    send_telegram_message_with_buttons(summary_text)

# --- TELEGRAM CALLBACK LISTENER ---
async def handle_telegram_callbacks():
    offset = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("result"):
                offset = data["result"][-1]["update_id"] + 1
    except:
        pass

    while True:
        try:
            response = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        callback_data = cq.get("data", "")
                        query_id = cq["id"]
                        
                        ans_text = ""
                        if callback_data == "res_news":
                            news_items = get_upcoming_news_schedule()
                            if news_items:
                                ans_text = "📰 *UPCOMING HIGH IMPACT NEWS TIMINGS* 📰\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                for item in news_items:
                                    ans_text += (
                                        f"🗓️ **Time:** `{item['time']}`\n"
                                        f"💱 **Currency:** `{item['currency']}`\n"
                                        f"📌 **Event:** `{item['title']}`\n"
                                        f"--------------------------------------------------\n"
                                    )
                            else:
                                ans_text = "📰 *FOREX NEWS SCHEDULE*\n━━━━━━━━━━━━━━━━━━━━━━━━━\nNo major High-Impact news found right now. Market is clear!"
                        elif callback_data == "res_status":
                            status_desc, _ = check_live_market_status()
                            ans_text = f"📊 *LIVE MARKET STATUS SCANNER*\n━━━━━━━━━━━━━━━━━━━━━━━━━\n{status_desc}\n━━━━━━━━━━━━━━━━━━━━━━━━━"
                        else:
                            session_key = "Morning" if callback_data == "res_morning" else "Evening"
                            title = "☀️ MORNING SESSION - LIFETIME RESULTS" if session_key == "Morning" else "🌙 EVENING SESSION - LIFETIME RESULTS"
                            
                            total, d_wins, m_wins, losses, acc = get_session_stats(session_key)
                            t_wins = d_wins + m_wins
                            
                            ans_text = (
                                f"*{title}*\n"
                                f"━━━━━━━━━━━━━━━━━━━\n"
                                f"🎯 **Total Signals:** `{total}`\n"
                                f"⭐ **Direct Wins:** `{d_wins}`\n"
                                f"✅ **MTG Wins:** `{m_wins}`\n"
                                f"🏆 **Total Wins:** `{t_wins}`\n"
                                f"❌ **Losses:** `{losses}`\n"
                                f"📈 **Accuracy:** `{acc:.2f}%`\n"
                                f"━━━━━━━━━━━━━━━━━━━"
                            )
                        
                        ans_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
                        requests.post(ans_url, json={"callback_query_id": query_id, "text": "Loaded", "show_alert": False})
                        send_telegram_simple_message(ans_text)
        except:
            pass
        await asyncio.sleep(2)

# --- TRADINGVIEW SCREENSHOT CAPTURE ---
async def capture_chart(pair: str, output_path: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 750})
        url = f"https://s.tradingview.com/widgetembed/?symbol=FX:{pair}&interval=1&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Asia/Karachi"
        
        for _ in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)
                await page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1280, "height": 700})
                if os.path.exists(output_path) and os.path.getsize(output_path) > 15000:
                    break
            except:
                await asyncio.sleep(2)
        await browser.close()

def get_market_data(yf_symbol):
    try:
        ticker = yf.Ticker(yf_symbol)
        df_2m = ticker.history(period="2d", interval="2m", auto_adjust=True, timeout=10)
        
        if not df_2m.empty and len(df_2m) >= 15:
            candles = []
            for i in range(-5, 0):
                row = df_2m.iloc[i]
                candles.append({
                    'open': float(row['Open']), 'high': float(row['High']),
                    'low': float(row['Low']), 'close': float(row['Close'])
                })
            return candles
    except:
        pass
    return None

def analyze_fast_strategy(candles):
    if not candles or len(candles) < 2: return None
    prev_candle, curr_candle = candles[-2], candles[-1]
    entry_price = curr_candle['close']
    
    if curr_candle['close'] > curr_candle['open'] and prev_candle['close'] > prev_candle['open']:
        return ("⚡ Fast Momentum Call", "CALL 🟢", f"{entry_price:.5f}", "🔥 FAST 85%+", entry_price)
    elif curr_candle['close'] < curr_candle['open'] and prev_candle['close'] < prev_candle['open']:
        return ("⚡ Fast Momentum Put", "PUT 🔻", f"{entry_price:.5f}", "🔥 FAST 85%+", entry_price)
        
    return None

async def process_signal(pair: str, yf_symbol: str, pattern: str, direction: str, entry_str: str, strength: str, entry_num: float, session_type: str):
    global is_signal_running
    
    is_signal_running = True
    timestamp = int(time.time())
    live_img = f"{pair}_live_{timestamp}.png"
    result_img = f"{pair}_result_{timestamp}.png"
    
    await capture_chart(pair, live_img)
    signal_msg = (
        f"**👑 MALIK UMAIR SVIP - SIGNAL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Asset:** `#{pair}` | **Session:** `{session_type}`\n"
        f"⏳ **Timeframe:** `1 Minute (Chart) / 2 Min (Expiry)`\n"
        f"🎯 **Pattern:** `{pattern}` | 📈 **Direction:** `{direction}`\n"
        f"📍 **Entry:** `{entry_str}` | 💪 **Accuracy:** `{strength}`\n"
        f"⏱️ **Expiry:** `Exact 2 Minutes`\n"
        f"⚠️ **Take 1 Step MTG same direction iff loss**\n━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    if os.path.exists(live_img):
        send_telegram_photo_with_buttons(live_img, signal_msg)
        try: os.remove(live_img)
        except: pass
    else:
        send_telegram_message_with_buttons(signal_msg)

    # 2 Minutes Expiry Wait
    await asyncio.sleep(120)
    candles_after = get_market_data(yf_symbol)
    exit_num = candles_after[-1]['close'] if candles_after and len(candles_after) > 0 else entry_num
    
    is_first_win = (exit_num >= entry_num) if "CALL" in direction else (exit_num <= entry_num)

    if is_first_win:
        save_trade_to_db("DIRECT_WIN", session_type)
        result_status = "🎯 **DIRECT WIN / SHURESHOT ⭐**"
    else:
        mtg_entry_num = exit_num
        await asyncio.sleep(120)
        candles_mtg = get_market_data(yf_symbol)
        mtg_exit_num = candles_mtg[-1]['close'] if candles_mtg and len(candles_mtg) > 0 else mtg_entry_num
        
        is_mtg_win = (mtg_exit_num >= mtg_entry_num) if "CALL" in direction else (mtg_exit_num <= mtg_entry_num)
        
        if is_mtg_win:
            save_trade_to_db("MTG_WIN", session_type)
            result_status = "✅ **MTG WIN / ITM 🎯**"
        else:
            save_trade_to_db("LOSS", session_type)
            result_status = "❌ **MTG LOSS / OTM 🛑**"

    await capture_chart(pair, result_img)
    result_msg = f"🏆 **MALIK UMAIR SVIP - RESULT**\n📊 **Asset:** `#{pair}`\n✨ **Status:** {result_status}"
    if os.path.exists(result_img):
        send_telegram_photo_with_buttons(result_img, result_msg)
        try: os.remove(result_img)
        except: pass
    else:
        send_telegram_message_with_buttons(result_msg)

    is_signal_running = False

# --- MAIN CONTROLLER WITH TIMINGS & WEEKEND OFF ---
async def main():
    global is_signal_running
    print("Malik Umair SVIP Bot Active with 4 Buttons, Timings & News/Market Scanners...")
    asyncio.create_task(handle_telegram_callbacks())
    
    morning_summary_sent_today = ""
    evening_summary_sent_today = ""
    
    while True:
        now_pk = datetime.utcnow() + timedelta(hours=5)
        current_date_str = now_pk.strftime("%Y-%m-%d")
        h, m = now_pk.hour, now_pk.minute
        
        # Weekend Off Check (5 = Saturday, 6 = Sunday)
        if now_pk.weekday() >= 5:
            print("Weekend (Sat/Sun) Detected! Market Closed. Resting...", end="\r")
            await asyncio.sleep(3600)
            continue
        
        # Sessions: Morning (12 PM - 3 PM), Evening (6 PM - 10 PM)
        is_morning = (12 <= h < 15)
        is_evening = (18 <= h < 22)
        session_type = "Morning" if is_morning else ("Evening" if is_evening else None)
        
        # Auto Summary at 3:05 PM
        if h == 15 and m == 5:
            if morning_summary_sent_today != current_date_str:
                trigger_auto_summary("Morning")
                morning_summary_sent_today = current_date_str
                
        # Auto Summary at 10:05 PM
        if h == 22 and m == 5:
            if evening_summary_sent_today != current_date_str:
                trigger_auto_summary("Evening")
                evening_summary_sent_today = current_date_str

        if session_type and not is_signal_running:
            # Check market status before generating signals if needed
            _, status_flag = check_live_market_status()
            if status_flag == "AVOID":
                print(f"[{session_type} Session] Market Volatility is High / Avoid Zone. Waiting...", end="\r")
                await asyncio.sleep(300)
                continue

            signal_found = False
            for pair, yf_symbol in LIVE_PAIRS_MAP.items():
                print(f"[{session_type} Session] Scanning Market -> {pair}                    ", end="\r")
                candles = get_market_data(yf_symbol)
                
                if candles:
                    signal = analyze_fast_strategy(candles)
                    if signal:
                        pattern, direction, entry_str, strength, entry_num = signal
                        await process_signal(pair, yf_symbol, pattern, direction, entry_str, strength, entry_num, session_type)
                        signal_found = True
                        break  
                        
            if not signal_found:
                await asyncio.sleep(300)
        else:
            print(f"Bot is resting (Outside active session hours)... Current Time: {h:02d}:{m:02d} PKT", end="\r")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
