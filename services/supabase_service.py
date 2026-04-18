from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY
import logging

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
        _client = create_client(SUPABASE_URL, key)
    return _client


async def upsert_user(user_id: int, username: str, first_name: str, last_name: str = "", language_code: str = "fa"):
    db = get_client()
    db.table("bot_users").upsert({
        "id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "language_code": language_code,
        "updated_at": "now()"
    }).execute()


async def get_user(user_id: int) -> dict | None:
    db = get_client()
    res = db.table("bot_users").select("*").eq("id", user_id).maybeSingle().execute()
    return res.data


async def set_active_course(user_id: int, course_id: str | None):
    db = get_client()
    db.table("bot_users").update({"active_course_id": course_id, "updated_at": "now()"}).eq("id", user_id).execute()


async def set_onboarded(user_id: int):
    db = get_client()
    db.table("bot_users").update({"onboarded": True}).eq("id", user_id).execute()


async def get_preferences(user_id: int) -> dict:
    db = get_client()
    res = db.table("user_preferences").select("*").eq("user_id", user_id).maybeSingle().execute()
    if res.data:
        return res.data
    defaults = {
        "user_id": user_id,
        "answer_mode": "auto",
        "explanation_depth": "normal",
        "output_language": "fa",
        "voice_enabled": False,
        "socratic_mode": False,
        "hint_mode": False,
    }
    db.table("user_preferences").insert(defaults).execute()
    return defaults


async def update_preferences(user_id: int, updates: dict):
    db = get_client()
    updates["updated_at"] = "now()"
    db.table("user_preferences").upsert({"user_id": user_id, **updates}).execute()


async def create_course(user_id: int, name: str, description: str = "", emoji: str = "📚") -> dict:
    db = get_client()
    res = db.table("courses").insert({
        "user_id": user_id,
        "name": name,
        "description": description,
        "emoji": emoji,
    }).execute()
    return res.data[0]


async def get_courses(user_id: int) -> list[dict]:
    db = get_client()
    res = db.table("courses").select("*").eq("user_id", user_id).order("created_at").execute()
    return res.data or []


async def get_course(course_id: str) -> dict | None:
    db = get_client()
    res = db.table("courses").select("*").eq("id", course_id).maybeSingle().execute()
    return res.data


async def delete_course(course_id: str, user_id: int):
    db = get_client()
    db.table("courses").delete().eq("id", course_id).eq("user_id", user_id).execute()


async def add_course_file(course_id: str, user_id: int, filename: str, original_filename: str, file_type: str, file_size: int) -> dict:
    db = get_client()
    res = db.table("course_files").insert({
        "course_id": course_id,
        "user_id": user_id,
        "filename": filename,
        "original_filename": original_filename,
        "file_type": file_type,
        "file_size_bytes": file_size,
    }).execute()
    db.table("courses").update({"file_count": db.table("courses").select("file_count").eq("id", course_id).execute().data[0]["file_count"] + 1}).eq("id", course_id).execute()
    return res.data[0]


async def update_file_indexed(file_id: str, chunk_count: int, summary: str = ""):
    db = get_client()
    db.table("course_files").update({
        "indexed": True,
        "chunk_count": chunk_count,
        "summary": summary,
    }).eq("id", file_id).execute()


async def get_course_files(course_id: str) -> list[dict]:
    db = get_client()
    res = db.table("course_files").select("*").eq("course_id", course_id).order("uploaded_at").execute()
    return res.data or []


async def delete_course_file(file_id: str, user_id: int) -> dict | None:
    db = get_client()
    res = db.table("course_files").select("*").eq("id", file_id).eq("user_id", user_id).maybeSingle().execute()
    if res.data:
        db.table("course_files").delete().eq("id", file_id).execute()
    return res.data


async def save_conversation(user_id: int, course_id: str | None, role: str, content: str, message_type: str = "text"):
    db = get_client()
    db.table("conversations").insert({
        "user_id": user_id,
        "course_id": course_id,
        "role": role,
        "content": content,
        "message_type": message_type,
    }).execute()


async def get_recent_conversations(user_id: int, course_id: str | None, limit: int = 10) -> list[dict]:
    db = get_client()
    query = db.table("conversations").select("role,content,created_at").eq("user_id", user_id)
    if course_id:
        query = query.eq("course_id", course_id)
    res = query.order("created_at", desc=True).limit(limit).execute()
    return list(reversed(res.data or []))


