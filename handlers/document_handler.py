import logging
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TimedOut, NetworkError
from services import supabase_service as db
from services import document_service as doc
from services import vector_store as vs
from services import ai_service
from utils.keyboards import course_actions_keyboard, back_to_main

logger = logging.getLogger(__name__)


async def safe_edit(msg, text, **kwargs):
    try:
        await msg.edit_text(text, **kwargs)
    except (TimedOut, NetworkError) as e:
        logger.warning(f"[edit_text] network error, retrying: {e}")
        try:
            await msg.edit_text(text, **kwargs)
        except Exception:
            logger.error(f"[edit_text] failed after retry")
    except Exception as e:
        logger.warning(f"[edit_text] skipped: {e}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document
    if not document:
        return

    user_data = await db.get_user(user.id)
    course_id = user_data.get("active_course_id") if user_data else None

    if not course_id:
        await update.message.reply_text(
            "⚠️ ابتدا یک درس انتخاب یا بساز، بعد فایل آپلود کن.",
            reply_markup=back_to_main(),
        )
        return

    course = await db.get_course(course_id)
    if not course:
        await update.message.reply_text("⚠️ درس فعال یافت نشد. لطفاً دوباره درس را انتخاب کن.")
        return

    course_name = course.get("name", "")
    filename = document.file_name or "file"
    file_type = doc.get_file_type(filename)

    if not file_type:
        await update.message.reply_text("❌ فرمت پشتیبانی نشده. لطفاً PDF، DOCX یا TXT ارسال کن.")
        return

    file_size = document.file_size or 0
    if not doc.is_valid_file_size(file_size):
        await update.message.reply_text(f"❌ حجم فایل بیش از {doc.MAX_FILE_SIZE_MB} MB است.")
        return

    progress_msg = await update.message.reply_text("📥 در حال دانلود فایل...", read_timeout=30, write_timeout=30)

    file_path = None
    try:
        logger.info(f"[upload] user={user.id} course='{course_name}' file='{filename}' size={file_size}")

        tg_file = await context.bot.get_file(document.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        unique_name = f"{uuid.uuid4().hex}_{filename}"

        await safe_edit(progress_msg, "💾 در حال ذخیره فایل...")
        file_path = await doc.save_file(
            bytes(file_bytes),
            user.id,
            course_id,
            unique_name,
            course_name=course_name,
        )
        logger.info(f"[upload] saved → {file_path}")

        await safe_edit(progress_msg, "📄 در حال استخراج متن...")
        text_content = doc.extract_text(file_path, file_type)
        if not text_content.strip():
            await safe_edit(progress_msg, "❌ نتوانستم متنی از این فایل استخراج کنم.")
            doc.delete_file(file_path)
            return

        file_record = await db.add_course_file(
            course_id=course_id,
            user_id=user.id,
            filename=unique_name,
            original_filename=filename,
            file_type=file_type,
            file_size=file_size or len(file_bytes),
        )
        file_id = str(file_record["id"])
        logger.info(f"[upload] db record created file_id={file_id}")

        await safe_edit(progress_msg, "🔍 در حال ایندکس‌گذاری و ساخت وکتور استور...")

        chunks_text = vs.chunk_text(text_content)
        if not chunks_text:
            await safe_edit(progress_msg, "❌ متن فایل خیلی کوتاه است یا قابل تقسیم نیست.")
            doc.delete_file(file_path)
            return

        logger.info(f"[upload] indexing {len(chunks_text)} chunks for file_id={file_id}")
        store = vs.get_store(course_id)

        batch_size = 50
        for i in range(0, len(chunks_text), batch_size):
            batch = chunks_text[i:i + batch_size]
            embeddings = await ai_service.get_embeddings(batch)
            chunk_metas = [
                {
                    "text": chunk,
                    "file_id": file_id,
                    "filename": filename,
                    "chunk_index": i + j,
                }
                for j, chunk in enumerate(batch)
            ]
            store.add_chunks(chunk_metas, embeddings)

        await safe_edit(progress_msg, "📝 در حال ساخت خلاصه فایل...")
        summary = ""
        try:
            sample_text = text_content[:2000]
            summary_prompt = f"این متن را در ۱-۲ جمله فارسی خلاصه کن:\n{sample_text}"
            summary = await ai_service.chat(
                [{"role": "user", "content": summary_prompt}],
                "یک خلاصه‌نویس حرفه‌ای هستی.",
                max_tokens=150,
            )
        except Exception as e:
            logger.warning(f"[upload] summary failed: {e}")

        await db.update_file_indexed(file_id, len(chunks_text), summary)
        logger.info(f"[upload] complete file_id={file_id} chunks={len(chunks_text)}")

        await safe_edit(
            progress_msg,
            f"✅ **فایل با موفقیت آپلود و ایندکس شد!**\n\n"
            f"📄 فایل: {filename}\n"
            f"📊 {len(chunks_text)} chunk استخراج شد\n"
            f"📚 درس: {course_name}\n\n"
            f"_{summary}_",
            reply_markup=course_actions_keyboard(course_id),
            parse_mode="Markdown",
        )

    except RuntimeError as e:
        logger.error(f"[upload] RuntimeError user={user.id}: {e}")
        await safe_edit(progress_msg, f"❌ {e}")
    except Exception as e:
        logger.exception(f"[upload] Unexpected error user={user.id} file='{filename}': {e}")
        await safe_edit(
            progress_msg,
            f"❌ خطا در آپلود فایل.\n\n`{type(e).__name__}: {str(e)[:200]}`",
            parse_mode="Markdown",
        )
        if file_path:
            doc.delete_file(file_path)
