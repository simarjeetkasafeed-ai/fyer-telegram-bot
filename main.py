import os
import telebot
from flask import Flask
import threading

# --- CONFIG ---
TOKEN = '8644451164:AAElOSx3cYqrxUzBeUCxr-PT5oE9yVgFBGY'
CHAT_ID = '944397272'

bot = telebot.TeleBot(TOKEN)
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive!"

@bot.message_handler(commands=['start'])
def send_welcome(m):
    bot.send_message(CHAT_ID, "🚀 PRO BOT IS WORKING! Ab Fyers connect karte hain.")

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flask ko alag thread mein chalayenge
    t = threading.Thread(target=run_flask)
    t.setDaemon(True)
    t.start()
    
    print("Starting Bot Polling...")
    bot.infinity_polling(skip_pending=True)
