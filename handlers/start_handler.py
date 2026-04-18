import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from utils.keyboards import main_menu, settings_keyboard, back_to_main
from utils.formatters import format_progress

logger = logging.getLogger(__name__)

HELP_TEXT = """🤖 **راهنمای استاد هوشمند**

**چطور شروع کنم؟**
۱. یک درس بساز (دکمه ➕ درس جدید)
۲. فایل‌های PDF، DOCX یا TXT آپلود کن
۳. سوالت رو بپرس!

**قابلیت‌ها:**
📚 **آموزش** - سوال بپرس، مسئله حل کن، مدار تحلیل کن
🧠 **کوییز** - از محتوای کتاب‌هات امتحان بده
🃏 **فلش‌کارت** - با مرور فاصله‌دار یاد بگیر
📝 **خلاصه** - خلاصه امتحانی، ساختاریافته و Mind Map
🎙️ **صوتی** - پیام صوتی بفرست، پاسخ بگیر
📸 **تصویر** - عکس سوال یا مدار بفرست

**دستورات:**
/start - صفحه اصلی
/help - این راهنما
/courses - لیست دروس
/settings - تنظیمات
/reset - ریست مکالمه فعلی

**نکته:** بعد از انتخاب درس فعال، همه سوالاتت با محتوای اون درس پاسخ داده می‌شه."""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.upsert_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        language_code=user.language_code or "fa",
    )
    user_data = await db.get_user(user.id)
    if not user_data or not user_data.get("onboarded"):
        await db.set_onboarded(user.id)
        await update.message.reply_text(
            f"👋 سلام {user.first_name}! خوش اومدی به استاد هوشمند!\n\n"
            "من یه دستیار آموزشی هستم که بهت کمک می‌کنم:\n"
            "✅ سوالات درسیت رو پاسخ بدم\n"
            "✅ مسئله حل کنم\n"
            "✅ کوییز و فلش‌کارت بسازم\n"
            "✅ محتوای کتاب‌هات رو خلاصه کنم\n\n"
            "برای شروع، یه درس بساز! 👇",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )
    else:
        active_course = None
        if user_data.get("active_course_id"):
            active_course = await db.get_course(user_data["active_course_id"])
        course_text = f"\n\n📚 درس فعال: **{active_course['name']}**" if active_course else "\n\n_(هنوز درسی انتخاب نشده)_"
        await update.message.reply_text(
            f"👋 سلام {user.first_name}!{course_text}\n\nچی می‌خوای؟",
            reply_markup=main_menu(),
            parse_mode="Markdown",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, reply_markup=back_to_main(), parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await db.get_user(user.id)
    course_id = user_data.get("active_course_id") if user_data else None
    await db.clear_conversation_history(user.id, course_id)
    await update.message.reply_text("🔄 مکالمه فعلی ریست شد.", reply_markup=main_menu())


async def courses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import course_list_keyboard
    user = update.effective_user
    courses = await db.get_courses(user.id)
    if not courses:
        await update.message.reply_text(
            "هنوز درسی نداری. بزن ➕ تا اولین درست رو بسازی!",
            reply_markup=main_menu(),
        )
        return
    await update.message.reply_text(
        "📚 **دروس من:**\nکدوم درس رو می‌خوای؟",
        reply_markup=course_list_keyboard(courses),
        parse_mode="Markdown",
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prefs = await db.get_preferences(user.id)
    await update.message.reply_text(
        "⚙️ **تنظیمات:**",
        reply_markup=settings_keyboard(prefs),
        parse_mode="Markdown",
    )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = await db.get_user(user.id)
    if not user_data or not user_data.get("active_course_id"):
        await update.message.reply_text("ابتدا یک درس انتخاب کن.", reply_markup=main_menu())
        return
    course_id = user_data["active_course_id"]
    course = await db.get_course(course_id)
    weak_topics = await db.get_weak_topics(user.id, course_id)
    text = format_progress(weak_topics, course["name"] if course else "درس")
    await update.message.reply_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
