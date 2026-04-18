import aiosqlite
import json
import logging
from datetime import datetime, timezone
from config import DB_PATH

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bot_users (
    id INTEGER PRIMARY KEY,
    username TEXT DEFAULT '',
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    language_code TEXT DEFAULT 'fa',
    active_course_id TEXT,
    onboarded INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    emoji TEXT DEFAULT '📚',
    file_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS course_files (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0,
    chunk_count INTEGER DEFAULT 0,
    indexed INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    uploaded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    options TEXT DEFAULT '[]',
    question_type TEXT DEFAULT 'mcq',
    topic TEXT DEFAULT '',
    difficulty INTEGER DEFAULT 3,
    source_file_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_performance (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    correct INTEGER NOT NULL,
    user_answer TEXT DEFAULT '',
    answered_at TEXT DEFAULT (datetime('now')),
    next_review_at TEXT DEFAULT (datetime('now')),
    ease_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    UNIQUE(user_id, question_id)
);

CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    topic TEXT DEFAULT '',
    source TEXT DEFAULT 'manual',
    ease_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    repetitions INTEGER DEFAULT 0,
    next_review_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES bot_users(id) ON DELETE CASCADE,
    answer_mode TEXT DEFAULT 'auto',
    explanation_depth TEXT DEFAULT 'normal',
    output_language TEXT DEFAULT 'fa',
    voice_enabled INTEGER DEFAULT 0,
    socratic_mode INTEGER DEFAULT 0,
    hint_mode INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    course_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_course ON conversations(user_id, course_id, created_at);

CREATE TABLE IF NOT EXISTS user_memory (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    course_id TEXT,
    memory_type TEXT NOT NULL,
    topic TEXT DEFAULT '',
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 3,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topic_mastery (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    mastery_score REAL DEFAULT 0.0,
    total_attempts INTEGER DEFAULT 0,
    correct_attempts INTEGER DEFAULT 0,
    last_activity_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, course_id, topic)
);
"""


def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()
    logger.info(f"SQLite database initialized at {DB_PATH}")


def get_client():
    return None


async def upsert_user(user_id: int, username: str, first_name: str, last_name: str = "", language_code: str = "fa"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO bot_users (id, username, first_name, last_name, language_code, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(id) DO UPDATE SET
                 username=excluded.username,
                 first_name=excluded.first_name,
                 last_name=excluded.last_name,
                 updated_at=datetime('now')""",
            (user_id, username, first_name, last_name, language_code),
        )
        await db.commit()


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_users WHERE id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def set_active_course(user_id: int, course_id: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bot_users SET active_course_id = ?, updated_at = datetime('now') WHERE id = ?",
            (course_id, user_id),
        )
        await db.commit()


async def set_onboarded(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bot_users SET onboarded = 1 WHERE id = ?", (user_id,))
        await db.commit()


async def get_preferences(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["voice_enabled"] = bool(d["voice_enabled"])
                d["socratic_mode"] = bool(d["socratic_mode"])
                d["hint_mode"] = bool(d["hint_mode"])
                return d
        await db.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (user_id,))
        await db.commit()
    return {
        "user_id": user_id,
        "answer_mode": "auto",
        "explanation_depth": "normal",
        "output_language": "fa",
        "voice_enabled": False,
        "socratic_mode": False,
        "hint_mode": False,
    }


async def update_preferences(user_id: int, updates: dict):
    updates.pop("updated_at", None)
    allowed = {"answer_mode", "explanation_depth", "output_language", "voice_enabled", "socratic_mode", "hint_mode"}
    updates = {k: (1 if v is True else (0 if v is False else v)) for k, v in updates.items() if k in allowed}
    if not updates:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (user_id,))
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE user_preferences SET {sets}, updated_at = datetime('now') WHERE user_id = ?", vals)
        await db.commit()


async def create_course(user_id: int, name: str, description: str = "", emoji: str = "📚") -> dict:
    cid = _new_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO courses (id, user_id, name, description, emoji) VALUES (?, ?, ?, ?, ?)",
            (cid, user_id, name, description, emoji),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM courses WHERE id = ?", (cid,)) as cur:
            return dict(await cur.fetchone())


async def get_courses(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM courses WHERE user_id = ? ORDER BY created_at", (user_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_course(course_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM courses WHERE id = ?", (course_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_course(course_id: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM courses WHERE id = ? AND user_id = ?", (course_id, user_id))
        await db.commit()


async def add_course_file(course_id: str, user_id: int, filename: str, original_filename: str, file_type: str, file_size: int) -> dict:
    fid = _new_id()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO course_files (id, course_id, user_id, filename, original_filename, file_type, file_size_bytes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fid, course_id, user_id, filename, original_filename, file_type, file_size),
        )
        await db.execute("UPDATE courses SET file_count = file_count + 1 WHERE id = ?", (course_id,))
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM course_files WHERE id = ?", (fid,)) as cur:
            return dict(await cur.fetchone())


async def update_file_indexed(file_id: str, chunk_count: int, summary: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE course_files SET indexed = 1, chunk_count = ?, summary = ? WHERE id = ?",
            (chunk_count, summary, file_id),
        )
        await db.commit()


async def get_course_files(course_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM course_files WHERE course_id = ? ORDER BY uploaded_at", (course_id,)) as cur:
            rows = await cur.fetchall()
            return [{**dict(r), "indexed": bool(r["indexed"])} for r in rows]


async def delete_course_file(file_id: str, user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM course_files WHERE id = ? AND user_id = ?", (file_id, user_id)) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        data = {**dict(row), "indexed": bool(row["indexed"])}
        await db.execute("UPDATE courses SET file_count = MAX(0, file_count - 1) WHERE id = ?", (data["course_id"],))
        await db.execute("DELETE FROM course_files WHERE id = ?", (file_id,))
        await db.commit()
        return data


async def save_conversation(user_id: int, course_id: str | None, role: str, content: str, message_type: str = "text"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (id, user_id, course_id, role, content, message_type) VALUES (?, ?, ?, ?, ?, ?)",
            (_new_id(), user_id, course_id, role, content, message_type),
        )
        await db.commit()


async def get_recent_conversations(user_id: int, course_id: str | None, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if course_id:
            async with db.execute(
                "SELECT role, content, created_at FROM conversations WHERE user_id = ? AND course_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, course_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT role, content, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        return list(reversed([dict(r) for r in rows]))


async def clear_conversation_history(user_id: int, course_id: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        if course_id:
            await db.execute("DELETE FROM conversations WHERE user_id = ? AND course_id = ?", (user_id, course_id))
        else:
            await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        await db.commit()


async def save_quiz_questions(questions: list[dict]) -> list[dict]:
    saved = []
    async with aiosqlite.connect(DB_PATH) as db:
        for q in questions:
            qid = _new_id()
            await db.execute(
                "INSERT INTO quiz_questions (id, course_id, user_id, question, answer, options, question_type, topic, difficulty, source_file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    qid, q["course_id"], q["user_id"], q["question"], q["answer"],
                    json.dumps(q.get("options", []), ensure_ascii=False),
                    q.get("question_type", "mcq"), q.get("topic", ""),
                    q.get("difficulty", 3), q.get("source_file_id"),
                ),
            )
            saved.append({**q, "id": qid})
        await db.commit()
    return saved


async def get_quiz_questions(user_id: int, course_id: str, limit: int = 5, due_only: bool = False) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if due_only:
            async with db.execute(
                """SELECT q.* FROM quiz_questions q
                   INNER JOIN quiz_performance p ON p.question_id = q.id AND p.user_id = ?
                   WHERE q.course_id = ? AND p.next_review_at <= datetime('now')
                   LIMIT ?""",
                (user_id, course_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM quiz_questions WHERE course_id = ? AND user_id = ? LIMIT ?",
                (course_id, user_id, limit),
            ) as cur:
                rows = await cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["options"] = json.loads(d.get("options") or "[]")
            result.append(d)
        return result


async def upsert_quiz_performance(user_id: int, question_id: str, course_id: str, correct: bool, user_answer: str, ease_factor: float, interval_days: int, repetitions: int, next_review_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO quiz_performance (id, user_id, question_id, course_id, correct, user_answer, ease_factor, interval_days, repetitions, next_review_at, answered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, question_id) DO UPDATE SET
                 correct=excluded.correct, user_answer=excluded.user_answer,
                 ease_factor=excluded.ease_factor, interval_days=excluded.interval_days,
                 repetitions=excluded.repetitions, next_review_at=excluded.next_review_at,
                 answered_at=datetime('now')""",
            (_new_id(), user_id, question_id, course_id, int(correct), user_answer, ease_factor, interval_days, repetitions, next_review_at),
        )
        await db.commit()


async def get_weak_topics(user_id: int, course_id: str, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topic_mastery WHERE user_id = ? AND course_id = ? ORDER BY mastery_score ASC LIMIT ?",
            (user_id, course_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def upsert_topic_mastery(user_id: int, course_id: str, topic: str, correct: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM topic_mastery WHERE user_id = ? AND course_id = ? AND topic = ?",
            (user_id, course_id, topic),
        ) as cur:
            row = await cur.fetchone()
        if row:
            d = dict(row)
            total = d["total_attempts"] + 1
            correct_count = d["correct_attempts"] + (1 if correct else 0)
            await db.execute(
                "UPDATE topic_mastery SET total_attempts=?, correct_attempts=?, mastery_score=?, last_activity_at=datetime('now') WHERE id=?",
                (total, correct_count, correct_count / total, d["id"]),
            )
        else:
            await db.execute(
                "INSERT INTO topic_mastery (id, user_id, course_id, topic, mastery_score, total_attempts, correct_attempts) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (_new_id(), user_id, course_id, topic, 1.0 if correct else 0.0, 1 if correct else 0),
            )
        await db.commit()


async def save_flashcards(cards: list[dict]) -> list[dict]:
    saved = []
    async with aiosqlite.connect(DB_PATH) as db:
        for card in cards:
            cid = _new_id()
            await db.execute(
                "INSERT INTO flashcards (id, user_id, course_id, front, back, topic, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cid, card["user_id"], card["course_id"], card["front"], card["back"], card.get("topic", ""), card.get("source", "manual")),
            )
            saved.append({**card, "id": cid, "ease_factor": 2.5, "interval_days": 1, "repetitions": 0})
        await db.commit()
    return saved


async def get_due_flashcards(user_id: int, course_id: str, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM flashcards WHERE user_id = ? AND course_id = ? AND next_review_at <= datetime('now') ORDER BY next_review_at LIMIT ?",
            (user_id, course_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def update_flashcard_review(card_id: str, ease_factor: float, interval_days: int, repetitions: int, next_review_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE flashcards SET ease_factor=?, interval_days=?, repetitions=?, next_review_at=? WHERE id=?",
            (ease_factor, interval_days, repetitions, next_review_at, card_id),
        )
        await db.commit()


async def save_memory(user_id: int, course_id: str | None, memory_type: str, topic: str, content: str, importance: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_memory (id, user_id, course_id, memory_type, topic, content, importance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_new_id(), user_id, course_id, memory_type, topic, content, importance),
        )
        await db.commit()


async def get_user_memories(user_id: int, course_id: str | None, memory_type: str | None = None, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conditions = ["user_id = ?"]
        params: list = [user_id]
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        params.append(limit)
        sql = f"SELECT * FROM user_memory WHERE {' AND '.join(conditions)} ORDER BY importance DESC, created_at DESC LIMIT ?"
        async with db.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]
