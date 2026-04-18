import base64
import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_VISION_MODEL, OPENAI_EMBEDDING_MODEL

logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_BASE = """تو یک استاد خصوصی هوشمند و صبور هستی که به دانشجویان کمک می‌کنی مفاهیم درسی را یاد بگیرند.
پاسخ‌هایت باید:
- واضح، آموزشی و مفید باشند
- به فارسی روان و قابل فهم باشند
- از فرمول‌بندی درست برای مراحل استفاده کنند
- اگر موضوع مدار یا ریاضیات است، مراحل را دقیق توضیح بدهی"""

MODE_PROMPTS = {
    "qa": """حالت: پاسخ به سوال (QA)
سوال دانشجو را مستقیم و کامل پاسخ بده. اگر context داری از آن استفاده کن. پاسخ باید جامع ولی مختصر باشد.""",

    "solver": """حالت: حل مسئله مرحله‌به‌مرحله
مسئله را مرحله به مرحله حل کن:
۱. ابتدا مسئله را تحلیل کن و مجهولات را شناسایی کن
۲. روش حل را توضیح بده
۳. هر مرحله را با جزئیات کافی شرح بده
۴. نتیجه نهایی را مشخص کن
۵. در صورت لزوم پاسخ را چک کن""",

    "circuit": """حالت: تحلیل مدار
مدار را به صورت حرفه‌ای تحلیل کن:
۱. نوع مدار و المان‌های آن را شناسایی کن
۲. قوانین مرتبط (KVL، KCL، قانون اهم و غیره) را اعمال کن
۳. معادلات مدار را بنویس
۴. حل کن و نتایج را توضیح بده
۵. نکات مهم و تفسیر نتایج را ذکر کن""",

    "hint": """حالت: راهنمایی تدریجی (Hint)
فقط راهنمایی کن، نه جواب کامل بده!
- یک اشاره کوچک برای شروع بده
- دانشجو را به فکر کردن تشویق کن
- سوال بپرس که دانشجو خودش به جواب برسد
- اگر دانشجو گیر کرد یک راهنمایی بیشتر بده""",

    "review": """حالت: بررسی پاسخ دانشجو
پاسخ دانشجو را بررسی کن:
۱. آیا پاسخ درست است؟
۲. اگر اشتباه دارد، کجا اشتباه کرده؟
۳. روش درست را توضیح بده
۴. تشویق کن و نکات مثبت را هم بگو""",

    "auto": "حالت پاسخ را بر اساس سوال خودت انتخاب کن.",
}

DEPTH_PROMPTS = {
    "simple": "پاسخ را خیلی ساده و با مثال‌های روزمره توضیح بده. انگار داری به یک مبتدی درس می‌دهی.",
    "normal": "پاسخ کامل و استاندارد بده.",
    "deep": "پاسخ عمیق و جامع بده. ریشه مفهوم را توضیح بده، ارتباط با سایر مفاهیم را نشان بده.",
    "exam": "پاسخ را طوری بده که برای امتحان مناسب باشد. فرمول‌ها، تعریف‌ها و نکات کلیدی را برجسته کن.",
}


def build_system_prompt(mode: str, depth: str, socratic: bool, context: str = "") -> str:
    parts = [SYSTEM_BASE]
    parts.append(MODE_PROMPTS.get(mode, MODE_PROMPTS["auto"]))
    parts.append(DEPTH_PROMPTS.get(depth, DEPTH_PROMPTS["normal"]))
    if socratic:
        parts.append("در پایان یک سوال متقابل از دانشجو بپرس تا درک او را بسنجی.")
    if context:
        parts.append(f"\n--- محتوای درس (استفاده کن اگر مرتبط است) ---\n{context}\n--- پایان محتوای درس ---")
    return "\n\n".join(parts)


async def detect_mode(text: str) -> str:
    prompt = f"""این سوال دانشجو را بخوان و تشخیص بده چه نوع سوالی است:
"{text}"

یکی از موارد زیر را انتخاب کن:
- solver: اگر مسئله‌ای برای حل وجود دارد
- circuit: اگر درباره مدار الکتریکی است
- qa: اگر سوال مفهومی یا توضیح می‌خواهد
- hint: اگر دانشجو دنبال راهنمایی است نه جواب کامل

فقط یک کلمه از لیست بالا برگردان."""
    res = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
    )
    detected = res.choices[0].message.content.strip().lower()
    return detected if detected in MODE_PROMPTS else "qa"


