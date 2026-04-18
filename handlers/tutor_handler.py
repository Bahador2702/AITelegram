import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from services import ai_service
from services import vector_store as vs
from utils.keyboards import feedback_keyboard, main_menu
from utils.formatters import format_memory_context, truncate

logger = logging.getLogger(__name__)

_awaiting_state: dict[int, str] = {}


def set_user_state(user_id: int, state: str):
    _awaiting_state[user_id] = state


def get_user_state(user_id: int) -> str | None:
    return _awaiting_state.get(user_id)


def clear_user_state(user_id: int):
    _awaiting_state.pop(user_id, None)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    if not text:
        return

    user_data = await db.get_user(user.id)
    if not user_data:
        await db.upsert_user(user.id, user.username or "", user.first_name or "", user.last_name or "")
        user_data = await db.get_user(user.id)

    prefs = await db.get_preferences(user.id)
    course_id = user_data.get("active_course_id") if user_data else None
    course = await db.get_course(course_id) if course_id else None

    state = get_user_state(user.id)
    if state and state.startswith("awaiting_"):
        await _handle_state_input(update, context, state, text, user.id)
        return

    loading_msg = await update.message.reply_text("⏳ در حال پردازش...")

    try:
        mode = prefs.get("answer_mode", "auto")
        depth = prefs.get("explanation_depth", "normal")
        socratic = prefs.get("socratic_mode", False)

        if prefs.get("hint_mode"):
            mode = "hint"

        if mode == "auto":
            mode = await ai_service.detect_mode(text)

        context_text = ""
        if course_id:
            store = vs.get_store(course_id)
            if store.get_chunk_count() > 0:
                embeddings = await ai_service.get_embeddings([text])
                if embeddings:
                    results = store.search(embeddings[0], k=5)
                    if results:
                        context_text = "\n\n".join(r.get("text", "") for r in results[:5])

        memories = await db.get_user_memories(user.id, course_id, limit=5)
        memory_context = format_memory_context(memories)
        if memory_context:
            context_text = memory_context + "\n\n" + context_text

        history = await db.get_recent_conversations(user.id, course_id, limit=10)
        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": text})

        course_name = course["name"] if course else ""
        system = ai_service.build_system_prompt(mode, depth, socratic, context_text)
        if course_name:
            system = f"درس فعال: {course_name}\n\n" + system

        response = await ai_service.chat(messages, system)

        await db.save_conversation(user.id, course_id, "user", text)
        await db.save_conversation(user.id, course_id, "assistant", response)

        await loading_msg.delete()
        await update.message.reply_text(
            truncate(response),
            reply_markup=feedback_keyboard(),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error in text handler: {e}")
        await loading_msg.edit_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کن.")


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    caption = update.message.caption or ""

    user_data = await db.get_user(user.id)
    prefs = await db.get_preferences(user.id)
    course_id = user_data.get("active_course_id") if user_data else None
    course = await db.get_course(course_id) if course_id else None

    loading_msg = await update.message.reply_text("🖼️ در حال تحلیل تصویر...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        mode = prefs.get("answer_mode", "auto")
        depth = prefs.get("explanation_depth", "normal")
        socratic = prefs.get("socratic_mode", False)

        image_system = f"""تو یک استاد هوشمند هستی که تصاویر آموزشی تحلیل می‌کنی.
اگر تصویر یک مسئله ریاضی یا فیزیک است: مرحله به مرحله حل کن.
اگر تصویر یک مدار الکتریکی است: مدار را تحلیل کن، المان‌ها را شناسایی کن و قوانین مربوطه را اعمال کن.
اگر تصویر یک سوال درسی است: پاسخ کامل و آموزشی بده.
{ai_service.DEPTH_PROMPTS.get(depth, '')}
{'یک سوال متقابل از دانشجو بپرس.' if socratic else ''}
{"درس فعال: " + course["name"] if course else ""}
پاسخ به فارسی باشد."""

        prompt = caption if caption else "این تصویر را تحلیل و پاسخ بده"
        response = await ai_service.chat_with_image(prompt, bytes(image_bytes), image_system)

        await db.save_conversation(user.id, course_id, "user", f"[تصویر] {caption}")
        await db.save_conversation(user.id, course_id, "assistant", response)

        await loading_msg.delete()
        await update.message.reply_text(truncate(response), reply_markup=feedback_keyboard(), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await loading_msg.edit_text("❌ خطا در پردازش تصویر.")


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prefs = await db.get_preferences(user.id)

    loading_msg = await update.message.reply_text("🎙️ در حال تبدیل صوت به متن...")
    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        transcript = await ai_service.transcribe_voice(bytes(audio_bytes))
        if not transcript.strip():
            await loading_msg.edit_text("❌ نتوانستم صدا را تشخیص بدم. لطفاً دوباره ضبط کن.")
            return

        await loading_msg.edit_text(f"🎙️ متن پیام: _{transcript}_\n\n⏳ در حال پردازش...", parse_mode="Markdown")
        fake_update = update
        context.user_data["voice_transcript"] = transcript

        user_data = await db.get_user(user.id)
        mode = prefs.get("answer_mode", "auto")
        depth = prefs.get("explanation_depth", "normal")
        socratic = prefs.get("socratic_mode", False)
        course_id = user_data.get("active_course_id") if user_data else None
        course = await db.get_course(course_id) if course_id else None

        if mode == "auto":
            mode = await ai_service.detect_mode(transcript)

        context_text = ""
        if course_id:
            store = vs.get_store(course_id)
            if store.get_chunk_count() > 0:
                embeddings = await ai_service.get_embeddings([transcript])
                if embeddings:
                    results = store.search(embeddings[0], k=5)
                    context_text = "\n\n".join(r.get("text", "") for r in results[:5])

        history = await db.get_recent_conversations(user.id, course_id, limit=8)
        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": transcript})

        system = ai_service.build_system_prompt(mode, depth, socratic, context_text)
        if course:
            system = f"درس فعال: {course['name']}\n\n" + system

        response = await ai_service.chat(messages, system)
        await db.save_conversation(user.id, course_id, "user", f"[صوتی] {transcript}")
        await db.save_conversation(user.id, course_id, "assistant", response)

        await loading_msg.delete()
        await update.message.reply_text(truncate(response), reply_markup=feedback_keyboard(), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Voice handler error: {e}")
        await loading_msg.edit_text("❌ خطا در پردازش پیام صوتی.")


async def _handle_state_input(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str, text: str, user_id: int):
    clear_user_state(user_id)
    if state == "awaiting_course_name":
        from handlers.course_handler import create_course_with_name
        await create_course_with_name(update, context, text)
    elif state == "awaiting_course_name_for_new":
        from handlers.course_handler import create_course_with_name
        await create_course_with_name(update, context, text)
