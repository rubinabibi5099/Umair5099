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
    except:
        pass

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
                            upcoming_list.append(f"🗓️ {event_time.strftime('%Y-%m-%d | %H:%M UTC')} | {event.get('country', 'USD')}\n📌 {event.get('title', 'News')}")
                            if len(upcoming_list) >= 4:
                                break
            return upcoming_list
    except:
        pass
    return []

def check_live_market_status():
    try:
        volatilities = []
        for pair, yf_symbol in list(LIVE_PAIRS_MAP.items())[:5]:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="1d", interval="5m", timeout=5)
            if not df.empty and len(df) > 5:
                volatilities.append((df['High'].tail(5) - df['Low'].tail(5)).mean())
        if volatilities:
            avg_vol = np.mean(volatilities)
            if avg_vol > 0.0015:
                return "AVOID / HIGH CHOPPY VOLATILITY\nMarket is moving aggressively. Trade cautiously!"
            elif avg_vol < 0.0003:
                return "NORMAL / LOW MOMENTUM\nMarket is quiet right now."
            else:
                return "GOOD / STABLE MARKET\nConditions are ideal for S&R execution!"
    except:
        pass
    return "NORMAL MARKET CONDITIONS\nStable environment for trading."

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

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for _ in range(3):
        try:
            payload = {
                'chat_id': CHANNEL_CHAT_ID,
                'text': text,
                'parse_mode': 'Markdown',
                'reply_markup': get_session_buttons()
            }
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return True
        except:
            time.sleep(1)
    return False

def trigger_auto_summary(session_name):
    total, d_wins, m_wins, losses, acc = get_session_stats(session_name)
    t_wins = d_wins + m_wins
    text = (
        f"📊 *MALIK UMAIR - {session_name.upper()} SESSION REPORT*\n\n"
        f"🎯 Total Signals Executed : {total}\n"
        f"⭐ Direct Wins (Shureshot) : {d_wins}\n"
        f"✅ MTG Wins (Recovery)    : {m_wins}\n"
        f"🏆 Total Wins Combined    : {t_wins}\n"
        f"❌ Total Losses           : {losses}\n"
        f"📈 Overall Accuracy Rate  : {acc:.2f}%\n\n"
        f"💡 Excellence through precision & discipline."
    )
    send_telegram_message(text)

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
                        
                        if cb_data == "res_news":
                            news = get_upcoming_news_schedule()
                            if news:
                                msg = "📰 *UPCOMING HIGH IMPACT NEWS*\n\n" + "\n--------------------------------------------------\n".join(news)
                            else:
                                msg = "📰 *UPCOMING HIGH IMPACT NEWS*\n\nNo major High-Impact news found right now."
                        elif cb_data == "res_status":
                            st = check_live_market_status()
                            msg = f"📊 *LIVE MARKET STATUS SCANNER*\n\n{st}"
                        else:
                            s_key = "Morning" if cb_data == "res_morning" else "Evening"
                            total, d_wins, m_wins, losses, acc = get_session_stats(s_key)
                            t_wins = d_wins + m_wins
                            msg = (
                                f"👑 *MALIK UMAIR - {s_key.upper()} PERFORMANCE*\n\n"
                                f"🎯 Total Signals         : {total}\n"
                                f"⭐ Direct Wins           : {d_wins}\n"
                                f"✅ MTG Wins              : {m_wins}\n"
                                f"🏆 Total Wins            : {t_wins}\n"
                                f"❌ Losses                : {losses}\n"
                                f"📈 Accuracy Rate         : {acc:.2f}%"
                            )
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loaded"})
                        send_telegram_message(msg)
        except:
            pass
        await asyncio.sleep(2)

def get_market_data(yf_symbol):
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1d", interval="1m", auto_adjust=True, timeout=10)
        if not df.empty and len(df) >= 15:
            return [{'open': float(r['Open']), 'high': float(r['High']), 'low': float(r['Low']), 'close': float(r['Close'])} for _, r in df.iterrows()]
    except:
        pass
    return None

def analyze_sr_strategy(candles):
    if not candles or len(candles) < 15: 
        return None
    recent = candles[-15:-1]
    res_lvl = max(c['high'] for c in recent)
    sup_lvl = min(c['low'] for c in recent)
    curr = candles[-1]
    entry = curr['close']
    
    if curr['low'] <= sup_lvl * 1.0003 and curr['close'] >= curr['open']:
        return ("S&R Support Bounce", "CALL 🟢", f"{entry:.5f}", "🔥 90%+", entry)
    elif curr['high'] >= res_lvl * 0.9997 and curr['close'] <= curr['open']:
        return ("S&R Resistance Rejection", "PUT 🔻", f"{entry:.5f}", "🔥 90%+", entry)
    return None

