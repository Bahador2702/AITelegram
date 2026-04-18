import os
import logging
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from services import supabase_service as db
from services import document_service as doc
from services import vector_store as vs
from services import ai_service
from utils.keyboards import course_actions_keyboard, back_to_main

logger = logging.getLogger(__name__)


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

    filename = document.file_name or "file"
    file_type = doc.get_file_type(filename)

    if not file_type:
        await update.message.reply_text("❌ فرمت پشتیبانی نشده. لطفاً PDF، DOCX یا TXT ارسال کن.")
        return

    if not doc.is_valid_file_size(document.file_size or 0):
        await update.message.reply_text(f"❌ حجم فایل بیش از {doc.MAX_FILE_SIZE_MB} MB است.")
        return

    progress_msg = await update.message.reply_text("📥 در حال دانلود فایل...")

    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file_path = await doc.save_file(bytes(file_bytes), user.id, course_id, unique_name)

        await progress_msg.edit_text("📄 در حال استخراج متن...")

        text_content = doc.extract_text(file_path, file_type)
        if not text_content.strip():
            await progress_msg.edit_text("❌ نتوانستم متنی از این فایل استخراج کنم.")
            doc.delete_file(file_path)
            return

        file_record = await db.add_course_file(
            course_id=course_id,
            user_id=user.id,
            filename=unique_name,
            original_filename=filename,
            file_type=file_type,
            file_size=document.file_size or len(file_bytes),
        )
        file_id = str(file_record["id"])

        await progress_msg.edit_text("🔍 در حال ایندکس‌گذاری و ساخت وکتور استور...")

        chunks_text = vs.chunk_text(text_content)
        store = vs.get_store(course_id)

        batch_size = 50
        all_chunks = []
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
            all_chunks.extend(chunk_metas)

        await progress_msg.edit_text("📝 در حال ساخت خلاصه فایل...")
        sample_text = text_content[:2000]
        summary_prompt = f"این متن را در ۱-۲ جمله فارسی خلاصه کن:\n{sample_text}"
        summary = ""
        try:
            res = await ai_service.chat(
                [{"role": "user", "content": summary_prompt}],
                "یک خلاصه‌نویس حرفه‌ای هستی.",
                max_tokens=150,
            )
            summary = res
        except Exception:
            pass

        await db.update_file_indexed(file_id, len(chunks_text), summary)

        course = await db.get_course(course_id)
        await progress_msg.edit_text(
            f"✅ **فایل با موفقیت آپلود و ایندکس شد!**\n\n"
            f"📄 فایل: {filename}\n"
            f"📊 {len(chunks_text)} chunk استخراج شد\n"
            f"📚 درس: {course['name'] if course else ''}\n\n"
            f"_{summary}_",
            reply_markup=course_actions_keyboard(course_id),
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Document upload error: {e}")
        await progress_msg.edit_text("❌ خطا در آپلود فایل. لطفاً دوباره تلاش کن.")
