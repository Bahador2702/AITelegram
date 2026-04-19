import aiosqlite
from config import DB_PATH


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM bot_users") as cur:
            total_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM bot_users WHERE onboarded=1") as cur:
            onboarded_users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM courses") as cur:
            total_courses = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM course_files") as cur:
            total_files = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM quiz_questions") as cur:
            total_questions = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM quiz_performance") as cur:
            total_answers = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM flashcards") as cur:
            total_flashcards = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM conversations") as cur:
            total_messages = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM bot_users WHERE created_at >= datetime('now', '-7 days')"
        ) as cur:
            new_users_week = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM conversations WHERE created_at >= datetime('now', '-1 day')"
        ) as cur:
            messages_today = (await cur.fetchone())[0]
    return {
        "total_users": total_users,
        "onboarded_users": onboarded_users,
        "total_courses": total_courses,
        "total_files": total_files,
        "total_questions": total_questions,
        "total_answers": total_answers,
        "total_flashcards": total_flashcards,
        "total_messages": total_messages,
        "new_users_week": new_users_week,
        "messages_today": messages_today,
    }


async def get_all_users(limit: int = 100, offset: int = 0) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT u.*,
               COUNT(DISTINCT c.id) as course_count,
               COUNT(DISTINCT cf.id) as file_count,
               COUNT(DISTINCT conv.id) as message_count
               FROM bot_users u
               LEFT JOIN courses c ON c.user_id = u.id
               LEFT JOIN course_files cf ON cf.user_id = u.id
               LEFT JOIN conversations conv ON conv.user_id = u.id
               GROUP BY u.id
               ORDER BY u.created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_detail(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        user = dict(row)

        async with db.execute("SELECT * FROM courses WHERE user_id = ? ORDER BY created_at DESC", (user_id,)) as cur:
            user["courses"] = [dict(r) for r in await cur.fetchall()]

        async with db.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)) as cur:
            pref_row = await cur.fetchone()
            user["preferences"] = dict(pref_row) if pref_row else {}

        async with db.execute(
            "SELECT topic, mastery_score, total_attempts, correct_attempts FROM topic_mastery WHERE user_id = ? ORDER BY mastery_score ASC LIMIT 10",
            (user_id,),
        ) as cur:
            user["weak_topics"] = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT role, content, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ) as cur:
            user["recent_conversations"] = list(reversed([dict(r) for r in await cur.fetchall()]))

        async with db.execute(
            "SELECT COUNT(*) as total, SUM(correct) as correct FROM quiz_performance WHERE user_id = ?",
            (user_id,),
        ) as cur:
            qp = await cur.fetchone()
            user["quiz_total"] = qp[0] or 0
            user["quiz_correct"] = qp[1] or 0

        return user


async def get_all_courses(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.*, u.username, u.first_name,
               COUNT(DISTINCT cf.id) as file_count,
               COUNT(DISTINCT qq.id) as question_count
               FROM courses c
               LEFT JOIN bot_users u ON u.id = c.user_id
               LEFT JOIN course_files cf ON cf.course_id = c.id
               LEFT JOIN quiz_questions qq ON qq.course_id = c.id
               GROUP BY c.id
               ORDER BY c.created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_course_files(course_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM course_files WHERE course_id = ? ORDER BY uploaded_at DESC",
            (course_id,),
        ) as cur:
            return [{**dict(r), "indexed": bool(r["indexed"])} for r in await cur.fetchall()]


async def get_quiz_stats() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT c.name as course_name, u.first_name, u.username,
               COUNT(DISTINCT qq.id) as question_count,
               COUNT(qp.id) as answer_count,
               ROUND(AVG(qp.correct) * 100, 1) as accuracy
               FROM courses c
               JOIN bot_users u ON u.id = c.user_id
               LEFT JOIN quiz_questions qq ON qq.course_id = c.id
               LEFT JOIN quiz_performance qp ON qp.course_id = c.id
               GROUP BY c.id
               ORDER BY answer_count DESC
               LIMIT 50"""
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bot_users WHERE id = ?", (user_id,))
        await db.commit()


async def clear_user_conversations(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_recent_activity(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT conv.created_at, conv.role, SUBSTR(conv.content, 1, 80) as preview,
               u.first_name, u.username, u.id as user_id
               FROM conversations conv
               JOIN bot_users u ON u.id = conv.user_id
               ORDER BY conv.created_at DESC
               LIMIT ?""",
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
