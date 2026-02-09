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

# Fallback se non trova variabili
if not TOKEN:
    TOKEN = "8396839304:AAHLBwLsSPbZPaz0i31C_TtQBUHQmjr1MJU"

app = Flask(__name__)

# ========== FIREBASE ==========
try:
    firebase_json = os.getenv('FIREBASE_CONFIG')
    if firebase_json:
        cred_dict = json.loads(firebase_json)
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase_config.json")
    
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Firebase connesso")
except Exception as e:
    print(f"❌ Errore Firebase: {e}")
    db = None

bot = telebot.TeleBot(TOKEN)
user_states = {}  # Per gestire input multi-step

# ========== FUNZIONI HELPER ==========
def is_admin(user_id):
    """Controlla se l'utente è admin"""
    if not db:
        return False
    try:
        # Controlla se è l'admin principale (primo utente che usa /admin)
        admins_ref = db.collection('admins').document(str(user_id)).get()
        return admins_ref.exists
    except:
        return False

def get_main_admin():
    """Restituisce l'ID del primo admin"""
    if not db:
        return None
    try:
        admins = db.collection('admins').limit(1).get()
        for admin in admins:
            return admin.id
    except:
        return None
    return None

# ========== COMANDI CLIENTE ==========
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Visualizza Menu", callback_data="menu_principale"))
    markup.row(InlineKeyboardButton("📞 Prenota Tavolo", callback_data="prenota"))
    markup.row(InlineKeyboardButton("ℹ️ Info", callback_data="info"))
    
    welcome_text = """🍹 *Benvenuto al Bar Caldarelli!*

Cosa posso fare per te?"""
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "menu_principale")
def menu_principale(call):
    """Mostra tutte le categorie"""
    if not db:
        bot.answer_callback_query(call.id, "⚠️ Database non disponibile")
        return
    
    try:
        categories = db.collection('categories').stream()
        markup = InlineKeyboardMarkup()
        
        for cat in categories:
            cat_data = cat.to_dict()
            nome = cat_data.get('nome', cat.id)
            markup.row(InlineKeyboardButton(f"📂 {nome}", callback_data=f"cat_{cat.id}"))
        
        markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="back_start"))
        
        bot.edit_message_text("📋 *Menu Caldarelli*\n\nScegli una categoria:", 
                              call.message.chat.id, 
                              call.message.message_id,
                              parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"Errore menu: {e}")
        bot.answer_callback_query(call.id, "⚠️ Errore caricamento menu")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def mostra_prodotti(call):
    """Mostra i prodotti di una categoria"""
    if not db:
        return
    
    cat_id = call.data.replace("cat_", "")
    
    try:
        # Prendi nome categoria
        cat_ref = db.collection('categories').document(cat_id).get()
        cat_nome = cat_ref.to_dict().get('nome', cat_id) if cat_ref.exists else cat_id
        
        # Prendi prodotti
        products = db.collection('prodotti').where('categoria', '==', cat_id).stream()
        
        text = f"🍽️ *{cat_nome}*\n\n"
        markup = InlineKeyboardMarkup()
        
        for prod in products:
            prod_data = prod.to_dict()
            nome = prod_data.get('nome', 'Sconosciuto')
            prezzo = prod_data.get('prezzo', 0)
            text += f"• *{nome}* - €{prezzo:.2f}\n"
            markup.row(InlineKeyboardButton(f"🛒 {nome}", callback_data=f"prod_{prod.id}"))
        
        if text == f"🍽️ *{cat_nome}*\n\n":
            text += "_Nessun prodotto disponibile_"
        
        markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="menu_principale"))
        
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"Errore prodotti: {e}")
        bot.answer_callback_query(call.id, "⚠️ Errore caricamento prodotti")

@bot.callback_query_handler(func=lambda call: call.data == "prenota")
def prenota_tavolo(call):
    """Prenotazione tavolo"""
    text = """📞 *Prenota un Tavolo*

Chiama il numero: +39 123 456 7890
Oppure invia una richiesta qui."""
    
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "info")
def info_bar(call):
    """Info del bar"""
    text = """ *Bar Caldarelli*

📍 Indirizzo: Via Roma 123
📞 Telefono: +39 123 456 7890
🕐 Orari: 08:00 - 02:00

Benvenuti!"""
    
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode='Markdown', reply_markup=InlineKeyboardMarkup().row(
                              InlineKeyboardButton("🔙 Indietro", callback_data="back_start")))

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
    """Torna alla home"""
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📋 Visualizza Menu", callback_data="menu_principale"))
    markup.row(InlineKeyboardButton("📞 Prenota Tavolo", callback_data="prenota"))
    markup.row(InlineKeyboardButton("ℹ️ Info", callback_data="info"))
    
    bot.edit_message_text("🍹 *Benvenuto al Bar Caldarelli!*\n\nCosa posso fare per te?", 
                          call.message.chat.id, 
                          call.message.message_id,
                          parse_mode='Markdown', reply_markup=markup)

