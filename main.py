import os
import time
import telebot
import threading
from telebot import types
from fyers_apiv3 import fyersModel
from flask import Flask

# --- 1. CONFIGURATION ---
TOKEN = '8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY'
APP_ID = 'CI0NFNURCW-100'
SECRET_KEY = 'H7RXH9IXJT'
CHAT_ID = '944397272'
REDIRECT_URI = 'https://trade.fyers.in/api-login/redirect-uri/index.html'
TOKEN_FILE = "fyers_token.txt"

# Render Server
app = Flask('')
@app.route('/')
def home(): return "Bot is Online and Ready!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = telebot.TeleBot(TOKEN)
fyers = None

# --- UI ---
def pro_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btns = [types.KeyboardButton(x) for x in ['🚀 Pick Stocks', '💰 Balance', '📈 Live P&L', '👤 Profile', '🚨 EXIT ALL', '🔗 Login Link']]
    markup.add(*btns)
    return markup

# --- TOKEN HELPERS ---
def save_token(t):
    with open(TOKEN_FILE, "w") as f: f.write(t)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f: return f.read().strip()
    return None

# --- CONNECT COMMAND (FIXED) ---
@bot.message_handler(commands=['connect'])
def connect_fyers(m):
    global fyers
    try:
        # Auth code extract karna
        args = m.text.split()
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Format: /connect <auth_code>")
            return

        auth_code = args[1]
        
        # Fyers Session Setup
        session = fyersModel.SessionModel(
            client_id=APP_ID, secret_key=SECRET_KEY,
            redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code'
        )
        session.set_token(auth_code)
        
        # Token generate karna (Donon method try karenge)
        try:
            res = session.generate_access_token()
        except:
            res = session.generate_token()
            
        print(f"DEBUG: Fyers Response -> {res}") # Render Logs mein check karein

        if res.get('s') == 'ok':
            tk = res.get('access_token')
            save_token(tk)
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, log_path="")
            bot.send_message(CHAT_ID, "✅ BINGO! Pro Bot Connected. Ab '💰 Balance' check karein.", reply_markup=pro_menu())
        else:
            bot.send_message(CHAT_ID, f"❌ Fyers Error: {res.get('message', 'Invalid Code')}")
            
    except Exception as e:
        bot.send_message(CHAT_ID, f"⚠️ Error: {str(e)}")

# --- BAKI HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.send_message(CHAT_ID, "🚀 Pro Bot Live on Render!\nSystem Ready.", reply_markup=pro_menu())

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global fyers
    if str(message.chat.id) != CHAT_ID: return
    text = message.text
    
    if text == '🔗 Login Link':
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code')
        bot.send_message(CHAT_ID, f"🔗 Click to Login:\n{session.generate_authcode()}")
    
    elif text == '💰 Balance' or text == '👤 Profile':
        if fyers:
            try:
                p = fyers.get_profile()['d']
                f = fyers.funds()['fund_limit'][0]
                bot.send_message(CHAT_ID, f"👤 **User**: {p['display_name']}\n💰 **Margin**: ₹{f['equityAmount']}")
            except: bot.send_message(CHAT_ID, "❌ Data Fetch Error (Login Expired?).")
        else: bot.send_message(CHAT_ID, "❌ Pehle Login Karein!")

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    st = load_token()
    if st:
        try:
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=st, log_path="")
            if fyers.get_profile().get('s') == 'ok': print("Auto-login success")
        except: print("Token expired")
    
    bot.infinity_polling(skip_pending=True)
