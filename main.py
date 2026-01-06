import telebot
from telebot import types
import time
import threading
import re
import random
import string
from flask import Flask

# --- Flask Server for Render (बोट को ऑनलाइन रखने के लिए) ---
app = Flask('')
@app.route('/')
def home(): 
    return "MPC Bot is Live!"

def run_web_server():
    app.run(host='0.0.0.0', port=10000)

# --- BOT CONFIGURATION ---
# अपना टेलीग्राम बॉट टोकन यहाँ डालें
API_TOKEN = '8231937886:AAE2vAFQmsaxboou_FsbtZztyqShQI61z8Q' 
bot = telebot.TeleBot(API_TOKEN)

quiz_sessions = {} 
id_map = {} 
stop_signals = {}

def generate_quiz_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=7))

@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    arg = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if arg:
        process_quiz_by_id(chat_id, arg)
    else:
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup.add(types.KeyboardButton('➕ Create New Quiz'))
        bot.send_message(chat_id, "👋 **Welcome to MPC QUIZ BOT**\n\nनीचे दिए गए बटन से क्विज़ बनाएं।", reply_markup=markup, parse_mode='Markdown')

# --- क्विज़ निर्माण प्रक्रिया ---
@bot.message_handler(func=lambda message: message.text == '➕ Create New Quiz')
def ask_title(message):
    msg = bot.send_message(message.chat.id, "📝 **क्विज़ का नाम (Title) लिखें:**")
    bot.register_next_step_handler(msg, get_title)

def get_title(message):
    chat_id = message.chat.id
    q_id = generate_quiz_id()
    id_map[q_id] = chat_id
    quiz_sessions[chat_id] = {
        'title': message.text, 'questions': [], 'q_id': q_id, 
        'timer': 15, 'type': 'free', 'neg': '0.00',
        'creator': message.from_user.first_name, 'active_polls': {}
    }
    msg = bot.send_message(chat_id, "🔢 **सवाल भेजें!**\n\nप्रारूप (Format):\nQ. भारत की राजधानी क्या है?\na) मुंबई\nb) ✅ नई दिल्ली")
    bot.register_next_step_handler(msg, parse_questions)

def parse_questions(message):
    chat_id = message.chat.id
    blocks = re.split(r'\n\n+', message.text.strip())
    quiz_sessions[chat_id]['questions'] = [b.strip() for b in blocks if "a)" in b.lower()]
    msg = bot.send_message(chat_id, "⏱ **समय (जैसे 15) और नेगेटिव मार्किंग (जैसे 0.25) लिखें:**")
    bot.register_next_step_handler(msg, finalize_quiz)

def finalize_quiz(message):
    chat_id = message.chat.id
    data = quiz_sessions[chat_id]
    vals = re.findall(r"[\d\.]+", message.text)
    data['timer'] = int(vals[0]) if len(vals) > 0 else 15
    data['neg'] = vals[1] if len(vals) > 1 else '0.00'
    
    bot_info = bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={data['q_id']}"
    
    success_msg = (
        f"┏━━━━━━━━━━━━━━━━━━\n"
        f"┃ 📝 **Quiz Created Successfully!**\n"
        f"┗━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 **Quiz Name:** {data['title']}\n"
        f"🔢 **Questions:** {len(data['questions'])}\n"
        f"⏰ **Timer:** {data['timer']} seconds\n"
        f"🆔 **Quiz ID:** `{data['q_id']}`\n"
        f"👷 **Creator:** 🔥 {data['creator']} 🔥"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎯 Start Quiz Now", url=link))
    markup.row(types.InlineKeyboardButton("🚀 Start Quiz in Group", url=f"https://t.me/{bot_info.username}?startgroup={data['q_id']}"))
    markup.row(types.InlineKeyboardButton("🔗 Share Quiz", switch_inline_query=data['q_id']))
    
    bot.send_message(chat_id, success_msg, reply_markup=markup, parse_mode='Markdown')

# --- रिजल्ट और लीडरबोर्ड ---
def send_result(chat_id, scores, title, total_q, q_id):
    if not scores:
        bot.send_message(chat_id, f"🏆 **रिजल्ट: {title}**\n\nकोई प्रतिभागी नहीं मिला।")
        return

    sorted_s = sorted(scores.items(), key=lambda x: x[1]['c'], reverse=True)
    leaderboard = f"🏆 **LEADERBOARD: {title}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
    
    for i, (uid, info) in enumerate(sorted_s[:10]):
        rank = medals[i] if i < len(medals) else f"{i+1}."
        corr = info['c']
        wrng = total_q - corr
        perc = round((corr/total_q)*100, 2)
        leaderboard += f"{rank} **{info['n']}** | ✅ {corr} | ❌ {wrng} | 📊 {perc}%\n━━━━━━━━━━━━━━━━━━━━\n"

    bot_info = bot.get_me()
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🔄 Restart Quiz", url=f"https://t.me/{bot_info.username}?start={q_id}"))
    
    bot.send_message(chat_id, leaderboard, reply_markup=markup, parse_mode='Markdown')

# --- क्विज़ इंजन ---
def process_quiz_by_id(chat_id, q_id):
    if q_id in id_map:
        stop_signals[chat_id] = False
        owner_id = id_map[q_id]
        bot.send_message(chat_id, f"🚀 **{quiz_sessions[owner_id]['title']}** शुरू हो रही है...")
        threading.Thread(target=run_quiz_loop, args=(chat_id, owner_id)).start()
    else: 
        bot.send_message(chat_id, "❌ गलत क्विज़ ID।")

def run_quiz_loop(chat_id, owner_id):
    data = quiz_sessions[owner_id]
    scores = {}
    total = len(data['questions'])
    for i, q_block in enumerate(data['questions'], 1):
        if stop_signals.get(chat_id, False): break
        lines = q_block.split('\n')
        opts = []
        corr_id = 0
        for line in lines[1:]:
            if ')' in line:
                clean = line.replace("✅", "").strip()[2:].strip()
                if "✅" in line: corr_id = len(opts)
                opts.append(clean)
        try:
            p = bot.send_poll(chat_id, f"[{i}/{total}] {lines[0]}", opts, is_anonymous=False, type='quiz', correct_option_id=corr_id, open_period=data['timer'])
            data['active_polls'][p.poll.id] = {'correct': corr_id, 'scores': scores}
            time.sleep(data['timer'] + 1)
        except: 
            continue
    send_result(chat_id, scores, data['title'], total, data['q_id'])

@bot.poll_answer_handler()
def handle_ans(ans):
    for owner_id in quiz_sessions:
        active = quiz_sessions[owner_id].get('active_polls', {})
        if ans.poll_id in active:
            poll_info = active[ans.poll_id]
            uid = ans.user.id
            if uid not in poll_info['scores']: 
                poll_info['scores'][uid] = {'n': ans.user.first_name, 'c': 0}
            if ans.option_ids[0] == poll_info['correct']: 
                poll_info['scores'][uid]['c'] += 1

if __name__ == "__main__":
    # वेब सर्वर को अलग थ्रेड में चलाना ताकि रेंडर/रैपलिट पर बॉट बंद न हो
    threading.Thread(target=run_web_server, daemon=True).start()
    bot.infinity_polling()
