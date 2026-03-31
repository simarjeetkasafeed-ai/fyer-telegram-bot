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
# STARTUP CHECKS
# ============================================================
print("=" * 50)
print("TRADING BOT STARTING (V3 READY)...")
print("=" * 50)

if not TOKEN or not APP_ID or not SECRET_KEY or not CHAT_ID:
    raise ValueError("Check Environment Variables! One or more keys are missing.")

# ============================================================
# INIT
# ============================================================
bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

# NSE HOLIDAYS 2026
NSE_HOLIDAYS_2026 = [
    "2026-01-15","2026-01-26","2026-03-03","2026-03-26",
    "2026-03-31","2026-04-03","2026-04-14","2026-05-01",
    "2026-05-28","2026-06-26","2026-09-14","2026-10-02",
    "2026-10-20","2026-11-10","2026-11-24","2026-12-25"
]

@app.route('/')
def home():
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S IST")
    st  = "Connected" if fyers else "Not Connected"
    return f"Trading Bot V3 | {now} | Fyers: {st}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ============================================================
# HELPERS
# ============================================================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"SEND ERROR: {e}")

def is_market_open():
    now     = datetime.now(IST)
    today   = date.today().strftime("%Y-%m-%d")
    if now.weekday() >= 5: return False, "Weekend"
    if today in NSE_HOLIDAYS_2026: return False, "NSE Holiday"
    start = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now < start: return False, "Market not opened yet"
    if now > end:   return False, "Market closed for today"
    return True, "Market LIVE"

# ============================================================
# COMMANDS
# ============================================================

@bot.message_handler(commands=['start'])
def cmd_start(m):
    send(
        "🚀 *Trading Bot V3 Online!*\n\n"
        "Fyers connect karne ke liye:\n"
        "1️⃣ /login\n"
        "2️⃣ URL kholo, login karo\n"
        "3️⃣ /connect URL_PASTE_HERE\n\n"
        "Saare commands: /help"
    )

# ── FYERS LOGIN (V3 UPDATED) ──────────────────────────────────

@bot.message_handler(commands=['login'])
def cmd_login(m):
    try:
        # V3 ke liye session object banate hain
        session = fyersModel.SessionModel(
            client_id=APP_ID,
            secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code"
        )
        # V3 Login URL generate karna
        auth_url = session.generate_authcode()
        
        send(
            "🔑 *Fyers V3 Login:*\n\n"
            "1️⃣ Niche link browser mein kholo\n"
            "2️⃣ Login ke baad browser URL copy karo\n"
            "3️⃣ Yahan bhejo: `/connect URL_YAHAN` \n\n"
            f"🌐 *Login Link:*\n{auth_url}"
        )
    except Exception as e:
        send(f"❌ Login Error: `{str(e)}`")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            send("⚠️ Format: `/connect POORA_URL_YAHAN`")
            return

        inp = args[1].strip()
        # URL se auth code nikalna
        if "auth_code=" in inp:
            auth_code = inp.split("auth_code=")[1].split("&")[0]
        else:
            auth_code = inp

        send("⏳ V3 Connection in progress...")

        session = fyersModel.SessionModel(
            client_id=APP_ID,
            secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth_code)
        
        # V3 Token Generation
        res = session.generate_access_token()

        if res.get("s") == "ok":
            token = res.get("access_token")
            fyers = fyersModel.FyersModel(
                client_id=APP_ID,
                token=token,
                log_path="",
                is_async=False
            )
            profile = fyers.get_profile()
            name = profile.get("data", {}).get("name", "Trader")
            send(f"✅ *BINGO! V3 Connected!*\n👤 *Trader:* {name}")
        else:
            send(f"❌ *Fail:* `{res.get('message', 'Check Keys')}`")
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

# ── MARKET DATA HANDLERS (SAME AS BEFORE) ──────────────────────

@bot.message_handler(commands=['market'])
def cmd_market(m):
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX,NSE:INDIAVIX-INDEX"})
        nifty = res["d"][0]["v"]
        vix = res["d"][1]["v"]
        e = "🟢" if nifty["chp"] >= 0 else "🔴"
        send(f"📈 *Nifty 50:* {nifty['lp']} {e} ({nifty['chp']}%)\n📉 *India VIX:* {vix['lp']}")
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

# Baaki commands (funds, positions, orders) as it is kaam karenge...

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    send("🚀 *Bot Online (V3 Ready)!*")
    bot.infinity_polling(skip_pending=True)
