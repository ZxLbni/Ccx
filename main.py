import logging
import requests
import telebot
from flask import Flask, request
from threading import Event
import time
import json

# Configuration
TOKEN = "6531798224:AAFMgokXvj8bLTXyxQw2IkE0hyQnJf7oFTk"
OWNER_ID = 6742022802  # Owner's Telegram ID
WEBHOOK_URL = "https://ccx.onrender.com/" + TOKEN
API_URL = "https://daxxteam.com/chk/api.php"

# Initialize the bot
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Event to control the stopping of the card check process
stop_event = Event()

# Lists to store authorized group IDs and user IDs with credits
authorized_groups = []
user_credits = {}

# Load authorized groups and user credits from file (if exists)
try:
    with open('authorized_groups.json', 'r') as file:
        authorized_groups = json.load(file)
except FileNotFoundError:
    authorized_groups = []

try:
    with open('user_credits.json', 'r') as file:
        user_credits = json.load(file)
except FileNotFoundError:
    user_credits = {}

def save_authorized_groups():
    with open('authorized_groups.json', 'w') as file:
        json.dump(authorized_groups, file)

def save_user_credits():
    with open('user_credits.json', 'w') as file:
        json.dump(user_credits, file)

# Set webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok'

@app.route('/')
def index():
    return "Bot is running"

# Command handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Welcome! Use /register to register and get 10 credits. Use the /chk command followed by card details in the format `cc|mm|yyyy|cvv`, or send a TXT file with card details. Use /stop to stop the card check process.")

@bot.message_handler(commands=['cmds'])
def send_cmds(message):
    cmds_message = (
        "Available commands:\n"
        "/start - Welcome message\n"
        "/cmds - List all commands\n"
        "/register - Register and get 10 credits\n"
        "/info - Get your information\n"
        "/add - Authorize a group or user\n"
        "/remove - Unauthorize a group or user\n"
        "/chk - Check card details\n"
        "/stop - Stop the card check process\n"
    )
    bot.reply_to(message, cmds_message)

@bot.message_handler(commands=['register'])
def register_user(message):
    user_id = message.from_user.id
    if user_id in user_credits:
        bot.reply_to(message, "You are already registered.")
        return
    
    user_credits[user_id] = 10
    save_user_credits()
    bot.reply_to(message, "You have been registered and received 10 credits.")

@bot.message_handler(commands=['info'])
def user_info(message):
    user_id = message.from_user.id
    if user_id not in user_credits and user_id != OWNER_ID:
        bot.reply_to(message, "You are not registered. Use /register to register.")
        return

    credits = "Unlimited" if user_id == OWNER_ID else user_credits.get(user_id, 0)
    rank = "Owner" if user_id == OWNER_ID else "Free"
    username = message.from_user.username or "N/A"
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    
    info_message = (
        f"User Information:\n"
        f"Username: {username}\n"
        f"User ID: {user_id}\n"
        f"Full Name: {full_name}\n"
        f"Credits: {credits}\n"
        f"Rank: {rank}\n"
    )
    bot.reply_to(message, info_message)

