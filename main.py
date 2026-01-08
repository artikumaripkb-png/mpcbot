import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# --- अपनी डिटेल्स यहाँ भरें ---
# 1. BotFather से प्राप्त टोकन यहाँ डालें
TELEGRAM_TOKEN = '8231937886:AAHSvwlJ6wQGnFOVxbEB0ij_8wcf2B0T0rI'
# अपनी नई API Key यहाँ पेस्ट करें जो ...Rs8k पर खत्म होती है
GEMINI_API_KEY = 'AIzaSyBn5j15Fb63z0AMWWLQ1g1AGzR6itFoiIs'

# Gemini सेटअप
genai.configure(api_key=GEMINI_API_KEY)

# यही वो मॉडल है जो आपकी की (Key) के साथ एक्सेस होगा
model = genai.GenerativeModel('gemini-2.5-flash')

# फीचर 1: टेक्स्ट मैसेज का जवाब (Gemini 1.5 Flash द्वारा)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text: return
    user_text = update.message.text
    
    # टाइपिंग स्टेटस दिखाएँ
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # मॉडल से कंटेंट जनरेट करना
        response = model.generate_content(user_text)
        if response.text:
            await update.message.reply_text(response.text)
        else:
            await update.message.reply_text("माफ़ कीजिये, मॉडल ने कोई जवाब नहीं दिया।")
    except Exception as e:
        # अगर कोई एरर आता है तो उसे प्रिंट करें
        print(f"Error Details: {e}")
        await update.message.reply_text("सर्वर अभी रिस्पॉन्स नहीं दे रहा है। कृपया अपनी API Key चेक करें।")

# फीचर 2: इमेज जनरेशन (/image prompt)
async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("कृपया बताएं कैसी फोटो चाहिए? जैसे: /image a flying car")
        return
    
    prompt = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    
    # इमेज के लिए फ्री सर्विस का उपयोग
    image_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024"
    
    try:
        await update.message.reply_photo(photo=image_url, caption=f"आपकी इमेज: {prompt}")
    except:
        await update.message.reply_text("फोटो लोड करने में दिक्कत हुई।")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # हैंडलर्स जोड़ना
    application.add_handler(CommandHandler("image", generate_image))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("बोट सफलतापुर्वक चालू हो गया है!")
    application.run_polling()
