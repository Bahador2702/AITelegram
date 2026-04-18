import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from services import study_service
from utils.keyboards import flashcard_menu_keyboard, flashcard_rating_keyboard, summary_menu_keyboard, back_to_main
from utils.formatters import format_flashcard_front, format_flashcard_back, format_flashcard_result, truncate

logger = logging.getLogger(__name__)


async def show_flashcard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    course = await db.get_course(course_id)
    name = course["name"] if course else "درس"
    cards = await db.get_due_flashcards(update.effective_user.id, course_id, limit=100)
    due_count = len(cards)
    text = f"🃏 **فلش‌کارت - {name}**\n\n📅 {due_count} کارت برای مرور آماده."
    await query.edit_message_text(text, reply_markup=flashcard_menu_keyboard(course_id), parse_mode="Markdown")


async def start_flashcard_review(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    card = await study_service.start_flashcard_review(user.id, course_id)
    if not card:
        await query.edit_message_text(
            "✅ هیچ کارتی برای مرور نداری! بعداً دوباره بیا.",
            reply_markup=flashcard_menu_keyboard(course_id),
        )
        return
    context.user_data["active_fc_course"] = course_id
    session = study_service.get_flashcard_session(user.id)
    text = format_flashcard_front(card, 1, session["total"])
    await query.edit_message_text(text, reply_markup=flashcard_rating_keyboard(), parse_mode="Markdown")


async def handle_flashcard_rating(update: Update, context: ContextTypes.DEFAULT_TYPE, rating: int):
    query = update.callback_query
    user = update.effective_user
    course_id = context.user_data.get("active_fc_course", "")
    card = study_service.current_flashcard(user.id)
    if not card:
        await query.answer("مرور تموم شد!")
        return

    back_text = format_flashcard_back(card)
    await query.edit_message_text(back_text, parse_mode="Markdown")

    knew_it = await study_service.rate_flashcard(user.id, card, rating)
    session = study_service.get_flashcard_session(user.id)

    next_card = study_service.current_flashcard(user.id)
    if not next_card or not session:
        result = study_service.get_flashcard_result(user.id)
        study_service.clear_flashcard_session(user.id)
        if result:
            text = format_flashcard_result(result)
            await query.message.reply_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
        return

    idx = session["current_index"] + 1
    total = session["total"]
    text = format_flashcard_front(next_card, idx, total)
    await query.message.reply_text(text, reply_markup=flashcard_rating_keyboard(), parse_mode="Markdown")


async def end_flashcard_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    result = study_service.get_flashcard_result(user.id)
    study_service.clear_flashcard_session(user.id)
    if result:
        text = format_flashcard_result(result)
        await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
    else:
        await query.edit_message_text("مرور پایان یافت.", reply_markup=back_to_main())


async def generate_flashcards_from_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    await query.edit_message_text("⏳ در حال ساخت فلش‌کارت...")
    cards = await study_service.generate_and_save_flashcards(user.id, course_id, num_cards=10)
    if not cards:
        await query.edit_message_text(
            "❌ نتوانستم فلش‌کارت بسازم. مطمئن شو که فایل آپلود کردی.",
            reply_markup=flashcard_menu_keyboard(course_id),
        )
        return
    await query.edit_message_text(
        f"✅ **{len(cards)} فلش‌کارت ساخته شد!**\nحالا می‌تونی مرور کنی.",
        reply_markup=flashcard_menu_keyboard(course_id),
        parse_mode="Markdown",
    )


async def generate_flashcards_from_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    user_data = await db.get_user(user.id)
    conv_history = await db.get_recent_conversations(user.id, user_data.get("active_course_id"), limit=20)
    if not conv_history:
        await query.edit_message_text(
            "❌ هنوز مکالمه‌ای نداری. اول یه سوال بپرس بعد فلش‌کارت بساز!",
            reply_markup=flashcard_menu_keyboard(course_id),
        )
        return
    conv_text = "\n".join(f"{h['role']}: {h['content']}" for h in conv_history)
    await query.edit_message_text("⏳ در حال ساخت فلش‌کارت از مکالمه...")
    cards = await study_service.generate_flashcards_from_conversation(user.id, course_id, conv_text)
    if not cards:
        await query.edit_message_text("❌ خطا در ساخت فلش‌کارت.", reply_markup=flashcard_menu_keyboard(course_id))
        return
    await query.edit_message_text(
        f"✅ **{len(cards)} فلش‌کارت از مکالمه ساخته شد!**",
        reply_markup=flashcard_menu_keyboard(course_id),
        parse_mode="Markdown",
    )


async def show_summary_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    course = await db.get_course(course_id)
    name = course["name"] if course else "درس"
    text = f"📝 **خلاصه‌سازی - {name}**\n\nچه نوع خلاصه‌ای می‌خوای؟"
    await query.edit_message_text(text, reply_markup=summary_menu_keyboard(course_id), parse_mode="Markdown")


async def generate_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str, summary_type: str):
    query = update.callback_query
    course = await db.get_course(course_id)
    course_name = course["name"] if course else "درس"
    type_names = {
        "general": "کلی",
        "exam": "امتحانی",
        "structured": "ساختاریافته",
        "mindmap": "Mind Map",
    }
    await query.edit_message_text(f"⏳ در حال ساخت خلاصه {type_names.get(summary_type, '')}...")
    summary = await study_service.generate_summary(course_id, summary_type, course_name)
    if not summary:
        await query.edit_message_text(
            "❌ نتوانستم خلاصه بسازم. مطمئن شو که فایل آپلود کردی.",
            reply_markup=summary_menu_keyboard(course_id),
        )
        return
    header = f"📝 **خلاصه {type_names.get(summary_type, '')} - {course_name}**\n\n"
    full_text = header + truncate(summary, 3800)
    await query.edit_message_text(full_text, reply_markup=summary_menu_keyboard(course_id), parse_mode="Markdown")