@bot.message_handler(commands=['add'])
def add_authorization(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Usage: /add group <group_id> or /add <user_id> <credits>")
        return

    if args[1] == 'group':
        group_id = int(args[2])
        if group_id not in authorized_groups:
            authorized_groups.append(group_id)
            save_authorized_groups()
            bot.reply_to(message, f"Group {group_id} has been authorized for CC checks.")
        else:
            bot.reply_to(message, f"Group {group_id} is already authorized.")
    else:
        if len(args) != 3:
            bot.reply_to(message, "Usage: /add <user_id> <credits>")
            return
        user_id = int(args[1])
        credits = int(args[2])
        user_credits[user_id] = user_credits.get(user_id, 0) + credits
        save_user_credits()
        bot.reply_to(message, f"User {user_id} has been authorized with {credits} credits.")

@bot.message_handler(commands=['remove'])
def remove_authorization(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    args = message.text.split()
    if len(args) != 3:
        bot.reply_to(message, "Usage: /remove group <group_id> or /remove userid <user_id>")
        return

    if args[1] == 'group':
        group_id = int(args[2])
        if group_id in authorized_groups:
            authorized_groups.remove(group_id)
            save_authorized_groups()
            bot.reply_to(message, f"Group {group_id} has been unauthorized.")
        else:
            bot.reply_to(message, f"Group {group_id} is not authorized.")
    elif args[1] == 'userid':
        user_id = int(args[2])
        if user_id in user_credits:
            del user_credits[user_id]
            save_user_credits()
            bot.reply_to(message, f"User {user_id} has been unauthorized.")
        else:
            bot.reply_to(message, f"User {user_id} is not authorized.")
    else:
        bot.reply_to(message, "Invalid type. Use 'group' or 'userid'.")

@bot.message_handler(commands=['chk'])
def check_card(message):
    user_id = message.from_user.id
    if user_id != OWNER_ID and user_id not in user_credits and message.chat.id not in authorized_groups:
        bot.reply_to(message, "You are not authorized to use this command.")
        return

    if user_id != OWNER_ID and user_credits.get(user_id, 0) <= 0:
        bot.reply_to(message, "You don't have enough credits to use this command.")
        return

    card_details = message.text.split()[1:]
    if not card_details:
        bot.reply_to(message, "Please provide card details in the format `cc|mm|yyyy|cvv`.")
        return

    stop_event.clear()

    for card in card_details:
        if stop_event.is_set():
            bot.reply_to(message, "Card check process stopped.")
            break

        if user_id != OWNER_ID:
            user_credits[user_id] -= 1
            save_user_credits()

        start_time = time.time()
        params = {
            'lista': card,
            'mode': 'cvv',
            'amount': 0.5,
            'currency': 'eur'
        }
        try:
            response = requests.get(API_URL, params=params)
            end_time = time.time()
        except requests.exceptions.RequestException as e:
            bot.reply_to(message, f"Error connecting to API: {e}")
            continue
        
        if response.headers.get('Content-Type') == 'application/json':
            try:
                response_data = response.json()
                bot.reply_to(message, response_data.get("response", "No response"))
            except requests.exceptions.JSONDecodeError:
                bot.reply_to(message, f"Failed to decode JSON response. Response content: {response.text}")
                continue
        else:
            bot.reply_to(message, response.text)

        time.sleep(10)

@bot.message_handler(content_types=['document'])
def handle_file(message):
    user_id = message.from_user.id
    if user_id not in user_credits and user_id != OWNER_ID:
        bot.reply_to(message, "You are not registered. Use /register to register.")
        return

    if user_id != OWNER_ID and user_credits.get(user_id, 0) <= 0:
        bot.reply_to(message, "You don't have enough credits to use this command.")
        return

    if message.document.mime_type == 'text/plain':
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open('lista.txt', 'wb') as f:
            f.write(downloaded_file)
        
        with open('lista.txt', 'r') as f:
            lista_values = f.readlines()
        
        stop_event.clear()

        for lista in lista_values:
            if stop_event.is_set():
                bot.reply_to(message, "Card check process stopped.")
                break

            if user_id != OWNER_ID:
                user_credits[user_id] -= 1
                save_user_credits()

            start_time = time.time()
            lista = lista.strip()
            if lista:
                params = {
                    'lista': lista,
                    'mode': 'cvv',
                    'amount': 0.5,
                    'currency': 'eur'
                }
                try:
                    response = requests.get(API_URL, params=params)
                    end_time = time.time()
                except requests.exceptions.RequestException as e:
                    bot.reply_to(message, f"Error connecting to API: {e}")
                    continue
                
                if response.headers.get('Content-Type') == 'application/json':
                    try:
                        response_data = response.json()
                        bot.reply_to(message, response_data.get("response", "No response"))
                    except requests.exceptions.JSONDecodeError:
                        bot.reply_to(message, f"Failed to decode JSON response. Response content: {response.text}")
                        continue
                else:
                    bot.reply_to(message, response.text)

                time.sleep(10)

@bot.message_handler(commands=['stop'])
def stop_process(message):
    if message.from_user.id == OWNER_ID:
        stop_event.set()
        bot.reply_to(message, "Card check process has been stopped.")
    else:
        bot.reply_to(message, "You are not authorized to use this command.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=5000)  # Ensure to use appropriate port for deployment
