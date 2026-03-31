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
TOKEN        = os.environ.get("TELEGRAM_TOKEN")
APP_ID       = os.environ.get("FYERS_APP_ID")
SECRET_KEY   = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID      = os.environ.get("CHAT_ID")
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
IST          = pytz.timezone("Asia/Kolkata")

# ============================================================
# STARTUP CHECKS
# ============================================================
print("=" * 50)
print("TRADING BOT STARTING...")
print(f"TOKEN    set: {bool(TOKEN)}")
print(f"APP_ID   set: {bool(APP_ID)}")
print(f"SECRET   set: {bool(SECRET_KEY)}")
print(f"CHAT_ID  set: {bool(CHAT_ID)}")
print("=" * 50)

if not TOKEN:    raise ValueError("TELEGRAM_TOKEN not set!")
if not APP_ID:   raise ValueError("FYERS_APP_ID not set!")
if not SECRET_KEY: raise ValueError("FYERS_SECRET_KEY not set!")
if not CHAT_ID:  raise ValueError("CHAT_ID not set!")

# ============================================================
# INIT
# ============================================================
bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

# ============================================================
# NSE HOLIDAYS 2026
# ============================================================
NSE_HOLIDAYS_2026 = [
    "2026-01-15","2026-01-26","2026-03-03","2026-03-26",
    "2026-03-31","2026-04-03","2026-04-14","2026-05-01",
    "2026-05-28","2026-06-26","2026-09-14","2026-10-02",
    "2026-10-20","2026-11-10","2026-11-24","2026-12-25"
]

# ============================================================
# FLASK — Render alive rakhne ke liye
# ============================================================
@app.route('/')
def home():
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S IST")
    st  = "Connected" if fyers else "Not Connected"
    return f"Trading Bot | {now} | Fyers: {st}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"Flask on port {port}")
    app.run(host='0.0.0.0', port=port)

# ============================================================
# HELPERS
# ============================================================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        print(f"SENT: {msg[:60]}...")
    except Exception as e:
        print(f"SEND ERROR: {e}")

def is_market_open():
    now     = datetime.now(IST)
    today   = date.today().strftime("%Y-%m-%d")
    if now.weekday() >= 5:
        return False, "Weekend"
    if today in NSE_HOLIDAYS_2026:
        return False, "NSE Holiday"
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
    print(f"START from {m.chat.id}")
    send(
        "🚀 *Trading Bot Online!*\n\n"
        "Fyers connect karne ke liye:\n"
        "1️⃣ /login\n"
        "2️⃣ URL kholo, login karo\n"
        "3️⃣ /connect URL_PASTE_HERE\n\n"
        "Saare commands: /help"
    )

@bot.message_handler(commands=['help'])
def cmd_help(m):
    print("HELP")
    send(
        "📋 *Commands:*\n\n"
        "*Fyers Login:*\n"
        "/login — Login URL pao\n"
        "/connect CODE — Connect karo\n"
        "/connected — Status check\n\n"
        "*Market Data:*\n"
        "/market — Nifty + VIX live\n"
        "/status — Market open/closed\n"
        "/funds — Account balance\n"
        "/positions — Open positions\n"
        "/orders — Order book\n"
        "/holdings — Holdings\n"
        "/profile — Account info\n\n"
        "*Utility:*\n"
        "/ping — Bot alive check\n"
        "/stop — Emergency stop"
    )

@bot.message_handler(commands=['ping'])
def cmd_ping(m):
    print("PING")
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    send(f"✅ Bot alive!\n⏰ {now}")

@bot.message_handler(commands=['connected'])
def cmd_connected(m):
    print("CONNECTED check")
    if fyers:
        send("✅ *Fyers Connected!*\nBot ready hai.")
    else:
        send("❌ *Not Connected!*\n/login bhejo pehle.")

# ── FYERS LOGIN ──────────────────────────────────────────────

