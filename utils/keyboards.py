from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📚 دروس من", callback_data="courses_list"),
            InlineKeyboardButton("➕ درس جدید", callback_data="course_new"),
        ],
        [
            InlineKeyboardButton("🧠 کوییز", callback_data="quiz_menu"),
            InlineKeyboardButton("🃏 فلش‌کارت", callback_data="flashcard_menu"),
        ],
        [
            InlineKeyboardButton("📝 خلاصه‌سازی", callback_data="summary_menu"),
            InlineKeyboardButton("📊 پیشرفت من", callback_data="progress_view"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings_menu"),
            InlineKeyboardButton("❓ راهنما", callback_data="help_view"),
        ],
    ])


def course_list_keyboard(courses: list[dict], show_select: bool = True) -> InlineKeyboardMarkup:
    rows = []
    for c in courses:
        emoji = c.get("emoji", "📚")
        name = c["name"]
        file_count = c.get("file_count", 0)
        label = f"{emoji} {name} ({file_count} فایل)"
        rows.append([InlineKeyboardButton(label, callback_data=f"course_select_{c['id']}")])
    if show_select:
        rows.append([InlineKeyboardButton("➕ درس جدید", callback_data="course_new")])
    rows.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


def course_actions_keyboard(course_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📂 فایل‌های درس", callback_data=f"course_files_{course_id}"),
            InlineKeyboardButton("📤 آپلود فایل", callback_data=f"course_upload_{course_id}"),
        ],
        [
            InlineKeyboardButton("🧠 کوییز", callback_data=f"quiz_start_{course_id}"),
            InlineKeyboardButton("🃏 فلش‌کارت", callback_data=f"flashcard_start_{course_id}"),
        ],
        [
            InlineKeyboardButton("📝 خلاصه", callback_data=f"summary_course_{course_id}"),
            InlineKeyboardButton("📊 موضوعات ضعیف", callback_data=f"weak_topics_{course_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ حذف درس", callback_data=f"course_delete_{course_id}"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu"),
        ],
    ])


def file_list_keyboard(files: list[dict], course_id: str) -> InlineKeyboardMarkup:
    rows = []
    for f in files:
        status = "✅" if f.get("indexed") else "⏳"
        name = f.get("original_filename", f.get("filename", "فایل"))[:30]
        rows.append([
            InlineKeyboardButton(f"{status} {name}", callback_data=f"file_info_{f['id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"file_delete_{f['id']}_{course_id}"),
        ])
    rows.append([
        InlineKeyboardButton("📤 آپلود فایل جدید", callback_data=f"course_upload_{course_id}"),
        InlineKeyboardButton("🔙 برگشت", callback_data=f"course_select_{course_id}"),
    ])
    return InlineKeyboardMarkup(rows)


def quiz_menu_keyboard(course_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 چندگزینه‌ای", callback_data=f"quiz_gen_mcq_{course_id}"),
            InlineKeyboardButton("📝 تشریحی", callback_data=f"quiz_gen_open_{course_id}"),
        ],
        [
            InlineKeyboardButton("🔄 مرور بقیه‌مانده", callback_data=f"quiz_due_{course_id}"),
            InlineKeyboardButton("🔥 موضوعات ضعیف", callback_data=f"quiz_weak_{course_id}"),
        ],
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")],
    ])


def quiz_options_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    labels = ["الف", "ب", "ج", "د"]
    rows = []
    for i, opt in enumerate(options[:4]):
        rows.append([InlineKeyboardButton(f"{labels[i]}) {opt[:60]}", callback_data=f"quiz_answer_{labels[i]}")])
    rows.append([InlineKeyboardButton("🏳️ رد کردن", callback_data="quiz_skip")])
    return InlineKeyboardMarkup(rows)


def quiz_next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➡️ سوال بعدی", callback_data="quiz_next"),
            InlineKeyboardButton("⏹️ پایان", callback_data="quiz_end"),
        ],
    ])


