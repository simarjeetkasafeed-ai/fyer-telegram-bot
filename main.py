import os
import telebot
import threading
import time
import pytz
from datetime import datetime, date
from fyers_apiv3 import fyersModel
from flask import Flask

# ============================================================
# CONFIG
# ============================================================
TOKEN        = os.environ.get("TELEGRAM_TOKEN")
APP_ID       = os.environ.get("FYERS_APP_ID")
SECRET_KEY   = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID      = os.environ.get("CHAT_ID")
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
IST          = pytz.timezone("Asia/Kolkata")

# ============================================================
# VALIDATION
# ============================================================
print("=" * 50)
print("CHECKING ENVIRONMENT VARIABLES...")
print(f"TELEGRAM_TOKEN  set: {bool(TOKEN)}")
print(f"FYERS_APP_ID    set: {bool(APP_ID)}")
print(f"FYERS_SECRET_KEY set: {bool(SECRET_KEY)}")
print(f"CHAT_ID         set: {bool(CHAT_ID)}")
print("=" * 50)

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")
if not APP_ID:
    raise ValueError("FYERS_APP_ID not set!")
if not SECRET_KEY:
    raise ValueError("FYERS_SECRET_KEY not set!")
if not CHAT_ID:
    raise ValueError("CHAT_ID not set!")

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
    return f"Trading Bot Running! | Time: {now} | Fyers: {st}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    print(f"Flask starting on port {port}...")
    app.run(host='0.0.0.0', port=port)

# ============================================================
# HELPER
# ============================================================
def send(msg):
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
        print(f"MSG SENT: {msg[:40]}...")
    except Exception as e:
        print(f"SEND ERROR: {e}")

def is_market_open():
    now     = datetime.now(IST)
    today   = date.today().strftime("%Y-%m-%d")
    weekday = now.weekday()
    if weekday >= 5:
        return False, "Weekend"
    if today in NSE_HOLIDAYS_2026:
        return False, "NSE Holiday"
    start = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    end   = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now < start:
        return False, "Market not opened yet"
    if now > end:
        return False, "Market closed for today"
    return True, "Market LIVE"

def get_live_data():
    if not fyers:
        return None, "Fyers not connected! /login bhejo"
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
        vix_dir = "Rising" if vix["lp"] > vix["open_price"] else "Falling"
        v = vix["lp"]
        if v < 16:
            mode = "NORMAL - Iron Condor"
        elif v > 19 and vix_dir == "Rising":
            mode = "PANIC - Buy Straddle"
        elif v > 19 and vix_dir == "Falling":
            mode = "SKIP - Volatility Crush"
        else:
            mode = "SKIP - VIX Danger Zone"
        if abs(gap) > 0.5 and "NORMAL" in mode:
            mode = "SKIP - Big Gap"
        return {
            "nifty_lp"  : nifty["lp"],
            "nifty_chp" : nifty["chp"],
            "nifty_ch"  : nifty["ch"],
            "nifty_high": nifty["high_price"],
            "nifty_low" : nifty["low_price"],
            "vix_lp"    : vix["lp"],
            "vix_open"  : vix["open_price"],
            "vix_dir"   : vix_dir,
            "gap"       : gap,
            "mode"      : mode,
            "atm_nifty" : round(nifty["lp"] / 50)  * 50,
            "atm_bn"    : round(nifty["lp"] / 100) * 100,
        }, "ok"
    except Exception as e:
        return None, str(e)

# ============================================================
# TELEGRAM COMMANDS
# ============================================================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    print(f"START command from chat_id: {m.chat.id}")
    send(
        "🚀 *Trading Bot Online!*\n\n"
        "Pehle Fyers connect karo:\n"
        "1️⃣ /login bhejo\n"
        "2️⃣ Browser mein login karo\n"
        "3️⃣ /connect CODE bhejo\n\n"
        "Saare commands: /help"
    )

@bot.message_handler(commands=['help'])
def cmd_help(m):
    print("HELP command")
    send(
        "📋 *All Commands:*\n\n"
        "*Login:*\n"
        "/login — Fyers login URL pao\n"
        "/connect CODE — Bot connect karo\n\n"
        "*Market:*\n"
        "/market — Live Nifty + VIX\n"
        "/decision — Aaj ka trading mode\n"
        "/strike — ATM strike prices\n"
        "/status — Market open/closed\n\n"
        "*Safety:*\n"
        "/stop — Emergency stop\n"
        "/ping — Bot alive check\n"
        "/connected — Fyers status"
    )

@bot.message_handler(commands=['ping'])
def cmd_ping(m):
    print("PING command")
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    send(f"✅ Bot alive!\n⏰ {now}")

