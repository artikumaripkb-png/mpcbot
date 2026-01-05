import telebot
from telebot import types
import time
import threading
import re
import random
import string

# --- अपना टोकन यहाँ डालें ---
API_TOKEN = '8231937886:AAEr8XTJC5q97IaaVKqgcg5WALP7DAvM4MQ'
bot = telebot.TeleBot(API_TOKEN)

# बॉट का यूजरनेम (लिंक बनाने के लिए) - इसे अपने बॉट के यूजरनेम से बदलें
BOT_USERNAME = "YourBotUsername" 

quiz_sessions = {} 
id_map = {} 
stop_signals = {} 

def generate_quiz_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

@bot.message_handler(commands=['start'])
def welcome(message):
    chat_id = message.chat.id
    text_split = message.text.split()
    
    # Deep Link Logic: अगर यूजर /start aB3dE5fG फॉर्मेट में आता है
    if len(text_split) > 1:
        q_id = text_split[1]
        process_quiz_by_id(chat_id, q_id)
        return

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(types.KeyboardButton('➕ Create New Quiz'))
    bot.send_message(chat_id, "👋 **MPC MEGA QUIZ BOT**\n\nQuiz ID सीधे मैसेज में भेजें या नई क्विज़ बनाएँ।", reply_markup=markup, parse_mode='Markdown')

# --- Quiz ID Input Handling (Public ID) ---
@bot.message_handler(func=lambda message: len(message.text) == 8)
def handle_quiz_id(message):
    q_id = message.text
    process_quiz_by_id(message.chat.id, q_id)

def process_quiz_by_id(chat_id, q_id):
    if q_id in id_map:
        owner_id = id_map[q_id]
        if owner_id in quiz_sessions:
            data = quiz_sessions[owner_id]
            bot.send_message(chat_id, f"✅ **Quiz Mil Gayi!**\n📌 **Title:** {data['title']}\n🚀 क्विज़ शुरू हो रही है...")
            stop_signals[chat_id] = False
            threading.Thread(target=run_quiz_loop, args=(chat_id, owner_id)).start()
        else:
            bot.send_message(chat_id, "❌ Error: Quiz का डेटा डिलीट हो चुका है।")
    else:
        bot.send_message(chat_id, "❌ **Galat ID!** कृपया सही 8 अंकों की Quiz ID भेजें।")

@bot.message_handler(func=lambda message: message.text == '➕ Create New Quiz')
def ask_title(message):
    msg = bot.send_message(message.chat.id, "📝 **Quiz का Title (नाम) लिखें:**")
    bot.register_next_step_handler(msg, get_title)

def get_title(message):
    chat_id = message.chat.id
    q_id = generate_quiz_id()
    id_map[q_id] = chat_id # ID को रजिस्टर करना
    
    quiz_sessions[chat_id] = {
        'title': message.text, 
        'questions': [], 
        'q_id': q_id, 
        'timer': 30,
        'creator': message.from_user.first_name,
        'active_polls_global': {} # पोल ट्रैक करने के लिए
    }
    msg = bot.send_message(chat_id, "🔢 **सवाल भेजें (Format: Question और a,b,c,d विकल्प ✅ के साथ):**")
    bot.register_next_step_handler(msg, parse_questions)

def parse_questions(message):
    chat_id = message.chat.id
    blocks = re.split(r'\n\n+', message.text.strip())
    valid_qs = [b.strip() for b in blocks if "a)" in b.lower()]
    
    if not valid_qs:
        msg = bot.send_message(chat_id, "⚠️ Format गलत है। फिर से भेजें।")
        bot.register_next_step_handler(msg, parse_questions)
        return

    quiz_sessions[chat_id]['questions'] = valid_qs
    msg = bot.send_message(chat_id, "⏱️ **Timer सेट करें (Seconds):**")
    bot.register_next_step_handler(msg, set_timer)

def set_timer(message):
    chat_id = message.chat.id
    nums = re.findall(r'\d+', message.text)
    quiz_sessions[chat_id]['timer'] = int(nums[0]) if nums else 30
    show_summary(chat_id)

def show_summary(chat_id):
    data = quiz_sessions[chat_id]
    link = f"https://t.me/{BOT_USERNAME}?start={data['q_id']}"
    summary = (
        f"✅ **Quiz Taiyar Hai!**\n\n"
        f"📌 **Title:** {data['title']}\n"
        f"🆔 **Quiz ID:** `{data['q_id']}`\n"
        f"🔗 **Direct Link:** [Click here to Start]({link})\n\n"
        f"📢 आप ID या Link शेयर कर सकते हैं।"
    )
    bot.send_message(chat_id, summary, parse_mode='Markdown', disable_web_page_preview=True)

def run_quiz_loop(chat_id, owner_id):
    data = quiz_sessions[owner_id]
    user_scores = {} # इस चैट के लिए अलग स्कोर
    
    for i, q_block in enumerate(data['questions'], 1):
        if stop_signals.get(chat_id, False): break
        
        lines = [l.strip() for l in q_block.split('\n') if l.strip()]
        question = lines[0]
        options, correct_id = [], 0
        
        for line in lines[1:]:
            if any(line.lower().startswith(p) for p in ['a)', 'b)', 'c)', 'd)']):
                if "✅" in line: correct_id = len(options)
                options.append(line.replace("✅", "").strip()[2:].strip())
        
        try:
            poll = bot.send_poll(chat_id, f"[{i}/{len(data['questions'])}] {question}", options, 
                                 is_anonymous=False, type='quiz', correct_option_id=correct_id, 
                                 open_period=data['timer'])
            
            # ग्लोबल डिक्शनरी में इस चैट के पोल को रजिस्टर करना
            data['active_polls_global'][poll.poll.id] = {'correct': correct_id, 'scores': user_scores}
            time.sleep(data['timer'] + 1)
        except: continue
    
    send_final_result(chat_id, user_scores, data['title'])

def send_final_result(chat_id, scores, title):
    res = f"🏆 **Final Result: {title}**\n\n"
    if not scores:
        res += "No one participated."
    else:
        sorted_s = sorted(scores.items(), key=lambda x: x[1]['c'], reverse=True)
        for i, (uid, info) in enumerate(sorted_s[:10], 1):
            res += f"{i}. {info['n']} — ✅ {info['c']}\n"
    bot.send_message(chat_id, res, parse_mode='Markdown')

@bot.poll_answer_handler()
def handle_ans(ans):
    # सभी एक्टिव क्विज़ में चेक करना
    for owner_id in quiz_sessions:
        active_polls = quiz_sessions[owner_id].get('active_polls_global', {})
        if ans.poll_id in active_polls:
            poll_data = active_polls[ans.poll_id]
            scores = poll_data['scores']
            uid = ans.user.id
            if uid not in scores:
                scores[uid] = {'n': ans.user.first_name, 'c': 0}
            if ans.option_ids[0] == poll_data['correct']:
                scores[uid]['c'] += 1
            return

bot.infinity_polling()