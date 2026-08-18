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
TELEGRAM_BOT_TOKEN = "8690803539:AAEYG77XPI5DGmegur7m-0oejiaUHrFNU7s"
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
last_loss_time = 0
COOLDOWN_DURATION = 1800  # 30 Minutes Break when market is shaky/loss

# --- DATABASE FUNCTIONS ---
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
        "date": (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d"),
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
                            upcoming_list.append({
                                "time": event_time.strftime("%Y-%m-%d | %H:%M UTC"),
                                "currency": event.get("country", "USD"),
                                "title": event.get("title", "News")
                            })
                            if len(upcoming_list) >= 4:
                                break
            return upcoming_list
    except:
        pass
    return []

# --- LIVE MARKET STATUS & BREAK CHECKER ---
def check_live_market_status():
    try:
        volatilities = []
        for pair, yf_symbol in list(LIVE_PAIRS_MAP.items())[:5]:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1d", interval="5m", timeout=5)
            if not df.empty and len(df) > 5:
                avg_range = (df['High'].tail(5) - df['Low'].tail(5)).mean()
                volatilities.append(avg_range)
        
        if volatilities:
            avg_vol = np.mean(volatilities)
            if avg_vol > 0.0015:
                return "🔴 **AVOID / HIGH CHOPPY VOLATILITY**\nMarket moving aggressively. 30m Break Recommended!", "AVOID"
            elif avg_vol < 0.0003:
                return "🟡 **NORMAL / LOW MOMENTUM**\nMarket is quiet.", "NORMAL"
            else:
                return "🟢 **GOOD / STABLE MARKET**\nConditions ideal for S&R execution!", "GOOD"
    except:
        pass
    return "🟢 **NORMAL MARKET CONDITIONS**\nStable environment.", "NORMAL"

# --- INTERACTIVE BUTTONS (WITH NIGHT RESULT & OTHERS) ---
def get_session_buttons():
    return {
        "inline_keyboard": [
            [
                {"text": "☀️ Morning", "callback_data": "res_morning"},
                {"text": "🌙 Evening", "callback_data": "res_evening"},
                {"text": "🌃 Night", "callback_data": "res_night"}
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
        requests.post(url, json=payload, timeout=20)
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
                        'reply_markup': json.dumps(get_session_buttons())
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
        f"🚨 *MALIK UMAIR - {session_name.upper()} SESSION COMPLETED* 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Total Signals:** `{total}`\n"
        f"⭐ **Direct Wins:** `{d_wins}`\n"
        f"✅ **MTG Wins:** `{m_wins}`\n"
        f"🏆 **Total Wins:** `{t_wins}`\n"
        f"❌ **Losses:** `{losses}`\n"
        f"📈 **Accuracy:** `{acc:.2f}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Use buttons below to check records!*"
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
                                ans_text = "📰 *UPCOMING HIGH IMPACT NEWS* 📰\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                for item in news_items:
                                    ans_text += f"🗓️ `{item['time']}` | {item['currency']}\n📌 {item['title']}\n--------------------\n"
                            else:
                                ans_text = "📰 *FOREX NEWS*\nNo major High-Impact news right now."
                        elif callback_data == "res_status":
                            status_desc, _ = check_live_market_status()
                            ans_text = f"📊 *MARKET STATUS*\n{status_desc}"
                        else:
                            if callback_data == "res_morning":
                                session_key, title = "Morning", "☀️ MORNING SESSION RESULTS"
                            elif callback_data == "res_evening":
                                session_key, title = "Evening", "🌙 EVENING SESSION RESULTS"
                            else:
                                session_key, title = "Night", "🌃 NIGHT SESSION RESULTS"
                            
                            total, d_wins, m_wins, losses, acc = get_session_stats(session_key)
                            t_wins = d_wins + m_wins
                            ans_text = (
                                f"*{title}*\n"
                                f"━━━━━━━━━━━━━━━━━━━\n"
                                f"🎯 Total: `{total}` | ⭐ Direct: `{d_wins}`\n"
                                f"✅ MTG: `{m_wins}` | ❌ Losses: `{losses}`\n"
                                f"📈 Accuracy: `{acc:.2f}%`\n"
                                f"━━━━━━━━━━━━━━━━━━━"
                            )
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loaded"})
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
                await asyncio.sleep(3)
                await page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1280, "height": 700})
                if os.path.exists(output_path) and os.path.getsize(output_path) > 15000:
                    break
            except:
                await asyncio.sleep(2)
        await browser.close()

def get_market_data(yf_symbol):
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1d", interval="1m", auto_adjust=True, timeout=10)
        if not df.empty and len(df) >= 25:
            return [{'open': float(r['Open']), 'high': float(r['High']), 'low': float(r['Low']), 'close': float(r['Close'])} for _, r in df.iterrows()]
    except:
        pass
    return None

# --- STRATEGY WITH TREND FILTER (EMA 20) ---
def analyze_sr_strategy(candles):
    if not candles or len(candles) < 25: 
        return None
    
    df = pd.DataFrame(candles)
    ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    curr_close = df['close'].iloc[-1]
    
    recent_slice = candles[-15:-1]
    resistance_level = max(c['high'] for c in recent_slice)
    support_level = min(c['low'] for c in recent_slice)
    curr_candle = candles[-1]
    entry_price = curr_candle['close']
    
    # REQUIREMENT 2: Trend Filter Check (No trade against trend)
    is_bullish_trend = curr_close > ema20
    
    if curr_candle['low'] <= support_level * 1.0003 and curr_candle['close'] >= curr_candle['open']:
        if is_bullish_trend:  # Only Call if uptrend
            return ("🛡️ S&R Support Bounce", "CALL 🟢", f"{entry_price:.5f}", "🔥 S&R 90%+", entry_price)
            
    elif curr_candle['high'] >= resistance_level * 0.9997 and curr_candle['close'] <= curr_candle['open']:
        if not is_bullish_trend:  # Only Put if downtrend
            return ("🛡️ S&R Resistance Rejection", "PUT 🔻", f"{entry_price:.5f}", "🔥 S&R 90%+", entry_price)
            
    return None

async def process_signal(pair: str, yf_symbol: str, pattern: str, direction: str, entry_str: str, strength: str, entry_num: float, session_type: str):
    global is_signal_running, last_loss_time
    is_signal_running = True
    
    timestamp = int(time.time())
    live_img = f"{pair}_live_{timestamp}.png"
    result_img = f"{pair}_result_{timestamp}.png"
    
    await capture_chart(pair, live_img)
    signal_msg = (
        f"**👑 MALIK UMAIR SVIP - S&R SIGNAL**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Asset:** `#{pair}` | **Session:** `{session_type}`\n"
        f"⏳ **Timeframe:** `1 Min Chart / 2 Min Expiry`\n"
        f"🎯 **Pattern:** `{pattern}` | 📈 **Direction:** `{direction}`\n"
        f"📍 **Exact Entry:** `{entry_str}`\n"
        f"⚠️ **Take 1 Step MTG strictly if first loses**\n━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    if os.path.exists(live_img):
        send_telegram_photo_with_buttons(live_img, signal_msg)
        try: os.remove(live_img)
        except: pass
    else:
        send_telegram_message_with_buttons(signal_msg)

    # EXACT 2 MINUTES EXPIRY WAIT (Zero Lag Sync)
    await asyncio.sleep(120)
    
    candles_after = get_market_data(yf_symbol)
    exit_num = candles_after[-1]['close'] if candles_after and len(candles_after) > 0 else entry_num
    is_first_win = (exit_num > entry_num) if "CALL" in direction else (exit_num < entry_num)

    if is_first_win:
        save_trade_to_db("DIRECT_WIN", session_type)
        result_status = "🎯 **DIRECT WIN / SHURESHOT ⭐**"
    else:
        mtg_entry_num = exit_num
        await asyncio.sleep(120)  # MTG wait
        candles_mtg = get_market_data(yf_symbol)
        mtg_exit_num = candles_mtg[-1]['close'] if candles_mtg and len(candles_mtg) > 0 else mtg_entry_num
        is_mtg_win = (mtg_exit_num > mtg_entry_num) if "CALL" in direction else (mtg_exit_num < mtg_entry_num)
        
        if is_mtg_win:
            save_trade_to_db("MTG_WIN", session_type)
            result_status = "✅ **MTG WIN / ITM 🎯**"
        else:
            save_trade_to_db("LOSS", session_type)
            result_status = "❌ **MTG LOSS / OTM 🛑**"
            last_loss_time = time.time()  # REQUIREMENT 3: Trigger 30m break on loss

    # FORAN RESULT SENDING WITHOUT DELAY
    await capture_chart(pair, result_img)
    result_msg = f"🏆 **MALIK UMAIR SVIP - RESULT**\n📊 **Asset:** `#{pair}`\n✨ **Status:** {result_status}"
    
    if os.path.exists(result_img):
        send_telegram_photo_with_buttons(result_img, result_msg)
        try: os.remove(result_img)
        except: pass
    else:
        send_telegram_message_with_buttons(result_msg)

    is_signal_running = False

# --- MAIN CONTROLLER WITH ALL CUSTOM TIMINGS ---
async def main():
    global is_signal_running, last_loss_time
    print("Malik Umair SVIP Perfect Sync Bot Active...")
    asyncio.create_task(handle_telegram_callbacks())
    
    morning_ready_sent, morning_sum_sent = "", ""
    evening_ready_sent, evening_sum_sent = "", ""
    night_ready_sent, night_sum_sent = "", ""
    
    while True:
        # REQUIREMENT 1: Zero Lag & UTC + 5 (Pakistan Time sync)
        now_pk = datetime.utcnow() + timedelta(hours=5)
        current_date_str = now_pk.strftime("%Y-%m-%d")
        h, m = now_pk.hour, now_pk.minute
        
        # Weekend Off Check (Sat/Sun)
        if now_pk.weekday() >= 5:
            await asyncio.sleep(3600)
            continue
            
        # REQUIREMENT 3: Cooldown Break Check (30 mins rest)
        if time.time() - last_loss_time < COOLDOWN_DURATION:
            print("Bot is on 30-min market cool-down break due to volatility/loss...", end="\r")
            await asyncio.sleep(60)
            continue

        # --- REQUIREMENT 4: NOTIFICATIONS & SESSIONS TIMING ---
        # 1. Morning Notifications & Sessions
        if h == 11 and m == 45 and morning_ready_sent != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR MORNING SESSION!* Get ready team, session starts in 15 minutes! ☀️")
            morning_ready_sent = current_date_str
            
        is_morning = (12 <= h < 15)
        if h == 15 and m == 5 and morning_sum_sent != current_date_str:
            trigger_auto_summary("Morning")
            morning_sum_sent = current_date_str

        # 2. Evening Notifications & Sessions
        if h == 15 and m == 45 and evening_ready_sent != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR EVENING SESSION!* Prepare your terminals, session starts at 4:00 PM! 🌙")
            evening_ready_sent = current_date_str
            
        is_evening = (16 <= h < 19)
        if h == 19 and m == 5 and evening_sum_sent != current_date_str:
            trigger_auto_summary("Evening")
            evening_sum_sent = current_date_str

        # 3. Night Notifications & Sessions
        if h == 19 and m == 45 and night_ready_sent != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR NIGHT SESSION!* High volume night session starting at 8:00 PM! 🌃")
            night_ready_sent = current_date_str
            
        is_night = (20 <= h or h == 0) and not (0 < h < 8) # Active up to midnight (12 AM)
        if h == 0 and m == 5 and night_sum_sent != current_date_str:
            trigger_auto_summary("Night")
            night_sum_sent = current_date_str

        session_type = "Morning" if is_morning else ("Evening" if is_evening else ("Night" if is_night else None))

        # Synchronize exactly to 00 seconds of the minute to remove any lag
        if session_type and not is_signal_running:
            if datetime.now().second != 0:
                await asyncio.sleep(0.2)
                continue
                
            signal_found = False
            pairs_list = list(LIVE_PAIRS_MAP.items())
            np.random.shuffle(pairs_list)
            
            for pair, yf_symbol in pairs_list:
                print(f"[{session_type}] Scanning S&R -> {pair}                    ", end="\r")
                candles = get_market_data(yf_symbol)
                
                if candles:
                    signal = analyze_sr_strategy(candles)
                    if signal:
                        pattern, direction, entry_str, strength, entry_num = signal
                        await process_signal(pair, yf_symbol, pattern, direction, entry_str, strength, entry_num, session_type)
                        signal_found = True
                        break  
                        
            if not signal_found:
                await asyncio.sleep(15)
        else:
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
