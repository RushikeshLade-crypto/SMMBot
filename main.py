import os
from dotenv import load_dotenv
import time
import logging
import telebot
import requests
import sqlite3
import random
import threading
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from telebot import TeleBot
from dotenv import load_dotenv, set_key
from functions import (insertUser, getData, isExists, addBalance, cutBalance, setWelcomeStatus, 
                      addAffiliateCount, addAffiliateEarning, setAffiliatedStatus, get_total_users, save_order, 
                      get_order_history, update_order_stats)
from smm_functions import getFoldersAndServices, getServiceDetailsByName

# Load environment variables from .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
admin_user_id = int(os.getenv("ADMIN_USER_ID"))
admin_username = os.getenv("ADMIN_USERNAME")
service_api = os.getenv("SERVICE_API")
service_key = os.getenv("SERVICE_KEY")
payment_channel = os.getenv("PAYMENT_CHANNEL")
minimum_deposit = Decimal(os.getenv("MINIMUM_DEPOSIT"))
affiliate_bonus = Decimal(os.getenv("AFFILIATE_BONUS"))
welcome_bonus = Decimal(os.getenv("WELCOME_BONUS"))
merchant_api_key = os.getenv("MERCHANT_API_KEY")
bonus_percent = os.getenv("DEPOSIT_BONUS_PERCENT")

bot = telebot.TeleBot(bot_token)
folder_path = "Services"  # Default Services folder