async def chat(messages: list[dict], system_prompt: str, max_tokens: int = 2000) -> str:
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    res = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=all_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return res.choices[0].message.content.strip()


async def chat_with_image(text: str, image_bytes: bytes, system_prompt: str, max_tokens: int = 2000) -> str:
    b64 = base64.b64encode(image_bytes).decode()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": text or "این تصویر را تحلیل کن"},
            ],
        },
    ]
    res = await client.chat.completions.create(
        model=OPENAI_VISION_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return res.choices[0].message.content.strip()


async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    import io
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="fa",
    )
    return transcript.text


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    res = await client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in res.data]


async def generate_quiz_questions(content: str, course_name: str, num_questions: int = 5, question_type: str = "mcq", topic: str = "") -> list[dict]:
    type_desc = {
        "mcq": "چندگزینه‌ای (4 گزینه)",
        "open": "تشریحی",
        "mixed": "ترکیبی از چندگزینه‌ای و تشریحی",
    }
    prompt = f"""از محتوای زیر، {num_questions} سوال {type_desc.get(question_type, 'چندگزینه‌ای')} برای درس "{course_name}" بساز.
{f'موضوع: {topic}' if topic else ''}

محتوا:
{content[:3000]}

خروجی را دقیقاً به این فرمت JSON برگردان (آرایه از آبجکت):
[
  {{
    "question": "متن سوال",
    "answer": "پاسخ درست",
    "options": ["گزینه الف", "گزینه ب", "گزینه ج", "گزینه د"],
    "question_type": "mcq",
    "topic": "موضوع سوال",
    "difficulty": 3
  }}
]

برای سوالات تشریحی، options یک آرایه خالی باشد.
difficulty بین 1 تا 5 باشد."""
    res = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.8,
        response_format={"type": "json_object"},
    )
    import json
    try:
        data = json.loads(res.choices[0].message.content)
        if isinstance(data, list):
            return data
        for key in data:
            if isinstance(data[key], list):
                return data[key]
    except Exception as e:
        logger.error(f"Quiz generation parse error: {e}")
    return []


async def generate_flashcards(content: str, num_cards: int = 10, topic: str = "") -> list[dict]:
    prompt = f"""از محتوای زیر، {num_cards} فلش‌کارت آموزشی بساز.
{f'موضوع: {topic}' if topic else ''}

محتوا:
{content[:3000]}

خروجی را دقیقاً به این فرمت JSON برگردان:
[
  {{
    "front": "سوال یا مفهوم روی کارت",
    "back": "پاسخ یا توضیح پشت کارت",
    "topic": "موضوع"
  }}
]"""
    res = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    import json
    try:
        data = json.loads(res.choices[0].message.content)
        if isinstance(data, list):
            return data
        for key in data:
            if isinstance(data[key], list):
                return data[key]
    except Exception as e:
        logger.error(f"Flashcard generation parse error: {e}")
    return []


async def generate_summary(content: str, summary_type: str = "general", course_name: str = "") -> str:
    prompts = {
        "general": f"محتوای درس '{course_name}' را خلاصه کن. مفاهیم اصلی، تعریف‌ها و نکات مهم را پوشش بده.",
        "exam": f"یک خلاصه امتحانی (cheat sheet) از درس '{course_name}' بساز. فقط مهم‌ترین فرمول‌ها، تعریف‌ها و نکات کلیدی.",
        "structured": f"یک خلاصه ساختاریافته از درس '{course_name}' بساز با عنوان‌بندی و زیرعنوان‌های واضح.",
        "mindmap": f"ساختار mind-map گونه از مفاهیم درس '{course_name}' بساز. از تورفتگی و نشانه‌گذاری برای نشان دادن روابط استفاده کن.",
    }
    system = "تو یک استاد خبره هستی که خلاصه‌های آموزشی می‌نویسی. خلاصه‌هایت واضح، جامع و قابل استفاده هستند."
    user_prompt = f"{prompts.get(summary_type, prompts['general'])}\n\nمحتوا:\n{content[:4000]}"
    res = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2000,
        temperature=0.5,
    )
    return res.choices[0].message.content.strip()