# ========== PANNELLO ADMIN ==========
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Pannello admin"""
    user_id = message.from_user.id
    
    # Se non ci sono admin, il primo che usa /admin diventa admin
    if not db:
        bot.reply_to(message, "❌ Database non disponibile")
        return
    
    try:
        admins = list(db.collection('admins').limit(1).get())
        if not admins:
            # Primo admin
            db.collection('admins').document(str(user_id)).set({
                'username': message.from_user.username,
                'created': firestore.SERVER_TIMESTAMP
            })
            bot.reply_to(message, "🔐 *Sei stato registrato come Admin principale!*", parse_mode='Markdown')
        elif not is_admin(user_id):
            bot.reply_to(message, "❌ Non sei autorizzato!")
            return
        
        # Mostra pannello
        markup = InlineKeyboardMarkup(row_width=2)
        markup.row(
            InlineKeyboardButton("➕ Categoria", callback_data="add_cat"),
            InlineKeyboardButton("➕ Prodotto", callback_data="add_prod")
        )
        markup.row(
            InlineKeyboardButton("🗑️ Rimuovi", callback_data="remove_item"),
            InlineKeyboardButton("📊 Lista Admin", callback_data="list_admin")
        )
        markup.row(InlineKeyboardButton("➕ Aggiungi Admin", callback_data="add_admin"))
        
        bot.reply_to(message, "🔐 *Pannello Admin*\n\nSeleziona un'azione:", 
                     parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        print(f"Errore admin panel: {e}")
        bot.reply_to(message, "❌ Errore nel caricamento pannello")

# ========== GESTIONE CATEGORIE ==========
@bot.callback_query_handler(func=lambda call: call.data == "add_cat")
def add_category_start(call):
    """Inizia aggiunta categoria"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Non autorizzato")
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, 
                          "Inserisci il nome della nuova categoria:\n\n(Scrivi /cancel per annullare)")
    user_states[call.from_user.id] = {'action': 'add_category'}

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('action') == 'add_category')
def add_category_execute(message):
    """Esegue aggiunta categoria"""
    if message.text == '/cancel':
        user_states.pop(message.from_user.id, None)
        bot.reply_to(message, "❌ Operazione annullata")
        return
    
    try:
        cat_name = message.text.strip()
        db.collection('categories').document(cat_name.lower().replace(' ', '_')).set({
            'nome': cat_name,
            'created': firestore.SERVER_TIMESTAMP
        })
        bot.reply_to(message, f"✅ Categoria *{cat_name}* aggiunta!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Errore: {e}")
    finally:
        user_states.pop(message.from_user.id, None)

