import os
import telebot
import threading
import time
import requests
from flask import Flask
from datetime import datetime, date
import pytz

# ============================================================
# CONFIG — Render Environment Variables se aata hai
# ============================================================
TOKEN    = os.environ.get("8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY")
CHAT_ID  = os.environ.get("944397272")
IST      = pytz.timezone("Asia/Kolkata")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable not set!")
if not CHAT_ID:
    raise ValueError("CHAT_ID environment variable not set!")

bot = telebot.TeleBot(TOKEN)
app = Flask('')

# ============================================================
# FLASK — Render ke liye alive rakhne ka server
# ============================================================
@app.route('/')
def home():
    now = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S IST")
    return f"Trading Bot Running! Time: {now}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ============================================================
# NSE HOLIDAY LIST 2026
# ============================================================
NSE_HOLIDAYS_2026 = [
    "2026-01-15", "2026-01-26", "2026-03-03",
    "2026-03-26", "2026-03-31", "2026-04-03",
    "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-09-14", "2026-10-02",
    "2026-10-20", "2026-11-10", "2026-11-24",
    "2026-12-25"
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def send_alert(message):
    """Telegram pe message bhejo"""
    try:
        bot.send_message(CHAT_ID, message, parse_mode="Markdown")
        print(f"Alert sent: {message[:50]}...")
    except Exception as e:
        print(f"Alert failed: {e}")

def is_market_open():
    """Aaj market open hai ya nahi"""
    now     = datetime.now(IST)
    today   = date.today().strftime("%Y-%m-%d")
    weekday = now.weekday()

    # Weekend check
    if weekday >= 5:
        return False, "Weekend — market closed"

    # Holiday check
    if today in NSE_HOLIDAYS_2026:
        return False, f"NSE Holiday today!"

    # Time check
    market_start = now.replace(hour=9,  minute=15, second=0)
    market_end   = now.replace(hour=15, minute=30, second=0)

    if now < market_start:
        return False, "Market not opened yet"
    if now > market_end:
        return False, "Market closed for today"

    return True, "Market is LIVE"

def get_nifty_data():
    """Nifty + VIX data fetch karo"""
    try:
        fyers_token   = os.environ.get("FYERS_ACCESS_TOKEN", "")
        fyers_client  = os.environ.get("FYERS_CLIENT_ID", "")

        if not fyers_token or not fyers_client:
            return None, "Fyers token not set"

        headers = {
            "Authorization": f"{fyers_client}:{fyers_token}",
            "Content-Type": "application/json"
        }

        # Nifty quote
        url    = "https://api.fyers.in/api/v3/quotes"
        params = {"symbols": "NSE:NIFTY50-INDEX,NSE:INDIAVIX-INDEX"}
        res    = requests.get(url, headers=headers, params=params)
        data   = res.json()

        if data.get("code") != 200:
            return None, f"API error: {data.get('message')}"

        nifty = data["d"][0]["v"]
        vix   = data["d"][1]["v"]

        return {
            "nifty_lp"   : nifty["lp"],
            "nifty_open" : nifty["open_price"],
            "nifty_prev" : nifty["prev_close_price"],
            "nifty_chp"  : nifty["chp"],
            "vix_lp"     : vix["lp"],
            "vix_open"   : vix["open_price"],
        }, "ok"

    except Exception as e:
        return None, str(e)

def analyze_market(data):
    """Market analysis aur bot decision"""
    nifty = data["nifty_lp"]
    vix   = data["vix_lp"]
    v_open= data["vix_open"]
    gap   = round((data["nifty_open"] - data["nifty_prev"])
                  / data["nifty_prev"] * 100, 2)

    vix_dir = "Rising" if vix > v_open else "Falling"

    # Bot decision logic
    if vix < 16:
        mode = "NORMAL — Iron Condor"
    elif vix > 19 and vix_dir == "Rising":
        mode = "PANIC — Buy Straddle"
    elif vix > 19 and vix_dir == "Falling":
        mode = "SKIP — Volatility Crush"
    else:
        mode = "SKIP — VIX Danger Zone"

    # Gap filter
    gap_status = "OK"
    if abs(gap) > 0.5:
        if mode == "NORMAL — Iron Condor":
            mode = "SKIP — Big Gap"
        gap_status = "CAUTION"

    return {
        "nifty"     : nifty,
        "vix"       : vix,
        "vix_dir"   : vix_dir,
        "gap"       : gap,
        "gap_status": gap_status,
        "mode"      : mode,
        "atm_strike": round(nifty / 50) * 50
    }

# ============================================================
# TELEGRAM COMMANDS
# ============================================================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(m.chat.id,
        "🚀 *Trading Bot Online!*\n\n"
        "Commands:\n"
        "/status — Bot aur market status\n"
        "/market — Live Nifty + VIX\n"
        "/decision — Aaj ka trading decision\n"
        "/help — Sabhi commands\n\n"
        "_Simarjeet Singh Trading Bot v2.2_",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['help'])
