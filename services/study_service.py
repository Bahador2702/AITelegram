import logging
from datetime import datetime, timedelta, timezone
from services import supabase_service as db
from services import ai_service
from services import vector_store as vs
from services.quiz_service import sm2_update, next_review_iso

logger = logging.getLogger(__name__)

_flashcard_sessions: dict[int, dict] = {}


async def generate_and_save_flashcards(user_id: int, course_id: str, num_cards: int = 10, topic: str = "", file_id: str | None = None) -> list[dict]:
    store = vs.get_store(course_id)
    all_text = store.get_all_text(file_id=file_id)
    if not all_text.strip():
        return []
    generated = await ai_service.generate_flashcards(all_text, num_cards, topic)
    if not generated:
        return []
    cards_to_save = []
    for card in generated:
        cards_to_save.append({
            "user_id": user_id,
            "course_id": course_id,
            "front": card.get("front", ""),
            "back": card.get("back", ""),
            "topic": card.get("topic", topic),
            "source": "pdf" if file_id else "course",
        })
    saved = await db.save_flashcards(cards_to_save)
    return saved


async def generate_flashcards_from_conversation(user_id: int, course_id: str, conversation_text: str) -> list[dict]:
    generated = await ai_service.generate_flashcards(conversation_text, num_cards=5, topic="مکالمه")
    if not generated:
        return []
    cards_to_save = [
        {
            "user_id": user_id,
            "course_id": course_id,
            "front": card.get("front", ""),
            "back": card.get("back", ""),
            "topic": card.get("topic", ""),
            "source": "conversation",
        }
        for card in generated
    ]
    return await db.save_flashcards(cards_to_save)


async def start_flashcard_review(user_id: int, course_id: str) -> dict | None:
    cards = await db.get_due_flashcards(user_id, course_id, limit=10)
    if not cards:
        return None
    _flashcard_sessions[user_id] = {
        "cards": cards,
        "current_index": 0,
        "score": 0,
        "total": len(cards),
    }
    return cards[0]


def get_flashcard_session(user_id: int) -> dict | None:
    return _flashcard_sessions.get(user_id)


def current_flashcard(user_id: int) -> dict | None:
    session = _flashcard_sessions.get(user_id)
    if not session:
        return None
    idx = session["current_index"]
    if idx >= len(session["cards"]):
        return None
    return session["cards"][idx]


async def rate_flashcard(user_id: int, card: dict, rating: int) -> bool:
    ef = card.get("ease_factor", 2.5)
    interval = card.get("interval_days", 1)
    reps = card.get("repetitions", 0)
    quality = {1: 1, 2: 2, 3: 4, 4: 5}.get(rating, 3)
    ef, interval, reps = sm2_update(ef, interval, reps, quality)
    next_review = next_review_iso(interval)
    await db.update_flashcard_review(
        card_id=str(card["id"]),
        ease_factor=ef,
        interval_days=interval,
        repetitions=reps,
        next_review_at=next_review,
    )
    session = _flashcard_sessions.get(user_id)
    if session:
        if quality >= 3:
            session["score"] += 1
        session["current_index"] += 1
    return quality >= 3


def clear_flashcard_session(user_id: int):
    _flashcard_sessions.pop(user_id, None)


def get_flashcard_result(user_id: int) -> dict | None:
    session = _flashcard_sessions.get(user_id)
    if not session:
        return None
    return {
        "score": session["score"],
        "total": session["total"],
        "percentage": round(session["score"] / session["total"] * 100) if session["total"] else 0,
    }


async def generate_summary(course_id: str, summary_type: str, course_name: str, file_id: str | None = None) -> str:
    store = vs.get_store(course_id)
    content = store.get_all_text(file_id=file_id)
    if not content.strip():
        return ""
    return await ai_service.generate_summary(content, summary_type, course_name)
