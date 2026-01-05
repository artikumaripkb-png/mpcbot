import telebot
from telebot import types
import time
import threading
import re
import random
import string
from flask import Flask

# --- Flask Web Server (Render ke liye zaroori hai) ---
app = Flask('')

@app.route('/')
def home():
    return "MPC Bot is Alive and Running!"

def run_web_server():
    # Render hamesha port 10000 check karta hai
    try:
        app.run(host='0.0.0.0', port=10000)
    except Exception as e:
        print(f"Server Error: {e}")

# --- TELEGRAM BOT CODE ---
# Apna sahi API TOKEN yahan dalein
API_TOKEN = '8231937886:AAHQFPzsaEA7IIY0wOcvuRpYhsA0iQ6b9Ew'
bot = telebot.TeleBot(API_TOKEN)

# Quiz settings store karne ke liye
quiz_sessions = {} 
id_map = {} 
stop_signals = {} 

def generate_quiz_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    text_split = message.text.split()
    
    # Agar user link se aaya hai (e.g. /start abcd123)
    if len(text_split) > 1:
        process_quiz_by_id(chat_id, text_split[1])
        return

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('➕ Create New Quiz'))
    bot.send_message(chat_id, "👋 **MPC MEGA QUIZ BOT**\n\nNiche diye gaye button par click karein ya Quiz ID bhejein.", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(func=lambda message: len(message.text) == 8)
def handle_quiz_id(message):
    process_quiz_by_id(message.chat.id, message.text)

def process_quiz_by_id(chat_id, q_id):
    if q_id in id_map:
        owner_id = id_map[q_id]
        bot.send_message(chat_id, f"✅ **Quiz Mil Gayi!**\n🚀 Bas kuch hi der mein shuru ho rahi hai...")
        stop_signals[chat_id] = False
        threading.Thread(target=run_quiz_loop, args=(chat_id, owner_id)).start()
    else:
        bot.send_message(chat_id, "❌ Galat ID! Kripya sahi ID dalein.")

@bot.message_handler(func=lambda message: message.text == '➕ Create New Quiz')
def ask_title(message):
    msg = bot.send_message(message.chat.id, "📝 **Quiz ka naam (Title) likhein:**")
    bot.register_next_step_handler(msg, get_title)

def get_title(message):
    chat_id = message.chat.id
    q_id = generate_quiz_id()
    id_map[q_id] = chat_id
    quiz_sessions[chat_id] = {
        'title': message.text, 
        'questions': [], 
        'q_id': q_id, 
        'timer': 30, 
        'active_polls_global': {}
    }
    msg = bot.send_message(chat_id, "🔢 **Ab saare Sawal ek saath bhejein!**\n\nFormat:\nQ1. Sawal?\na) Galat\nb) ✅ Sahi\nc) Galat\nd) Galat")
    bot.register_next_step_handler(msg, parse_questions)

def parse_questions(message):
    chat_id = message.chat.id
    blocks = re.split(r'\n\n+', message.text.strip())
    valid_qs = [b.strip() for b in blocks if "a)" in b.lower()]
    quiz_sessions[chat_id]['questions'] = valid_qs
    msg = bot.send_message(chat_id, "⏱️ **Har sawal ke liye kitne Seconds ka time chahiye?** (Sirf number bhejein, jaise: 30)")
    bot.register_next_step_handler(msg, set_timer)

def set_timer(message):
    chat_id = message.chat.id
    nums = re.findall(r'\d+', message.text)
    quiz_sessions[chat_id]['timer'] = int(nums[0]) if nums else 30
    
    data = quiz_sessions[chat_id]
    bot_info = bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={data['q_id']}"
    
    bot.send_message(chat_id, f"✅ **Quiz Ready Ho Gayi!**\n\n🆔 ID: `{data['q_id']}`\n🔗 Direct Link: {link}\n\nIs ID ko group mein share karein!", parse_mode='Markdown')

def run_quiz_loop(chat_id, owner_id):
    data = quiz_sessions[owner_id]
    scores = {}
    
    for i, q_block in enumerate(data['questions'], 1):
        if stop_signals.get(chat_id, False):
            break
            
        lines = [l.strip() for l in q_block.split('\n') if l.strip()]
        question_text = lines[0]
        options = []
        correct_id = 0
        
        for line in lines[1:]:
            if any(line.lower().startswith(p) for p in ['a)', 'b)', 'c)', 'd)']):
                clean_option = line.replace("✅", "").strip()[2:].strip()
                if "✅" in line:
                    correct_id = len(options)
                options.append(clean_option)
        
        try:
            poll = bot.send_poll(
                chat_id, 
                f"[{i}/{len(data['questions'])}] {question_text}", 
                options, 
                is_anonymous=False, 
                type='quiz', 
                correct_option_id=correct_id, 
                open_period=data['timer']
            )
            data['active_polls_global'][poll.poll.id] = {'correct': correct_id, 'scores': scores}
            time.sleep(data['timer'] + 1)
        except Exception as e:
            print(f"Poll Error: {e}")
            continue
            
    send_result(chat_id, scores, data['title'])

def send_result(chat_id, scores, title):
    res = f"🏆 **QUIZ RESULT: {title}**\n\n"
    if not scores:
        res += "Kisi ne hissa nahi liya."
    else:
        sorted_s = sorted(scores.items(), key=lambda x: x[1]['c'], reverse=True)
        for i, (uid, info) in enumerate(sorted_s[:10], 1):
            res += f"{i}. {info['n']} — ✅ {info['c']} Sahi\n"
    bot.send_message(chat_id, res, parse_mode='Markdown')

@bot.poll_answer_handler()
def handle_ans(ans):
    for owner_id in quiz_sessions:
        active_polls = quiz_sessions[owner_id].get('active_polls_global', {})
        if ans.poll_id in active_polls:
            poll_data = active_polls[ans.poll_id]
            uid = ans.user.id
            if uid not in poll_data['scores']:
                poll_data['scores'][uid] = {'n': ans.user.first_name, 'c': 0}
            if ans.option_ids[0] == poll_data['correct']:
                poll_data['scores'][uid]['c'] += 1

# --- Execution ---
if __name__ == "__main__":
    # Web server ko background mein chalayein
    threading.Thread(target=run_web_server, daemon=True).start()
    print("Bot is starting...")
    # Bot ko polling par lagayein
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

