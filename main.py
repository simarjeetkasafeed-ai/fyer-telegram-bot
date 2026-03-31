import os
import telebot
import threading
import urllib.parse
from fyers_apiv3 import fyersModel
from flask import Flask

# --- CONFIG ---
TOKEN         = os.environ.get("TELEGRAM_TOKEN")
APP_ID        = os.environ.get("FYERS_APP_ID")
SECRET_KEY    = os.environ.get("FYERS_SECRET_KEY")
CHAT_ID       = os.environ.get("CHAT_ID")
REDIRECT_URI  = "https://trade.fyers.in/api-login/redirect-uri/index.html"

bot   = telebot.TeleBot(TOKEN)
fyers = None
app   = Flask('')

@app.route('/')
def home(): return "Bot is Online"

# --- COMMANDS ---

@bot.message_handler(commands=['start'])
def cmd_start(m):
    bot.send_message(CHAT_ID, "🚀 Bot Online!\n\n1. /login\n2. /connect <url>")

@bot.message_handler(commands=['login'])
def cmd_login(m):
    try:
        # EXACT V3 STRUCTURE
        base_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
        params = {
            "client_id": APP_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "state": "None"
        }
        auth_url = base_url + "?" + urllib.parse.urlencode(params)
        bot.send_message(CHAT_ID, f"🔑 Login Link:\n{auth_url}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Use: /connect <URL>")
            return
        
        inp = args[1].strip()
        auth_code = inp.split("auth_code=")[1].split("&")[0] if "auth_code=" in inp else inp

        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code"
        )
        session.set_token(auth_code)

        # --- FIX: Dono method try karenge (AttributeError se bachne ke liye) ---
        try:
            res = session.generate_access_token()
        except AttributeError:
            res = session.generate_token()

        if res.get("s") == "ok":
            tk = res.get("access_token")
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, is_async=False, log_path="")
            bot.send_message(CHAT_ID, "✅ Connected! Ab /funds check karein.")
        else:
            bot.send_message(CHAT_ID, f"❌ Fail: {res.get('message')}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(commands=['funds'])
def cmd_funds(m):
    if not fyers:
        bot.send_message(CHAT_ID, "❌ Pehle /login karein")
        return
    try:
        res = fyers.funds()
        bal = res.get("fund_limit", [{}])[0].get("equityAmount", 0)
        bot.send_message(CHAT_ID, f"💰 Balance: ₹{bal}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
