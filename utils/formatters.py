def escape_markdown(text: str) -> str:
    special = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{c}" if c in special else c for c in text)


def format_course_info(course: dict, files: list[dict] | None = None) -> str:
    emoji = course.get("emoji", "📚")
    name = course.get("name", "")
    desc = course.get("description", "")
    file_count = course.get("file_count", 0)
    lines = [f"{emoji} **{name}**"]
    if desc:
        lines.append(f"_{desc}_")
    lines.append(f"📁 {file_count} فایل آپلود شده")
    if files:
        lines.append("\n**فایل‌ها:**")
        for f in files:
            status = "✅" if f.get("indexed") else "⏳"
            name_f = f.get("original_filename", f.get("filename", "فایل"))
            chunks = f.get("chunk_count", 0)
            lines.append(f"  {status} {name_f} ({chunks} chunk)")
    return "\n".join(lines)


def format_quiz_question(question: dict, index: int, total: int) -> str:
    q_type = question.get("question_type", "mcq")
    topic = question.get("topic", "")
    difficulty = question.get("difficulty", 3)
    stars = "⭐" * difficulty
    lines = [f"**سوال {index}/{total}** {stars}"]
    if topic:
        lines.append(f"📌 موضوع: {topic}")
    lines.append("")
    lines.append(question["question"])
    if q_type == "mcq" and question.get("options"):
        labels = ["الف", "ب", "ج", "د"]
        for i, opt in enumerate(question["options"][:4]):
            lines.append(f"  **{labels[i]}**) {opt}")
    return "\n".join(lines)


def format_quiz_result(result: dict) -> str:
    score = result["score"]
    total = result["total"]
    pct = result["percentage"]
    if pct >= 80:
        medal = "🏆"
        comment = "عالی! نتیجه بسیار خوبی گرفتی."
    elif pct >= 60:
        medal = "👍"
        comment = "خوب بود! جای پیشرفت داری."
    elif pct >= 40:
        medal = "📚"
        comment = "بد نبود ولی باید بیشتر تمرین کنی."
    else:
        medal = "💪"
        comment = "نگران نباش، تمرین بیشتری لازمه!"
    return f"""{medal} **نتیجه کوییز**

✅ درست: {score} از {total}
📊 امتیاز: {pct}%

{comment}"""


def format_flashcard_front(card: dict, index: int, total: int) -> str:
    topic = card.get("topic", "")
    lines = [f"🃏 **کارت {index}/{total}**"]
    if topic:
        lines.append(f"📌 {topic}")
    lines.append("")
    lines.append(f"❓ **{card['front']}**")
    lines.append("\n_پاسخت چیه؟ برای دیدن جواب، گزینه‌ای انتخاب کن:_")
    return "\n".join(lines)


def format_flashcard_back(card: dict) -> str:
    return f"✅ **پاسخ:**\n\n{card['back']}\n\n_چقدر بلد بودی؟_"


def format_progress(weak_topics: list[dict], course_name: str) -> str:
    if not weak_topics:
        return f"📊 **پیشرفت در {course_name}**\n\n✅ هنوز اطلاعاتی ثبت نشده. کوییز بزن تا وضعیتت مشخص بشه!"
    lines = [f"📊 **ضعیف‌ترین موضوعات در {course_name}:**\n"]
    for t in weak_topics:
        mastery = t.get("mastery_score", 0)
        total = t.get("total_attempts", 0)
        topic_name = t.get("topic", "نامشخص")
        bar = progress_bar(mastery)
        lines.append(f"📌 **{topic_name}**")
        lines.append(f"   {bar} {round(mastery * 100)}% ({total} تمرین)")
    return "\n".join(lines)


def progress_bar(ratio: float, length: int = 8) -> str:
    filled = round(ratio * length)
    return "█" * filled + "░" * (length - filled)


def format_memory_context(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = ["اطلاعات مرتبط درباره این دانشجو:"]
    for m in memories:
        mtype = m.get("memory_type", "")
        content = m.get("content", "")
        topic = m.get("topic", "")
        if mtype == "weakness":
            lines.append(f"- ضعف در: {topic} - {content}")
        elif mtype == "preference":
            lines.append(f"- ترجیح: {content}")
        elif mtype == "strength":
            lines.append(f"- قوی در: {topic}")
    return "\n".join(lines)


def format_flashcard_result(result: dict) -> str:
    score = result["score"]
    total = result["total"]
    pct = result["percentage"]
    if pct >= 80:
        medal = "🏆"
        comment = "عالی! خیلی خوب بلدی."
    elif pct >= 60:
        medal = "👍"
        comment = "خوب بود! ادامه بده."
    else:
        medal = "💪"
        comment = "بیشتر مرور کن!"
    return f"""{medal} **نتیجه مرور فلش‌کارت**

✅ بلد بودم: {score} از {total}
📊 امتیاز: {pct}%

{comment}"""


def truncate(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."
