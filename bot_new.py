import os
import telebot
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configurazione da variabili d'ambiente
TOKEN = os.getenv('BOT_TOKEN')
RENDER_URL = os.getenv('RENDER_URL')

if not TOKEN:
    raise ValueError("BOT_TOKEN non impostato!")

app = Flask(__name__)

# Inizializza Firebase
try:
    firebase_json = os.getenv('FIREBASE_CONFIG')
    if firebase_json:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase_config.json")
    
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Errore Firebase: {e}")
    db = None

bot = telebot.TeleBot(TOKEN)
user_states = {}

# ============ FUNZIONI ADMIN ============
def is_admin(user_id):
    """Controlla se l'utente è admin."""
    if not db:
        return False
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        return False
    data = doc.to_dict()
    admins = data.get('admins', [])
    return str(user_id) in admins

# ============ HANDLER COMANDI ============
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Visualizza Menu", callback_data="show_menu"))
    markup.row(InlineKeyboardButton("📞 Prenota Tavolo", callback_data="book_table"))
    
    welcome_text = """🍹 *Benvenuto al Bar Caldarelli!*

Cosa posso fare per te?"""
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=markup)

# Aggiungi qui gli altri tuoi handler (@bot.message_handler, @bot.callback_query_handler)
# che avevi nel codice vecchio...

# ========== WEBHOOK (PER RENDER) ==========
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/")
def index():
    return "🤖 Bot Caldarelli Online!", 200

if __name__ == "__main__":
    # Imposta webhook
    bot.remove_webhook()
    if RENDER_URL:
        bot.set_webhook(url=RENDER_URL + '/' + TOKEN)
        print(f"Webhook impostato: {RENDER_URL}/{TOKEN}")
    
    # Avvia Flask sulla porta corretta
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