async def clear_conversation_history(user_id: int, course_id: str | None):
    db = get_client()
    query = db.table("conversations").delete().eq("user_id", user_id)
    if course_id:
        query = query.eq("course_id", course_id)
    query.execute()


async def save_quiz_questions(questions: list[dict]) -> list[dict]:
    db = get_client()
    res = db.table("quiz_questions").insert(questions).execute()
    return res.data or []


async def get_quiz_questions(user_id: int, course_id: str, limit: int = 5, due_only: bool = False) -> list[dict]:
    db = get_client()
    if due_only:
        perf = db.table("quiz_performance").select("question_id").eq("user_id", user_id).lte("next_review_at", "now()").execute()
        due_ids = [p["question_id"] for p in (perf.data or [])]
        if not due_ids:
            return []
        res = db.table("quiz_questions").select("*").eq("course_id", course_id).in_("id", due_ids).limit(limit).execute()
    else:
        res = db.table("quiz_questions").select("*").eq("course_id", course_id).eq("user_id", user_id).limit(limit).execute()
    return res.data or []


async def upsert_quiz_performance(user_id: int, question_id: str, course_id: str, correct: bool, user_answer: str, ease_factor: float, interval_days: int, repetitions: int, next_review_at: str):
    db = get_client()
    db.table("quiz_performance").upsert({
        "user_id": user_id,
        "question_id": question_id,
        "course_id": course_id,
        "correct": correct,
        "user_answer": user_answer,
        "ease_factor": ease_factor,
        "interval_days": interval_days,
        "repetitions": repetitions,
        "next_review_at": next_review_at,
        "answered_at": "now()",
    }).execute()


async def get_weak_topics(user_id: int, course_id: str, limit: int = 5) -> list[dict]:
    db = get_client()
    res = db.table("topic_mastery").select("*").eq("user_id", user_id).eq("course_id", course_id).order("mastery_score").limit(limit).execute()
    return res.data or []


async def upsert_topic_mastery(user_id: int, course_id: str, topic: str, correct: bool):
    db = get_client()
    existing = db.table("topic_mastery").select("*").eq("user_id", user_id).eq("course_id", course_id).eq("topic", topic).maybeSingle().execute()
    if existing.data:
        total = existing.data["total_attempts"] + 1
        correct_count = existing.data["correct_attempts"] + (1 if correct else 0)
        mastery = correct_count / total
        db.table("topic_mastery").update({
            "total_attempts": total,
            "correct_attempts": correct_count,
            "mastery_score": mastery,
            "last_activity_at": "now()",
        }).eq("id", existing.data["id"]).execute()
    else:
        db.table("topic_mastery").insert({
            "user_id": user_id,
            "course_id": course_id,
            "topic": topic,
            "mastery_score": 1.0 if correct else 0.0,
            "total_attempts": 1,
            "correct_attempts": 1 if correct else 0,
        }).execute()


async def save_flashcards(cards: list[dict]) -> list[dict]:
    db = get_client()
    res = db.table("flashcards").insert(cards).execute()
    return res.data or []


async def get_due_flashcards(user_id: int, course_id: str, limit: int = 5) -> list[dict]:
    db = get_client()
    res = db.table("flashcards").select("*").eq("user_id", user_id).eq("course_id", course_id).lte("next_review_at", "now()").order("next_review_at").limit(limit).execute()
    return res.data or []


async def update_flashcard_review(card_id: str, ease_factor: float, interval_days: int, repetitions: int, next_review_at: str):
    db = get_client()
    db.table("flashcards").update({
        "ease_factor": ease_factor,
        "interval_days": interval_days,
        "repetitions": repetitions,
        "next_review_at": next_review_at,
    }).eq("id", card_id).execute()


async def save_memory(user_id: int, course_id: str | None, memory_type: str, topic: str, content: str, importance: int = 3):
    db = get_client()
    db.table("user_memory").insert({
        "user_id": user_id,
        "course_id": course_id,
        "memory_type": memory_type,
        "topic": topic,
        "content": content,
        "importance": importance,
    }).execute()


async def get_user_memories(user_id: int, course_id: str | None, memory_type: str | None = None, limit: int = 10) -> list[dict]:
    db = get_client()
    query = db.table("user_memory").select("*").eq("user_id", user_id)
    if course_id:
        query = query.eq("course_id", course_id)
    if memory_type:
        query = query.eq("memory_type", memory_type)
    res = query.order("importance", desc=True).order("created_at", desc=True).limit(limit).execute()
    return res.data or []