user_folder_paths = {}
user_message_ids = {}
admin_message_ids = {}
user_service_context = {}
deposit_message_ids = {}
user_deposit_context = {}
# Initialize deposits database
def init_deposit_db():
    conn = sqlite3.connect("deposits.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_deposits (
            track_id TEXT PRIMARY KEY,
            user_id TEXT,
            amount TEXT,
            status TEXT,
            timestamp REAL,
            pay_link TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_deposit_db()

# Add deposit record
def add_deposit(track_id, user_id, amount, pay_link):
    conn = sqlite3.connect("deposits.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO pending_deposits (track_id, user_id, amount, status, timestamp, pay_link) VALUES (?, ?, ?, ?, ?, ?)",
                   (track_id, user_id, str(amount), "new", time.time(), pay_link))
    conn.commit()
    conn.close()

# Delete deposit record
def delete_deposit(track_id):
    conn = sqlite3.connect("deposits.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_deposits WHERE track_id = ?", (track_id,))
    conn.commit()
    conn.close()

# Get pending invoices for a user
def get_pending_invoices(user_id):
    conn = sqlite3.connect("deposits.db")
    cursor = conn.cursor()
    cursor.execute("SELECT track_id, amount, status, pay_link FROM pending_deposits WHERE user_id = ? AND status IN ('new', 'waiting', 'paying', 'underpaid')", (user_id,))
    invoices = cursor.fetchall()
    conn.close()
    return invoices

# Format decimal values
def format_decimal(value):
    """Decimal মানকে সঠিক ফরম্যাটে দেখানোর জন্য, সায়েন্টিফিক নোটেশন এড়িয়ে।"""
    value = Decimal(str(value)).normalize()
    return f"{value:f}".rstrip('0').rstrip('.') if '.' in f"{value:f}" else f"{value:f}"

# 🔝 Main Menu Function
def main_menu(chat_id, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Social Media Services", callback_data="services"))
    markup.add(InlineKeyboardButton("👛 Wallet", callback_data="wallet"), 
               InlineKeyboardButton("📊 Order Status", callback_data="order_status"))
    markup.add(InlineKeyboardButton("📜 Order History", callback_data="order_history"), 
               InlineKeyboardButton("📑 Help", callback_data="about"))
    markup.add(InlineKeyboardButton("🏆 Affiliate Program", callback_data="affiliate"))
    if chat_id == admin_user_id:
        markup.add(InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel"))

    msg_text = "<b>🚀 Smm Menu --</> a Social Media Marketing Service provider Telegram bot.\nAt cheapest price on telegram,\n\nJoin <b>@SmmMenu</b> for Maintenance, Service, Price cost updates!"
    if message_id:
        try:
            bot.edit_message_text(msg_text, chat_id, message_id, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit main menu: {e}")
            msg = bot.send_message(chat_id, msg_text, parse_mode="HTML", reply_markup=markup)
            user_message_ids[chat_id] = msg.message_id
    else:
        msg = bot.send_message(chat_id, msg_text, parse_mode="HTML", reply_markup=markup)
        user_message_ids[chat_id] = msg.message_id
    bot.clear_step_handler_by_chat_id(chat_id)

# 🏆 Affiliate System & Welcome Bonus
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.chat.id)
    if hasattr(message, 'from_user') and message.from_user:
        first_name = message.from_user.first_name or 'User'
        username = message.from_user.username
    else:
        first_name = 'User'
        username = None

    aff_by = message.text.split()[1] if len(message.text.split()) > 1 and message.text.split()[1].isdigit() else None

    if hasattr(message, 'from_user') and message.message_id > 0:
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print(f"Failed to delete /start message: {e}")

    if not isExists(user_id):
        insertUser(user_id, {
            "user_id": user_id, "balance": Decimal('0.00'), "aff_by": aff_by if aff_by else "none",
            "affiliated": 0, "welcome_bonus": 0, "total_affs": 0, "total_orders": 0, "total_spend": Decimal('0.00')
        })
        total_users = get_total_users()
        user_link = f"https://t.me/{username}" if username else f"[Permanent Link](tg://user?id={user_id})"
        admin_message = f"""🆕 *New User Joined!*
👤 *User ID:* `{user_id}`
📛 *First Name:* {first_name}
🔗 *Username:* @{username if username else "N/A"}
🔗 *Profile:* {user_link}
👥 *Total Users:* {total_users}
"""
        try:
            bot.send_message(admin_user_id, admin_message, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            print(f"Failed to send admin notification: {e}")

    data = getData(user_id)
    aff_by = data['aff_by']
    affiliated = data['affiliated']
    welcome_bonus_received = data['welcome_bonus']

    if aff_by != "none" and affiliated == 0:
        try:
            bot.send_message(aff_by, f"ℹ️ A new user joined via your affiliate link!")
            addAffiliateCount(aff_by)
            setAffiliatedStatus(user_id)
        except Exception as e:
            print(f"Failed to process affiliate notification: {e}")

    if welcome_bonus_received == 0:
        try:
            bot.send_message(user_id, f"🎁 Welcome Bonus: +{format_decimal(welcome_bonus)} USD (500 TG Views)!")
            addBalance(user_id, welcome_bonus)
            setWelcomeStatus(user_id)
        except Exception as e:
            print(f"Failed to process welcome bonus: {e}")

    main_menu(user_id)

# 🏆 Affiliate Program
@bot.callback_query_handler(func=lambda call: call.data == "affiliate")
def affiliate_info(call):
    user_id = call.message.chat.id
    data = getData(user_id)
    aff_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    
    msg = f"""<a href="https://t.me/smmmenu/84"><b>🏆 Affiliate Program</b></a>
    
<i>💸 Share your unique Affiliate link and earn 1% <b>Commission of order cost</> on every order placed by your referrals—forever! The more they spend, the کوه you earn. No limits, no effort—just passive income!</>

    
🔗 <b>Affiliate Link:</b> 
{aff_link}
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📊 Affiliate Statistics", callback_data="affiliate_stats"))
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit affiliate message: {e}")
        msg_sent = bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
        user_message_ids[user_id] = msg_sent.message_id

# 📊 Affiliate Statistics
@bot.callback_query_handler(func=lambda call: call.data == "affiliate_stats")
def affiliate_stats(call):
    user_id = call.message.chat.id
    data = getData(user_id)
    total_affs = data.get('total_affs', 0)
    affiliate_earnings = data.get('affiliate_earnings', Decimal('0.00'))
    
    msg = f"""📊 <b>Affiliate Statistics</b>
    
    
👥 <b>Total Referred:</b> {total_affs}

💰 <b>Total Earned:</b> ${format_decimal(affiliate_earnings)}
"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="affiliate"))
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit affiliate stats message: {e}")
        msg_sent = bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
        user_message_ids[user_id] = msg_sent.message_id

# Initialize invoice history database
def init_invoice_history_db():
    with sqlite3.connect('invhis.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_history (
                user_id TEXT,
                track_id TEXT,
                amount REAL,
                status TEXT,
                PRIMARY KEY (user_id, track_id)
            )
        ''')
        conn.commit()

# Add invoice to history
def add_invoice_history(user_id, track_id, amount, status="new"):
    with sqlite3.connect('invhis.db') as conn:
        cursor = conn.cursor()
        amount_float = float(amount) if isinstance(amount, Decimal) else amount
        cursor.execute('''
            INSERT OR REPLACE INTO invoice_history (user_id, track_id, amount, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, track_id, amount_float, status))
        
        cursor.execute('''
            SELECT COUNT(*) FROM invoice_history WHERE user_id = ?
        ''', (user_id,))
        count = cursor.fetchone()[0]
        
        if count > 5:
            cursor.execute('''
                DELETE FROM invoice_history
                WHERE user_id = ? AND rowid = (
                    SELECT MIN(rowid) FROM invoice_history WHERE user_id = ?
                )
            ''', (user_id, user_id))
        
        conn.commit()

# Update invoice status in invhis.db
def update_invoice_status(user_id, track_id, status):
    with sqlite3.connect('invhis.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE invoice_history
            SET status = ?
            WHERE user_id = ? AND track_id = ?
        ''', (status, user_id, track_id))
        conn.commit()

# Get last 5 invoices for a user
def get_last_five_invoices(user_id):
    with sqlite3.connect('invhis.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT track_id, amount, status
            FROM invoice_history
            WHERE user_id = ?
            ORDER BY rowid DESC
            LIMIT 5
        ''', (user_id,))
        return cursor.fetchall()

# Initialize invoice history database on startup
init_invoice_history_db()

@bot.callback_query_handler(func=lambda call: call.data == "wallet")
def show_wallet(call):
    user_id = str(call.message.chat.id)
    data = getData(user_id)
    balance = data['balance']
    total_orders = data['total_orders']
    total_spend = data['total_spend']
    
    # .env থেকে বোনাস পার্সেন্টেজ লোড করা
    bonus_percent = float(os.getenv("DEPOSIT_BONUS_PERCENT", "0"))

    msg = f"""<b>👛 Your Wallet Overview</b>
    
    
<b>💰 Balance:</b> <code>${format_decimal(balance)}</code>
<b>⭐ UID:</b> <code>{user_id}</code>

<b>📈 Total Orders Placed:</b> <b>{total_orders}</b>
<b>💵 Lifetime Spending:</b> <code>${format_decimal(total_spend)}</code>
"""
    # বোনাস > 0 হলে বোনাস লাইন যোগ করা
    if bonus_percent > 0:
        msg += f"\n⚡ <b>{bonus_percent}% Bonus on deposit available for limited time!</b>"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 Deposit", callback_data="add_fund"))
    markup.add(InlineKeyboardButton("📜 Transaction History", callback_data="transaction_history"))
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, user_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit wallet message: {e}")
        msg_sent = bot.send_message(user_id, msg, parse_mode="HTML", reply_markup=markup)
        user_message_ids[user_id] = msg_sent.message_id

# Transaction History
@bot.callback_query_handler(func=lambda call: call.data == "transaction_history")
def show_transaction_history(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    
    invoices = get_last_five_invoices(user_id)
    
    if not invoices:
        msg = "📜 *Transaction History*\n\nYou have no recent payments."
    else:
        msg = "📜 *Transaction History*\n\nYour recent pay history:\n\n"
        status_display = {
            "new": "🆕 Created",
            "paid": "✅ Paid",
            "underpaid": "💲 Underpaid",
            "expired": "❌ Expired",
            "waiting": "⏳Waiting",
            "paying": "💲 Paying",
            "manual_accept": "✅ Paid",
            "refunding": "🚀 Refunding",
            "refunded": "📥 Refunded"
        }
        for i, (track_id, amount, status) in enumerate(invoices, 1):
            display_status = status_display.get(status.lower(), status.capitalize())
            msg += f"{i}.💰 Amount  ${format_decimal(amount)} USD \n🆔 Payment ID: `{track_id}` \n📊 Status: {display_status}\n\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="wallet"))
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit transaction history message: {e}")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_fund")
def add_fund_info(call):
    chat_id = call.message.chat.id
    user_id = str(chat_id)
    bot.clear_step_handler_by_chat_id(chat_id)
    
    pending_invoices = get_pending_invoices(user_id)
    msg = f"""🌟 *Add Funds to Your Wallet!* 🌟

🚀 Want to top up instantly? Use our *Crypto Autopay* for seamless, automatic deposits in USDT, BTC, ETH, and more!

📩 Prefer Binance Pay or other methods? Contact {admin_username} for secure manual deposits.

🚀 Choose your way and keep your SMM journey soaring!"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💸 Crypto Autopay", callback_data="crypto_autopay"))
    if pending_invoices:
        markup.add(InlineKeyboardButton("📋 Check Pending Payments", callback_data="check_pending_invoices"))
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="wallet"),
               InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    
    user_deposit_context[user_id] = {"previous_step": "wallet"}
    
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        deposit_message_ids[chat_id] = call.message.message_id
    except Exception as e:
        print(f"Failed to edit add_fund message: {e}")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        deposit_message_ids[chat_id] = msg_sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "crypto_autopay")
def ask_deposit_amount(call):
    chat_id = call.message.chat.id
    bot.clear_step_handler_by_chat_id(chat_id)
    
    msg = f"💰 *Enter Deposit Amount (USD)*\n\n📌 *Minimum*: ${format_decimal(minimum_deposit)}\n\nExample: 0.50 | 1 | 5"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="add_fund"))
    
    user_deposit_context[chat_id] = {"previous_step": "add_fund"}
    
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        deposit_message_ids[chat_id] = call.message.message_id
    except Exception as e:
        print(f"Failed to edit ask amount message: {e}")
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        deposit_message_ids[chat_id] = msg_sent.message_id
    bot.register_next_step_handler_by_chat_id(chat_id, process_deposit_amount)

def process_deposit_amount(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    unique_id = str(int(time.time()))

    try:
        amount = Decimal(message.text.strip())
        if amount < minimum_deposit:
            msg = f"❌ *Amount too low!*\n\n📌 *Minimum*: ${format_decimal(minimum_deposit)}\nPlease enter a valid number (e.g., 0.50):\n\n*Retry {unique_id}*"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancel", callback_data="add_fund"))
            try:
                bot.edit_message_text(msg, chat_id, deposit_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Failed to edit low amount message: {e}")
                try:
                    bot.delete_message(chat_id, deposit_message_ids[chat_id])
                except:
                    pass
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                deposit_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, process_deposit_amount)
            return
    except (InvalidOperation, ValueError):
        msg = f"❌ *Invalid input!*\n\n📌 Please enter only a number (e.g., 0.50):\n\n*Retry {unique_id}-{random.randint(1, 1000)}*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="add_fund"))
        try:
            bot.edit_message_text(msg, chat_id, deposit_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit invalid amount message: {e}")
            try:
                bot.delete_message(chat_id, deposit_message_ids[chat_id])
            except:
                pass
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            deposit_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_deposit_amount)
        return

    try:
        response = requests.post("https://api.oxapay.com/merchants/request", json={
            "merchant": merchant_api_key,
            "amount": str(amount),
            "currency": "USD",
            "lifeTime": 15,
            "feePaidByPayer": 1,
            "underPaidCover": 0,
            "description": f"Deposit by User {chat_id}",
            "orderId": f"DEP_{chat_id}_{int(time.time())}",
            "email": ""
        }, timeout=10).json()
        
        if response.get("result") == 0:
            raise Exception(response.get("message", "Unknown error"))
        
        track_id = response.get("trackId")
        pay_link = response.get("payLink")
        
        if not track_id or not pay_link:
            raise Exception("Invalid response from OxaPay")
        
        add_deposit(track_id, str(chat_id), amount, pay_link)
        add_invoice_history(str(chat_id), track_id, amount)
        
        msg = f"""✅ *Payment Created!*

🆔 *Payment ID*: `{track_id}`
💰 *Amount*: ${format_decimal(amount)} USD
🔗 *Payment Link*: [Pay Now]({pay_link})

📩 *Note*: If you've sent the payment and it’s not reflected or you face any issues, contact {admin_username} for support."""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💳 Pay Now", url=pay_link))
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="add_fund"))
        
        user_deposit_context[chat_id] = {"previous_step": "crypto_autopay"}
        
        try:
            bot.edit_message_text(msg, chat_id, deposit_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit payment message: {e}")
            try:
                bot.delete_message(chat_id, deposit_message_ids[chat_id])
            except:
                pass
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            deposit_message_ids[chat_id] = msg_sent.message_id
        
        threading.Thread(target=track_invoice, args=(chat_id, track_id, amount), daemon=True).start()
        
    except Exception as e:
        msg = f"❌ *Failed to create payment*: {str(e)}\n\nPlease try again or contact {admin_username}.\n\n*Retry {unique_id}*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="add_fund"))
        try:
            bot.edit_message_text(msg, chat_id, deposit_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as edit_e:
            print(f"Failed to edit payment error message: {edit_e}")
            try:
                bot.delete_message(chat_id, deposit_message_ids[chat_id])
            except:
                pass
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            deposit_message_ids[chat_id] = msg_sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "check_pending_invoices")
def check_pending_invoices(call):
    chat_id = call.message.chat.id
    pending_invoices = get_pending_invoices(str(chat_id))
    
    if not pending_invoices:
        msg = "✅ *No pending payments found!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="add_fund"),
                   InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit no pending payments message: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    msg = "🌟 *Your Pending Payments* 🌟\n\n"
    for idx, (track_id, amount, status, pay_link) in enumerate(pending_invoices, 1):
        try:
            response = requests.post("https://api.oxapay.com/merchants/inquiry", json={
                "merchant": merchant_api_key,
                "trackId": track_id
            }, timeout=10).json()
            
            if response.get("result") == 100:
                current_status = response.get("status")
                update_invoice_status(str(chat_id), track_id, current_status)  # Update invhis.db
                if current_status in ["new", "waiting", "paying", "underpaid"]:
                    status_emoji = {"new": "🆕", "waiting": "⏳", "paying": "💸", "underpaid": "⚠️"}.get(current_status, "❓")
                    msg += (f"{idx}. 🆔 *Payment ID*: `{track_id}`\n"
                            f"   💰 *Amount*: ${format_decimal(amount)} USD\n"
                            f"   {status_emoji} *Status*: `{current_status.capitalize()}`\n"
                            f"   🔗 *Pay Now*: [Click Here]({pay_link})\n\n")
                    conn = sqlite3.connect("deposits.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE pending_deposits SET status = ? WHERE track_id = ?", (current_status, track_id))
                    conn.commit()
                    conn.close()
                else:
                    delete_deposit(track_id)
        except Exception as e:
            print(f"Failed to check payment status for track_id {track_id}: {e}")
            msg += (f"{idx}. 🆔 *Payment ID*: `{track_id}`\n"
                    f"   💰 *Amount*: ${format_decimal(amount)} USD\n"
                    f"   ❓ *Status*: `{status.capitalize()}`\n"
                    f"   🔗 *Pay Now*: [Click Here]({pay_link})\n\n")

    msg += "ℹ️ *Complete your payments to proceed!*"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="add_fund"),
               InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    
    user_deposit_context[chat_id] = {"previous_step": "add_fund"}
    
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit pending payments message: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id

import logging

# লগিং সেটআপ
logging.basicConfig(filename="bot_errors.log", level=logging.ERROR)

def track_invoice(chat_id, track_id, amount):
    user_id = str(chat_id)
    start_time = time.time()
    lifetime = 900  # 15 minutes
    track_duration = 900

    while time.time() - start_time < track_duration:
        try:
            # API কল
            response = requests.post("https://api.oxapay.com/merchants/inquiry", json={
                "merchant": merchant_api_key,
                "trackId": track_id
            }, timeout=10).json()
            
            if response.get("result") == 100:
                status = response.get("status").lower()
                
                # ডাটাবেস আপডেট
                try:
                    conn = sqlite3.connect("deposits.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE pending_deposits SET status = ? WHERE track_id = ?", (status, track_id))
                    conn.commit()
                except sqlite3.Error as e:
                    logging.error(f"Database error for track_id {track_id}: {e}")
                finally:
                    conn.close()
                
                update_invoice_status(user_id, track_id, status)
                
                # Handle paid or manual_accept
                if status in ["paid", "manual_accept"]:
                    # বোনাস হিসাব
                    bonus_percent = Decimal(os.getenv("DEPOSIT_BONUS_PERCENT", "0"))
                    bonus_amount = amount * Decimal(bonus_percent / 100)
                    total_amount = amount + bonus_amount

                    # ব্যালেন্সে মোট পরিমাণ যোগ
                    try:
                        addBalance(chat_id, total_amount)
                    except Exception as e:
                        logging.error(f"Failed to update balance for user {chat_id}: {e}")
                        continue

                    user_data = getData(user_id)
                    balance = user_data['balance']
                    username = bot.get_chat(chat_id).username or "N/A"

                    # কনফার্মেশন মেসেজ (ইউজারের জন্য)
                    confirmation_message = (
                        f"🎉 Payment Confirmed!\n\n"
                        f"💰 Amount: ${format_decimal(amount)} USD\n"
                        f"🆔 Payment ID: `{track_id}`\n"
                        f"📊 Status: ✅ Paid"
                    )
                    if bonus_percent > 0:
                        confirmation_message += f"\n🎉 ${format_decimal(bonus_amount)} USD Received from deposit bonus"
                    confirmation_message += f"\n\nThanks for deposit!"

                    # চ্যানেলের মেসেজ
                    channel_message = (
                        f"✅ *New Payment Confirmed!*\n"
                        f"👤 *User ID*: `{chat_id}`\n"
                        f"📛 *Username*: @{username}\n"
                        f"💰 *Amount*: ${format_decimal(amount)} USD\n"
                        f"💸 *Current Balance*: ${format_decimal(balance)} USD\n"
                        f"🆔 *Payment ID*: `{track_id}`\n"
                        f"📊 *Status*: Complete"
                    )
                    if bonus_percent > 0:
                        channel_message += f"\n🎉 ${format_decimal(bonus_amount)} USD Received from deposit bonus"

                    try:
                        # ইউজারকে মেসেজ
                        bot.send_message(chat_id, confirmation_message, parse_mode="Markdown")
                        # চ্যানেলে মেসেজ
                        bot.send_message(payment_channel, channel_message, parse_mode="Markdown")
                    except Exception as e:
                        logging.error(f"Failed to send message to {chat_id} or channel: {e}")
                    
                    try:
                        delete_deposit(track_id)
                    except Exception as e:
                        logging.error(f"Failed to delete deposit for track_id {track_id}: {e}")
                    break
                
                # Handle underpaid
                elif status == "underpaid":
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="check_pending_invoices"),
                                   InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
                        bot.send_message(
                            chat_id,
                            (
                                f"⚠️ Payment Underpaid!\n"
                                f"🆔 Payment ID: `{track_id}`\n"
                                f"Please pay the remaining amount."
                            ),
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logging.error(f"Failed to send underpaid message to {chat_id}: {e}")
                
                # Handle expired (API response)
                elif status == "expired":
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="crypto_autopay"),
                                   InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
                        bot.send_message(
                            chat_id,
                            (
                                f"❌ Payment Expired!\n"
                                f"🆔 Payment ID: `{track_id}`\n"
                                f"Please create a new payment."
                            ),
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logging.error(f"Failed to send expired message to {chat_id}: {e}")
                    delete_deposit(track_id)
                    break
                
                # Handle refunding or refunded
                elif status in ["refunding", "refunded"]:
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="check_pending_invoices"),
                                   InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
                        bot.send_message(
                            chat_id,
                            (
                                f"🔄 Payment Refunded!\n"
                                f"🆔 Payment ID: `{track_id}`\n"
                                f"Status: `{status.capitalize()}`"
                            ),
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logging.error(f"Failed to send refunded message to {chat_id}: {e}")
                    delete_deposit(track_id)
                    break
                
                # Check lifetime for new or waiting
                if (time.time() - start_time >= lifetime) and status in ["new", "waiting"]:
                    try:
                        conn = sqlite3.connect("deposits.db")
                        cursor = conn.cursor()
                        cursor.execute("UPDATE pending_deposits SET status = ? WHERE track_id = ?", ("expired", track_id))
                        conn.commit()
                    except sqlite3.Error as e:
                        logging.error(f"Database error on expire update for track_id {track_id}: {e}")
                    finally:
                        conn.close()
                    
                    update_invoice_status(user_id, track_id, "expired")
                    try:
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="crypto_autopay"),
                                   InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
                        bot.send_message(
                            chat_id,
                            (
                                f"❌ Payment Expired!\n"
                                f"🆔 Payment ID: `{track_id}`\n"
                                f"Please create a new payment."
                            ),
                            parse_mode="Markdown",
                            reply_markup=markup
                        )
                    except Exception as e:
                        logging.error(f"Failed to send expired message to {chat_id}: {e}")
                    delete_deposit(track_id)
                    break

        except requests.RequestException as e:
            logging.error(f"API request failed for track_id {track_id}: {e}")
        
        time.sleep(10)

