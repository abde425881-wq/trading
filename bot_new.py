import os
import telebot
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, request
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== CONFIGURAZIONE ==========
TOKEN = os.getenv('BOT_TOKEN')
RENDER_URL = os.getenv('RENDER_URL')

# Se non trova il token nelle variabili d'ambiente, usa quello hardcoded (solo per sicurezza)
if not TOKEN:
    TOKEN = "8396839304:AAHLBwLsSPbZPaz0i31C_TtQBUHQmjr1MJU"

app = Flask(__name__)

# ========== FIREBASE ==========
try:
    firebase_json = os.getenv('FIREBASE_CONFIG')
    if firebase_json:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
        print("✅ Firebase caricato da variabile d'ambiente")
    else:
        cred = credentials.Certificate("firebase_config.json")
        print("✅ Firebase caricato da file")
    
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"❌ Errore Firebase: {e}")
    db = None

bot = telebot.TeleBot(TOKEN)
user_states = {}

# ========== FUNZIONI ADMIN ==========
def is_admin(user_id):
    """Controlla se l'utente è admin."""
    if not db:
        return False
    try:
        ref = db.collection('menu').document('caldarelli')
        doc = ref.get()
        if not doc.exists:
            return False
        data = doc.to_dict()
        admins = data.get('admins', [])
        return str(user_id) in admins
    except:
        return False

# ========== HANDLER TELEGRAM ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Visualizza Menu", callback_data="show_menu"))
    markup.row(InlineKeyboardButton("📞 Prenota Tavolo", callback_data="book_table"))
    
    welcome_text = """🍹 *Benvenuto al Bar Caldarelli!*

Cosa posso fare per te?"""
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "show_menu")
def show_menu(call):
    if not db:
        bot.answer_callback_query(call.id, "⚠️ Database non disponibile")
        return
    
    try:
        categories = db.collection('categories').stream()
        markup = InlineKeyboardMarkup()
        
        for cat in categories:
            cat_data = cat.to_dict()
            markup.row(InlineKeyboardButton(
                f"📂 {cat.id}", 
                callback_data=f"cat_{cat.id}"
            ))
        
        markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="back_start"))
        bot.edit_message_text("📋 Seleziona una categoria:", 
                              call.message.chat.id, 
                              call.message.message_id,
                              reply_markup=markup)
    except Exception as e:
        print(f"Errore menu: {e}")
        bot.answer_callback_query(call.id, "⚠️ Errore nel caricamento menu")

@bot.callback_query_handler(func=lambda call: call.data == "book_table")
def book_table(call):
    text = """📞 *Prenota un Tavolo*

Chiama il numero: +39 123 456 7890"""
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_start(call):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Visualizza Menu", callback_data="show_menu"))
    markup.row(InlineKeyboardButton("📞 Prenota Tavolo", callback_data="book_table"))
    
    bot.edit_message_text("🍹 *Benvenuto al Bar Caldarelli!*\n\nCosa posso fare per te?", 
                          call.message.chat.id, 
                          call.message.message_id,
                          parse_mode='Markdown', reply_markup=markup)

# ========== ROUTE FLASK (FONDAMENTALI PER RENDER) ==========

@app.route("/")
def index():
    """Pagina principale - Health check"""
    return """
    <h1>🤖 Bot Caldarelli Online!</h1>
    <p>Il bot è attivo e funzionante.</p>
    <a href='/setwebhook'><button>🔧 Imposta Webhook</button></a>
    """, 200

@app.route("/setwebhook")
def set_webhook():
    """Route per impostare manualmente il webhook su Telegram"""
    if not RENDER_URL:
        return "❌ ERRORE: RENDER_URL non impostato nelle variabili d'ambiente!<br>Vai su Render > Environment e aggiungi RENDER_URL = https://trading-rfhw.onrender.com", 400
    
    try:
        # Rimuovi webhook precedente
        bot.remove_webhook()
        
        # Imposta nuovo webhook
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        result = bot.set_webhook(url=webhook_url)
        
        if result:
            return f"""
            ✅ Webhook impostato con successo!<br><br>
            <b>URL:</b> {webhook_url}<br><br>
            Ora il bot risponderà su Telegram!<br>
            Prova a scrivere /start al bot.
            """, 200
        else:
            return "❌ Errore: Telegram ha rifiutato il webhook", 500
    except Exception as e:
        return f"❌ Errore durante l'impostazione: {str(e)}", 500

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Endpoint che riceve i messaggi da Telegram"""
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        print(f"Errore nel processare update: {e}")
        return "error", 500

# ========== AVVIO ==========
if __name__ == "__main__":
    # Imposta webhook automaticamente all'avvio se RENDER_URL esiste
    if RENDER_URL:
        try:
            bot.remove_webhook()
            webhook_url = f"{RENDER_URL}/{TOKEN}"
            bot.set_webhook(url=webhook_url)
            print(f"✅ Webhook auto-impostato: {webhook_url}")
        except Exception as e:
            print(f"⚠️ Errore auto-webhook: {e}")
            print("🔧 Vai su https://trading-rfhw.onrender.com/setwebhook per impostarlo manualmente")
    
    # Avvia Flask sulla porta 10000 (richiesto da Render)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
