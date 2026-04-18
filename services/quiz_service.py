import logging
from datetime import datetime, timedelta, timezone
from services import supabase_service as db
from services import ai_service
from services import vector_store as vs

logger = logging.getLogger(__name__)

_active_sessions: dict[int, dict] = {}


def sm2_update(ease_factor: float, interval: int, repetitions: int, quality: int) -> tuple[float, int, int]:
    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1
    ease_factor = ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    ease_factor = max(1.3, ease_factor)
    return ease_factor, interval, repetitions


def next_review_iso(interval_days: int) -> str:
    next_dt = datetime.now(timezone.utc) + timedelta(days=interval_days)
    return next_dt.isoformat()


def get_session(user_id: int) -> dict | None:
    return _active_sessions.get(user_id)


def clear_session(user_id: int):
    _active_sessions.pop(user_id, None)


def start_session(user_id: int, questions: list[dict], mode: str = "quiz") -> dict:
    session = {
        "questions": questions,
        "current_index": 0,
        "score": 0,
        "total": len(questions),
        "mode": mode,
        "answers": [],
    }
    _active_sessions[user_id] = session
    return session


def current_question(user_id: int) -> dict | None:
    session = _active_sessions.get(user_id)
    if not session:
        return None
    idx = session["current_index"]
    if idx >= len(session["questions"]):
        return None
    return session["questions"][idx]


async def generate_and_save_quiz(user_id: int, course_id: str, course_name: str, num_questions: int = 5, question_type: str = "mcq", topic: str = "", file_id: str | None = None) -> list[dict]:
    store = vs.get_store(course_id)
    all_text = store.get_all_text(file_id=file_id)
    if not all_text.strip():
        return []
    generated = await ai_service.generate_quiz_questions(all_text, course_name, num_questions, question_type, topic)
    if not generated:
        return []
    questions_to_save = []
    for q in generated:
        questions_to_save.append({
            "course_id": course_id,
            "user_id": user_id,
            "question": q.get("question", ""),
            "answer": q.get("answer", ""),
            "options": q.get("options", []),
            "question_type": q.get("question_type", "mcq"),
            "topic": q.get("topic", topic),
            "difficulty": q.get("difficulty", 3),
            "source_file_id": file_id,
        })
    saved = await db.save_quiz_questions(questions_to_save)
    return saved


async def process_answer(user_id: int, course_id: str, question: dict, user_answer: str) -> dict:
    session = _active_sessions.get(user_id)
    correct_answer = question["answer"].strip().lower()
    user_ans_clean = user_answer.strip().lower()
    is_correct = False
    if question.get("question_type") == "mcq" and question.get("options"):
        try:
            opts = question["options"]
            if user_ans_clean in ["الف", "a", "1"]:
                is_correct = opts[0].strip().lower() == correct_answer
            elif user_ans_clean in ["ب", "b", "2"]:
                is_correct = opts[1].strip().lower() == correct_answer
            elif user_ans_clean in ["ج", "c", "3"]:
                is_correct = opts[2].strip().lower() == correct_answer
            elif user_ans_clean in ["د", "d", "4"]:
                is_correct = opts[3].strip().lower() == correct_answer
            else:
                is_correct = user_ans_clean == correct_answer or user_answer.strip() == question["answer"].strip()
        except (IndexError, AttributeError):
            is_correct = user_ans_clean == correct_answer
    else:
        is_correct = user_ans_clean == correct_answer or len(set(user_ans_clean.split()) & set(correct_answer.split())) > len(correct_answer.split()) * 0.5

    quality = 5 if is_correct else 1
    perf = await db.get_quiz_questions(user_id, course_id, 1)
    ef, interval, reps = 2.5, 1, 0
    ef, interval, reps = sm2_update(ef, interval, reps, quality)
    next_review = next_review_iso(interval)

    await db.upsert_quiz_performance(
        user_id=user_id,
        question_id=str(question["id"]),
        course_id=course_id,
        correct=is_correct,
        user_answer=user_answer,
        ease_factor=ef,
        interval_days=interval,
        repetitions=reps,
        next_review_at=next_review,
    )
    if question.get("topic"):
        await db.upsert_topic_mastery(user_id, course_id, question["topic"], is_correct)

    if session:
        session["answers"].append({"question": question["question"], "correct": is_correct, "user_answer": user_answer})
        if is_correct:
            session["score"] += 1
        session["current_index"] += 1

    return {"correct": is_correct, "correct_answer": question["answer"]}


def get_session_result(user_id: int) -> dict | None:
    session = _active_sessions.get(user_id)
    if not session:
        return None
    return {
        "score": session["score"],
        "total": session["total"],
        "percentage": round(session["score"] / session["total"] * 100) if session["total"] else 0,
        "answers": session["answers"],
    }
