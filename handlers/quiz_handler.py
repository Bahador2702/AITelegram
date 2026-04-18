import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from services import quiz_service
from utils.keyboards import quiz_menu_keyboard, quiz_options_keyboard, quiz_next_keyboard, back_to_main
from utils.formatters import format_quiz_question, format_quiz_result

logger = logging.getLogger(__name__)


async def show_quiz_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str, edit: bool = True):
    query = update.callback_query
    course = await db.get_course(course_id)
    name = course["name"] if course else "درس"
    text = f"🧠 **کوییز - {name}**\n\nچه نوع کوییزی می‌خوای؟"
    if edit and query:
        await query.edit_message_text(text, reply_markup=quiz_menu_keyboard(course_id), parse_mode="Markdown")
    else:
        await (query.message if query else update.message).reply_text(text, reply_markup=quiz_menu_keyboard(course_id), parse_mode="Markdown")


async def generate_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str, question_type: str = "mcq", topic: str = ""):
    query = update.callback_query
    user = update.effective_user
    course = await db.get_course(course_id)
    if not course:
        await query.answer("درس پیدا نشد!")
        return

    await query.edit_message_text("⏳ در حال ساخت سوالات...")

    questions = await quiz_service.generate_and_save_quiz(
        user_id=user.id,
        course_id=course_id,
        course_name=course["name"],
        num_questions=5,
        question_type=question_type,
        topic=topic,
    )
    if not questions:
        await query.edit_message_text(
            "❌ نتوانستم سوال بسازم. مطمئن شو که فایل آپلود کردی و ایندکس شده.",
            reply_markup=quiz_menu_keyboard(course_id),
        )
        return
    await _start_quiz_session(update, context, user.id, course_id, questions)


async def start_due_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    questions = await db.get_quiz_questions(user.id, course_id, limit=10, due_only=True)
    if not questions:
        await query.edit_message_text(
            "✅ هیچ سوالی برای مرور نداری! بعداً دوباره چک کن.",
            reply_markup=quiz_menu_keyboard(course_id),
        )
        return
    await _start_quiz_session(update, context, user.id, course_id, questions)


async def start_weak_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    weak_topics = await db.get_weak_topics(user.id, course_id, limit=3)
    if not weak_topics:
        await query.edit_message_text(
            "هنوز اطلاعاتی درباره ضعف‌هات نداریم. اول یه کوییز بزن!",
            reply_markup=quiz_menu_keyboard(course_id),
        )
        return
    topic = weak_topics[0]["topic"]
    course = await db.get_course(course_id)
    await query.edit_message_text(f"⏳ در حال ساخت سوالات درباره '{topic}'...")
    questions = await quiz_service.generate_and_save_quiz(
        user_id=user.id,
        course_id=course_id,
        course_name=course["name"] if course else "",
        num_questions=5,
        topic=topic,
    )
    if not questions:
        await query.edit_message_text("❌ خطا در ساخت سوال.", reply_markup=back_to_main())
        return
    await _start_quiz_session(update, context, user.id, course_id, questions)


async def _start_quiz_session(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, course_id: str, questions: list[dict]):
    query = update.callback_query
    session = quiz_service.start_session(user_id, questions)
    context.user_data["active_quiz_course"] = course_id
    await _send_current_question(query.message, session, questions, user_id)


async def _send_current_question(message, session: dict, questions: list[dict], user_id: int):
    current_q = quiz_service.current_question(user_id)
    if not current_q:
        return
    idx = session["current_index"] + 1
    total = session["total"]
    text = format_quiz_question(current_q, idx, total)
    if current_q.get("question_type") == "mcq" and current_q.get("options"):
        markup = quiz_options_keyboard(current_q["options"])
    else:
        markup = quiz_next_keyboard()
    await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, answer: str):
    query = update.callback_query
    user = update.effective_user
    course_id = context.user_data.get("active_quiz_course", "")
    current_q = quiz_service.current_question(user.id)
    if not current_q:
        await query.answer("کوییزی فعال نیست!")
        return

    result = await quiz_service.process_answer(user.id, course_id, current_q, answer)
    session = quiz_service.get_session(user.id)

    if result["correct"]:
        await query.answer("✅ درست!")
        feedback = "✅ **آفرین! پاسخ درسته!**"
    else:
        await query.answer("❌ اشتباه!")
        feedback = f"❌ **اشتباه!**\n\nپاسخ درست: **{result['correct_answer']}**"

    if session and session["current_index"] >= session["total"]:
        final_result = quiz_service.get_session_result(user.id)
        quiz_service.clear_session(user.id)
        text = format_quiz_result(final_result)
        await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
    else:
        await query.edit_message_text(feedback, reply_markup=quiz_next_keyboard(), parse_mode="Markdown")


async def next_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    session = quiz_service.get_session(user.id)
    if not session:
        await query.answer("کوییزی فعال نیست!")
        return
    if session["current_index"] >= session["total"]:
        final_result = quiz_service.get_session_result(user.id)
        quiz_service.clear_session(user.id)
        text = format_quiz_result(final_result)
        await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
        return
    await _send_current_question(query.message, session, session["questions"], user.id)
    await query.delete_message()


async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    result = quiz_service.get_session_result(user.id)
    quiz_service.clear_session(user.id)
    if result:
        text = format_quiz_result(result)
        await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
    else:
        await query.edit_message_text("کوییز پایان یافت.", reply_markup=back_to_main())
