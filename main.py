import os, telebot, threading, urllib.parse, requests, time
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

@app.route('/')
def home(): return "Bot is Online"

# --- NSE DATA FETCH ---
def get_institutional_stats():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/'
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        time.sleep(1) # Chota delay taaki NSE block na kare
        
        response = session.get("https://www.nseindia.com/api/allIndices", headers=headers, timeout=10)
        s_data = response.json()
        
        report = "<b>🏛️ Market Stats (NSE)</b>\n━━━━━━━━━━━━━━\n"
        sectors = ['NIFTY 500', 'NIFTY BANK', 'NIFTY IT', 'NIFTY AUTO', 'NIFTY METAL', 'NIFTY PHARMA']
        
        for s in s_data['data']:
            if s['index'] in sectors:
                name = s['index']
                p_chg = s['pChange']
                adv, dec = int(s['advances']), int(s['declines'])
                icon = "🟢" if p_chg > 0 else "🔴"
                
                # Divergence Logic
                div = ""
                if p_chg > 0.4 and dec > adv: div = "\n⚠️ <i>Manipulation Alert!</i>"
                elif p_chg < -0.4 and adv > dec: div = "\n⚠️ <i>Short Covering!</i>"
                
                report += f"{icon} <b>{name}:</b> {p_chg}% (A:{adv}/D:{dec}){div}\n"
        return report
    except:
        return "❌ NSE Server Busy. Try /stats again."

# --- KEYBOARD ---
def main_menu():
    m = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    m.add('🔗 Login', '📊 Stats', '💰 Funds', '📈 Market', '📋 Help')
    return m

# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(CHAT_ID, "🚀 <b>Bot Ready!</b>", parse_mode="HTML", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ['🔗 Login', '/login'])
def login(m):
    url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={APP_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&response_type=code&state=None"
    bot.send_message(CHAT_ID, f"🔑 <b>Login Link:</b>\n\n{url}", parse_mode="HTML")

@bot.message_handler(commands=['connect'])
def connect(m):
    global fyers
    try:
        code = m.text.split("auth_code=")[1].split("&")[0] if "auth_code=" in m.text else m.text.replace("/connect ", "")
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code")
        session.set_token(code.strip())
        try: res = session.generate_access_token()
        except: res = session.generate_token()

        if res.get("s") == "ok":
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=res.get("access_token"), is_async=False)
            bot.send_message(CHAT_ID, "✅ <b>Connected!</b>", parse_mode="HTML")
        else:
            bot.send_message(CHAT_ID, f"❌ Fail: {res.get('message')}")
    except Exception as e: bot.send_message(CHAT_ID, f"❌ Error: {str(e)}")

@bot.message_handler(func=lambda m: m.text == '📊 Stats')
def stats(m):
    bot.send_message(CHAT_ID, get_institutional_stats(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == '💰 Funds')
def funds(m):
    if not fyers: return bot.send_message(CHAT_ID, "❌ Login First!")
    res = fyers.funds()
    bal = res.get("fund_limit", [{}])[0].get("equityAmount", 0)
    bot.send_message(CHAT_ID, f"💰 <b>Balance:</b> ₹{bal}", parse_mode="HTML")

# --- AUTO TASK ---
def auto_run():
    while True:
        now = datetime.now(IST)
        if now.hour == 9 and now.minute == 26 and now.weekday() < 5:
            bot.send_message(CHAT_ID, get_institutional_stats(), parse_mode="HTML")
            time.sleep(60)
        time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=auto_run, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
