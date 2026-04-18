import logging
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from utils.keyboards import main_menu, settings_keyboard, mode_select_keyboard, back_to_main
from handlers import course_handler, quiz_handler, study_handler

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user

    try:
        if data == "main_menu":
            user_data = await db.get_user(user.id)
            course = None
            if user_data and user_data.get("active_course_id"):
                course = await db.get_course(user_data["active_course_id"])
            course_text = f"\n\n📚 درس فعال: **{course['name']}**" if course else "\n\n_(هنوز درسی انتخاب نشده)_"
            await query.edit_message_text(
                f"🏠 **منوی اصلی**{course_text}",
                reply_markup=main_menu(),
                parse_mode="Markdown",
            )

        elif data == "courses_list":
            await course_handler.show_courses(update, context, edit=True)

        elif data == "course_new":
            await course_handler.prompt_course_name(update, context)

        elif data.startswith("course_select_"):
            course_id = data.replace("course_select_", "")
            await course_handler.select_course(update, context, course_id)

        elif data.startswith("course_files_"):
            course_id = data.replace("course_files_", "")
            await course_handler.show_course_files(update, context, course_id)

        elif data.startswith("course_upload_"):
            course_id = data.replace("course_upload_", "")
            await db.set_active_course(user.id, course_id)
            await query.edit_message_text(
                "📤 **آپلود فایل**\n\nفایل PDF، DOCX یا TXT خودت رو بفرست!\n\n_(حداکثر ۵۰ مگابایت)_",
                reply_markup=back_to_main(),
                parse_mode="Markdown",
            )

        elif data.startswith("course_delete_"):
            course_id = data.replace("course_delete_", "")
            await course_handler.delete_course_confirm(update, context, course_id)

        elif data.startswith("confirm_delete_course_"):
            course_id = data.replace("confirm_delete_course_", "")
            await course_handler.delete_course_execute(update, context, course_id)

        elif data.startswith("file_info_"):
            file_id = data.replace("file_info_", "")
            await _show_file_info(update, context, file_id)

        elif data.startswith("file_delete_"):
            parts = data.replace("file_delete_", "").split("_")
            file_id = parts[0]
            course_id = parts[1] if len(parts) > 1 else ""
            await course_handler.delete_file_execute(update, context, file_id, course_id)

        elif data == "quiz_menu":
            user_data = await db.get_user(user.id)
            course_id = user_data.get("active_course_id") if user_data else None
            if not course_id:
                await query.edit_message_text("ابتدا یک درس انتخاب کن.", reply_markup=back_to_main())
                return
            await quiz_handler.show_quiz_menu(update, context, course_id)

        elif data.startswith("quiz_start_"):
            course_id = data.replace("quiz_start_", "")
            await quiz_handler.show_quiz_menu(update, context, course_id)

        elif data.startswith("quiz_gen_mcq_"):
            course_id = data.replace("quiz_gen_mcq_", "")
            await quiz_handler.generate_quiz(update, context, course_id, "mcq")

        elif data.startswith("quiz_gen_open_"):
            course_id = data.replace("quiz_gen_open_", "")
            await quiz_handler.generate_quiz(update, context, course_id, "open")

        elif data.startswith("quiz_due_"):
            course_id = data.replace("quiz_due_", "")
            await quiz_handler.start_due_quiz(update, context, course_id)

        elif data.startswith("quiz_weak_"):
            course_id = data.replace("quiz_weak_", "")
            await quiz_handler.start_weak_quiz(update, context, course_id)

        elif data.startswith("quiz_answer_"):
            answer = data.replace("quiz_answer_", "")
            await quiz_handler.handle_quiz_answer(update, context, answer)

        elif data == "quiz_next":
            await quiz_handler.next_quiz_question(update, context)

        elif data == "quiz_end":
            await quiz_handler.end_quiz(update, context)

        elif data == "quiz_skip":
            session = __import__("services.quiz_service", fromlist=["quiz_service"]).get_session(user.id)
            if session:
                session["current_index"] += 1
            await quiz_handler.next_quiz_question(update, context)

        elif data == "flashcard_menu":
            user_data = await db.get_user(user.id)
            course_id = user_data.get("active_course_id") if user_data else None
            if not course_id:
                await query.edit_message_text("ابتدا یک درس انتخاب کن.", reply_markup=back_to_main())
                return
            await study_handler.show_flashcard_menu(update, context, course_id)

        elif data.startswith("flashcard_start_"):
            course_id = data.replace("flashcard_start_", "")
            await study_handler.show_flashcard_menu(update, context, course_id)

        elif data.startswith("flashcard_review_"):
            course_id = data.replace("flashcard_review_", "")
            await study_handler.start_flashcard_review(update, context, course_id)

        elif data.startswith("flashcard_gen_pdf_"):
            course_id = data.replace("flashcard_gen_pdf_", "")
            await study_handler.generate_flashcards_from_pdf(update, context, course_id)

        elif data.startswith("flashcard_gen_conv_"):
            course_id = data.replace("flashcard_gen_conv_", "")
            await study_handler.generate_flashcards_from_conversation(update, context, course_id)

        elif data.startswith("fc_rate_"):
            rating = int(data.replace("fc_rate_", ""))
            await study_handler.handle_flashcard_rating(update, context, rating)

        elif data == "fc_end":
            await study_handler.end_flashcard_review(update, context)

        elif data == "summary_menu":
            user_data = await db.get_user(user.id)
            course_id = user_data.get("active_course_id") if user_data else None
            if not course_id:
                await query.edit_message_text("ابتدا یک درس انتخاب کن.", reply_markup=back_to_main())
                return
            await study_handler.show_summary_menu(update, context, course_id)

        elif data.startswith("summary_course_"):
            course_id = data.replace("summary_course_", "")
            await study_handler.show_summary_menu(update, context, course_id)

        elif data.startswith("summary_general_"):
            course_id = data.replace("summary_general_", "")
            await study_handler.generate_summary(update, context, course_id, "general")

        elif data.startswith("summary_exam_"):
            course_id = data.replace("summary_exam_", "")
            await study_handler.generate_summary(update, context, course_id, "exam")

        elif data.startswith("summary_structured_"):
            course_id = data.replace("summary_structured_", "")
            await study_handler.generate_summary(update, context, course_id, "structured")

        elif data.startswith("summary_mindmap_"):
            course_id = data.replace("summary_mindmap_", "")
            await study_handler.generate_summary(update, context, course_id, "mindmap")

        elif data == "settings_menu":
            prefs = await db.get_preferences(user.id)
            await query.edit_message_text("⚙️ **تنظیمات:**", reply_markup=settings_keyboard(prefs), parse_mode="Markdown")

        elif data == "settings_mode_toggle":
            await query.edit_message_text("🎯 **حالت پاسخ را انتخاب کن:**", reply_markup=mode_select_keyboard(), parse_mode="Markdown")

        elif data.startswith("mode_set_"):
            mode = data.replace("mode_set_", "")
            await db.update_preferences(user.id, {"answer_mode": mode})
            prefs = await db.get_preferences(user.id)
            mode_names = {"auto": "خودکار", "qa": "QA", "solver": "حل مسئله", "circuit": "مدار", "hint": "راهنما", "review": "بررسی پاسخ"}
            await query.edit_message_text(
                f"✅ حالت به **{mode_names.get(mode, mode)}** تغییر کرد.",
                reply_markup=settings_keyboard(prefs),
                parse_mode="Markdown",
            )

        elif data == "settings_depth_toggle":
            prefs = await db.get_preferences(user.id)
            depths = ["simple", "normal", "deep", "exam"]
            current = prefs.get("explanation_depth", "normal")
            next_depth = depths[(depths.index(current) + 1) % len(depths)] if current in depths else "normal"
            await db.update_preferences(user.id, {"explanation_depth": next_depth})
            prefs = await db.get_preferences(user.id)
            await query.edit_message_text("⚙️ **تنظیمات:**", reply_markup=settings_keyboard(prefs), parse_mode="Markdown")

        elif data == "settings_socratic_toggle":
            prefs = await db.get_preferences(user.id)
            await db.update_preferences(user.id, {"socratic_mode": not prefs.get("socratic_mode", False)})
            prefs = await db.get_preferences(user.id)
            await query.edit_message_text("⚙️ **تنظیمات:**", reply_markup=settings_keyboard(prefs), parse_mode="Markdown")

        elif data == "settings_voice_toggle":
            prefs = await db.get_preferences(user.id)
            await db.update_preferences(user.id, {"voice_enabled": not prefs.get("voice_enabled", False)})
            prefs = await db.get_preferences(user.id)
            await query.edit_message_text("⚙️ **تنظیمات:**", reply_markup=settings_keyboard(prefs), parse_mode="Markdown")

        elif data == "settings_hint_toggle":
            prefs = await db.get_preferences(user.id)
            await db.update_preferences(user.id, {"hint_mode": not prefs.get("hint_mode", False)})
            prefs = await db.get_preferences(user.id)
            await query.edit_message_text("⚙️ **تنظیمات:**", reply_markup=settings_keyboard(prefs), parse_mode="Markdown")

        elif data == "session_reset":
            user_data = await db.get_user(user.id)
            course_id = user_data.get("active_course_id") if user_data else None
            await db.clear_conversation_history(user.id, course_id)
            await query.edit_message_text("🔄 مکالمه فعلی ریست شد.", reply_markup=main_menu())

        elif data.startswith("weak_topics_"):
            course_id = data.replace("weak_topics_", "")
            await _show_weak_topics(update, context, course_id)

        elif data == "progress_view":
            user_data = await db.get_user(user.id)
            course_id = user_data.get("active_course_id") if user_data else None
            if not course_id:
                await query.edit_message_text("ابتدا یک درس انتخاب کن.", reply_markup=back_to_main())
                return
            course = await db.get_course(course_id)
            weak_topics = await db.get_weak_topics(user.id, course_id)
            from utils.formatters import format_progress
            text = format_progress(weak_topics, course["name"] if course else "درس")
            await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")

        elif data == "help_view":
            from handlers.start_handler import HELP_TEXT
            await query.edit_message_text(HELP_TEXT, reply_markup=back_to_main(), parse_mode="Markdown")

        elif data in ("feedback_good", "feedback_bad"):
            if data == "feedback_good":
                await query.answer("ممنون! خوشحالم که مفید بود 😊")
            else:
                await query.answer("ممنون از بازخوردت. سعی می‌کنم بهتر بشم!")

        elif data == "new_question":
            await query.edit_message_text("بفرما! سوالت رو بپرس 🎓", reply_markup=None)

        elif data == "cancel_action":
            await query.edit_message_text("❌ عملیات لغو شد.", reply_markup=main_menu())

    except Exception as e:
        logger.error(f"Callback error for {data}: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ خطایی رخ داد. لطفاً دوباره تلاش کن.", reply_markup=main_menu())
        except Exception:
            pass


