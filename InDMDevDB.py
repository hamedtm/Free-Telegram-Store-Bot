import sqlite3
import telebot
from telebot import types
import threading
import logging

# 1. إعدادات البوت والتوكن الخاص بك
API_TOKEN = '8719306254:AAF3qc4MFK4cIxA-gr5F2BNGrSGIPx_EniM'
bot = telebot.TeleBot(API_TOKEN)

# 2. إعداد قاعدة البيانات
DB_FILE = 'InDMDevDBShop.db'
db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = db_connection.cursor()
db_lock = threading.Lock()

# 3. إنشاء الجداول (مع إضافة التقييم والموقع)
def create_all_tables():
    with db_lock:
        # جدول المستخدمين
        cursor.execute("CREATE TABLE IF NOT EXISTS ShopUserTable(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, wallet INTEGER DEFAULT 0)")
        
        # جدول الطلبات (مضاف إليه الموقع الجغرافي)
        cursor.execute("""CREATE TABLE IF NOT EXISTS ShopOrderTable(
            id INTEGER PRIMARY KEY, 
            buyerid INTEGER, 
            productname TEXT, 
            ordernumber INTEGER UNIQUE,
            latitude TEXT, 
            longitude TEXT,
            status TEXT DEFAULT 'PENDING'
        )""")
        
        # جدول التقييم الموثوق (الذي طلبته)
        cursor.execute("""CREATE TABLE IF NOT EXISTS ShopReviewTable(
            id INTEGER PRIMARY KEY,
            order_number INTEGER,
            buyer_id INTEGER,
            rating INTEGER,
            comment TEXT,
            FOREIGN KEY (order_number) REFERENCES ShopOrderTable(ordernumber)
        )""")
        db_connection.commit()

create_all_tables()

# --- 4. أوامر البوت المخصصة للخدمات ---

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🛠 طلب خدمة جديد")
    btn2 = types.KeyboardButton("📦 متجر المنتجات")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "مرحباً بك! اختر طلب خدمة لتحديد موقعك وتقييم الحرفي لاحقاً.", reply_markup=markup)

# طلب الموقع الجغرافي عند طلب خدمة
@bot.message_handler(func=lambda m: m.text == "🛠 طلب خدمة جديد")
def request_service(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    loc_btn = types.KeyboardButton("📍 إرسال موقعي الحالي", request_location=True)
    markup.add(loc_btn)
    bot.send_message(message.chat.id, "من فضلك أرسل موقعك ليتمكن الحرفي من الوصول إليك:", reply_markup=markup)

# استقبال الموقع وحفظه في القاعدة
@bot.message_handler(content_types=['location'])
def handle_location(message):
    lat = message.location.latitude
    lon = message.location.longitude
    order_num = message.message_id  # استخدام ID الرسالة كرقم طلب مؤقت
    
    with db_lock:
        cursor.execute("INSERT INTO ShopOrderTable (buyerid, ordernumber, latitude, longitude) VALUES (?, ?, ?, ?)",
                       (message.chat.id, order_num, str(lat), str(lon)))
        db_connection.commit()
    
    # رسالة تأكيد للمشتري مع زر للتقييم لاحقاً
    markup = types.InlineKeyboardMarkup()
    review_btn = types.InlineKeyboardButton("⭐ تقييم الخدمة لاحقاً", callback_data=f"rev_{order_num}")
    markup.add(review_btn)
    
    bot.send_message(message.chat.id, f"✅ تم استلام طلبك وموقعك بنجاح!\nرقم الطلب: {order_num}", reply_markup=markup)

# نظام التقييم (النجوم)
@bot.callback_query_handler(func=lambda call: call.data.startswith('rev_'))
def ask_rating(call):
    order_id = call.data.split('_')[1]
    markup = types.InlineKeyboardMarkup()
    stars = [types.InlineKeyboardButton(f"{i} ⭐", callback_data=f"rate_{order_id}_{i}") for i in range(1, 6)]
    markup.add(*stars)
    bot.edit_message_text("شكراً لثقتك! من فضلك قيم جودة الخدمة:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_'))
def save_rating(call):
    data = call.data.split('_')
    order_id, rating = data[1], data[2]
    
    with db_lock:
        cursor.execute("INSERT INTO ShopReviewTable (order_number, buyer_id, rating) VALUES (?, ?, ?)",
                       (order_id, call.from_user.id, rating))
        db_connection.commit()
    
    bot.answer_callback_query(call.id, "شكراً لك! تم حفظ تقييمك بنجاح.")
    bot.edit_message_text(f"✅ تم تقييم الطلب بـ {rating} نجوم. شكراً لمساعدتنا في تحسين الجودة!", call.message.chat.id, call.message.message_id)

# تشغيل البوت
print("Bot is running...")
bot.polling()
