import asyncio
import logging
import sys
import threading
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import uvicorn
from config import TELEGRAM_BOT_TOKEN, LOG_LEVEL, DASHBOARD_HOST, DASHBOARD_PORT
from services.supabase_service import init_db
from dashboard.log_handler import setup_log_capture
from handlers.start_handler import start_command, help_command, reset_command, courses_command, settings_command, progress_command
from handlers.tutor_handler import handle_text_message, handle_photo_message, handle_voice_message
from handlers.document_handler import handle_document
from handlers.callback_handler import handle_callback

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def create_bot() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set!")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).read_timeout(60).write_timeout(60).connect_timeout(30).pool_timeout(60).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("courses", courses_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app


def run_dashboard():
    from dashboard.app import app as dashboard_app
    config = uvicorn.Config(
        dashboard_app,
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    setup_log_capture()
    logger.info("Starting AI Tutor Bot...")

    asyncio.get_event_loop().run_until_complete(init_db())

    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True, name="dashboard")
    dashboard_thread.start()
    logger.info(f"Admin dashboard running at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    bot = create_bot()
    logger.info("Telegram bot is running!")
    bot.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
