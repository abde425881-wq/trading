import telebot
import firebase_admin
from firebase_admin import credentials, firestore
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# TOKEN
TOKEN = "8396839304:AAHLBwLsSPbZPaz0i31C_TtQBUHQmjr1MJU"
bot = telebot.TeleBot(TOKEN)

# Firebase
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

user_states = {}

# ============ FUNZIONI ADMIN ============

def is_admin(user_id):
    """Controlla se l'utente è admin. Se non ci sono admin, il primo diventa admin."""
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        return False
    
    data = doc.to_dict()
    admins = data.get('admins', [])
    
    # Se non ci sono admin, il primo utente diventa admin
    if not admins:
        data['admins'] = [user_id]
        ref.set(data)
        return True
    
    return user_id in admins

def add_admin_to_db(new_admin_id):
    """Aggiunge un nuovo admin al database"""
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        return False
    
    data = doc.to_dict()
    admins = data.get('admins', [])
    
    if new_admin_id in admins:
        return False  # Già admin
    
    admins.append(new_admin_id)
    data['admins'] = admins
    ref.set(data)
    return True

# ============ MENU ============

def menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Bottoni per tutti
    buttons = [
        InlineKeyboardButton("📋 Visualizza Menu", callback_data="list")
    ]
    
    # Bottoni solo per admin
    if is_admin(user_id):
        buttons.extend([
            InlineKeyboardButton("➕ Categoria", callback_data="add_cat"),
            InlineKeyboardButton("📝 Prodotto", callback_data="add_prod"),
            InlineKeyboardButton("❌ Rimuovi Prodotto", callback_data="rem_prod"),
            InlineKeyboardButton("👤 Gestione Admin", callback_data="admin_menu")
        ])
    
    markup.add(*buttons)
    return markup

def admin_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Aggiungi Admin", callback_data="add_admin"),
        InlineKeyboardButton("📋 Lista Admin", callback_data="list_admin"),
        InlineKeyboardButton("🔙 Indietro", callback_data="back")
    )
    return markup

# ============ HANDLERS ============

@bot.message_handler(commands=['start'])
def start(m):
    user_id = m.from_user.id
    
    # Se è il primo avvio e non ci sono admin, lo informa
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if doc.exists:
        data = doc.to_dict()
        if not data.get('admins', []):
            bot.send_message(m.chat.id, "👑 *Sei il primo admin!* Autorizzazione automatica concessa.", parse_mode="Markdown")
    
    bot.send_message(m.chat.id, "🍸 *Caldarelli Bot*\nGestione menu digitale", parse_mode="Markdown", reply_markup=menu(user_id))

# ============ GESTIONE ADMIN ============

