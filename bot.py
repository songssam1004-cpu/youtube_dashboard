"""
pip install python-telegram-bot youtube-transcript-api anthropic supabase yt-dlp
"""
import re, asyncio, anthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from youtube_transcript_api import YouTubeTranscriptApi
from supabase import create_client

# ── 설정 ────────────────────────────────────────────
TELEGRAM_TOKEN  = "YOUR_TELEGRAM_BOT_TOKEN"   # @BotFather에서 발급
ANTHROPIC_KEY   = "YOUR_ANTHROPIC_API_KEY"
SUPABASE_URL    = "https://steezutktgefzzirvqme.supabase.co"
SUPABASE_KEY    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN0ZWV6dXRrdGdlZnp6aXJ2cW1lIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjIyMjg2MCwiZXhwIjoyMDg3Nzk4ODYwfQ.b7lMXQ1wC4T1ld_UKzZXINM4oo4JEsariLnde7enY7A"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ai       = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

PROMPT_TEMPLATE = """당신은 유튜브 영상을 요약하는 전문가입니다.
youtube transcript가 인입됩니다. 약간의 노이즈가 있기 때문에 그것을 감안하여 아래 요약 템플릿 형태로 요약을 수행해주세요.
또한 keyword tag도 3개 정도 정의해서 출력
tag안에 들어가는 키워드는 명사

---
## 🚀 [제목] (Title)

### 💡 핵심 비유 (Analogy)
- 내용을 한눈에 파악할 수 있는 강력하고 기억하기 쉬운 비유 또는 캐치프레이즈

### ✨ 핵심 요약 (Key Points)
- 가장 중요한 내용 3가지 요약
    - Point 1
    - Point 2
    - Point 3

### 📚 상세 내용 (Details)
- 핵심 요약에서 제시된 내용에 대한 구체적인 설명, 배경 또는 주요 특징 기술

### 🤔 비판적 관점 (Critical Points)
- 해당 내용에 대해 주의 깊게 생각하거나 경계해야 할 지점, 또는 더 깊이 생각해 볼 만한 질문 제시
    - Point 1
    - Point 2

### 📊 숫자 (Numbers)
*(선택 사항: 관련 데이터가 중요할 경우)*
- 핵심 통계 1:
- 핵심 통계 2:

### 👟 쉬운 첫걸음 (Easy Next Step)
- 핵심 교훈을 바탕으로, 가장 마찰이 적고 즉시 실행 가능한 구체적인 행동 1가지 제안

---
### 🧩 핵심 개념 & 용어
- 기술적으로 중요하거나 어려운 핵심 용어 3개를 비유를 통해 한 줄로 설명
    - **용어 1**:
    - **용어 2**:
    - **용어 3**:

### 📖 참고: 선행 지식 (Prerequisites)
- 이 정보를 완전히 이해하기 위해 필요한 사전 지식이나 조건

---
[TAGS] 태그1, 태그2, 태그3

---
transcript:
{transcript}
"""

# ── 유틸 함수 ────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def get_transcript(video_id: str) -> str:
    try:
        # 한국어 우선, 없으면 영어, 없으면 자동생성
        for lang in [["ko"], ["en"], None]:
            try:
                entries = (
                    YouTubeTranscriptApi.get_transcript(video_id, languages=lang)
                    if lang else
                    YouTubeTranscriptApi.get_transcript(video_id)
                )
                return " ".join(e["text"] for e in entries)
            except Exception:
                continue
    except Exception:
        pass
    return ""

def get_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

def parse_tags(summary: str) -> list[str]:
    """[TAGS] 태그1, 태그2, 태그3 형식 파싱"""
    m = re.search(r"\[TAGS\]\s*(.+)", summary)
    if m:
        return [t.strip() for t in m.group(1).split(",") if t.strip()]
    return []

def parse_title(summary: str) -> str:
    """## 🚀 [제목] 형식에서 제목 추출"""
    m = re.search(r"##\s*🚀\s*(.+?)(?:\s*\(Title\))?$", summary, re.MULTILINE)
    if m:
        return m.group(1).strip().strip("[]")
    return "제목 없음"

def summarize(transcript: str) -> str:
    msg = ai.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(transcript=transcript[:12000])}]
    )
    return msg.content[0].text

def save_to_db(youtube_url: str, video_id: str, title: str, summary: str, transcript: str, tags: list):
    supabase.table("youtube_summaries").insert({
        "youtube_url":   youtube_url,
        "title":         title,
        "thumbnail_url": get_thumbnail(video_id),
        "summary_text":  summary,
        "tags":          tags,
        "video_stt_url": transcript,
    }).execute()

# ── 텔레그램 핸들러 ──────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if "youtube.com" not in text and "youtu.be" not in text:
        await update.message.reply_text("유튜브 링크를 보내주세요! 🎬")
        return

    video_id = extract_video_id(text)
    if not video_id:
        await update.message.reply_text("유효한 유튜브 링크를 찾을 수 없어요 😢")
        return

    msg = await update.message.reply_text("⏳ 트랜스크립트 가져오는 중...")

    transcript = get_transcript(video_id)
    if not transcript:
        await msg.edit_text("❌ 자막/트랜스크립트를 가져올 수 없는 영상이에요.")
        return

    await msg.edit_text("🤖 AI 요약 중... (약 30초 소요)")

    try:
        summary = summarize(transcript)
        title   = parse_title(summary)
        tags    = parse_tags(summary)
        save_to_db(text, video_id, title, summary, transcript, tags)
        await msg.edit_text(f"✅ 요약 완료!\n\n📌 *{title}*\n🏷️ {' '.join(f'#{t}' for t in tags)}\n\n대시보드에서 확인하세요!", parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ 오류 발생: {e}")

# ── 실행 ─────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("봇 시작!")
    app.run_polling()