@bot.message_handler(commands=['login'])
def cmd_login(m):
    print("LOGIN command!")
    if not APP_ID or not SECRET_KEY:
        send("❌ FYERS_APP_ID ya SECRET_KEY set nahi!\nRender environment variables check karo.")
        return

    send("⏳ Login URL ban raha hai...")

    try:
        # Manually correct URL banate hain
        base_url = "https://api.fyers.in/api/v2/generate-authcode"
        params   = {
            "client_id"    : APP_ID,
            "redirect_uri" : REDIRECT_URI,
            "response_type": "code",
            "state"        : "trading_bot"
        }
        auth_url = base_url + "?" + urllib.parse.urlencode(params)
        print(f"Auth URL: {auth_url}")

        send(
            "🔑 *Login Steps:*\n\n"
            "1️⃣ Niche link browser mein kholo\n"
            "2️⃣ Fyers ID + Password se login karo\n"
            "3️⃣ Login ke baad browser address bar\n"
            "    ka *poora URL* copy karo\n"
            "4️⃣ Yahan bhejo:\n"
            "`/connect POORA_URL_YAHAN`\n\n"
            f"🌐 *Login Link:*\n{auth_url}"
        )
    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    print("CONNECT command!")
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            send(
                "⚠️ *Format:*\n"
                "`/connect AUTH_CODE`\n\n"
                "Ya poora redirect URL:\n"
                "`/connect https://trade.fyers.in/...?auth_code=XXXX`"
            )
            return

        inp = args[1].strip()

        # URL se auth code nikalo
        if "auth_code=" in inp:
            auth_code = inp.split("auth_code=")[1].split("&")[0]
            print(f"Code from URL: {auth_code[:15]}...")
        else:
            auth_code = inp
            print(f"Direct code: {auth_code[:15]}...")

        send("⏳ Fyers se connect ho raha hai...")

        session = fyersModel.SessionModel(
            client_id     = APP_ID,
            secret_key    = SECRET_KEY,
            redirect_uri  = REDIRECT_URI,
            response_type = "code",
            grant_type    = "authorization_code"
        )
        session.set_token(auth_code)
        res = session.generate_token()
        print(f"Token response: {str(res)[:100]}")

        if res.get("s") == "ok" or "access_token" in res:
            token = res.get("access_token")
            fyers = fyersModel.FyersModel(
                client_id = APP_ID,
                is_async  = False,
                token     = token,
                log_path  = ""
            )
            # Profile verify
            profile = fyers.get_profile()
            name    = profile.get("data", {}).get("name", "Trader")
            email   = profile.get("data", {}).get("email_id", "")
            print(f"Connected: {name}")
            send(
                f"✅ *BINGO! Fyers Connected!*\n\n"
                f"👤 *Name:* {name}\n"
                f"📧 *Email:* {email}\n"
                f"🔑 *Token:* Active\n\n"
                f"Ab use karo:\n"
                f"/market /funds /positions"
            )
        else:
            error = res.get("message", str(res))
            print(f"Failed: {error}")
            send(
                f"❌ *Connection Failed!*\n"
                f"Error: `{error}`\n\n"
                f"Dobara /login se fresh code lo"
            )
    except Exception as e:
        print(f"CONNECT ERROR: {e}")
        send(f"❌ Error: `{str(e)}`\n\n/login se dobara try karo")

# ── MARKET DATA ──────────────────────────────────────────────

@bot.message_handler(commands=['status'])
def cmd_status(m):
    print("STATUS")
    open_st, reason = is_market_open()
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    fst = "✅ Connected" if fyers else "❌ Not connected"
    if open_st:
        send(f"✅ *Market OPEN*\n⏰ {now}\n🔗 Fyers: {fst}")
    else:
        send(f"🔴 *Market Closed*\n⏰ {now}\nReason: {reason}\n🔗 Fyers: {fst}")

