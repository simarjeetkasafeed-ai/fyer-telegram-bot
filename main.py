import os
import telebot
import threading
import time
import pytz
from datetime import datetime, date
from fyers_apiv3 import fyersModel
from flask import Flask

TOKEN        = os.environ.get("TELEGRAM_TOKEN")
APP_ID       = os.environ.get("FYERS_APP_ID")
SECRET_KEY   = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID      = os.environ.get("CHAT_ID")
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
IST          = pytz.timezone("Asia/Kolkata")

bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

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
    return f"Trading Bot Running! Time: {now} | Fyers: {st}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def send(msg):
    try:
        bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Send error: {e}")

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
        return None, "Fyers not connected! Send /login"
    try:
        res   = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX,NSE:INDIAVIX-INDEX"})
        nifty = res["d"][0]["v"]
        vix   = res["d"][1]["v"]
        gap   = round((nifty["open_price"] - nifty["prev_close_price"]) / nifty["prev_close_price"] * 100, 2)
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

@bot.message_handler(commands=['start'])
def cmd_start(m):
    print(f"Start from {m.chat.id}")
    send(
        "🚀 *Trading Bot Online!*\n\n"
        "Pehle Fyers connect karo:\n"
        "1️⃣ /login bhejo\n"
        "2️⃣ Browser mein login karo\n"
        "3️⃣ /connect CODE bhejo\n\n"
        "Commands: /help"
    )

@bot.message_handler(commands=['help'])
def cmd_help(m):
    send(
        "📋 *All Commands:*\n\n"
        "*Login:*\n"
        "/login — Login URL pao\n"
        "/connect CODE — Connect karo\n\n"
        "*Market:*\n"
        "/market — Live Nifty + VIX\n"
        "/decision — Aaj ka mode\n"
        "/strike — ATM strikes\n"
        "/status — Market status\n\n"
        "*Safety:*\n"
        "/stop — Emergency stop\n"
        "/ping — Bot alive check\n"
        "/connected — Fyers status"
    )

@bot.message_handler(commands=['ping'])
def cmd_ping(m):
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    send(f"✅ Bot alive!\n⏰ {now}")

@bot.message_handler(commands=['connected'])
def cmd_connected(m):
    if fyers:
        send("✅ *Fyers Connected!*\nBot ready hai.")
    else:
        send("❌ *Not Connected!*\n/login bhejo pehle.")

@bot.message_handler(commands=['login'])
def cmd_login(m):
    try:
        session  = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI,
            response_type="code", grant_type="authorization_code"
        )
        auth_url = session.generate_authcode()
        send(
            "🔑 *Login Steps:*\n\n"
            "1️⃣ Niche link open karo\n"
            "2️⃣ Fyers mein login karo\n"
            "3️⃣ Browser ka *poora URL* copy karo\n"
            "4️⃣ Yahan bhejo:\n"
            "`/connect PASTE_URL_HERE`\n\n"
            f"🌐 *Login Link:*\n{auth_url}"
        )
    except Exception as e:
        send(f"❌ Login URL failed!\n{str(e)}")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            send("⚠️ Format:\n`/connect YOUR_AUTH_CODE`\n\nYa poora URL paste karo")
            return
        inp = args[1].strip()
        if "auth_code=" in inp:
            auth_code = inp.split("auth_code=")[1].split("&")[0]
        else:
            auth_code = inp
        send("⏳ Connecting to Fyers...")
        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI,
            response_type="code", grant_type="authorization_code"
        )
        session.set_token(auth_code)
        res = session.generate_token()
        if res.get("s") == "ok" or "access_token" in res:
            token = res.get("access_token")
            fyers = fyersModel.FyersModel(
                client_id=APP_ID, is_async=False,
                token=token, log_path=""
            )
            profile = fyers.get_profile()
            name    = profile.get("data", {}).get("name", "Trader")
            send(
                f"✅ *BINGO! Connected!*\n\n"
                f"👤 {name}\n"
                f"🔑 Token active\n\n"
                f"Ab use karo:\n"
                f"/market — Live data\n"
                f"/decision — Aaj ka mode"
            )
            print(f"Fyers connected: {name}")
        else:
            send(f"❌ *Failed!*\nError: {res.get('message', str(res))}\n\nDobara /login try karo")
    except Exception as e:
        send(f"❌ Error: {str(e)}\n\n/login se dobara try karo")

@bot.message_handler(commands=['status'])
def cmd_status(m):
    open_st, reason = is_market_open()
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    fst = "✅ Connected" if fyers else "❌ Not connected"
    if open_st:
        send(f"✅ *Market OPEN*\n⏰ {now}\n🔗 Fyers: {fst}")
    else:
        send(f"🔴 *Market Closed*\n⏰ {now}\nReason: {reason}\n🔗 Fyers: {fst}")

