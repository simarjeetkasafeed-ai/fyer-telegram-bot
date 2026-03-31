import os
import telebot
import threading
import time
import pytz
import urllib.parse
from datetime import datetime, date
from fyers_apiv3 import fyersModel
from flask import Flask

# ============================================================
# CONFIG — Render Environment Variables
# ============================================================
TOKEN         = os.environ.get("TELEGRAM_TOKEN")
APP_ID        = os.environ.get("FYERS_APP_ID")
SECRET_KEY    = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID       = os.environ.get("CHAT_ID")
REDIRECT_URI  = "https://trade.fyers.in/api-login/redirect-uri/index.html"
IST           = pytz.timezone("Asia/Kolkata")

# ============================================================
# INIT & CHECKS
# ============================================================
bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

# ============================================================
# FLASK SERVER (Render active rakhne ke liye)
# ============================================================
@app.route('/')
def home():
    now = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    return f"Fyers Bot V3 Active | {now}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ============================================================
# BOT COMMANDS
# ============================================================

@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(CHAT_ID, 
        "🚀 *Trading Bot V3 Ready!*\n\n"
        "Fyers connect karne ke liye:\n"
        "1️⃣ /login - Fresh login link paao\n"
        "2️⃣ /connect - Link paste karke connect karo\n"
        "3️⃣ /funds - Balance check karo", 
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['login'])
def cmd_login(m):
    try:
        # EXACT V3 LINK STRUCTURE (Jo aapne bataya)
        base_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
        params = {
            "client_id": APP_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "state": "None"
        }
        auth_url = base_url + "?" + urllib.parse.urlencode(params)
        
        msg = (
            "🔑 *Fyers V3 Login:*\n\n"
            f"1️⃣ [Is Link Par Click Karein]({auth_url})\n\n"
            "2️⃣ Login ke baad browser URL copy karein\n"
            "3️⃣ Bot par bhejein: `/connect YOUR_URL`"
        )
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Login Error: {e}")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Use: `/connect POORA_URL_YAHAN`")
            return

        inp = args[1].strip()
        # URL se auth_code extract karna
        auth_code = inp.split("auth_code=")[1].split("&")[0] if "auth_code=" in inp else inp

        bot.send_message(CHAT_ID, "⏳ Connecting to Fyers V3...")

        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code"
        )
        session.set_token(auth_code)
        res = session.generate_access_token()

        if res.get("s") == "ok":
            tk = res.get("access_token")
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, log_path="", is_async=False)
            
            p = fyers.get_profile()
            name = p.get("data", {}).get("name", "Trader")
            bot.send_message(CHAT_ID, f"✅ *BINGO! Connected.*\n👤 *User:* {name}\nTry `/funds` now.", parse_mode="Markdown")
        else:
            bot.send_message(CHAT_ID, f"❌ *Fyers Error:* {res.get('message')}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ System Error: {e}")

@bot.message_handler(commands=['funds'])
def cmd_funds(m):
    if not fyers:
        bot.send_message(CHAT_ID, "❌ Pehle /login karo!")
        return
    try:
        res = fyers.funds()
        bal = res.get("fund_limit", [{}])[0].get("equityAmount", 0)
        bot.send_message(CHAT_ID, f"💰 *Margin Available:* ₹{bal:,.2f}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(commands=['market'])
def cmd_market(m):
    if not fyers:
        bot.send_message(CHAT_ID, "❌ Login Required!")
        return
    try:
        res = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX,NSE:INDIAVIX-INDEX"})
        nifty = res["d"][0]["v"]
        e = "🟢" if nifty["chp"] >= 0 else "🔴"
        bot.send_message(CHAT_ID, f"📈 *Nifty 50:* {nifty['lp']} {e} ({nifty['chp']}%)\n📊 *VIX:* {res['d'][1]['v']['lp']}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Quote Error: {e}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Bot Polling Started...")
    bot.infinity_polling(skip_pending=True)
