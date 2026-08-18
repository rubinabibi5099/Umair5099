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
                return ["✨ HIGH CHOPPY VOLATILITY", "Market is wild! Trade with elegance & care."]
            elif avg_vol < 0.0003:
                return ["🌙 LOW MOMENTUM", "Market is peaceful and calm."]
            else:
                return ["💖 STABLE & IDEAL", "Market conditions are pure magic for execution!"]
    except:
        pass
    return ["✨ STABLE MARKET", "Ready for golden opportunities."]

def get_session_buttons():
    return {
        "inline_keyboard": [
            [
                {"text": "✨ Morning Results", "callback_data": "res_morning"},
                {"text": "💖 Evening Results", "callback_data": "res_evening"}
            ],
            [
                {"text": "🌟 Forex News", "callback_data": "res_news"},
                {"text": "💫 Market Status", "callback_data": "res_status"}
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
                    response = requests.post(url, data=payload, files={'photo': photo}, timeout=45)
                    if response.status_code == 200:
                        return True
        except:
            time.sleep(1)
    return False

# --- FANCY, ROMANTIC & ATTRACTIVE GRAPHIC CARD GENERATOR ---
def create_graphic_card(title_text, rows_data, output_path):
    try:
        img_w, img_h = 850, 520
        # Deep romantic night gradient background look with dark navy/violet tone
        card = Image.new("RGBA", (img_w, img_h), (12, 10, 22, 255))
        draw = ImageDraw.Draw(card)
        
        # Fancy Glowing Golden & Rose Borders
        draw.rounded_rectangle([10, 10, img_w - 10, img_h - 10], radius=16, fill=(18, 15, 30, 255), outline=(255, 215, 0, 255), width=4)
        draw.rounded_rectangle([14, 14, img_w - 14, img_h - 14], radius=13, outline=(255, 105, 180, 100), width=1)
        
        # Top Romantic Header Banner Box
        draw.rounded_rectangle([30, 28, img_w - 30, 92], radius=12, fill=(28, 20, 45, 255), outline=(255, 215, 0, 255), width=2)
        
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 22)
            font_label = ImageFont.truetype("arialbd.ttf", 18)
            font_val = ImageFont.truetype("arialbd.ttf", 18)
        except:
            font_title = ImageFont.load_default()
            font_label = ImageFont.load_default()
            font_val = ImageFont.load_default()
            
        # Draw Title with Glowing Shadow Effect
        bbox = font_title.getbbox(title_text) if hasattr(font_title, 'getbbox') else (0,0,200,20)
        tw = bbox[2] - bbox[0]
        draw.text(((img_w - tw) // 2 + 2, 45 + 2), title_text, font=font_title, fill=(255, 105, 180, 150))
        draw.text(((img_w - tw) // 2, 45), title_text, font=font_title, fill=(255, 223, 0, 255))
        
        # Draw Data Rows inside Card with Clear Contrast
        y_offset = 125
        for label, val in rows_data:
            draw.rounded_rectangle([30, y_offset, img_w - 30, y_offset + 38], radius=8, fill=(22, 18, 35, 255), outline=(70, 50, 95, 255), width=1)
            draw.text((45, y_offset + 8), label, font=font_label, fill=(255, 182, 193, 255)) # Soft Pink
            draw.text((380, y_offset + 8), val, font=font_val, fill=(255, 255, 255, 255))     # Pure White Clean
            y_offset += 48
            
        # Attractive Footer Branding
        footer_text = "✨ Malik Umair SVIP • Built with Passion & Precision 💖"
        draw.text((45, img_h - 35), footer_text, font=font_val, fill=(255, 192, 203, 180))
            
        card.convert("RGB").save(output_path, "PNG")
    except Exception as e:
        print(f"Graphic Card Error: {e}")

def trigger_auto_summary(session_name):
    total, d_wins, m_wins, losses, acc = get_session_stats(session_name)
    t_wins = d_wins + m_wins
    rows = [
        ("🎯 Total Executed Signals:", f"{total}"),
        ("⭐ Direct Sureshot Wins:", f"{d_wins}"),
        ("💖 MTG Recovery Wins:   ", f"{m_wins}"),
        ("🏆 Total Combined Wins:  ", f"{t_wins}"),
        ("❌ Total Market Losses:  ", f"{losses}"),
        ("📈 Session Accuracy Rate:", f"{acc:.2f}%")
    ]
    img_path = f"summary_{session_name}_{int(time.time())}.png"
    create_graphic_card(f"MALIK UMAIR - {session_name.upper()} REPORT", rows, img_path)
    send_telegram_photo_with_buttons(img_path, f"📊 **{session_name.upper()} SESSION SUMMARY REPORT**")
    try: os.remove(img_path)
    except: pass

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
                        
                        img_filename = f"cb_card_{int(time.time())}.png"
                        if cb_data == "res_news":
                            news = get_upcoming_news_schedule()
                            rows = []
                            if news:
                                for item in news[:4]:
                                    rows.append((f"{item['currency']} ({item['time']})", item['title'][:25]))
                            else:
                                rows.append(("Status", "No High-Impact News"))
                            create_graphic_card("UPCOMING HIGH IMPACT NEWS", rows, img_filename)
                        elif cb_data == "res_status":
                            st = check_live_market_status()
                            rows = [("Market State:", st[0]), ("Recommendation:", st[1])]
                            create_graphic_card("LIVE MARKET STATUS SCANNER", rows, img_filename)
                        else:
                            s_key = "Morning" if cb_data == "res_morning" else "Evening"
                            total, d_wins, m_wins, losses, acc = get_session_stats(s_key)
                            rows = [
                                ("Total Signals:", f"{total}"),
                                ("Direct Wins:  ", f"{d_wins}"),
                                ("MTG Wins:     ", f"{m_wins}"),
                                ("Total Losses: ", f"{losses}"),
                                ("Accuracy:     ", f"{acc:.2f}%")
                            ]
                            create_graphic_card(f"{s_key.upper()} PERFORMANCE STATS", rows, img_filename)
                        
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", json={"callback_query_id": query_id, "text": "Loaded ✨"})
                        send_telegram_photo_with_buttons(img_filename, "💖 **MALIK UMAIR FOREX SIGNAL**")
                        try: os.remove(img_filename)
                        except: pass
        except:
            pass
        await asyncio.sleep(2)

# --- FANCY TRADINGVIEW SCREENSHOT WITH HIGHLIGHT FRAME ---
def apply_exact_vip_frame_with_highlights(image_path: str, entry_str: str, direction: str):
    try:
        chart_img = Image.open(image_path).convert("RGBA")
        c_w, c_h = chart_img.size
        
        padding = 24
        header_space = 50
        new_w = c_w + (padding * 2)
        new_h = c_h + padding + header_space + padding
        
        # Romantic dark violet/navy theme frame background
        framed_img = Image.new("RGBA", (new_w, new_h), (12, 10, 22, 255))
        draw = ImageDraw.Draw(framed_img)
        
        chart_x = padding
        chart_y = padding + header_space
        framed_img.paste(chart_img, (chart_x, chart_y))
        
        # Outer Glowing Golden Frame Border
        draw.rounded_rectangle([10, 10, new_w - 10, new_h - 10], radius=14, fill=None, outline=(255, 215, 0, 255), width=3)
        
        # Fancy Neon Highlight Box on Chart for Entry
        box_color = (0, 255, 120, 200) if "CALL" in direction else (255, 60, 100, 200)
        draw.rounded_rectangle([chart_x + c_w - 190, chart_y + c_h - 120, chart_x + c_w - 20, chart_y + c_h - 70], radius=8, fill=(15, 15, 25, 220), outline=box_color, width=3)
        
        try:
            f_small = ImageFont.truetype("arialbd.ttf", 14)
            f_head = ImageFont.truetype("arialbd.ttf", 18)
        except:
            f_small = ImageFont.load_default()
            f_head = ImageFont.load_default()
            
        draw.text((chart_x + c_w - 180, chart_y + c_h - 113), f"ENTRY: {entry_str}", font=f_small, fill=(255, 255, 255, 255))
        draw.text((chart_x + c_w - 180, chart_y + c_h - 93), f"ACTION: {direction}", font=f_small, fill=box_color)

        # Header Title Banner Inside Image with Gold/Rose Glow
        banner_w = int(new_w * 0.65)
        banner_h = 42
        b_x1 = (new_w - banner_w) // 2
        b_y1 = padding + 4
        b_x2 = b_x1 + banner_w
        b_y2 = b_y1 + banner_h
        
        draw.rounded_rectangle([b_x1, b_y1, b_x2, b_y2], radius=10, fill=(28, 20, 45, 255), outline=(255, 215, 0, 255), width=3)
        title_text = "✨ Malik Umair Forex Signal 💖"
        bbox = f_head.getbbox(title_text) if hasattr(f_head, 'getbbox') else (0,0,220,18)
        t_w = bbox[2] - bbox[0]
        draw.text((b_x1 + (banner_w - t_w) // 2, b_y1 + 10), title_text, font=f_head, fill=(255, 215, 0, 255))
        
        framed_img.convert("RGB").save(image_path, "PNG")
    except Exception as e:
        print(f"Highlight Frame Error: {e}")

async def capture_chart(pair: str, output_path: str, entry_str: str, direction: str):
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
                    apply_exact_vip_frame_with_highlights(output_path, entry_str, direction)
                    break
            except:
                await asyncio.sleep(2)
        await browser.close()

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
        return ("S&R Support Bounce", "CALL 🟢", f"{entry:.5f}", "✨ 90%+ Sureshot", entry)
    elif curr['high'] >= res_lvl * 0.9997 and curr['close'] <= curr['open']:
        return ("S&R Resistance Rejection", "PUT 🔻", f"{entry:.5f}", "✨ 90%+ Sureshot", entry)
    return None

async def process_signal(pair: str, yf_symbol: str, pattern: str, direction: str, entry_str: str, strength: str, entry_num: float, session_type: str):
    global is_signal_running
    is_signal_running = True
    ts = int(time.time())
    
    live_img = f"{pair}_live_{ts}.png"
    result_img = f"{pair}_result_{ts}.png"
    
    await capture_chart(pair, live_img, entry_str, direction)
    
    signal_card = f"signal_card_{ts}.png"
    rows = [
        ("Asset / Pair:", f"#{pair}"),
        ("Session:     ", f"{session_type} Session"),
        ("Timeframe:   ", "1 Min Chart | 2 Min Expiry"),
        ("Strategy:    ", pattern),
        ("Direction:   ", direction),
        ("Entry Point: ", entry_str),
        ("Confidence:  ", strength)
    ]
    create_graphic_card("✨ MALIK UMAIR SVIP SIGNAL 💖", rows, signal_card)
    
    if os.path.exists(live_img):
        send_telegram_photo_with_buttons(live_img, f"📈 **LIVE CHART ANALYSIS FOR #{pair} ✨**")
        send_telegram_photo_with_buttons(signal_card, f"👑 **MALIK UMAIR SVIP SIGNAL CARD (#{pair}) 💖**")
        try: os.remove(live_img)
        except: pass
        try: os.remove(signal_card)
        except: pass

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
            outcome = "💖 MTG WIN (RECOVERY ITM 🎯)"
        else:
            save_trade_to_db("LOSS", session_type)
            outcome = "❌ MTG LOSS (OTM 🛑)"

    await capture_chart(pair, result_img, f"{exit_num:.5f}", direction)
    
    result_card = f"result_card_{ts}.png"
    res_rows = [
        ("Asset / Pair:", f"#{pair}"),
        ("Outcome:     ", outcome),
        ("Exit Price:  ", f"{exit_num:.5f}")
    ]
    create_graphic_card("✨ MALIK UMAIR TRADE RESULT 🏆", res_rows, result_card)
    
    if os.path.exists(result_img):
        send_telegram_photo_with_buttons(result_img, f"📊 **EXPIRY CHART OUTCOME (#{pair}) ✨**")
        send_telegram_photo_with_buttons(result_card, f"🏆 **RESULT REPORT CARD (#{pair}) 💖**")
        try: os.remove(result_img)
        except: pass
        try: os.remove(result_card)
        except: pass

    is_signal_running = False

async def main():
    global is_signal_running
    print("Malik Umair SVIP Fancy & Romantic Graphic Bot Active...")
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