# ========== GESTIONE PRODOTTI ==========
@bot.callback_query_handler(func=lambda call: call.data == "add_prod")
def add_product_start(call):
    """Inizia aggiunta prodotto"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Non autorizzato")
        return
    
    try:
        # Mostra categorie disponibili
        categories = db.collection('categories').stream()
        markup = InlineKeyboardMarkup()
        
        for cat in categories:
            cat_data = cat.to_dict()
            nome = cat_data.get('nome', cat.id)
            markup.row(InlineKeyboardButton(nome, callback_data=f"selcat_{cat.id}"))
        
        markup.row(InlineKeyboardButton("❌ Annulla", callback_data="cancel_action"))
        
        bot.edit_message_text("Seleziona la categoria per il nuovo prodotto:",
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("selcat_"))
def select_category_for_product(call):
    """Seleziona categoria e chiede nome prodotto"""
    cat_id = call.data.replace("selcat_", "")
    user_states[call.from_user.id] = {'action': 'add_product', 'category': cat_id}
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, 
                          "Inserisci nome e prezzo del prodotto nel formato:\n"
                          "*Nome Prodotto | Prezzo*\n\n"
                          "Esempio: Spritz Aperol | 5.00\n\n"
                          "(Scrivi /cancel per annullare)",
                          parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('action') == 'add_product')
def add_product_execute(message):
    """Esegue aggiunta prodotto"""
    if message.text == '/cancel':
        user_states.pop(message.from_user.id, None)
        bot.reply_to(message, "❌ Operazione annullata")
        return
    
    try:
        parts = message.text.split('|')
        if len(parts) != 2:
            raise ValueError("Formato errato")
        
        nome = parts[0].strip()
        prezzo = float(parts[1].strip())
        cat_id = user_states[message.from_user.id]['category']
        
        # Prendi nome categoria
        cat_ref = db.collection('categories').document(cat_id).get()
        cat_nome = cat_ref.to_dict().get('nome', cat_id) if cat_ref.exists else cat_id
        
        db.collection('prodotti').add({
            'nome': nome,
            'prezzo': prezzo,
            'categoria': cat_id,
            'categoria_nome': cat_nome,
            'created': firestore.SERVER_TIMESTAMP
        })
        
        bot.reply_to(message, f"✅ Prodotto *{nome}* (€{prezzo:.2f}) aggiunto a *{cat_nome}*!", 
                     parse_mode='Markdown')
    except ValueError:
        bot.reply_to(message, "❌ Formato errato! Usa: Nome | Prezzo\nEsempio: Spritz | 5.00")
    except Exception as e:
        bot.reply_to(message, f"❌ Errore: {e}")
    finally:
        user_states.pop(message.from_user.id, None)

# ========== RIMOZIONE ==========
@bot.callback_query_handler(func=lambda call: call.data == "remove_item")
def remove_menu(call):
    """Menu rimozione"""
    if not is_admin(call.from_user.id):
        return
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🗑️ Categoria", callback_data="rem_cat_sel"),
        InlineKeyboardButton("🗑️ Prodotto", callback_data="rem_prod_sel")
    )
    markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="back_admin"))
    
    bot.edit_message_text("Cosa vuoi rimuovere?", call.message.chat.id, call.message.message_id,
                          reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "rem_prod_sel")
def remove_product_select(call):
    """Seleziona prodotto da rimuovere"""
    try:
        products = db.collection('prodotti').stream()
        markup = InlineKeyboardMarkup()
        
        for prod in products:
            prod_data = prod.to_dict()
            nome = prod_data.get('nome', 'Sconosciuto')
            markup.row(InlineKeyboardButton(f"🗑️ {nome}", callback_data=f"delprod_{prod.id}"))
        
        markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="remove_item"))
        
        bot.edit_message_text("Seleziona il prodotto da rimuovere:", 
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delprod_"))
def delete_product(call):
    """Cancella prodotto"""
    prod_id = call.data.replace("delprod_", "")
    try:
        db.collection('prodotti').document(prod_id).delete()
        bot.answer_callback_query(call.id, "✅ Prodotto rimosso!")
        remove_product_select(call)  # Ricarica lista
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "rem_cat_sel")
def remove_category_select(call):
    """Seleziona categoria da rimuovere"""
    try:
        categories = db.collection('categories').stream()
        markup = InlineKeyboardMarkup()
        
        for cat in categories:
            cat_data = cat.to_dict()
            nome = cat_data.get('nome', cat.id)
            markup.row(InlineKeyboardButton(f"🗑️ {nome}", callback_data=f"delcat_{cat.id}"))
        
        markup.row(InlineKeyboardButton("🔙 Indietro", callback_data="remove_item"))
        
        bot.edit_message_text("⚠️ Attenzione: rimuovendo una categoria, rimuovi anche tutti i suoi prodotti!\n\n"
                              "Seleziona la categoria da rimuovere:", 
                              call.message.chat.id, call.message.message_id,
                              reply_markup=markup)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delcat_"))
def delete_category(call):
    """Cancella categoria e tutti i suoi prodotti"""
    cat_id = call.data.replace("delcat_", "")
    try:
        # Rimuovi prodotti della categoria
        products = db.collection('prodotti').where('categoria', '==', cat_id).get()
        for prod in products:
            prod.reference.delete()
        
        # Rimuovi categoria
        db.collection('categories').document(cat_id).delete()
        
        bot.answer_callback_query(call.id, "✅ Categoria e prodotti rimossi!")
        bot.edit_message_text("🔐 *Pannello Admin*", call.message.chat.id, call.message.message_id,
                              parse_mode='Markdown', reply_markup=admin_markup(call))
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Errore: {e}")

def admin_markup(call):
    """Ricrea markup admin"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("➕ Categoria", callback_data="add_cat"),
        InlineKeyboardButton("➕ Prodotto", callback_data="add_prod")
    )
    markup.row(
        InlineKeyboardButton("🗑️ Rimuovi", callback_data="remove_item"),
        InlineKeyboardButton("📊 Lista Admin", callback_data="list_admin")
    )
    markup.row(InlineKeyboardButton("➕ Aggiungi Admin", callback_data="add_admin"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "back_admin")
def back_admin(call):
    """Torna a pannello admin"""
    if not is_admin(call.from_user.id):
        return
    bot.edit_message_text("🔐 *Pannello Admin*\n\nSeleziona un'azione:", 
                          call.message.chat.id, call.message.message_id,
                          parse_mode='Markdown', reply_markup=admin_markup(call))

# ========== GESTIONE ADMIN ==========
@bot.callback_query_handler(func=lambda call: call.data == "add_admin")
def add_admin_start(call):
    """Inizia aggiunta admin"""
    if not is_admin(call.from_user.id):
        return
    
    bot.answer_callback_query(call.id)
    msg = bot.send_message(call.message.chat.id, 
                          "Inserisci l'ID Telegram del nuovo admin:\n\n"
                          "(Puoi ottenere l'ID da @userinfobot)\n"
                          "Scrivi /cancel per annullare")
    user_states[call.from_user.id] = {'action': 'add_admin'}

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, {}).get('action') == 'add_admin')
def add_admin_execute(message):
    """Aggiunge admin"""
    if message.text == '/cancel':
        user_states.pop(message.from_user.id, None)
        bot.reply_to(message, "❌ Operazione annullata")
        return
    
    try:
        new_admin_id = message.text.strip()
        db.collection('admins').document(new_admin_id).set({
            'added_by': message.from_user.id,
            'created': firestore.SERVER_TIMESTAMP
        })
        bot.reply_to(message, f"✅ Admin *{new_admin_id}* aggiunto!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Errore: {e}")
    finally:
        user_states.pop(message.from_user.id, None)

