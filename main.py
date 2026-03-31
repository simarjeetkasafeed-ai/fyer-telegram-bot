import os
import telebot
import threading
import urllib.parse
from fyers_apiv3 import fyersModel
from flask import Flask
from telebot import types # Buttons ke liye

# --- CONFIG (Environment Variables) ---
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

# --- KEYBOARD SHORTCUTS ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    # Buttons ke naam short aur simple
    btn1 = types.KeyboardButton('🔗 Login')
    btn2 = types.KeyboardButton('💰 Funds')
    btn3 = types.KeyboardButton('📈 Market')
    btn4 = types.KeyboardButton('📋 Help')
    markup.add(btn1, btn2, btn3, btn4)
    return markup

# --- COMMANDS ---

@bot.message_handler(commands=['start'])
def cmd_start(m):
    # Start bhejte hi buttons aa jayenge
    bot.send_message(CHAT_ID, "🚀 *Pro Bot Online!*\nNeeche diye buttons use karein:", 
                     parse_mode="Markdown", reply_markup=main_menu())

# Login button ya command dono par chalega
@bot.message_handler(func=lambda m: m.text == '🔗 Login' or m.text == '/login')
def cmd_login(m):
    try:
        base_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
        params = {"client_id": APP_ID, "redirect_uri": REDIRECT_URI, "response_type": "code", "state": "None"}
        auth_url = base_url + "?" + urllib.parse.urlencode(params)
        bot.send_message(CHAT_ID, f"🔑 *Login Link:*\n{auth_url}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(commands=['connect'])
def cmd_connect(m):
    global fyers
    try:
        args = m.text.split(None, 1)
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Use: `/connect URL_YAHAN`", parse_mode="Markdown")
            return
        
        inp = args[1].strip()
        auth_code = inp.split("auth_code=")[1].split("&")[0] if "auth_code=" in inp else inp

        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code")
        session.set_token(auth_code)

        # Fix for Attribute Error (Dono methods try karega)
        try:
            res = session.generate_access_token()
        except:
            res = session.generate_token()

        if res.get("s") == "ok":
            tk = res.get("access_token")
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, is_async=False, log_path="")
            bot.send_message(CHAT_ID, "✅ *Connected!* Ab Funds check karein.", parse_mode="Markdown")
        else:
            bot.send_message(CHAT_ID, f"❌ Fail: {res.get('message')}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == '💰 Funds' or m.text == '/funds')
def cmd_funds(m):
    if not fyers:
        bot.send_message(CHAT_ID, "❌ Pehle Login karein!")
        return
    try:
        res = fyers.funds()
        # Equity amount nikalne ka simple logic
        bal = res.get("fund_limit", [{}])[0].get("equityAmount", 0)
        bot.send_message(CHAT_ID, f"💰 *Balance:* ₹{bal}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == '📈 Market' or m.text == '/market')
def cmd_market(m):
    if not fyers:
        bot.send_message(CHAT_ID, "❌ Login Required!")
        return
    try:
        res = fyers.quotes({"symbols": "NSE:NIFTY50-INDEX"})
        nifty = res["d"][0]["v"]
        bot.send_message(CHAT_ID, f"📈 *Nifty 50:* {nifty['lp']} ({nifty['chp']}%)", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Error: {e}")

@bot.message_handler(func=lambda m: m.text == '📋 Help' or m.text == '/help')
def cmd_help(m):
    bot.send_message(CHAT_ID, "📌 *Commands:*\n/login - Link ke liye\n/connect - URL paste karein\n/funds - Balance ke liye\n/market - Nifty info", parse_mode="Markdown")

# --- RUN ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    bot.infinity_polling(skip_pending=True)
