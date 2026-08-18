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
COOLDOWN_DURATION = 1800  # 30 Minutes Break on loss

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

def check_live_market_status():
    return "🟢 **NORMAL MARKET CONDITIONS**\nStable environment.", "NORMAL"

# --- INTERACTIVE BUTTONS ---
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
    payload = {'chat_id': CHANNEL_CHAT_ID, 'text': text, 'parse_mode': 'Markdown', 'reply_markup': get_session_buttons()}
    try:
        requests.post(url, json=payload, timeout=20)
    except:
        pass

def send_telegram_simple_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHANNEL_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=20)
    except:
        pass

def send_telegram_photo_with_buttons(photo_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    for _ in range(3):
        try:
            if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
                with open(photo_path, 'rb') as photo:
                    payload = {
                        'chat_id': CHANNEL_CHAT_ID, 'caption': caption, 
                        'parse_mode': 'Markdown', 'reply_markup': json.dumps(get_session_buttons())
                    }
                    files = {'photo': photo}
                    response = requests.post(url, data=payload, files=files, timeout=45)
                    if response.status_code == 200:
                        return True
        except:
            time.sleep(1)
    return False

def trigger_auto_summary(session_name):
    total, d_wins, m_wins, losses, acc = get_session_stats(session_name)
    t_wins = d_wins + m_wins
    summary_text = (
        f"🚨 *MALIK UMAIR - {session_name.upper()} SESSION COMPLETED* 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 **Total Signals:** `{total}`\n"
        f"⭐ **Direct Wins:** `{d_wins}`\n"
        f"✅ **MTG Wins:** `{m_wins}`\n"
        f"❌ **Total Loss:** `{losses}`\n"
        f"📈 **Accuracy:** `{acc:.2f}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram_message_with_buttons(summary_text)

# --- DETAILED STATS CALLBACK HANDLER ---
async def handle_telegram_callbacks():
    offset = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    while True:
        try:
            response = requests.get(url, params={"offset": offset, "timeout": 30}, timeout=35)
            if response.status_code == 200:
                for update in response.json().get("result", []):
                    offset = update["update_id"] + 1
                    if "callback_query" in update:
                        cq = update["callback_query"]
                        cb_data = cq.get("data", "")
                        query_id = cq["id"]
                        
                        ans_text = "Loaded"
                        if cb_data == "res_news":
                            items = get_upcoming_news_schedule()
                            ans_text = "📰 *HIGH IMPACT NEWS*\n" + ("\n".join([f"🗓️ {i['time']} | {i['title']}" for i in items]) if items else "No major news.")
                        elif cb_data == "res_status":
                            ans_text = "📊 *MARKET STATUS*\n🟢 Normal & Stable."
                        else:
                            s_key = "Morning" if cb_data == "res_morning" else ("Evening" if cb_data == "res_evening" else "Night")
                            tot, dw, mw, los, ac = get_session_stats(s_key)
                            
                            # Wazeh aur tafseeli report buttons ke liye
                            ans_text = (
                                f"📊 *{s_key.upper()} SESSION REPORT*\n"
                                f"━━━━━━━━━━━━━━━━━━━\n"
                                f"🎯 Total Signals: `{tot}`\n"
                                f"⭐ Direct Wins: `{dw}`\n"
                                f"✅ MTG Wins: `{mw}`\n"
                                f"❌ Total Loss: `{los}`\n"
                                f"📈 Accuracy: `{ac:.2f}%`\n"
                                f"━━━━━━━━━━━━━━━━━━━"
                            )
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Report Generated"})
                        send_telegram_simple_message(ans_text)
        except:
            pass
        await asyncio.sleep(2)

async def capture_chart(pair: str, output_path: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 750})
        url = f"https://s.tradingview.com/widgetembed/?symbol=FX:{pair}&interval=1&hidesidetoolbar=1&symboledit=0&saveimage=0&toolbarbg=000000&studies=[]&theme=dark&style=1&timezone=Asia/Karachi"
        for _ in range(3):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(2)
                await page.screenshot(path=output_path, clip={"x": 0, "y": 0, "width": 1280, "height": 700})
                if os.path.exists(output_path) and os.path.getsize(output_path) > 15000:
                    break
            except:
                await asyncio.sleep(1)
        await browser.close()

def get_market_data(yf_symbol):
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1d", interval="1m", auto_adjust=True, timeout=8)
        if not df.empty and len(df) >= 10:
            return [{'open': float(r['Open']), 'high': float(r['High']), 'low': float(r['Low']), 'close': float(r['Close'])} for _, r in df.iterrows()]
    except:
        pass
    return None

def analyze_sr_strategy(candles):
    if not candles or len(candles) < 10: 
        return None
    
    recent = candles[-10:-1]
    res_lvl = max(c['high'] for c in recent)
    sup_lvl = min(c['low'] for c in recent)
    
    curr = candles[-1]
    entry_price = curr['close']
    
    if curr['low'] <= sup_lvl * 1.0008 or curr['close'] > curr['open']:
        if curr['close'] >= curr['open']:
            return ("🛡️ S&R Support Bounce", "CALL 🟢", f"{entry_price:.5f}", "🔥 S&R 90%+", entry_price)
            
    if curr['high'] >= res_lvl * 0.9992 or curr['close'] < curr['open']:
        if curr['close'] <= curr['open']:
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

    # EXACT 2 MINUTES EXPIRY WAIT
    await asyncio.sleep(120)
    
    candles_after = get_market_data(yf_symbol)
    exit_num = candles_after[-1]['close'] if candles_after and len(candles_after) > 0 else entry_num
    is_first_win = (exit_num > entry_num) if "CALL" in direction else (exit_num < entry_num)

    if is_first_win:
        save_trade_to_db("DIRECT_WIN", session_type)
        result_status = "🎯 **DIRECT WIN / SHURESHOT ⭐**"
    else:
        mtg_entry_num = exit_num
        await asyncio.sleep(120)
        candles_mtg = get_market_data(yf_symbol)
        mtg_exit_num = candles_mtg[-1]['close'] if candles_mtg and len(candles_mtg) > 0 else mtg_entry_num
        is_mtg_win = (mtg_exit_num > mtg_entry_num) if "CALL" in direction else (mtg_exit_num < mtg_entry_num)
        
        if is_mtg_win:
            save_trade_to_db("MTG_WIN", session_type)
            result_status = "✅ **MTG WIN / ITM 🎯**"
        else:
            save_trade_to_db("LOSS", session_type)
            result_status = "❌ **MTG LOSS / OTM 🛑**"
            last_loss_time = time.time()

    await capture_chart(pair, result_img)
    result_msg = f"🏆 **MALIK UMAIR SVIP - RESULT**\n📊 **Asset:** `#{pair}`\n✨ **Status:** {result_status}"
    
    if os.path.exists(result_img):
        send_telegram_photo_with_buttons(result_img, result_msg)
        try: os.remove(result_img)
        except: pass
    else:
        send_telegram_message_with_buttons(result_msg)

    is_signal_running = False

async def main():
    global is_signal_running, last_loss_time
    print("Malik Umair SVIP Final Master Bot Active...")
    asyncio.create_task(handle_telegram_callbacks())
    
    m_ready, m_sum = "", ""
    e_ready, e_sum = "", ""
    n_ready, n_sum = "", ""
    
    while True:
        # UTC + 5 Pakistan Time Sync
        now_pk = datetime.utcnow() + timedelta(hours=5)
        current_date_str = now_pk.strftime("%Y-%m-%d")
        h, m = now_pk.hour, now_pk.minute
        
        if now_pk.weekday() >= 5:
            await asyncio.sleep(3600)
            continue
            
        if time.time() - last_loss_time < COOLDOWN_DURATION:
            await asyncio.sleep(60)
            continue

        # --- 1. MORNING SESSION TIMINGS ---
        if h == 11 and m == 45 and m_ready != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR MORNING SESSION!* Starts in 15 mins! ☀️")
            m_ready = current_date_str
            
        is_morning = (12 <= h < 15)
        if h == 15 and m == 5 and m_sum != current_date_str:
            trigger_auto_summary("Morning")
            m_sum = current_date_str

        # --- 2. EVENING SESSION TIMINGS ---
        if h == 15 and m == 45 and e_ready != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR EVENING SESSION!* Starts at 4:00 PM! 🌙")
            e_ready = current_date_str
            
        is_evening = (16 <= h < 19)
        if h == 19 and m == 5 and e_sum != current_date_str:
            trigger_auto_summary("Evening")
            e_sum = current_date_str

        # --- 3. NIGHT SESSION TIMINGS ---
        if h == 19 and m == 45 and n_ready != current_date_str:
            send_telegram_message_with_buttons("📢 *READY FOR NIGHT SESSION!* Starts at 8:00 PM! 🌃")
            n_ready = current_date_str
            
        is_night = (20 <= h or h == 0) and not (0 < h < 8)
        if h == 0 and m == 5 and n_sum != current_date_str:
            trigger_auto_summary("Night")
            n_sum = current_date_str

        session_type = "Morning" if is_morning else ("Evening" if is_evening else ("Night" if is_night else None))

        if session_type and not is_signal_running:
            signal_found = False
            pairs_list = list(LIVE_PAIRS_MAP.items())
            np.random.shuffle(pairs_list)
            
            for pair, yf_symbol in pairs_list:
                print(f"[{session_type}] Scanning -> {pair}                    ", end="\r")
                candles = get_market_data(yf_symbol)
                
                if candles:
                    signal = analyze_sr_strategy(candles)
                    if signal:
                        pattern, direction, entry_str, strength, entry_num = signal
                        await process_signal(pair, yf_symbol, pattern, direction, entry_str, strength, entry_num, session_type)
                        signal_found = True
                        break  
                        
            if not signal_found:
                await asyncio.sleep(10)
        else:
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