@bot.message_handler(commands=['connected'])
def cmd_connected(m):
    print("CONNECTED command")
    if fyers:
        send("✅ *Fyers Connected!*\nBot trading ke liye ready hai.")
    else:
        send(
            "❌ *Not Connected!*\n\n"
            "Login karo:\n"
            "1️⃣ /login bhejo\n"
            "2️⃣ URL open karo\n"
            "3️⃣ /connect CODE bhejo"
        )

@bot.message_handler(commands=['login'])
def cmd_login(m):
    print("LOGIN command received!")

    if not APP_ID:
        send("❌ FYERS_APP_ID Render mein set nahi hai!")
        return
    if not SECRET_KEY:
        send("❌ FYERS_SECRET_KEY Render mein set nahi hai!")
        return

    send("⏳ Login URL generate ho raha hai...")

    try:
        session  = fyersModel.SessionModel(
            client_id     = APP_ID,
            secret_key    = SECRET_KEY,
            redirect_uri  = REDIRECT_URI,
            response_type = "code",
            grant_type    = "authorization_code"
        )
        auth_url = session.generate_authcode()
        print(f"Auth URL generated: {auth_url[:50]}...")

        if not auth_url:
            send("❌ Auth URL empty aaya!\nAPP_ID check karo.")
            return

        send(
            "🔑 *Login Steps:*\n\n"
            "1️⃣ Niche wala link browser mein kholo\n"
            "2️⃣ Fyers mein login karo\n"
            "3️⃣ Login ke baad browser ka\n"
            "    *poora URL* copy karo\n"
            "4️⃣ Wapas yahan paste karo:\n"
            "`/connect PASTE_FULL_URL_HERE`\n\n"
            f"🌐 *Login Link:*\n{auth_url}"
        )

    except Exception as e:
        print(f"LOGIN COMMAND ERROR: {e}")
        send(
            f"❌ Error aaya:\n`{str(e)}`\n\n"
            "Render mein Environment Variables\n"
            "check karo!"
        )

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    print("CONNECT command received!")

    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            send(
                "⚠️ *Format:*\n"
                "`/connect YOUR_AUTH_CODE`\n\n"
                "Ya poora URL:\n"
                "`/connect https://trade.fyers.in/...?auth_code=XXXX`"
            )
            return

        inp = args[1].strip()

        # Auth code extract karo — URL se bhi kaam kare
        if "auth_code=" in inp:
            auth_code = inp.split("auth_code=")[1].split("&")[0]
            print(f"Auth code extracted from URL: {auth_code[:10]}...")
        else:
            auth_code = inp
            print(f"Auth code direct: {auth_code[:10]}...")

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

            # Profile verify karo
            profile = fyers.get_profile()
            name    = profile.get("data", {}).get("name", "Trader")
            print(f"Fyers connected for: {name}")

            send(
                f"✅ *BINGO! Connected!*\n\n"
                f"👤 Name: *{name}*\n"
                f"🔑 Token: Active\n\n"
                f"Ab use karo:\n"
                f"/market — Live data\n"
                f"/decision — Aaj ka mode\n"
                f"/strike — ATM strikes"
            )
        else:
            error = res.get("message", str(res))
            print(f"Connection failed: {error}")
            send(
                f"❌ *Connection Failed!*\n"
                f"Error: {error}\n\n"
                f"Dobara try karo:\n"
                f"/login bhejo → fresh code lo"
            )

    except Exception as e:
        print(f"CONNECT ERROR: {e}")
        send(f"❌ Error: `{str(e)}`\n\nDobara /login se try karo")

@bot.message_handler(commands=['status'])
def cmd_status(m):
    print("STATUS command")
    open_st, reason = is_market_open()
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    fst = "✅ Connected" if fyers else "❌ Not connected"
    if open_st:
        send(f"✅ *Market OPEN*\n⏰ {now}\n🔗 Fyers: {fst}")
    else:
        send(
            f"🔴 *Market Closed*\n"
            f"⏰ {now}\n"
            f"📋 Reason: {reason}\n"
            f"🔗 Fyers: {fst}"
        )

@bot.message_handler(commands=['market'])
def cmd_market(m):
    print("MARKET command")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    send("📊 Live data fetch ho raha hai...")
    data, status = get_live_data()
    if not data:
        send(f"❌ Data failed!\n{status}")
        return
    e = "🟢" if data["nifty_chp"] >= 0 else "🔴"
    send(
        f"📈 *Live Market*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Nifty 50:* {data['nifty_lp']:,.1f} {e}\n"
        f"*Change:* {data['nifty_chp']:+.2f}%\n"
        f"*High:* {data['nifty_high']:,.1f}\n"
        f"*Low:* {data['nifty_low']:,.1f}\n"
        f"*Gap Open:* {data['gap']:+.2f}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*India VIX:* {data['vix_lp']:.2f}\n"
        f"*VIX Open:* {data['vix_open']:.2f}\n"
        f"*VIX Direction:* {data['vix_dir']}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Bot Mode:* `{data['mode']}`"
    )

