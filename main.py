import os
import telebot
import threading
from fyers_apiv3 import fyersModel
from flask import Flask

# --- 1. CONFIGURATION ---
TOKEN = '8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY'
APP_ID = 'CI0NFNURCW-100'
SECRET_KEY = 'H7RXH9IXJT'
CHAT_ID = '944397272'
REDIRECT_URI = 'https://trade.fyers.in/api-login/redirect-uri/index.html'

bot = telebot.TeleBot(TOKEN)
fyers = None

# --- FLASK FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Online!"

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    # Debug print for Render logs
    print(f"Start command received from {m.chat.id}")
    bot.send_message(CHAT_ID, "🚀 Pro Bot Live on Render!\nReady for Trading.")

@bot.message_handler(commands=['connect'])
def connect_fyers(m):
    global fyers
    try:
        args = m.text.split()
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Format: /connect <auth_code>")
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
            bot.send_message(CHAT_ID, "✅ BINGO! Bot Connected.")
        else:
            bot.send_message(CHAT_ID, f"❌ Fyers Error: {res.get('message')}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"⚠️ Script Error: {str(e)}")

# --- STARTUP LOGIC ---
def run_bot():
    print("Starting Telegram Polling...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # Flask ko thread mein nahi, seedha chalne dete hain agar manual run ho
    # Lekin Render par Gunicorn ise handle karega.
    t = threading.Thread(target=run_bot)
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
