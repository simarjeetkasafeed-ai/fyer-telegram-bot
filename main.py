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

# Global variable to keep session alive
fyers = None

# Render Health Check
app = Flask('')
@app.route('/')
def home(): return "Fyers Bot is Active and Syncing!"

def run_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

bot = telebot.TeleBot(TOKEN)

# --- UI BUTTONS ---
def pro_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btns = [types.KeyboardButton(x) for x in ['🚀 Pick Stocks', '💰 Balance', '📈 Live P&L', '👤 Profile', '🚨 EXIT ALL', '🔗 Login Link']]
    markup.add(*btns)
    return markup

# --- TRADING LOGIC ---
def get_momentum_stocks():
    global fyers
    watchlist = ["NSE:RELIANCE-EQ", "NSE:SBIN-EQ", "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ", "NSE:TCS-EQ"]
    selected = []
    if not fyers: return ["❌ Pehle Login Karein!"]
    for symbol in watchlist:
        try:
            res = fyers.quotes({"symbols": symbol})
            if res['s'] == 'ok':
                d = res['d'][0]['v']
                if abs(d.get('chp', 0)) > 1.2:
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
    bot.send_message(CHAT_ID, "🚀 Pro Bot Live on Render!\nReady for Trading.", reply_markup=pro_menu())

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
                profile_res = fyers.get_profile()
                if profile_res.get('s') == 'ok':
                    p = profile_res['d']
                    f = fyers.funds()['fund_limit'][0]
                    bot.send_message(CHAT_ID, f"👤 **User**: {p['display_name']}\n💰 **Margin**: ₹{f['equityAmount']}")
                else:
                    bot.send_message(CHAT_ID, f"❌ Session Expired: {profile_res.get('message', 'Login Again')}")
                    fyers = None
            except: bot.send_message(CHAT_ID, "❌ Connection Error with Fyers.")
        else: bot.send_message(CHAT_ID, "❌ Login Required! '🔗 Login Link' dabayein.")

    elif text == '📈 Live P&L':
        if fyers:
            pos = fyers.positions()
            pnl = pos.get('overall', {}).get('pl_total', 0) if pos['s'] == 'ok' else "N/A"
            bot.send_message(CHAT_ID, f"📊 **Total Live P&L**: ₹{pnl}")
        else: bot.send_message(CHAT_ID, "❌ Login Required.")

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
        args = m.text.split()
        if len(args) < 2:
            bot.send_message(CHAT_ID, "⚠️ Format: /connect <auth_code>")
            return

        auth_code = args[1]
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_KEY, redirect_uri=REDIRECT_URI, response_type='code', grant_type='authorization_code')
        session.set_token(auth_code)
        
        # Fresh Token Generation
        res = session.generate_access_token()
        
        if res.get('s') == 'ok':
            tk = res.get('access_token')
            fyers = fyersModel.FyersModel(client_id=APP_ID, token=tk, log_path="")
            
            # Instant Verification
            test_prof = fyers.get_profile()
            if test_prof.get('s') == 'ok':
                name = test_prof['d']['display_name']
                bot.send_message(CHAT_ID, f"✅ BINGO! Welcome {name}. Bot is now Active.")
            else:
                bot.send_message(CHAT_ID, f"❌ Token OK but Profile Fail: {test_prof.get('message')}")
        else:
            bot.send_message(CHAT_ID, f"❌ Connection Fail: {res.get('message', 'Invalid Auth Code')}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"⚠️ Script Error: {str(e)}")

if __name__ == "__main__":
    threading.Thread(target=run_server).start()
    print("Bot is starting...")
    bot.infinity_polling(skip_pending=True)