@bot.message_handler(commands=['decision'])
def cmd_decision(m):
    print("DECISION command")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    open_st, reason = is_market_open()
    if not open_st:
        send(f"🔴 Market closed!\nReason: {reason}")
        return
    data, status = get_live_data()
    if not data:
        send(f"❌ {status}")
        return
    mode = data["mode"]
    if "NORMAL" in mode:
        e      = "🟢"
        action = (
            f"*Iron Condor Setup:*\n"
            f"Sell CE: `{data['atm_nifty'] + 200}`\n"
            f"Buy CE:  `{data['atm_nifty'] + 300}`\n"
            f"Sell PE: `{data['atm_nifty'] - 200}`\n"
            f"Buy PE:  `{data['atm_nifty'] - 300}`\n"
            f"Lot size: 65 units"
        )
    elif "PANIC" in mode:
        e      = "🚨"
        action = (
            f"*Straddle Setup:*\n"
            f"Buy CE: `NIFTY{data['atm_nifty']}CE`\n"
            f"Buy PE: `NIFTY{data['atm_nifty']}PE`\n"
            f"Lot size: 65 units\n"
            f"Exit by: 10:30 AM"
        )
    else:
        e      = "⛔"
        action = "Aaj trade mat karo!\nCapital safe rakho."
    send(
        f"{e} *Aaj Ka Decision*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Mode:* `{mode}`\n\n"
        f"{action}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*VIX:* {data['vix_lp']:.2f} ({data['vix_dir']})\n"
        f"*Gap:* {data['gap']:+.2f}%"
    )

@bot.message_handler(commands=['strike'])
def cmd_strike(m):
    print("STRIKE command")
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    data, status = get_live_data()
    if not data:
        send(f"❌ {status}")
        return
    send(
        f"🎯 *ATM Strike Prices*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Nifty Spot:* {data['nifty_lp']:,.1f}\n\n"
        f"*Nifty ATM:* {data['atm_nifty']}\n"
        f"CE: `NIFTY{data['atm_nifty']}CE`\n"
        f"PE: `NIFTY{data['atm_nifty']}PE`\n\n"
        f"*BankNifty ATM:* {data['atm_bn']}\n"
        f"CE: `BANKNIFTY{data['atm_bn']}CE`\n"
        f"PE: `BANKNIFTY{data['atm_bn']}PE`"
    )

@bot.message_handler(commands=['stop'])
def cmd_stop(m):
    print("STOP command!")
    send(
        "🛑 *EMERGENCY STOP!*\n\n"
        "Fyers One app mein TURANT\n"
        "saari positions exit karo!\n\n"
        "Bot monitoring paused.\n"
        "Reconnect: /login"
    )

@bot.message_handler(func=lambda m: True)
def unknown(m):
    print(f"Unknown message: {m.text}")
    send("❓ Command samajh nahi aaya!\n/help se commands dekho.")

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
                    "Market 15 minute mein khulega!\n\n"
                    "🔑 Pehle login karo:\n"
                    "/login bhejo\n\n"
                    "Phir check karo:\n"
                    "/market — Live data\n"
                    "/decision — Aaj ka mode"
                )
                reminded_today = today
                print("Morning reminder sent!")
            time.sleep(30)
        except Exception as e:
            print(f"Morning reminder error: {e}")
            time.sleep(60)

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("TRADING BOT STARTING...")
    print(f"TOKEN    set: {bool(TOKEN)}")
    print(f"APP_ID   set: {bool(APP_ID)}")
    print(f"SECRET   set: {bool(SECRET_KEY)}")
    print(f"CHAT_ID  set: {bool(CHAT_ID)}")
    print("=" * 50)

    # Flask — background thread mein
    flask_t = threading.Thread(target=run_flask)
    flask_t.daemon = True
    flask_t.start()
    print("Flask thread started!")

    # Morning reminder — background thread
    morning_t = threading.Thread(target=morning_reminder_loop)
    morning_t.daemon = True
    morning_t.start()
    print("Morning reminder thread started!")

    # Startup Telegram message
    try:
        bot.send_message(
            CHAT_ID,
            "🚀 *Bot Online!*\n/login bhejo Fyers connect karne ke liye",
            parse_mode="Markdown"
        )
        print("Startup message sent to Telegram!")
    except Exception as e:
        print(f"Startup message error (continuing): {e}")

    # Telegram Polling — ye ZAROOR chalna chahiye
    print("Starting Telegram polling NOW...")
    try:
        bot.infinity_polling(
            skip_pending   = True,
            timeout        = 60,
            long_polling_timeout = 60
        )
    except Exception as e:
        print(f"POLLING CRASHED: {e}")
        raise