# 🚀 Social Media Services
@bot.callback_query_handler(func=lambda call: call.data == "services")
def show_main_services(call):
    user_folder_paths[call.message.chat.id] = ""  # Start from root folder
    show_folder_contents(call.message.chat.id, call.message.message_id, "")

def show_folder_contents(chat_id, message_id, folder_path):
    full_path = os.path.join("SMM", folder_path) if folder_path else "SMM"
    if not os.path.exists(full_path):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text("❌ *SMM services folder not found on server!* Please contact @UBOwner to set up services.", chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit folder not found: {e}")
            msg = bot.send_message(chat_id, "❌ *SMM services folder not found on server!* Please contact @UBOwner to set up services.", parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg.message_id
        return

    try:
        folders, services = getFoldersAndServices(folder_path)
    except Exception as e:
        print(f"Failed to get folders and services: {e}")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(f"❌ *Error loading services:* {str(e)}. Contact @UBOwner.", chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e2:
            print(f"Failed to edit error message: {e2}")
            msg = bot.send_message(chat_id, f"❌ *Error loading services:* {str(e)}. Contact @UBOwner.", parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg.message_id
        return

    if not folders and not services:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text("ℹ️ *No services or folders found in SMM directory!* Contact @UBOwner.", chat_id, message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit empty folder message: {e}")
            msg = bot.send_message(chat_id, "ℹ️ *No services or folders found in SMM directory!* Contact @UBOwner.", parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg.message_id
        return

    markup = InlineKeyboardMarkup()
    for folder in folders:
        markup.add(InlineKeyboardButton(f"📁 {folder}", callback_data=f"folder_{folder}"))  
    for service in services:
        markup.add(InlineKeyboardButton(f"🛒 {service}", callback_data=f"service_{service}"))
    if folder_path:
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="back"))
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))

    try:
        bot.edit_message_text("<b>🛒 Pick a Service:</b>", chat_id, message_id, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit folder contents: {e}")
        msg = bot.send_message(chat_id, "<b>🛒 Pick a Service:</b>", parse_mode="HTML", reply_markup=markup)
        user_message_ids[chat_id] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("folder_"))
def navigate_to_subfolder(call):
    folder_name = call.data.replace("folder_", "")
    current_path = user_folder_paths.get(call.message.chat.id, "")
    new_path = f"{current_path}/{folder_name}" if current_path else folder_name
    user_folder_paths[call.message.chat.id] = new_path
    show_folder_contents(call.message.chat.id, call.message.message_id, new_path)

@bot.callback_query_handler(func=lambda call: call.data == "back")
def go_back(call):
    current_path = user_folder_paths.get(call.message.chat.id, "")
    if "/" in current_path:
        new_path = "/".join(current_path.split("/")[:-1])  
    else:
        new_path = ""  
    user_folder_paths[call.message.chat.id] = new_path
    show_folder_contents(call.message.chat.id, call.message.message_id, new_path)

@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def show_service_details(call):
    service_name = call.data.replace("service_", "")
    current_path = user_folder_paths.get(call.message.chat.id, "")
    service = getServiceDetailsByName(service_name, current_path)

    if service:
        user_service_context[call.message.chat.id] = {"service_name": service_name, "folder_path": current_path}
        msg = (f"<b>{service['service_name']}</b>\n\n"
               f"💵 Price/1000: ${format_decimal(service['price_per_k'])}\n"
               f"🛒 Min: {format_decimal(service['min_order'])}\n"
               f"🛒 Max: {format_decimal(service['max_order'])}\n\n"
               f"📑 {service['description']}")
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛍️ Buy Now", callback_data=f"buy_{service_name}"))
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data="back"))
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit service details: {e}")
            msg_sent = bot.send_message(call.message.chat.id, msg, parse_mode="HTML", reply_markup=markup)
            user_message_ids[call.message.chat.id] = msg_sent.message_id
    else:
        bot.answer_callback_query(call.id, "🚫 Service not found!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def ask_quantity(call):
    service_name = call.data.replace("buy_", "")
    current_path = user_folder_paths.get(call.message.chat.id, "")
    service = getServiceDetailsByName(service_name, current_path)

    if not service:
        bot.answer_callback_query(call.id, "🚫 Service not found!")
        return

    msg = f"📌 Enter quantity for\n{service['service_name']}\n\nMin: {format_decimal(service['min_order'])} | Max: {format_decimal(service['max_order'])}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    
    try:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[call.message.chat.id] = call.message.message_id
    except Exception as e:
        print(f"Failed to edit ask_quantity message: {e}")
        msg_sent = bot.send_message(call.message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[call.message.chat.id] = msg_sent.message_id

    bot.register_next_step_handler_by_chat_id(call.message.chat.id, process_quantity, service_name, current_path)

def process_quantity(message, service_name, folder_path):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete quantity message: {e}")

    quantity = message.text
    service = getServiceDetailsByName(service_name, folder_path)

    if not quantity.isdigit():
        msg = f"❌ Enter a valid number!\n\n📌 Enter quantity again:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"Failed to edit invalid quantity message: {e}")
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                user_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_quantity, service_name, folder_path)
        return

    quantity = Decimal(quantity)
    if quantity < service['min_order'] or quantity > service['max_order']:
        msg = f"❌ Quantity must be between {format_decimal(service['min_order'])} and {format_decimal(service['max_order'])}!\n\n📌 Enter quantity again:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"Failed to edit quantity range message: {e}")
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                user_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_quantity, service_name, folder_path)
        return

    try:
        total_cost = (quantity / Decimal('1000')) * service['price_per_k']
        total_cost = total_cost.quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
    except InvalidOperation as e:
        msg = f"❌ Error calculating cost! {str(e)}\n\n📌 Enter quantity again:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as edit_e:
            if "message is not modified" not in str(edit_e):
                print(f"Failed to edit cost calculation error: {edit_e}")
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                user_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_quantity, service_name, folder_path)
        return

    user_data = getData(chat_id)
    user_balance = user_data['balance']

    if user_balance < total_cost:
        msg = f"❌ Low balance!\n💵 Current: ${format_decimal(user_balance)}\nℹ️ Needed: ${format_decimal(total_cost)}\n\n📌 Enter quantity again:"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"Failed to edit low balance message: {e}")
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                user_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_quantity, service_name, folder_path)
        return

    msg = f"🔗 Please Enter The Link ( Your Page, Channel, Post And ... ) 👇\n\n🛒 Quantity: {format_decimal(quantity)}\n💰 Cost: ${format_decimal(total_cost)}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel"))
    try:
        bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit link request message: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id
    bot.register_next_step_handler_by_chat_id(chat_id, process_link, service_name, quantity, total_cost, folder_path)

