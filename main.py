import os
import telebot
import threading
import urllib.parse
import requests
import time
from datetime import datetime
import pytz
from fyers_apiv3 import fyersModel
from flask import Flask
from telebot import types

# --- CONFIG ---
TOKEN         = os.environ.get("TELEGRAM_TOKEN")
APP_ID        = os.environ.get("FYERS_APP_ID")
SECRET_KEY    = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID       = os.environ.get("CHAT_ID")
REDIRECT_URI  = "https://trade.fyers.in/api-login/redirect-uri/index.html"
IST           = pytz.timezone("Asia/Kolkata")

bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

# --- NSE LIVE STATS & DIVERGENCE LOGIC ---
def get_institutional_stats():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        # 1. Broad Market Breadth (Nifty 500)
        m_url = "https://www.nseindia.com/api/marketStatus"
        m_data = session.get(m_url, headers=headers, timeout=10).json()
        adv, dec = 0, 0
        for m in m_data['marketState']:
            if m['index'] == 'NIFTY 500':
                adv, dec = m['advances'], m['declines']

        # 2. Sectoral Divergence Analysis
        s_url = "https://www.nseindia.com/api/allIndices"
        s_data = session.get(s_url, headers=headers, timeout=10).json()
        
        sector_report = ""
        sectors_to_scan = ['NIFTY BANK', 'NIFTY IT', 'NIFTY AUTO', 'NIFTY METAL', 'NIFTY PHARMA', 'NIFTY FMCG']
        
        for s in s_data['data']:
            if s['index'] in sectors_to_scan:
                idx_name = s['index']
                p_chg = s['pChange']
                # Divergence Check: Advances vs Declines within sector
                s_adv = int(s['advances'])
                s_dec = int(s['declines'])
                total = s_adv + s_dec
                
                status_icon = "🟢" if p_chg > 0 else "🔴"
                divergence_msg = ""
                
                # Divergence Logic: If Index is UP but more than 50% stocks are RED
                if p_chg > 0.5 and s_dec > s_adv:
                    divergence_msg = f"\n⚠️ <b>Divergence:</b> {idx_name} is manipulated by heavyweights! Avoid Longs."
                elif p_chg < -0.5 and s_adv > s_dec:
                    divergence_msg = f"\n⚠️ <b>Divergence:</b> Short covering or manipulation. Avoid Shorts."

                sector_report += f"{status_icon} <b>{idx_name}:</b> {p_chg}% (A:{s_adv}/D:{s_dec}){divergence_msg}\n"

        report = (
            f"<b>🏛️ Institutional Market Stats</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 <b>Broad Market (Nifty 500):</b>\n"
            f"✅ Advances: {adv} | ❌ Declines: {dec}\n"
            f"<i>Trend: {'Bullish' if adv > dec else 'Bearish'}</i>\n\n"
            f"🏗️ <b>Sectoral Analysis:</b>\n{sector_report}\n"
            f"🎯 <b>Strategy:</b> Trade in the direction of Breadth + Sector Strength."
        )
        return report
    except Exception as e:
        return f"❌ NSE API Error: {str(e)}"

# --- KEYBOARD ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('🔗 Login', '📊 Stats', '💰 Funds', '📈 Market', '📋 Help')
    return markup

# --- AUTOMATIC TASK (9:26 AM) ---
def auto_morning_report():
    sent_today = False
    while True:
        try:
            now = datetime.now(IST)
            if now.hour == 9 and now.minute == 26 and now.weekday() < 5:
                if not sent_today:
                    stats = get_institutional_stats()
                    bot.send_message(CHAT_ID, stats, parse_mode="HTML")
                    sent_today = True
            else:
                sent_today = False
            time.sleep(30)
        except:
            time.sleep(60)

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(CHAT_ID, "🚀 <b>Bot Ready!</b> Use buttons below:", parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == '📊 Stats')
def cmd_stats(m):
    bot.send_message(CHAT_ID, "⏳ Fetching Broad Market Stats...")
    report = get_institutional_stats()
    bot.send_message(CHAT_ID, report, parse_mode="HTML")

# ... (Include your existing /login, /connect, /funds handlers here) ...

if __name__ == "__main__":
    # Start the morning scanner thread
    threading.Thread(target=auto_morning_report, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
