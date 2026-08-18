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
from PIL import Image, ImageDraw, ImageFont

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
                return "AVOID / HIGH CHOPPY VOLATILITY\nMarket is moving aggressively. Trade with caution!"
            elif avg_vol < 0.0003:
                return "NORMAL / LOW MOMENTUM\nMarket is quiet."
            else:
                return "GOOD / STABLE MARKET\nConditions are ideal for S&R execution!"
    except:
        pass
    return "NORMAL MARKET CONDITIONS\nStable environment for trading."

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

def send_telegram_photo_with_buttons(photo_path, caption=""):
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

# --- GENERATE PROFESSIONAL TEXT CARD IMAGE ---
def create_text_card_image(title_text, content_lines, output_path):
    try:
        img_w, img_h = 800, 600
        card = Image.new("RGBA", (img_w, img_h), (18, 20, 26, 255))
        draw = ImageDraw.Draw(card)
        
        # Outer Golden Frame
        draw.rounded_rectangle([10, 10, img_w - 10, img_h - 10], radius=16, fill=(24, 26, 34, 255), outline=(212, 175, 55, 255), width=3)
        draw.rounded_rectangle([13, 13, img_w - 13, img_h - 13], radius=14, outline=(255, 223, 0, 150), width=1)
        
        # Header Banner
        draw.rounded_rectangle([30, 30, img_w - 30, 95], radius=10, fill=(32, 35, 45, 255), outline=(212, 175, 55, 255), width=2)
        
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 24)
            font_body = ImageFont.truetype("arial.ttf", 20)
        except:
            font_title = ImageFont.load_default()
            font_body = ImageFont.load_default()
            
        # Draw Title
        bbox = draw.textbbox((0, 0), title_text, font=font_title)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((img_w - tw) // 2 + 2, 50 + 2), title_text, font=font_title, fill=(0, 0, 0, 255))
        draw.text(((img_w - tw) // 2, 50), title_text, font=font_title, fill=(255, 215, 0, 255))
        
        # Draw Content Lines
        y_offset = 130
        for line in content_lines:
            draw.text((50, y_offset), line, font=font_body, fill=(240, 240, 240, 255))
            y_offset += 42
            
        card.convert("RGB").save(output_path, "PNG")
    except Exception as e:
        print(f"Card Generation Error: {e}")

# --- AUTO SUMMARY SENDER AS IMAGE ---
def trigger_auto_summary(session_name):
    total, d_wins, m_wins, losses, acc = get_session_stats(session_name)
    t_wins = d_wins + m_wins
    
    title = f"MALIK UMAIR - {session_name.upper()} SESSION REPORT"
    lines = [
        f"🎯 Total Signals Executed : {total}",
        f"⭐ Direct Wins (Shureshot) : {d_wins}",
        f"✅ MTG Wins (Recovery)    : {m_wins}",
        f"🏆 Total Wins Combined    : {t_wins}",
        f"❌ Total Losses           : {losses}",
        f"📈 Overall Accuracy Rate  : {acc:.2f}%",
        "--------------------------------------------------",
        "💡 Excellence through precision & discipline."
    ]
    
    img_path = f"summary_{session_name}_{int(time.time())}.png"
    create_text_card_image(title, lines, img_path)
    send_telegram_photo_with_buttons(img_path, f"📊 **{session_name.upper()} REPORT CARD**")
    try: os.remove(img_path)
    except: pass

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
                        
                        img_filename = f"callback_card_{int(time.time())}.png"
                        if callback_data == "res_news":
                            news_items = get_upcoming_news_schedule()
                            lines = []
                            if news_items:
                                for item in news_items:
                                    lines.append(f"🗓️ {item['time']} | {item['currency']}")
                                    lines.append(f"📌 {item['title'][:35]}")
                                    lines.append("--------------------------------------------------")
                            else:
                                lines.append("No major High-Impact news found right now.")
                            create_text_card_image("UPCOMING FOREX NEWS", lines, img_filename)
                            
                        elif callback_data == "res_status":
                            status_desc = check_live_market_status()
                            lines = status_desc.split("\n")
                            create_text_card_image("LIVE MARKET STATUS SCANNER", lines, img_filename)
                            
                        else:
                            session_key = "Morning" if callback_data == "res_morning" else "Evening"
                            total, d_wins, m_wins, losses, acc = get_session_stats(session_key)
                            t_wins = d_wins + m_wins
                            lines = [
                                f"🎯 Total Signals         : {total}",
                                f"⭐ Direct Wins           : {d_wins}",
                                f"✅ MTG Wins              : {m_wins}",
                                f"🏆 Total Wins            : {t_wins}",
                                f"❌ Losses                : {losses}",
                                f"📈 Accuracy Rate         : {acc:.2f}%"
                            ]
                            create_text_card_image(f"{session_key.upper()} PERFORMANCE", lines, img_filename)
                        
                        ans_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
                        requests.post(ans_url, json={"callback_query_id": query_id, "text": "Loaded", "show_alert": False})
                        
                        send_telegram_photo_with_buttons(img_filename, "👑 **MALIK UMAIR FOREX SIGNAL**")
                        try: os.remove(img_filename)
                        except: pass
        except:
            pass
        await asyncio.sleep(2)

# --- EXACT VIP FRAME COMPOSER ---
def apply_exact_vip_frame(image_path: str):
    try:
        chart_img = Image.open(image_path).convert("RGBA")
        c_w, c_h = chart_img.size
        
        padding = 24
        header_space = 46
        new_w = c_w + (padding * 2)
        new_h = c_h + padding + header_space + padding
        
        framed_img = Image.new("RGBA", (new_w, new_h), (20, 22, 28, 255))
        draw = ImageDraw.Draw(framed_img)
        
        chart_x = padding
        chart_y = padding + header_space
        framed_img.paste(chart_img, (chart_x, chart_y))
        
        draw.rounded_rectangle([12, 12, new_w - 12, new_h - 12], radius=14, fill=None, outline=(50, 55, 68, 255), width=3)
        
        banner_w = int(new_w * 0.55)
        banner_h = 42
        banner_x1 = (new_w - banner_w) // 2
        banner_y1 = padding + 4
        banner_x2 = banner_x1 + banner_w
        banner_y2 = banner_y1 + banner_h
        
        draw.rounded_rectangle([banner_x1, banner_y1, banner_x2, banner_y2], radius=10, fill=(28, 30, 38, 255), outline=(212, 175, 55, 255), width=3)
        draw.rounded_rectangle([banner_x1+2, banner_y1+2, banner_x2-2, banner_y2-2], radius=8, outline=(255, 223, 0, 180), width=1)
        
        try:
            font = ImageFont.truetype("arialbd.ttf", 18)
        except:
            font = ImageFont.load_default()
            
        title_text = " Malik Umair Forex Signal"
        bbox = draw.textbbox((0, 0), title_text, font=font)
        t_w = bbox[2] - bbox[0]
        t_h = bbox[3] - bbox[1]
        t_x = banner_x1 + (banner_w - t_w) // 2
        t_y = banner_y1 + (banner_h - t_h) // 2 - 2
        
        draw.text((t_x + 1, t_y + 1), title_text, font=font, fill=(0, 0, 0, 255))
        draw.text((t_x, t_y), title_text, font=font, fill=(255, 215, 0, 255))
        
        framed_img.convert("RGB").save(image_path, "PNG")
    except Exception as e:
        print(f"Frame Composer Error: {e}")

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
                    apply_exact_vip_frame(output_path)
                    break
            except:
                await asyncio.sleep(2)
        await browser.close()

def get_market_data(yf_symbol):
    try:
        ticker = yf.Ticker(yf_symbol)
        df_2m = ticker.history(period="1d", interval="1m", auto_adjust=True, timeout=10)
        
        if not df_2m.empty and len(df_2m) >= 15:
            candles = []
            for i in range(len(df_2m)):
                row = df_2m.iloc[i]
                candles.append({
                    'open': float(row['Open']), 'high': float(row['High']),
                    'low': float(row['Low']), 'close': float(row['Close'])
                })
            return candles
    except:
        pass
    return None

# --- FAST S&R STRATEGY LOGIC ---
def analyze_sr_strategy(candles):
    if not candles or len(candles) < 15: 
        return None
    
    recent_slice = candles[-15:-1]
    highs = [c['high'] for c in recent_slice]
    lows = [c['low'] for c in recent_slice]
    
    resistance_level = max(highs)
    support_level = min(lows)
    
    curr_candle = candles[-1]
    entry_price = curr_candle['close']
    
    if curr_candle['low'] <= support_level * 1.0003 and curr_candle['close'] >= curr_candle['open']:
        return ("🛡️ S&R Zone Support Bounce", "CALL 🟢", f"{entry_price:.5f}", "🔥 S&R 90%+", entry_price)
    elif curr_candle['high'] >= resistance_level * 0.9997 and curr_candle['close'] <= curr_candle['open']:
        return ("🛡️ S&R Zone Resistance Rejection", "PUT 🔻", f"{entry_price:.5f}", "🔥 S&R 90%+", entry_price)
        
    return None

async def process_signal(pair: str, yf_symbol: str, pattern: str, direction: str, entry_str: str, strength: str, entry_num: float, session_type: str):
    global is_signal_running
    
    is_signal_running = True
    timestamp = int(time.time())
    live_img = f"{pair}_live_{timestamp}.png"
    result_img = f"{pair}_result_{timestamp}.png"
    
    await capture_chart(pair, live_img)
    
    # Send Signal as an Image Card with details printed on it
    signal_card_path = f"signal_card_{timestamp}.png"
    signal_lines = [
        f"💎 Asset / Pair          : #{pair}",
        f"🕒 Trading Session     : {session_type} Session",
        f"⏳ Timeframe           : 1 Min (Chart) | 2 Min",
        f"🎯 Strategy Setup      : {pattern}",
        f"📈 Execution Direction : {direction}",
        f"📍 Precise Entry Point : {entry_str}",
        f"💪 Setup Confidence    : {strength}",
        "--------------------------------------------------",
        "⚠️ Take 1 Step MTG strictly if first trade loses."
    ]
    create_text_card_image("MALIK UMAIR SVIP SIGNAL", signal_lines, signal_card_path)
    
    if os.path.exists(live_img):
        # Send both Chart and Signal Card or combine them nicely
        send_telegram_photo_with_buttons(live_img, f"👑 **MALIK UMAIR SVIP - CHART ANALYSIS (#{pair})**")
        send_telegram_photo_with_buttons(signal_card_path, f"📋 **VIP SIGNAL DETAILS (#{pair})**")
        try: os.remove(live_img)
        except: pass
        try: os.remove(signal_card_path)
        except: pass

    # 2 Minutes Expiry Wait
    await asyncio.sleep(120)
    candles_after = get_market_data(yf_symbol)
    exit_num = candles_after[-1]['close'] if candles_after and len(candles_after) > 0 else entry_num
    
    is_first_win = (exit_num > entry_num) if "CALL" in direction else (exit_num < entry_num)

    if is_first_win:
        save_trade_to_db("DIRECT_WIN", session_type)
        result_status = "🎯 DIRECT WIN (SHURESHOT ITM ⭐)"
    else:
        mtg_entry_num = exit_num
        await asyncio.sleep(120)
        candles_mtg = get_market_data(yf_symbol)
        mtg_exit_num = candles_mtg[-1]['close'] if candles_mtg and len(candles_mtg) > 0 else mtg_entry_num
        
        is_mtg_win = (mtg_exit_num > mtg_entry_num) if "CALL" in direction else (mtg_exit_num < mtg_entry_num)
        
        if is_mtg_win:
            save_trade_to_db("MTG_WIN", session_type)
            result_status = "✅ MTG WIN (RECOVERY ITM 🎯)"
        else:
            save_trade_to_db("LOSS", session_type)
            result_status = "❌ MTG LOSS (OTM 🛑)"

    await capture_chart(pair, result_img)
    
    # Send Result as an Image Card
    result_card_path = f"result_card_{timestamp}.png"
    result_lines = [
        f"💎 Asset / Pair   : #{pair}",
        f"📊 Outcome Status : {result_status}",
        "--------------------------------------------------",
        "💡 Consistency is the key to trading success."
    ]
    create_text_card_image("MALIK UMAIR SVIP - TRADE RESULT", result_lines, result_card_path)
    
    if os.path.exists(result_img):
        send_telegram_photo_with_buttons(result_img, f"🏆 **TRADE OUTCOME CHART (#{pair})**")
        send_telegram_photo_with_buttons(result_card_path, f"📢 **RESULT CARD REPORT**")
        try: os.remove(result_img)
        except: pass
        try: os.remove(result_card_path)
        except: pass

    is_signal_running = False

# --- MAIN CONTROLLER WITH TIMINGS & WEEKEND OFF ---
async def main():
    global is_signal_running
    print("Malik Umair SVIP Fast S&R Bot Active...")
    asyncio.create_task(handle_telegram_callbacks())
    
    morning_summary_sent_today = ""
    evening_summary_sent_today = ""
    
    while True:
        now_pk = datetime.utcnow() + timedelta(hours=5)
        current_date_str = now_pk.strftime("%Y-%m-%d")
        h, m = now_pk.hour, now_pk.minute
        
        if now_pk.weekday() >= 5:
            print("Weekend (Sat/Sun) Detected! Market Closed. Resting...", end="\r")
            await asyncio.sleep(3600)
            continue
        
        is_morning = (10 <= h < 15)
        is_evening = (16 <= h < 22)
        session_type = "Morning" if is_morning else ("Evening" if is_evening else None)
        
        if h == 15 and m == 5:
            if morning_summary_sent_today != current_date_str:
                trigger_auto_summary("Morning")
                morning_summary_sent_today = current_date_str
                
        if h == 22 and m == 5:
            if evening_summary_sent_today != current_date_str:
                trigger_auto_summary("Evening")
                evening_summary_sent_today = current_date_str

        if session_type and not is_signal_running:
            signal_found = False
            
            pairs_list = list(LIVE_PAIRS_MAP.items())
            np.random.shuffle(pairs_list)
            
            for pair, yf_symbol in pairs_list:
                print(f"[{session_type} Session] Fast Scanning S&R -> {pair}                    ", end="\r")
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
            print(f"Bot is resting (Outside active session hours)... Current Time: {h:02d}:{m:02d} PKT", end="\r")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
