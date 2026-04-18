import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from services import vector_store as vs
from utils.keyboards import course_list_keyboard, course_actions_keyboard, file_list_keyboard, back_to_main, confirm_keyboard
from utils.formatters import format_course_info
from handlers.tutor_handler import set_user_state, clear_user_state

logger = logging.getLogger(__name__)


async def show_courses(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    user = update.effective_user
    query = update.callback_query
    courses = await db.get_courses(user.id)
    text = "📚 **دروس من:**\nیک درس انتخاب کن یا درس جدید بساز." if courses else "هنوز درسی نداری!\nاولین درست رو بساز 👇"
    markup = course_list_keyboard(courses)
    if edit and query:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        msg = query.message if query else update.message
        await msg.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def prompt_course_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    set_user_state(user.id, "awaiting_course_name")
    await query.edit_message_text(
        "📚 **درس جدید**\n\nاسم درس رو بنویس:\n_(مثال: مدارهای الکتریکی ۱)_",
        parse_mode="Markdown",
    )


async def create_course_with_name(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
    user = update.effective_user
    if len(name.strip()) < 2:
        await update.message.reply_text("اسم درس باید حداقل ۲ کاراکتر باشه.")
        return
    emojis = ["📚", "⚡", "🔧", "📐", "🧮", "💡", "🔬", "📡", "🖥️", "🎓"]
    courses = await db.get_courses(user.id)
    emoji = emojis[len(courses) % len(emojis)]
    course = await db.create_course(user.id, name.strip(), emoji=emoji)
    await db.set_active_course(user.id, str(course["id"]))
    await update.message.reply_text(
        f"✅ **درس '{name}' ساخته شد!**\n\nاین درس الان فعاله. حالا می‌تونی فایل آپلود کنی یا مستقیم سوال بپرسی.",
        reply_markup=course_actions_keyboard(str(course["id"])),
        parse_mode="Markdown",
    )


async def select_course(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    course = await db.get_course(course_id)
    if not course:
        await query.answer("درس پیدا نشد!")
        return
    await db.set_active_course(user.id, course_id)
    files = await db.get_course_files(course_id)
    store = vs.get_store(course_id)
    chunk_count = store.get_chunk_count()
    text = format_course_info(course, files)
    text += f"\n\n📊 {chunk_count} chunk در وکتور استور"
    await query.edit_message_text(
        text,
        reply_markup=course_actions_keyboard(course_id),
        parse_mode="Markdown",
    )


async def show_course_files(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    files = await db.get_course_files(course_id)
    course = await db.get_course(course_id)
    if not files:
        await query.edit_message_text(
            f"📂 **فایل‌های {course['name'] if course else 'درس'}:**\n\nهنوز فایلی آپلود نشده.",
            reply_markup=file_list_keyboard([], course_id),
            parse_mode="Markdown",
        )
        return
    text = f"📂 **فایل‌های {course['name'] if course else 'درس'}:**\n\n"
    for f in files:
        status = "✅" if f.get("indexed") else "⏳ (در حال ایندکس)"
        name = f.get("original_filename", f.get("filename", ""))
        chunks = f.get("chunk_count", 0)
        size_kb = f.get("file_size_bytes", 0) // 1024
        text += f"{status} **{name}**\n   📊 {chunks} chunk | 📦 {size_kb} KB\n"
        if f.get("summary"):
            text += f"   _{f['summary'][:80]}..._\n"
        text += "\n"
    await query.edit_message_text(text, reply_markup=file_list_keyboard(files, course_id), parse_mode="Markdown")


async def delete_course_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    course = await db.get_course(course_id)
    name = course["name"] if course else "این درس"
    await query.edit_message_text(
        f"⚠️ آیا مطمئنی که می‌خوای درس **{name}** رو حذف کنی؟\nهمه فایل‌ها و کوییزها حذف می‌شن!",
        reply_markup=confirm_keyboard(f"delete_course_{course_id}", "بله، حذف کن"),
        parse_mode="Markdown",
    )


async def delete_course_execute(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    user_data = await db.get_user(user.id)
    if user_data and user_data.get("active_course_id") == course_id:
        await db.set_active_course(user.id, None)
    store = vs.get_store(course_id)
    store.delete_store()
    vs.invalidate_store(course_id)
    await db.delete_course(course_id, user.id)
    await query.edit_message_text("🗑️ درس حذف شد.", reply_markup=back_to_main())


async def delete_file_execute(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, course_id: str):
    query = update.callback_query
    user = update.effective_user
    file_data = await db.delete_course_file(file_id, user.id)
    if file_data:
        store = vs.get_store(course_id)
        store.remove_file_chunks(file_id)
    await query.answer("فایل حذف شد.")
    await show_course_files(update, context, course_id)