@bot.message_handler(commands=['market'])
def cmd_market(m):
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    send("📊 Fetching...")
    data, status = get_live_data()
    if not data:
        send(f"❌ {status}")
        return
    e = "🟢" if data["nifty_chp"] >= 0 else "🔴"
    send(
        f"📈 *Live Market*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Nifty:* {data['nifty_lp']:,.1f} {e}\n"
        f"*Change:* {data['nifty_chp']:+.2f}%\n"
        f"*High:* {data['nifty_high']:,.1f}\n"
        f"*Low:* {data['nifty_low']:,.1f}\n"
        f"*Gap:* {data['gap']:+.2f}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*VIX:* {data['vix_lp']:.2f} ({data['vix_dir']})\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Mode:* `{data['mode']}`"
    )

@bot.message_handler(commands=['decision'])
def cmd_decision(m):
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    open_st, reason = is_market_open()
    if not open_st:
        send(f"🔴 Market closed!\n{reason}")
        return
    data, status = get_live_data()
    if not data:
        send(f"❌ {status}")
        return
    mode = data["mode"]
    if "NORMAL" in mode:
        e = "🟢"
        action = (f"*Iron Condor:*\nSell CE: {data['atm_nifty']+200}\n"
                  f"Buy CE: {data['atm_nifty']+300}\nSell PE: {data['atm_nifty']-200}\n"
                  f"Buy PE: {data['atm_nifty']-300}\nLots: 65 units")
    elif "PANIC" in mode:
        e = "🚨"
        action = (f"*Straddle:*\nBuy CE: {data['atm_nifty']}CE\n"
                  f"Buy PE: {data['atm_nifty']}PE\nLots: 65 units\nExit: 10:30 AM")
    else:
        e = "⛔"
        action = "Aaj trade mat karo!\nCapital safe rakho."
    send(
        f"{e} *Aaj Ka Decision*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Mode:* `{mode}`\n\n"
        f"{action}\n\n"
        f"VIX: {data['vix_lp']:.2f} | Gap: {data['gap']:+.2f}%"
    )

@bot.message_handler(commands=['strike'])
def cmd_strike(m):
    if not fyers:
        send("❌ Pehle /login karo!")
        return
    data, status = get_live_data()
    if not data:
        send(f"❌ {status}")
        return
    send(
        f"🎯 *Strike Prices*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Nifty Spot:* {data['nifty_lp']:,.1f}\n"
        f"*Nifty ATM:* {data['atm_nifty']}\n"
        f"CE: `NIFTY{data['atm_nifty']}CE`\n"
        f"PE: `NIFTY{data['atm_nifty']}PE`\n\n"
        f"*BankNifty ATM:* {data['atm_bn']}\n"
        f"CE: `BANKNIFTY{data['atm_bn']}CE`\n"
        f"PE: `BANKNIFTY{data['atm_bn']}PE`"
    )

@bot.message_handler(commands=['stop'])
def cmd_stop(m):
    send(
        "🛑 *EMERGENCY STOP!*\n\n"
        "Fyers One app mein TURANT\n"
        "saari positions exit karo!\n\n"
        "Reconnect: /login"
    )

@bot.message_handler(func=lambda m: True)
def unknown(m):
    send("❓ /help se commands dekho")

def morning_reminder_loop():
    reminded_today = None
    while True:
        try:
            now   = datetime.now(IST)
            today = now.date()
            if (now.hour == 9 and now.minute == 0 and
                now.weekday() < 5 and
                today.strftime("%Y-%m-%d") not in NSE_HOLIDAYS_2026 and
                reminded_today != today):
                send(
                    "🌅 *Good Morning Simarjeet!*\n\n"
                    "Market 15 minute mein khulega!\n\n"
                    "🔑 Pehle login karo:\n"
                    "/login bhejo → connect karo\n\n"
                    "Phir:\n"
                    "/market — Live data\n"
                    "/decision — Aaj ka mode"
                )
                reminded_today = today
            time.sleep(30)
        except Exception as e:
            print(f"Morning error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("=" * 50)
    print("TRADING BOT STARTING...")
    print("=" * 50)
    flask_t = threading.Thread(target=run_flask)
    flask_t.daemon = True
    flask_t.start()
    print("Flask started!")
    morning_t = threading.Thread(target=morning_reminder_loop)
    morning_t.daemon = True
    morning_t.start()
    print("Morning reminder started!")
    try:
        send("🚀 *Bot Online!*\n/login bhejo Fyers connect karne ke liye")
    except Exception as e:
        print(f"Startup msg error: {e}")
    print("Polling started!")
    print("=" * 50)
    bot.infinity_polling(skip_pending=True)