def cmd_help(m):
    bot.send_message(m.chat.id,
        "📋 *Available Commands:*\n\n"
        "/start — Bot start karo\n"
        "/status — Market open hai ya nahi\n"
        "/market — Live Nifty + VIX data\n"
        "/decision — Aaj ka trading mode\n"
        "/strike — ATM strike price\n"
        "/stop — Emergency stop\n"
        "/ping — Bot alive check",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['ping'])
def cmd_ping(m):
    now = datetime.now(IST).strftime("%H:%M:%S IST")
    bot.send_message(m.chat.id,
        f"✅ Bot alive!\nTime: {now}"
    )

@bot.message_handler(commands=['status'])
def cmd_status(m):
    open_status, reason = is_market_open()
    now = datetime.now(IST).strftime("%H:%M:%S IST")

    if open_status:
        msg = f"✅ *Market OPEN*\n⏰ {now}\n📊 Trading active"
    else:
        msg = f"🔴 *Market Closed*\n⏰ {now}\n📋 Reason: {reason}"

    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['market'])
def cmd_market(m):
    bot.send_message(m.chat.id, "📊 Fetching live data...")

    data, status = get_nifty_data()

    if not data:
        bot.send_message(m.chat.id,
            f"❌ Data fetch failed!\nReason: {status}\n\n"
            "Check Fyers token in Render environment variables."
        )
        return

    analysis = analyze_market(data)
    chg_emoji = "🟢" if data["nifty_chp"] >= 0 else "🔴"

    msg = (
        f"📈 *Live Market Data*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Nifty 50:* {analysis['nifty']:,.1f} {chg_emoji}\n"
        f"*Change:* {data['nifty_chp']:+.2f}%\n"
        f"*Gap Open:* {analysis['gap']:+.2f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*India VIX:* {analysis['vix']:.2f}\n"
        f"*VIX Direction:* {analysis['vix_dir']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*ATM Strike:* {analysis['atm_strike']}\n"
        f"*Bot Mode:* `{analysis['mode']}`"
    )

    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['decision'])
def cmd_decision(m):
    open_status, reason = is_market_open()

    if not open_status:
        bot.send_message(m.chat.id,
            f"🔴 Market closed!\nReason: {reason}\n\n"
            "Decision only available during market hours."
        )
        return

    data, status = get_nifty_data()

    if not data:
        bot.send_message(m.chat.id,
            f"❌ Cannot fetch data!\n{status}"
        )
        return

    analysis = analyze_market(data)
    mode     = analysis["mode"]

    if "NORMAL" in mode:
        emoji  = "🟢"
        action = "Iron Condor setup karo\nSell CE + PE spreads"
    elif "PANIC" in mode:
        emoji  = "🚨"
        action = "Buy Straddle!\nCE + PE dono kharido"
    else:
        emoji  = "⛔"
        action = "Aaj trade mat karo\nCapital safe rakho"

    msg = (
        f"{emoji} *Bot Decision*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*Mode:* `{mode}`\n\n"
        f"*Action:* {action}\n\n"
        f"*VIX:* {analysis['vix']:.2f} ({analysis['vix_dir']})\n"
        f"*Gap:* {analysis['gap']:+.2f}%\n"
        f"*ATM Strike:* {analysis['atm_strike']}"
    )

    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['strike'])
def cmd_strike(m):
    data, status = get_nifty_data()

    if not data:
        bot.send_message(m.chat.id, f"❌ {status}")
        return

    nifty      = data["nifty_lp"]
    atm        = round(nifty / 50) * 50
    atm_bn     = round(nifty / 100) * 100

    msg = (
        f"🎯 *Strike Prices*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"*Nifty Spot:* {nifty:,.1f}\n\n"
        f"*Nifty ATM:* {atm}\n"
        f"CE: {atm}CE  PE: {atm}PE\n\n"
        f"*BankNifty ATM:* {atm_bn}\n"
        f"CE: {atm_bn}CE  PE: {atm_bn}PE"
    )

    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['stop'])