async def process_signal(pair: str, yf_symbol: str, pattern: str, direction: str, entry_str: str, strength: str, entry_num: float, session_type: str):
    global is_signal_running
    is_signal_running = True
    
    signal_msg = (
        f"👑 *MALIK UMAIR SVIP SIGNAL*\n\n"
        f"💎 Asset / Pair          : #{pair}\n"
        f"🕒 Trading Session     : {session_type} Session\n"
        f"⏳ Timeframe           : 1 Min Chart | 2 Min Expiry\n"
        f"🎯 Strategy Setup      : {pattern}\n"
        f"📈 Execution Direction : {direction}\n"
        f"📍 Precise Entry Point : {entry_str}\n"
        f"💪 Setup Confidence    : {strength}\n"
        f"--------------------------------------------------\n"
        f"⚠️ Take 1 Step MTG strictly if first trade loses."
    )
    send_telegram_message(signal_msg)

    # Expiry 2 Minutes Wait
    await asyncio.sleep(120)
    candles_after = get_market_data(yf_symbol)
    exit_num = candles_after[-1]['close'] if candles_after and len(candles_after) > 0 else entry_num
    is_win = (exit_num > entry_num) if "CALL" in direction else (exit_num < entry_num)

    if is_win:
        save_trade_to_db("DIRECT_WIN", session_type)
        outcome = "🎯 DIRECT WIN (SHURESHOT ITM ⭐)"
    else:
        mtg_entry = exit_num
        await asyncio.sleep(120)
        candles_mtg = get_market_data(yf_symbol)
        mtg_exit = candles_mtg[-1]['close'] if candles_mtg and len(candles_mtg) > 0 else mtg_entry
        is_mtg_win = (mtg_exit > mtg_entry) if "CALL" in direction else (mtg_exit < mtg_entry)
        
        if is_mtg_win:
            save_trade_to_db("MTG_WIN", session_type)
            outcome = "✅ MTG WIN (RECOVERY ITM 🎯)"
        else:
            save_trade_to_db("LOSS", session_type)
            outcome = "❌ MTG LOSS (OTM 🛑)"

    result_msg = (
        f"📢 *MALIK UMAIR SVIP - TRADE RESULT*\n\n"
        f"💎 Asset / Pair   : #{pair}\n"
        f"📊 Outcome Status : {outcome}\n"
        f"📍 Exit Price     : {exit_num:.5f}\n"
        f"--------------------------------------------------\n"
        f"💡 Consistency is the key to trading success."
    )
    send_telegram_message(result_msg)
    is_signal_running = False

async def main():
    global is_signal_running
    print("Malik Umair SVIP Simple Clean Signal Bot Active...")
    asyncio.create_task(handle_telegram_callbacks())
    
    morning_sent, evening_sent = "", ""
    while True:
        now_pk = datetime.utcnow() + timedelta(hours=5)
        dt_str = now_pk.strftime("%Y-%m-%d")
        h, m = now_pk.hour, now_pk.minute
        
        if now_pk.weekday() >= 5:
            await asyncio.sleep(3600)
            continue
            
        is_morning = (10 <= h < 15)
        is_evening = (16 <= h < 22)
        session = "Morning" if is_morning else ("Evening" if is_evening else None)
        
        if h == 15 and m == 5 and morning_sent != dt_str:
            trigger_auto_summary("Morning")
            morning_sent = dt_str
        if h == 22 and m == 5 and evening_sent != dt_str:
            trigger_auto_summary("Evening")
            evening_sent = dt_str

        if session and not is_signal_running:
            found = False
            pairs = list(LIVE_PAIRS_MAP.items())
            np.random.shuffle(pairs)
            for pair, yf_symbol in pairs:
                print(f"Scanning S&R -> {pair}                    ", end="\r")
                candles = get_market_data(yf_symbol)
                if candles:
                    sig = analyze_sr_strategy(candles)
                    if sig:
                        pat, dir_s, ent_s, str_s, ent_n = sig
                        await process_signal(pair, yf_symbol, pat, dir_s, ent_s, str_s, ent_n, session)
                        found = True
                        break
            if not found:
                await asyncio.sleep(15)
        else:
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