@bot.callback_query_handler(func=lambda call: call.data == "list_admin")
def list_admins(call):
    """Mostra lista admin"""
    if not is_admin(call.from_user.id):
        return
    
    try:
        admins = db.collection('admins').stream()
        text = "👥 *Lista Admin:*\n\n"
        
        for admin in admins:
            admin_id = admin.id
            admin_data = admin.to_dict()
            username = admin_data.get('username', 'N/A')
            text += f"• ID: `{admin_id}` (@{username})\n"
        
        if text == "👥 *Lista Admin:*\n\n":
            text += "_Nessun admin registrato_"
        
        markup = InlineKeyboardMarkup().row(InlineKeyboardButton("🔙 Indietro", callback_data="back_admin"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                              parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Errore: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel_action")
def cancel_action(call):
    """Annulla azione"""
    user_states.pop(call.from_user.id, None)
    bot.answer_callback_query(call.id, "❌ Operazione annullata")
    send_welcome(call.message) if hasattr(call.message, 'chat') else None

# ========== WEBHOOK FLASK ==========
@app.route("/")
def index():
    """Pagina principale"""
    return """
    <h1>🤖 Bot Caldarelli Online!</h1>
    <p>Il bot è attivo e funzionante 24/7</p>
    <br>
    <a href='/setwebhook'><button style='padding:10px 20px;'>🔧 Imposta Webhook</button></a>
    """, 200

@app.route("/setwebhook")
def set_webhook():
    """Imposta webhook manualmente"""
    if not RENDER_URL:
        return "❌ RENDER_URL non impostato!", 400
    
    try:
        bot.remove_webhook()
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        result = bot.set_webhook(url=webhook_url)
        
        if result:
            return f"""
            ✅ Webhook impostato!<br><br>
            URL: {webhook_url}<br><br>
            Il bot ora risponde su Telegram!
            """
        else:
            return "❌ Errore impostazione webhook", 500
    except Exception as e:
        return f"❌ Errore: {str(e)}", 500

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Endpoint Telegram"""
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as e:
        print(f"Errore webhook: {e}")
        return "error", 500

# ========== AVVIO ==========
if __name__ == "__main__":
    # Auto-setup webhook
    if RENDER_URL:
        try:
            bot.remove_webhook()
            bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
            print(f"✅ Webhook: {RENDER_URL}/{TOKEN}")
        except Exception as e:
            print(f"⚠️ Webhook manuale richiesto: /setwebhook")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