def cmd_stop(m):
    bot.send_message(m.chat.id,
        "🛑 *EMERGENCY STOP RECEIVED!*\n\n"
        "⚠️ Please manually exit all positions\n"
        "in Fyers One terminal immediately!\n\n"
        "Bot monitoring paused.",
        parse_mode="Markdown"
    )
    send_alert("🚨 EMERGENCY STOP activated by user!")

# ============================================================
# AUTO MORNING ALERT — 9:15 AM
# ============================================================
def morning_alert_loop():
    """Har din 9:15 AM pe market alert bhejo"""
    alert_sent_today = None

    while True:
        try:
            now   = datetime.now(IST)
            today = now.date()

            # 9:15 AM pe ek baar alert bhejo
            if (now.hour == 9 and
                now.minute == 15 and
                alert_sent_today != today):

                open_status, reason = is_market_open()

                if open_status:
                    data, status = get_nifty_data()

                    if data:
                        analysis = analyze_market(data)
                        mode     = analysis["mode"]

                        if "NORMAL" in mode:
                            emoji = "🟢"
                        elif "PANIC" in mode:
                            emoji = "🚨"
                        else:
                            emoji = "⛔"

                        send_alert(
                            f"🌅 *Good Morning Simarjeet!*\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"*Nifty:* {analysis['nifty']:,.1f}\n"
                            f"*VIX:* {analysis['vix']:.2f} ({analysis['vix_dir']})\n"
                            f"*Gap:* {analysis['gap']:+.2f}%\n\n"
                            f"{emoji} *Today's Mode:* `{mode}`\n"
                            f"*ATM Strike:* {analysis['atm_strike']}"
                        )
                    else:
                        send_alert(
                            "🌅 Good Morning!\n"
                            "Market open hai!\n"
                            "⚠️ Data fetch failed — check Fyers token"
                        )
                else:
                    send_alert(f"🔴 Market Closed today\nReason: {reason}")

                alert_sent_today = today

            time.sleep(30)

        except Exception as e:
            print(f"Morning alert error: {e}")
            time.sleep(60)

# ============================================================
# VIX SPIKE MONITOR — Every 5 mins during market
# ============================================================
def vix_monitor_loop():
    """VIX spike detect karo aur alert bhejo"""
    last_vix      = None
    last_vix_open = None

    while True:
        try:
            now          = datetime.now(IST)
            open_status, _ = is_market_open()

            if open_status and 9 <= now.hour < 15:
                data, status = get_nifty_data()

                if data:
                    vix      = data["vix_lp"]
                    vix_open = data["vix_open"]

                    # VIX spike check (5%+ intraday)
                    vix_spike = (vix - vix_open) / vix_open * 100

                    if vix_spike > 5 and last_vix and vix > last_vix:
                        send_alert(
                            f"⚠️ *VIX SPIKE ALERT!*\n"
                            f"VIX: {vix:.2f} (spike {vix_spike:.1f}%)\n"
                            f"⛔ Exit all positions immediately!\n"
                            f"Do NOT enter new trades!"
                        )

                    # VIX crossed above 19
                    if (last_vix and last_vix <= 19 and vix > 19):
                        send_alert(
                            f"🚨 *VIX crossed 19!*\n"
                            f"VIX: {vix:.2f}\n"
                            f"Iron Condor danger zone!\n"
                            f"Mode switching to PANIC"
                        )

                    last_vix      = vix
                    last_vix_open = vix_open

            time.sleep(300)  # Check every 5 minutes

        except Exception as e:
            print(f"VIX monitor error: {e}")
            time.sleep(60)

# ============================================================
# MAIN — SAB KUCH SHURU KARO
# ============================================================
if __name__ == "__main__":

    print("=" * 50)
    print("TRADING BOT STARTING...")
    print("=" * 50)

    # Flask server — background mein
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server started!")

    # Morning alert loop — background mein
    morning_thread = threading.Thread(target=morning_alert_loop)
    morning_thread.daemon = True
    morning_thread.start()
    print("Morning alert loop started!")

    # VIX monitor — background mein
    vix_thread = threading.Thread(target=vix_monitor_loop)
    vix_thread.daemon = True
    vix_thread.start()
    print("VIX monitor started!")

    # Startup message
    try:
        bot.send_message(CHAT_ID,
            "🚀 *Trading Bot Online!*\n\n"
            "Sab systems active hain:\n"
            "✅ Telegram connected\n"
            "✅ Morning alerts ready\n"
            "✅ VIX monitor active\n\n"
            "Commands ke liye /help bhejein",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Startup message failed: {e}")

    print("Telegram polling started...")
    print("=" * 50)
    bot.infinity_polling(skip_pending=True)