def process_link(message, service_name, quantity, total_cost, folder_path):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete link message: {e}")

    link = message.text
    service = getServiceDetailsByName(service_name, folder_path)

    if not service:
        msg = "❌ *Service details not found!* Contact @UBOwner."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit service not found: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    # Double-check balance before proceeding
    user_data = getData(chat_id)
    if user_data['balance'] < total_cost:
        msg = f"❌ Insufficient balance after recheck!\n💵 Current: ${format_decimal(user_data['balance'])}\nℹ️ Needed: ${format_decimal(total_cost)}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit insufficient balance: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    try:
        response = requests.post(service_api, data={
            'key': service_key,
            'action': 'add',
            'service': service['service_id'],
            'link': link,
            'quantity': str(quantity)
        }, timeout=10).json()
    except requests.RequestException as e:
        msg = f"❌ *Order failed: Server issue ({str(e)})*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as edit_e:
            print(f"Failed to edit API error message: {edit_e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        try:
            bot.send_message(admin_user_id, f"⚠️ *API Error:* `{str(e)}`\nService: {service_name}")
        except Exception as admin_e:
            print(f"Failed to notify admin: {admin_e}")
        return

    if "order" not in response:
        error_msg = response.get("error", "Unknown error")
        msg = f"❌ *Order failed: {error_msg}*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit order failure message: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    oid = response["order"]
    if not cutBalance(chat_id, total_cost):
        msg = "❌ *Failed to deduct balance! Contact @UBOwner.*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit balance deduction failure: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    new_balance = getData(chat_id)['balance']
    save_order(chat_id, {"order_id": oid, "service_name": service_name, "timestamp": time.time(), "total_cost": total_cost})

    # Add to total_orders table
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO total_orders (order_id, user_id, timestamp) VALUES (?, ?, ?)", 
                   (oid, chat_id, time.time()))
    conn.commit()
    conn.close()

    # Update user's total_orders and total_spend
    update_order_stats(chat_id, total_cost)

    # Affiliate bonus logic (1% of total_cost)
    user_data = getData(chat_id)
    aff_by = user_data['aff_by']
    if aff_by != "none" and isExists(aff_by):
        affiliate_earning = (total_cost * affiliate_bonus).quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
        addBalance(aff_by, affiliate_earning)
        addAffiliateEarning(aff_by, affiliate_earning)
        try:
            bot.send_message(aff_by, f"💰 Affiliate commission!\n \n${format_decimal(affiliate_earning)} Received!")
        except Exception as e:
            print(f"Failed to notify affiliate: {e}")

    escaped_link = link.replace('_', '\\_').replace('*', '\\*')
    msg = (f"✅ *Order placed!*\n\n"
           f"📌 *Order ID:* `{oid}`\n"
           f"🛒 *Service:* `{service_name}`\n"
           f"📦 *Quantity:* `{format_decimal(quantity)}`\n"
           f"💰 *Cost:* `${format_decimal(total_cost)}`\n"
           f"💵 *New Balance:* `${format_decimal(new_balance)}`\n"
           f"🔗 *Link:* {escaped_link}")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit order confirmation: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id
    
    try:
        bot.send_message(payment_channel, 
                         f"✅ *New Order!*\n\n🛒 *Service:* `{service_name}`\n📦 *Quantity:* `{format_decimal(quantity)}`\n👤 *User:* `{chat_id}`\n💰 *Cost:* `${format_decimal(total_cost)}`\n🆔 *Order ID:* `{oid}`\n🔗 *Link:* {escaped_link}", 
                         parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to send payment channel message: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_order(call):
    chat_id = call.message.chat.id
    msg = "✅ *Order cancelled.*"
    markup = InlineKeyboardMarkup()
    
    if chat_id in user_service_context:
        service_name = user_service_context[chat_id]["service_name"]
        markup.add(InlineKeyboardButton("⬅️ Back", callback_data=f"service_{service_name}"))
    
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit cancel message: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id
    
    bot.clear_step_handler_by_chat_id(chat_id)

# 📊 Order Status
@bot.callback_query_handler(func=lambda call: call.data == "order_status")
def ask_order_id(call):
    chat_id = call.message.chat.id
    msg = "📋 *Enter your Order ID:*"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = call.message.message_id
    except Exception as e:
        print(f"Failed to edit order ID request: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id
    
    bot.register_next_step_handler_by_chat_id(chat_id, check_order_status)

def check_order_status(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete order ID message: {e}")

    order_id = message.text.strip()
    if not order_id.isdigit():
        msg = f"❌ *Invalid Order ID! Use numbers only.*\n\n📋 *Enter again (attempt {time.time()}):*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, check_order_status)
        except Exception as e:
            if "message is not modified" not in str(e):
                print(f"Failed to edit invalid order ID: {e}")
                msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
                user_message_ids[chat_id] = msg_sent.message_id
                bot.register_next_step_handler_by_chat_id(chat_id, check_order_status)
        return

    try:
        response = requests.post(service_api, data={
            'key': service_key,
            'action': 'status',
            'order': order_id
        }, timeout=10).json()
    except requests.RequestException as e:
        msg = f"❌ *Server connection failed! Error: {str(e)}*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as edit_e:
            print(f"Failed to edit server error: {edit_e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    if "error" in response or response.get("status") is None:
        msg = f"❌ *Order ID {order_id} not found!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit order not found: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    order_status = response.get('status', 'Unknown')
    quantity = response.get('quantity', 'N/A')
    start_count = response.get('start_count', 'N/A')
    remains = response.get('remains', 'N/A')

    msg = (f"📋 *Order Status:*\n\n"
           f"🆔 *Order ID:* `{order_id}`\n"
           f"🔹 *Status:* `{order_status}`\n"
           f"📦 *Quantity:* `{quantity}`\n"
           f"🚀 *Start:* `{start_count}`\n"
           f"⏳ *Remaining:* `{remains}`")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, user_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit order status: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id

# 📑 Help
@bot.callback_query_handler(func=lambda call: call.data == "about")
def about_bot(call):
    msg = (
    "🌟 *Welcome to SMM - Your Ultimate Social Media Growth Partner!*\n\n"
    "🚀 *Boost Your Online Presence*\n"
    "Step into the world of premium Social Media Marketing (SMM) with us! Whether you're aiming to skyrocket engagement, "
    "grow your follower base, or amplify your brand’s visibility, we’ve got the perfect tools to make it happen—fast, affordable, and reliable.\n\n"
    "📋 *What We Offer:*\n"
    "✔️ *Telegram*: Real Members, Post Views, Reactions\n"
    "✔️ *Instagram*: Followers, Likes, Comments, Story Views\n"
    "✔️ *X (Twitter)*: Followers, Retweets, Impressions\n"
    "✔️ *YouTube*: Views, Subscribers, Likes, Watch Hours\n"
    "✔️ *Facebook*: Page Likes, Post Engagement, Shares\n"
    "✔️ *More Platforms*: TikTok, LinkedIn, and beyond!\n\n"
    "🔥 *Exclusive Bot Features for You:*\n"
    "💸 *Wallet System*: Track your balance, total orders, and lifetime spending effortlessly,  Automatic deposit.\n"
    "📦 *Order Management*: Place orders, check status, and view history in seconds.\n"
    "🏆 *Affiliate Program*: Earn 1% commission on every referral’s order—forever!\n"
    "🎁 *Welcome Bonus*: Get started with a free bonus to kick off your growth.\n"
    "🕒 *Instant Processing*: No delays—just quick results at your fingertips.\n\n"
    "✅ *Why We’re the Best Choice:*\n"
    "🌐 Authentic, high-quality engagement from real users.\n"
    "💰 Unbeatable prices with instant delivery.\n"
    "🔒 Safe, secure, and user-friendly platform.\n"
    "🤖 Fully automated 24/7 service—no waiting required!\n\n"
    "💡 *Grow Smarter, Not Harder*\n"
    "With competitive pricing and a seamless experience, we empower you to take control of your social media success. "
    "Start today and watch your profiles thrive like never before!\n\n"
    "📩 *Need Help?* Reach out to @UBOwner anytime!"
)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit about message: {e}")
        msg_sent = bot.send_message(call.message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[call.message.chat.id] = msg_sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "order_history")
def show_order_history(call):
    chat_id = call.message.chat.id
    orders = get_order_history(chat_id)

    if not orders:
        msg = "📜 *No orders found!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit no orders message: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            user_message_ids[chat_id] = msg_sent.message_id
        return

    msg = "📜 *Your Last 5 Orders:*\n\n"
    for i, order in enumerate(orders[:5], 1):
        msg += (f"{i}.\n"
                f"🆔 *Order ID:* `{order['order_id']}`\n"
                f"🛒 *Service:* `{order['service_name']}`\n\n")

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit order history: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        user_message_ids[chat_id] = msg_sent.message_id

# ✅ Admin Panel
@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_main_menu(call):
    main_menu(call.message.chat.id, call.message.message_id)

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    chat_id = message.chat.id
    if chat_id != admin_user_id:
        try:
            bot.send_message(chat_id, "❌ *Unauthorized!*", parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send unauthorized message: {e}")
        return
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete /admin message: {e}")
    admin_panel(chat_id=chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_callback(call):
    if call.message.chat.id != admin_user_id:
        bot.answer_callback_query(call.id, "❌ Unauthorized!")
        return
    admin_panel(chat_id=call.message.chat.id, call=call)

def admin_panel(chat_id, call=None):
    if chat_id != admin_user_id:
        if call:
            bot.answer_callback_query(call.id, "❌ Unauthorized!")
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📊 Show Stats", callback_data="admin_stats"))
    markup.add(InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.add(InlineKeyboardButton("✉️ Send Private Message", callback_data="admin_private"))
    markup.add(InlineKeyboardButton("💰 Edit Balance", callback_data="admin_editbalance"))
    markup.add(InlineKeyboardButton("➕ Add Default User", callback_data="admin_add_default"))
    markup.add(InlineKeyboardButton("🎁 Set Bonus", callback_data="set_bonus"))  # নতুন বাটন
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))

    try:
        if call:
            bot.edit_message_text("<b>🛠️ Admin Panel</b>\n\nPick an option:", chat_id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        else:
            msg = bot.send_message(chat_id, "<b>🛠️ Admin Panel</b>\n\nPick an option:", parse_mode="HTML", reply_markup=markup)
            admin_message_ids[chat_id] = msg.message_id
    except Exception as e:
        print(f"Failed to send admin panel: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_options(call):
    chat_id = call.message.chat.id
    if chat_id != admin_user_id:
        bot.answer_callback_query(call.id, "❌ Unauthorized!")
        return

    option = call.data.replace("admin_", "")
    bot.answer_callback_query(call.id)

    if option == "stats":
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM total_orders")
        total_orders = cursor.fetchone()[0]
        conn.close()

        msg = f"📊 *Bot Stats:*\n\n👥 Total Users: {total_users}\n📦 Total Orders: {total_orders}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Back", callback_data="admin_panel"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit stats: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id

    elif option == "broadcast":
        msg = "📢 *Enter the broadcast message:*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, send_broadcast_message)
        except Exception as e:
            print(f"Failed to edit broadcast request: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, send_broadcast_message)

    elif option == "private":
        msg = "🆔 *Enter the User ID:*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, ask_private_message)
        except Exception as e:
            print(f"Failed to edit private message request: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, ask_private_message)

    elif option == "editbalance":
        msg = "🆔 *Enter the User ID:*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, ask_amount_for_balance_edit)
        except Exception as e:
            print(f"Failed to edit balance request: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, ask_amount_for_balance_edit)

    elif option == "add_default":
        msg = "➕ *Enter User ID(s) (e.g., '12345678' or '12345678,123456789'):*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_default_user)
        except Exception as e:
            print(f"Failed to edit add default request: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, process_add_default_user)

# নতুন হ্যান্ডলার ফাংশন
@bot.callback_query_handler(func=lambda call: call.data == "set_bonus")
def handle_set_bonus(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🎁 Send bonus amount of % 1-100 (e.g., 10, 5.5). Send 0 to turn off.", parse_mode="Markdown")
    bot.register_next_step_handler(call.message, process_bonus_input)

def send_broadcast_message(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete broadcast message: {e}")

    broadcast_text = message.text
    sent_count = 0
    blocked_count = 0

    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()

    for user_id in users:
        try:
            bot.send_message(user_id, broadcast_text, parse_mode="Markdown")
            sent_count += 1
        except Exception:
            blocked_count += 1

    msg = f"✅ *Broadcast Done!*\n📤 *Sent:* {sent_count}\n🚫 *Blocked:* {blocked_count}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit broadcast result: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id

def ask_private_message(message):
    chat_id = message.chat.id
    user_id = message.text.strip()
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete private user ID: {e}")

    msg = "✉️ *Enter the message:*"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler_by_chat_id(chat_id, send_private_message, user_id)
    except Exception as e:
        print(f"Failed to edit private message prompt: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, send_private_message, user_id)

def send_private_message(message, user_id):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete private message text: {e}")

    try:
        bot.send_message(user_id, message.text, parse_mode="Markdown")
        msg = "✅ *Message sent!*"
    except Exception as e:
        print(f"Failed to send private message: {e}")
        msg = "❌ *Failed: User may have blocked bot!*"

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit private message result: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id

def ask_amount_for_balance_edit(message):
    chat_id = message.chat.id
    user_id = message.text.strip()
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete balance user ID: {e}")

    if not isExists(user_id):
        msg = "❌ *User not found!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Failed to edit user not found: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
        return

    data = getData(user_id)
    current_balance = data['balance']
    msg = (f"💰 *User ID:* `{user_id}`\n"
           f"💵 *Balance:* `${format_decimal(current_balance)}`\n\n"
           f"✏️ *Enter amount (e.g., +0.005 or -10.25):*")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)
    except Exception as e:
        print(f"Failed to edit balance amount prompt: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id
        bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)

def process_balance_edit(message, user_id, current_balance):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete balance amount: {e}")

    amount_text = message.text.strip()
    try:
        if not (amount_text.startswith("+") or amount_text.startswith("-")):
            raise ValueError
        amount = Decimal(amount_text)
    except (InvalidOperation, ValueError):
        msg = "❌ *Invalid format! Use +0.005 or -10.25!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)
        except Exception as e:
            print(f"Failed to edit invalid balance format: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)
        return

    new_balance = current_balance + amount if amount > 0 else current_balance - abs(amount)
    if new_balance < 0:
        msg = "❌ *Cannot go below zero!*"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
        try:
            bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
            bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)
        except Exception as e:
            print(f"Failed to edit below zero message: {e}")
            msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
            admin_message_ids[chat_id] = msg_sent.message_id
            bot.register_next_step_handler_by_chat_id(chat_id, process_balance_edit, user_id, current_balance)
        return

    if amount > 0:
        addBalance(user_id, amount)
    else:
        cutBalance(user_id, abs(amount))

    updated_balance = getData(user_id)['balance']
    msg = (f"✅ *Balance Updated!*\n"
           f"👤 *User:* `{user_id}`\n"
           f"💵 *Old:* `${format_decimal(current_balance)}`\n"
           f"🔄 *Change:* `{amount_text}`\n"
           f"💰 *New:* `${format_decimal(updated_balance)}`")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit balance update: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id
    
    try:
        bot.send_message(user_id, 
                         f"🎉 Payment Confimed!\n\n💰 Amount:  ${amount_text} USD\n📊 Status: ✅ Paid\n\nThanks for deposit!", 
                         parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to notify user of balance update: {e}")

def process_add_default_user(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete add default message: {e}")

    try:
        user_ids = [uid.strip() for uid in message.text.split(",")]
        added_count = 0
        for user_id in user_ids:
            uid_str = str(user_id)
            if not isExists(uid_str):
                insertUser(uid_str, {
                    "user_id": uid_str, "balance": Decimal('0.00'), "aff_by": "none",
                    "affiliated": 0, "welcome_bonus": 0, "total_affs": 0, "total_orders": 0, "total_spend": Decimal('0.00')
                })
                added_count += 1
        msg = f"➕ *Added {added_count} user(s) as default.*"
    except Exception as e:
        msg = f"❌ *Error:* {str(e)}. Use valid User ID(s) separated by commas."

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔝 Main Menu", callback_data="main_menu"))
    try:
        bot.edit_message_text(msg, chat_id, admin_message_ids[chat_id], parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"Failed to edit add default result: {e}")
        msg_sent = bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=markup)
        admin_message_ids[chat_id] = msg_sent.message_id

def process_bonus_input(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logging.error(f"Failed to delete bonus input message: {e}")

    try:
        bonus_percent = float(message.text.strip())
        if 0 <= bonus_percent <= 100:
            # .env ফাইলে বোনাস আপডেট
            set_key(".env", "DEPOSIT_BONUS_PERCENT", str(bonus_percent))
            # নতুন করে .env ফাইল লোড
            load_dotenv(override=True)
            bot.send_message(chat_id, "✅ Done! Bonus set to {}%.".format(bonus_percent), parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ Invalid amount! Please send a number between 0 and 100.", parse_mode="Markdown")
            bot.register_next_step_handler_by_chat_id(chat_id, process_bonus_input)
    except ValueError:
        bot.send_message(chat_id, "❌ Invalid input! Please send a valid number (e.g., 10, 5.5).", parse_mode="Markdown")
        bot.register_next_step_handler_by_chat_id(chat_id, process_bonus_input)
    finally:
        bot.clear_step_handler_by_chat_id(chat_id)

# Random Message Handler
@bot.message_handler(func=lambda message: True)
def handle_random_message(message):
    chat_id = message.chat.id
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        print(f"Failed to delete random message: {e}")

# SQLite Database Setup
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        balance TEXT DEFAULT '0.0',
        aff_by TEXT DEFAULT 'none',
        affiliated INTEGER DEFAULT 0,
        welcome_bonus INTEGER DEFAULT 0,
        total_affs INTEGER DEFAULT 0,
        affiliate_earnings TEXT DEFAULT '0.0',
        total_orders INTEGER DEFAULT 0,
        total_spend TEXT DEFAULT '0.0'
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT,
        user_id TEXT,
        service_name TEXT,
        timestamp REAL,
        total_cost TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS total_orders (
        order_id TEXT,
        user_id TEXT,
        timestamp REAL
    )
''')
conn.commit()
conn.close()

if __name__ == '__main__':
    while True:
        try:
            print("Bot is running")
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Bot polling failed: {e}")
            try:
                bot.send_message(admin_user_id, f"Bot polling failed: {e}")
            except Exception as admin_e:
                print(f"Failed to notify admin of polling failure: {admin_e}")
            time.sleep(10)