async def _show_file_info(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str):
    import aiosqlite
    from config import DB_PATH
    query = update.callback_query
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM course_files WHERE id = ?", (file_id,)) as cur:
            row = await cur.fetchone()
    f = dict(row) if row else None
    if not f:
        await query.answer("فایل پیدا نشد!")
        return
    status = "✅ ایندکس شده" if f.get("indexed") else "⏳ در حال ایندکس"
    size_kb = f.get("file_size_bytes", 0) // 1024
    text = f"""📄 **{f.get('original_filename', 'فایل')}**

📊 وضعیت: {status}
📦 حجم: {size_kb} KB
🗃️ Chunk ها: {f.get('chunk_count', 0)}
📅 آپلود: {str(f.get('uploaded_at', ''))[:10]}

"""
    if f.get("summary"):
        text += f"📝 **خلاصه:**\n_{f['summary']}_"
    await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")


async def _show_weak_topics(update: Update, context: ContextTypes.DEFAULT_TYPE, course_id: str):
    query = update.callback_query
    user = update.effective_user
    course = await db.get_course(course_id)
    weak_topics = await db.get_weak_topics(user.id, course_id, limit=10)
    from utils.formatters import format_progress
    text = format_progress(weak_topics, course["name"] if course else "درس")
    await query.edit_message_text(text, reply_markup=back_to_main(), parse_mode="Markdown")
