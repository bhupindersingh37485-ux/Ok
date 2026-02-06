import json
import asyncio
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================
BOT_TOKEN = "PUT_NEW_TOKEN_HERE"
OWNER_ID = 123456789  # your Telegram user ID
DEFAULT_INTERVAL = 30
# ========================================

DATA_FILE = "channels.json"
CONFIG_FILE = "config.json"

BINANCE_URL = "https://api.binance.com/api/v3/ticker/price?symbol="
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

# ============ FLASK APP ============
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot is running", 200

def run_flask():
    app_flask.run(host="0.0.0.0", port=8080)
# ===================================

# ----------- Storage ----------
def load_json(file, default):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

channels = load_json(DATA_FILE, {})  # {channel_id: "BTC"}
config = load_json(CONFIG_FILE, {
    "interval": DEFAULT_INTERVAL,
    "paused": False
})

# ----------- Helpers ----------
def is_owner(update: Update):
    return update.effective_user.id == OWNER_ID

def get_price(symbol):
    pair = symbol + "USDT"

    # 1️⃣ Binance
    try:
        r = requests.get(BINANCE_URL + pair, timeout=5)
        return round(float(r.json()["price"]), 4)
    except:
        pass

    # 2️⃣ CoinGecko fallback
    cg_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "TON": "the-open-network"
    }

    cg_id = cg_map.get(symbol)
    if not cg_id:
        raise Exception("Unsupported coin")

    r = requests.get(
        COINGECKO_URL,
        params={"ids": cg_id, "vs_currencies": "usd"},
        timeout=5
    )
    return r.json()[cg_id]["usd"]

# ----------- Commands ----------
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /add <channel_id> <coin>")
        return

    cid = context.args[0]
    coin = context.args[1].upper()

    try:
        get_price(coin)
    except:
        await update.message.reply_text("Invalid coin.")
        return

    channels[cid] = coin
    save_json(DATA_FILE, channels)
    await update.message.reply_text(f"Added {cid} → {coin}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    cid = context.args[0]
    channels.pop(cid, None)
    save_json(DATA_FILE, channels)
    await update.message.reply_text(f"Removed {cid}")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    if not channels:
        await update.message.reply_text("No channels added.")
        return

    text = "\n".join(f"{c} → {s}" for c, s in channels.items())
    await update.message.reply_text(text)

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        return

    sec = max(10, int(context.args[0]))
    config["interval"] = sec
    save_json(CONFIG_FILE, config)
    await update.message.reply_text(f"Interval set to {sec}s")

# ----------- Price Loop ----------
async def price_loop(app):
    while True:
        for ch, coin in list(channels.items()):
            try:
                price = get_price(coin)
                msg = f"{coin} Price - {price}"
                await app.bot.send_message(chat_id=int(ch), text=msg)
            except:
                pass

        await asyncio.sleep(config["interval"])

# ----------- Main ----------
async def telegram_main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("add", add_channel))
    application.add_handler(CommandHandler("remove", remove_channel))
    application.add_handler(CommandHandler("list", list_channels))
    application.add_handler(CommandHandler("interval", set_interval))

    asyncio.create_task(price_loop(application))
    await application.run_polling()

if __name__ == "__main__":
    # Run Flask in background thread
    threading.Thread(target=run_flask).start()

    # Run Telegram bot
    asyncio.run(telegram_main())
