import os
import time
import telebot
import threading
from telebot import types
from fyers_apiv3 import fyersModel
from flask import Flask

# --- 1. CONFIGURATION (CLEANED) ---
TOKEN = '8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY'
APP_ID = 'CI0NFNURCW-100'
SECRET_KEY = 'H7RXH9IXJT'
CHAT_ID = '944397272'
REDIRECT_URI = 'https://trade.fyers.in/api-login/redirect-uri/index.html'
TOKEN_FILE = "fyers_token.txt"

# Render Health Check
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = telebot.TeleBot(TOKEN)
fyers = None

# --- UI BUTTONS ---
def pro_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btns = [types.KeyboardButton(x) for x in ['🚀 Pick Stocks', '💰 Balance', '📈 Live P&L', '👤 Profile', '🚨 EXIT ALL', '🔗 Login Link']]
    markup.add(*btns)
    return markup

# --- HELPERS ---
def save_token(t):
    with open(TOKEN_FILE, "w") as f: f.write(t)

def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f: return f.read().strip()
    return None

# --- TRADING LOGIC ---
def get_momentum_stocks():
    watchlist = ["NSE:RELIANCE-EQ", "NSE:SBIN-EQ", "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ", "NSE:TCS-EQ"]
    selected = []
    if not fyers: return ["❌ Pehle Login Karein!"]
    for symbol in watchlist:
        try:
            res = fyers.quotes({"symbols": symbol})
            if res['s'] == 'ok':
                d = res['d'][0]['v']
                if abs(d.get('chp', 0)) > 1.5:
                    selected.append(f"🔹 {symbol}: {d['chp']}% (LTP: {d['lp']})")
        except: continue
    return selected

def exit_all_positions():
    global fyers
    if not fyers: return "❌ Not Connected"
    try:
        pos = fyers.positions()
        if pos['s'] == 'ok' and pos.get('netPositions'):
            for p in pos['netPositions']:
                if p['netQty'] != 0:
                    side = -1 if p['netQty'] > 0 else 1
                    data = {"symbol": p['symbol'], "qty": abs(p['netQty']), "type": 2, "side": side, "productType": p['productType'], "limitPrice": 0, "stopPrice": 0, "validity": "DAY"}
                    fyers.place_order(data)
            return "✅ SARI POSITIONS EXIT KAR DI GAYI HAIN!"
        return "ℹ️ Koi open position nahi mili."
    except Exception as e: return f"❌ Error: {str(e)}"

# --- TELEGRAM HANDLERS ---
@bot.message_handler(commands=['start'])
def welcome(m):
    bot.send_message(CHAT_ID, "🚀 Pro Bot Live on Render!\nSystem Ready.", reply_markup=pro_menu())

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    global fyers
    if str(message.chat.id) != CHAT_ID: return
    
    text = message.text
    if text == '🚀 Pick Stocks':
        stocks = get_momentum_stocks()
        msg = "🎯 **Momentum Stocks:**\n\n" + "\n".join(stocks) if stocks else "😴 Market Shant Hai."
        bot.send_message(CHAT_ID, msg)
    elif text == '💰 Balance' or text == '👤 Profile':
        if fyers:
            try:
                p = fyers.get_profile()['d']
                f = fyers.funds()['fund_limit'][0]
                bot.send_message(CHAT_ID, f"👤 **User**: {p['display_name']}\n💰 **Margin**: ₹{f['equityAmount']}")
            except: bot.send_message(CHAT_ID, "❌ Data Fetch Error.")
        else: bot.send_message(CHAT_ID, "❌ Login Required.")
    elif text == '📈 Live P&L':
        if fyers:
            pos = fyers.positions()
            pnl = pos.get('overall', {}).get('pl_total', 0) if pos['s'] == 'ok' else "N/A"
            bot.send_message(CHAT_ID, f"📊 **Total Live P&L**: ₹{pnl}")
        else: bot.send_message(CHAT_ID, "❌ Not Connected.")
    elif text == '🚨 EXIT ALL':
        bot.send_message(CHAT_ID, "⚠️ Closing all positions...")
        bot.send_message(CHAT_ID, exit_all_positions())
    elif text == '🔗 Login Link':
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code')
        bot.send_message(CHAT_ID, f"🔗 Click to Login:\n{session.generate_authcode()}")

@bot.message_handler(commands=['connect'])
def connect_fyers(m):
    global fyers
    try:
        auth_code = m.text.split()[1]
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code')
        session.set_token(auth_code)
        res = session.generate_access_token()
        
        if res.get('s') == 'ok':
            tk = res.get('access_token')
            save_token(tk)
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, log_path="")
            bot.send_message(CHAT_ID, "✅ BINGO! Pro Bot Connected.")
        else:
            bot.send_message(CHAT_ID, f"❌ Fail: {res.get('message', 'Check App ID/Secret')}")
    except: bot.send_message(CHAT_ID, "⚠️ Format: /connect <code_yahan>")

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    st = load_token()
    if st:
        try:
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=st, log_path="")
            if fyers.get_profile().get('s') == 'ok': print("Auto-login success")
        except: print("Token expired")
    
    bot.infinity_polling(skip_pending=True)
