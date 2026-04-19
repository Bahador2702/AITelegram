import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature

from config import ADMIN_PASSWORD, ADMIN_SECRET_KEY, DATA_DIR
from dashboard import db_queries
from dashboard.log_handler import get_recent_logs, register_sse_queue, unregister_sse_queue

logger = logging.getLogger(__name__)

app = FastAPI(title="Bot Admin Dashboard", docs_url=None, redoc_url=None)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

serializer = URLSafeTimedSerializer(ADMIN_SECRET_KEY)
SESSION_COOKIE = "admin_session"
SESSION_MAX_AGE = 60 * 60 * 8


def create_session_token() -> str:
    return serializer.dumps("admin")


def verify_session(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        serializer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except BadSignature:
        return False


def require_auth(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if verify_session(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        token = create_session_token()
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE, httponly=True)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "رمز اشتباه است"})


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    stats = await db_queries.get_stats()
    activity = await db_queries.get_recent_activity(limit=15)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "activity": activity,
        "page": "dashboard",
    })


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, offset: int = 0):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    users = await db_queries.get_all_users(limit=50, offset=offset)
    return templates.TemplateResponse("users.html", {
        "request": request,
        "users": users,
        "offset": offset,
        "page": "users",
    })


@app.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail(request: Request, user_id: int):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    user = await db_queries.get_user_detail(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("user_detail.html", {
        "request": request,
        "user": user,
        "page": "users",
    })


@app.post("/users/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    await db_queries.delete_user(user_id)
    return RedirectResponse("/users", status_code=302)


@app.post("/users/{user_id}/clear-conversations")
async def clear_user_conversations(request: Request, user_id: int):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    await db_queries.clear_user_conversations(user_id)
    return RedirectResponse(f"/users/{user_id}", status_code=302)


@app.get("/courses", response_class=HTMLResponse)
async def courses_page(request: Request):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    courses = await db_queries.get_all_courses()
    return templates.TemplateResponse("courses.html", {
        "request": request,
        "courses": courses,
        "page": "courses",
    })


@app.get("/courses/{course_id}/files", response_class=HTMLResponse)
async def course_files(request: Request, course_id: str):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    files = await db_queries.get_course_files(course_id)
    return templates.TemplateResponse("course_files.html", {
        "request": request,
        "files": files,
        "course_id": course_id,
        "page": "courses",
    })


@app.get("/quiz-stats", response_class=HTMLResponse)
async def quiz_stats_page(request: Request):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    stats = await db_queries.get_quiz_stats()
    return templates.TemplateResponse("quiz_stats.html", {
        "request": request,
        "stats": stats,
        "page": "quiz",
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    if not verify_session(request):
        return RedirectResponse("/login", status_code=302)
    recent_logs = get_recent_logs(200)
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": recent_logs,
        "page": "logs",
    })


@app.get("/logs/stream")
async def logs_stream(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=401)

    async def event_generator() -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        register_sse_queue(q)
        try:
            yield "data: {\"message\": \"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"ping\": true}\n\n"
        finally:
            unregister_sse_queue(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/stats")
async def api_stats(request: Request):
    if not verify_session(request):
        raise HTTPException(status_code=401)
    return await db_queries.get_stats()