@bot.message_handler(commands=['market'])
def cmd_market(m):
    print("MARKET")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    send("📊 Fetching...")
    try:
        res   = fyers.quotes({
            "symbols": "NSE:NIFTY50-INDEX,NSE:INDIAVIX-INDEX"
        })
        nifty = res["d"][0]["v"]
        vix   = res["d"][1]["v"]
        gap   = round(
            (nifty["open_price"] - nifty["prev_close_price"])
            / nifty["prev_close_price"] * 100, 2
        )
        e = "🟢" if nifty["chp"] >= 0 else "🔴"
        vix_dir = "📈 Rising" if vix["lp"] > vix["open_price"] else "📉 Falling"
        send(
            f"📈 *Live Market*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"*Nifty 50:* {nifty['lp']:,.1f} {e}\n"
            f"*Change:* {nifty['chp']:+.2f}% ({nifty['ch']:+.1f})\n"
            f"*Open:* {nifty['open_price']:,.1f}\n"
            f"*High:* {nifty['high_price']:,.1f}\n"
            f"*Low:* {nifty['low_price']:,.1f}\n"
            f"*Prev Close:* {nifty['prev_close_price']:,.1f}\n"
            f"*Gap Open:* {gap:+.2f}%\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"*India VIX:* {vix['lp']:.2f}\n"
            f"*VIX Direction:* {vix_dir}\n"
            f"*VIX Change:* {vix['chp']:+.2f}%"
        )
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['profile'])
def cmd_profile(m):
    print("PROFILE")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res  = fyers.get_profile()
        data = res.get("data", {})
        send(
            f"👤 *Account Profile*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"*Name:* {data.get('name','')}\n"
            f"*Email:* {data.get('email_id','')}\n"
            f"*Mobile:* {data.get('mobile_number','')}\n"
            f"*PAN:* {data.get('pan','')}\n"
            f"*Client ID:* {data.get('fy_id','')}"
        )
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['funds'])
def cmd_funds(m):
    print("FUNDS")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res  = fyers.funds()
        data = res.get("fund_limit", [])
        msg  = "💰 *Account Funds*\n━━━━━━━━━━━━━━━━\n"
        for item in data:
            title = item.get("title", "")
            val   = item.get("equityAmount", 0)
            if title and val:
                msg += f"*{title}:* ₹{val:,.2f}\n"
        send(msg)
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['positions'])
def cmd_positions(m):
    print("POSITIONS")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res  = fyers.positions()
        data = res.get("netPositions", [])
        if not data:
            send("📋 *Positions*\n\nKoi open position nahi hai.")
            return
        msg = f"📋 *Open Positions ({len(data)})*\n━━━━━━━━━━━━━━━━\n"
        for p in data:
            sym = p.get("symbol","")
            qty = p.get("netQty", 0)
            pl  = p.get("pl", 0)
            ltp = p.get("ltp", 0)
            e   = "🟢" if pl >= 0 else "🔴"
            msg += (
                f"{e} *{sym}*\n"
                f"Qty: {qty} | LTP: {ltp}\n"
                f"P&L: ₹{pl:,.2f}\n\n"
            )
        send(msg)
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['orders'])
def cmd_orders(m):
    print("ORDERS")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res  = fyers.orderbook()
        data = res.get("orderBook", [])
        if not data:
            send("📒 *Orders*\n\nKoi order nahi hai.")
            return
        msg = f"📒 *Orders ({len(data)})*\n━━━━━━━━━━━━━━━━\n"
        for o in data[-5:]:  # Last 5 orders
            sym    = o.get("symbol","")
            side   = "BUY 🟢" if o.get("side") == 1 else "SELL 🔴"
            qty    = o.get("qty", 0)
            price  = o.get("tradedPrice", 0)
            status = o.get("status", 0)
            st_map = {1:"Cancelled", 2:"Traded ✅", 4:"Transit", 6:"Pending ⏳"}
            st_txt = st_map.get(status, str(status))
            msg += (
                f"*{sym}*\n"
                f"{side} | Qty: {qty} | ₹{price}\n"
                f"Status: {st_txt}\n\n"
            )
        send(msg)
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['holdings'])
def cmd_holdings(m):
    print("HOLDINGS")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    try:
        res  = fyers.holdings()
        data = res.get("holdings", [])
        if not data:
            send("📦 *Holdings*\n\nKoi holding nahi hai.")
            return
        msg       = f"📦 *Holdings ({len(data)})*\n━━━━━━━━━━━━━━━━\n"
        total_pl  = 0
        for h in data:
            sym  = h.get("symbol","")
            qty  = h.get("quantity", 0)
            pl   = h.get("pl", 0)
            ltp  = h.get("ltp", 0)
            e    = "🟢" if pl >= 0 else "🔴"
            total_pl += pl
            msg += f"{e} *{sym}*\nQty: {qty} | LTP: {ltp} | P&L: ₹{pl:,.2f}\n\n"
        total_e = "🟢" if total_pl >= 0 else "🔴"
        msg += f"━━━━━━━━━━━━━━━━\n{total_e} *Total P&L:* ₹{total_pl:,.2f}"
        send(msg)
    except Exception as e:
        send(f"❌ Error: `{str(e)}`")

@bot.message_handler(commands=['stop'])
def cmd_stop(m):
    print("STOP!")
    send(
        "🛑 *EMERGENCY STOP!*\n\n"
        "Fyers One app mein TURANT\n"
        "saari positions exit karo!\n\n"
        "Fyers One → Positions →\n"
        "Exit All Positions\n\n"
        "Reconnect: /login"
    )

@bot.message_handler(func=lambda m: True)
def unknown(m):
    print(f"Unknown: {m.text}")
    send("❓ /help se commands dekho")

# ============================================================
# MORNING REMINDER — 9:00 AM
# ============================================================
def morning_reminder_loop():
    reminded_today = None
    while True:
        try:
            now   = datetime.now(IST)
            today = now.date()
            if (now.hour == 9 and
                now.minute == 0 and
                now.weekday() < 5 and
                today.strftime("%Y-%m-%d") not in NSE_HOLIDAYS_2026 and
                reminded_today != today):
                send(
                    "🌅 *Good Morning Simarjeet!*\n\n"
                    "Market 15 min mein khulega!\n\n"
                    "🔑 Abhi login karo:\n"
                    "/login bhejo"
                )
                reminded_today = today
                print("Morning reminder sent!")
            time.sleep(30)
        except Exception as e:
            print(f"Morning error: {e}")
            time.sleep(60)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("ALL SYSTEMS GO!")
    print("=" * 50)

    # Flask background mein
    flask_t = threading.Thread(target=run_flask)
    flask_t.daemon = True
    flask_t.start()
    print("Flask started!")

    # Morning reminder
    morning_t = threading.Thread(target=morning_reminder_loop)
    morning_t.daemon = True
    morning_t.start()
    print("Morning reminder started!")

    # Startup message
    try:
        bot.send_message(
            CHAT_ID,
            "🚀 *Bot Online!*\n\n"
            "Fyers connect karne ke liye:\n"
            "/login bhejo",
            parse_mode="Markdown"
        )
        print("Startup message sent!")
    except Exception as e:
        print(f"Startup msg error (ok): {e}")

    # Telegram Polling
    print("Telegram polling starting...")
    print("=" * 50)
    bot.infinity_polling(
        skip_pending         = True,
        timeout              = 60,
        long_polling_timeout = 60
    )