def flashcard_menu_keyboard(course_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 مرور کارت‌های بقیه‌مانده", callback_data=f"flashcard_review_{course_id}")],
        [
            InlineKeyboardButton("📄 از PDF", callback_data=f"flashcard_gen_pdf_{course_id}"),
            InlineKeyboardButton("💬 از مکالمه", callback_data=f"flashcard_gen_conv_{course_id}"),
        ],
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")],
    ])


def flashcard_rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😰 نمی‌دونم (1)", callback_data="fc_rate_1"),
            InlineKeyboardButton("🤔 سخت (2)", callback_data="fc_rate_2"),
        ],
        [
            InlineKeyboardButton("🙂 خوب (3)", callback_data="fc_rate_3"),
            InlineKeyboardButton("😊 عالی (4)", callback_data="fc_rate_4"),
        ],
        [InlineKeyboardButton("⏹️ پایان مرور", callback_data="fc_end")],
    ])


def summary_menu_keyboard(course_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 خلاصه کلی", callback_data=f"summary_general_{course_id}"),
            InlineKeyboardButton("📌 امتحانی", callback_data=f"summary_exam_{course_id}"),
        ],
        [
            InlineKeyboardButton("🗂️ ساختاریافته", callback_data=f"summary_structured_{course_id}"),
            InlineKeyboardButton("🧠 Mind Map", callback_data=f"summary_mindmap_{course_id}"),
        ],
        [InlineKeyboardButton("🔙 برگشت", callback_data="main_menu")],
    ])


def settings_keyboard(prefs: dict) -> InlineKeyboardMarkup:
    mode_labels = {"auto": "🤖 خودکار", "qa": "💬 QA", "solver": "🔢 حل مسئله", "circuit": "⚡ مدار", "hint": "💡 راهنما"}
    depth_labels = {"simple": "🟢 ساده", "normal": "🟡 معمولی", "deep": "🔵 عمیق", "exam": "🔴 امتحانی"}
    current_mode = prefs.get("answer_mode", "auto")
    current_depth = prefs.get("explanation_depth", "normal")
    socratic = prefs.get("socratic_mode", False)
    voice = prefs.get("voice_enabled", False)
    hint = prefs.get("hint_mode", False)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"حالت: {mode_labels.get(current_mode, current_mode)}", callback_data="settings_mode_toggle")],
        [InlineKeyboardButton(f"عمق: {depth_labels.get(current_depth, current_depth)}", callback_data="settings_depth_toggle")],
        [
            InlineKeyboardButton(f"{'✅' if socratic else '❌'} سقراطی", callback_data="settings_socratic_toggle"),
            InlineKeyboardButton(f"{'✅' if voice else '❌'} صوتی", callback_data="settings_voice_toggle"),
        ],
        [InlineKeyboardButton(f"{'✅' if hint else '❌'} حالت راهنما", callback_data="settings_hint_toggle")],
        [
            InlineKeyboardButton("🔄 ریست مکالمه", callback_data="session_reset"),
            InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu"),
        ],
    ])


def mode_select_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤖 خودکار", callback_data="mode_set_auto"),
            InlineKeyboardButton("💬 پرسش و پاسخ", callback_data="mode_set_qa"),
        ],
        [
            InlineKeyboardButton("🔢 حل مسئله", callback_data="mode_set_solver"),
            InlineKeyboardButton("⚡ تحلیل مدار", callback_data="mode_set_circuit"),
        ],
        [
            InlineKeyboardButton("💡 راهنمایی", callback_data="mode_set_hint"),
            InlineKeyboardButton("🔍 بررسی پاسخ", callback_data="mode_set_review"),
        ],
        [InlineKeyboardButton("🔙 برگشت", callback_data="settings_menu")],
    ])


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]])


def confirm_keyboard(action: str, label: str = "تایید") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ {label}", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ لغو", callback_data="cancel_action"),
        ],
    ])


def feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 مفید بود", callback_data="feedback_good"),
            InlineKeyboardButton("👎 کافی نبود", callback_data="feedback_bad"),
        ],
        [InlineKeyboardButton("🔄 سوال جدید", callback_data="new_question")],
    ])
