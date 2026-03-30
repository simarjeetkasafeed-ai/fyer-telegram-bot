import os
import telebot
import threading
from fyers_apiv3 import fyersModel
from flask import Flask

# --- CONFIG ---
TOKEN = '8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY'
APP_ID = 'CI0NFNURCW-100'
SECRET_KEY = 'H7RXH9IXJT'
CHAT_ID = '944397272'
REDIRECT_URI = 'https://trade.fyers.in/api-login/redirect-uri/index.html'

bot = telebot.TeleBot(TOKEN)
fyers = None

# Render Server
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- COMMANDS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.send_message(CHAT_ID, "🚀 Pro Bot Live on Render!\n\n1. Pehle '🔗 Login Link' se login karein.\n2. Fir '/connect <auth_code>' bhejein.")

@bot.message_handler(commands=['connect'])
def connect_fyers(m):
    global fyers
    try:
        args = m.text.split()
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Format: /connect <auth_code_yahan>")
            return

        auth_code = args[1]
        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code'
        )
        session.set_token(auth_code)
        res = session.generate_access_token()
        
        if res.get('s') == 'ok':
            tk = res.get('access_token')
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, log_path="")
            bot.send_message(CHAT_ID, "✅ BINGO! Login Successful. Ab aap trades le sakte hain.")
        else:
            # YE LINE BATAYEGI KI KYUN CONNECT NAHI HUA
            bot.send_message(CHAT_ID, f"❌ Fyers Error: {res.get('message')}\nCode: {res.get('code')}")
            
    except Exception as e:
        bot.send_message(CHAT_ID, f"⚠️ Script Error: {str(e)}")

@bot.message_handler(func=lambda m: m.text == '🔗 Login Link')
def send_link(m):
    session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code')
    bot.send_message(CHAT_ID, f"🔗 Login Here:\n{session.generate_authcode()}")

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    bot.infinity_polling(skip_pending=True)