@bot.callback_query_handler(func=lambda c: c.data == "admin_menu")
def show_admin_menu(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Non sei autorizzato!")
        return
    
    bot.edit_message_text("👤 *Gestione Admin*", 
                         chat_id=c.message.chat.id, 
                         message_id=c.message.message_id,
                         parse_mode="Markdown",
                         reply_markup=admin_menu())

@bot.callback_query_handler(func=lambda c: c.data == "add_admin")
def request_add_admin(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Non sei autorizzato!")
        return
    
    msg = bot.send_message(c.message.chat.id, 
        "👤 *Aggiungi Nuovo Admin*\n\n"
        "Inoltra un messaggio del nuovo admin (deve aver avviato il bot)\n"
        "Oppure scrivi l'ID utente numerico.",
        parse_mode="Markdown")
    user_states[c.message.chat.id] = {'action': 'add_admin'}
    bot.register_next_step_handler(msg, process_new_admin)

def process_new_admin(m):
    chat_id = m.chat.id
    user_id = m.from_user.id
    
    if not is_admin(user_id):
        bot.send_message(chat_id, "⛔ Non sei più admin!")
        return
    
    new_admin_id = None
    
    # Metodo 1: Messaggio inoltrato
    if m.forward_from:
        new_admin_id = m.forward_from.id
        name = m.forward_from.first_name
    # Metodo 2: ID numerico scritto
    elif m.text and m.text.isdigit():
        new_admin_id = int(m.text)
        name = f"ID {new_admin_id}"
    else:
        bot.send_message(chat_id, "❌ Formato non valido. Inoltra un messaggio o scrivi un ID numerico.", reply_markup=menu(user_id))
        return
    
    if new_admin_id == user_id:
        bot.send_message(chat_id, "❌ Sei già admin!", reply_markup=menu(user_id))
        return
    
    if add_admin_to_db(new_admin_id):
        bot.send_message(chat_id, f"✅ *{name}* aggiunto come admin!", parse_mode="Markdown", reply_markup=menu(user_id))
        # Notifica il nuovo admin
        try:
            bot.send_message(new_admin_id, "🎉 *Sei stato promosso ad admin* del bot Caldarelli!", parse_mode="Markdown")
        except:
            pass
    else:
        bot.send_message(chat_id, "⚠️ Utente già admin o errore database.", reply_markup=menu(user_id))

@bot.callback_query_handler(func=lambda c: c.data == "list_admin")
def list_admins(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Non sei autorizzato!")
        return
    
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        return
    
    admins = doc.to_dict().get('admins', [])
    text = "👤 *Admin registrati:*\n\n"
    
    for admin_id in admins:
        try:
            # Prova a recuperare info utente (funziona solo se ha interagito con il bot)
            chat = bot.get_chat(admin_id)
            name = chat.first_name or "Sconosciuto"
            username = f" @{chat.username}" if chat.username else ""
            text += f"• {name}{username} (`{admin_id}`)\n"
        except:
            text += f"• ID: `{admin_id}`\n"
    
    bot.send_message(c.message.chat.id, text, parse_mode="Markdown", reply_markup=admin_menu())

# ============ OPERAZIONI MENU (PROTETTE) ============

@bot.callback_query_handler(func=lambda c: c.data == "add_cat")
def add_cat(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    
    msg = bot.send_message(c.message.chat.id, "Nome nuova categoria:")
    bot.register_next_step_handler(msg, save_cat)

def save_cat(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "⛔ Non autorizzato!")
        return
    
    cat = m.text
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    data = doc.to_dict() if doc.exists else {}
    if 'categorie' not in data: 
        data['categorie'] = {}
    if 'admins' not in data:
        data['admins'] = [m.from_user.id]  # Safety check
    
    data['categorie'][cat] = []
    ref.set(data)
    bot.send_message(m.chat.id, f"✅ Categoria *{cat}* creata!", parse_mode="Markdown", reply_markup=menu(m.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "add_prod")
def add_prod(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    show_cats(c.message.chat.id, "add")

@bot.callback_query_handler(func=lambda c: c.data == "rem_prod")
def rem_prod(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    show_cats(c.message.chat.id, "rem")

# ============ FUNZIONE MANCANTE! ============

def show_cats(chat_id, mode):
    """Mostra le categorie per aggiungere o rimuovere prodotti"""
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        bot.send_message(chat_id, "❌ Nessuna categoria trovata. Crea prima una categoria!")
        return
    
    data = doc.to_dict()
    cats = data.get('categorie', {})
    
    if not cats:
        bot.send_message(chat_id, "❌ Nessuna categoria disponibile.")
        return
    
    markup = InlineKeyboardMarkup()
    for cat_name in cats:
        if mode == "add":
            cb = f"a_{cat_name}"
            text = f"➕ {cat_name}"
        else:
            cb = f"r_{cat_name}"
            prod_count = len(cats[cat_name])
            text = f"❌ {cat_name} ({prod_count} prodotti)"
        markup.add(InlineKeyboardButton(text, callback_data=cb))
    
    markup.add(InlineKeyboardButton("🔙 Indietro", callback_data="back"))
    
    action_text = "aggiungere" if mode == "add" else "rimuovere da"
    bot.send_message(chat_id, f"Scegli categoria per {action_text}:", reply_markup=markup)

# ============ CONTINUAZIONE HANDLERS ============

@bot.callback_query_handler(func=lambda c: c.data.startswith("a_"))
def sel_add(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    cat = c.data[2:]
    user_states[c.message.chat.id] = {'cat': cat}
    msg = bot.send_message(c.message.chat.id, f"Nome prodotto per *{cat}*:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, ask_price)

def ask_price(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "⛔ Non autorizzato!")
        return
    user_states[m.chat.id]['name'] = m.text
    msg = bot.send_message(m.chat.id, "Prezzo (es: 4.50):")
    bot.register_next_step_handler(msg, save_prod)

def save_prod(m):
    if not is_admin(m.from_user.id):
        bot.send_message(m.chat.id, "⛔ Non autorizzato!")
        return
    
    try:
        price = float(m.text.replace(',', '.'))
        chat = m.chat.id
        cat = user_states[chat]['cat']
        name = user_states[chat]['name']
        ref = db.collection('menu').document('caldarelli')
        doc = ref.get()
        data = doc.to_dict()
        data['categorie'][cat].append({'nome': name, 'prezzo': price})
        ref.set(data)
        bot.send_message(chat, f"✅ *{name}* aggiunto a *{cat}*!", parse_mode="Markdown", reply_markup=menu(m.from_user.id))
        del user_states[chat]
    except Exception as e:
        bot.send_message(m.chat.id, "❌ Errore prezzo. Usa il formato: 4.50")

@bot.callback_query_handler(func=lambda c: c.data.startswith("r_"))
def sel_rem(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    
    cat = c.data[2:]
    ref = db.collection('menu').document('caldarelli')
    prods = ref.get().to_dict()['categorie'][cat]
    markup = InlineKeyboardMarkup()
    for p in prods:
        markup.add(InlineKeyboardButton(f"❌ {p['nome']} €{p['prezzo']}", 
                  callback_data=f"d_{cat}|{p['nome']}"))
    markup.add(InlineKeyboardButton("🔙 Indietro", callback_data="rem_prod"))
    bot.send_message(c.message.chat.id, f"Rimuovi da *{cat}*:", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("d_"))
def do_del(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "⛔ Solo admin!")
        return
    
    data = c.data[2:].split("|")
    cat, name = data[0], data[1]
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    data = doc.to_dict()
    data['categorie'][cat] = [p for p in data['categorie'][cat] if p['nome'] != name]
    ref.set(data)
    bot.send_message(c.message.chat.id, f"✅ *{name}* rimosso!", parse_mode="Markdown", reply_markup=menu(c.from_user.id))

# ============ LISTA (PUBBLICA) ============

@bot.callback_query_handler(func=lambda c: c.data == "list")
def lst(c):
    ref = db.collection('menu').document('caldarelli')
    doc = ref.get()
    if not doc.exists:
        bot.send_message(c.message.chat.id, "Menu vuoto.")
        return
    
    cats = doc.to_dict()['categorie']
    
    messages = []
    current_msg = "📋 *MENU CALDARELLI*\n\n"
    
    for cat, items in cats.items():
        cat_text = f"🍸 *{cat}*\n"
        for i in items: 
            cat_text += f"• {i['nome']} €{i['prezzo']:.2f}\n"
        cat_text += "\n"
        
        if len(current_msg) + len(cat_text) > 3500:
            messages.append(current_msg)
            current_msg = cat_text
        else:
            current_msg += cat_text
    
    if current_msg:
        messages.append(current_msg)
    
    for msg in messages:
        bot.send_message(c.message.chat.id, msg, parse_mode="Markdown")
    
    bot.send_message(c.message.chat.id, "✅ Fine menu", reply_markup=menu(c.from_user.id))

@bot.callback_query_handler(func=lambda c: c.data == "back")
def back(c):
    bot.send_message(c.message.chat.id, "Menu principale:", reply_markup=menu(c.from_user.id))

print("✅ Bot avviato con sistema Admin!")
bot.polling()