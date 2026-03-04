import os, re, asyncio, requests, threading
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from supabase import create_client
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── 설정 ────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_TOKEN"]
OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]
SUPABASE_URL    = os.environ["SUPABASE_URL"]
SUPABASE_KEY    = os.environ["SUPABASE_KEY"]
APIFY_TOKEN     = os.environ.get("APIFY_TOKEN", "")
DASHBOARD_URL   = os.environ.get("DASHBOARD_URL", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ai       = AsyncOpenAI(api_key=OPENAI_API_KEY)

YOUTUBE_PROMPT = """당신은 유튜브 영상을 요약하는 전문가입니다.
youtube transcript가 인입됩니다. 약간의 노이즈가 있기 때문에 그것을 감안하여 아래 요약 템플릿 형태로 요약을 수행해주세요.
또한 keyword tag도 5개 정도 정의해서 출력
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
- 해당 내용에 대해 주의 깊게 생각하거나 경계해야 할 지점
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
[TAGS] 태그1, 태그2, 태그3, 태그4, 태그5

---
transcript:
{content}
"""

INSTAGRAM_PROMPT = """당신은 인스타그램 게시물을 요약하는 전문가입니다.
아래 인스타그램 캐션(caption) 텍스트를 분석하고 요약해주세요.
keyword tag도 5개 정도 정의해서 출력 (tag는 명사)

---
## 📸 [제목] (Title)

### 💡 핵심 메시지 (Key Message)
- 게시물의 핵심 메시지를 한 줄로 요약

### ✨ 주요 내용 (Key Points)
- 중요한 내용 3가지
    - Point 1
    - Point 2
    - Point 3

### 📚 상세 내용 (Details)
- 게시물의 구체적인 내용, 맥락 설명

### 🤔 인사이트 (Insights)
- 이 게시물에서 얻을 수 있는 인사이트나 시사점

### 👟 액션 아이템 (Action Item)
- 이 게시물을 보고 바로 실행할 수 있는 행동 1가지

---
[TAGS] 태그1, 태그2, 태그3, 태그4, 태그5

---
caption:
{content}
"""

# ── 유틸 함수 ────────────────────────────────────────
def extract_video_id(url: str):
    patterns = [
        r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def is_instagram(url: str) -> bool:
    return "instagram.com" in url

# ── YouTube 트랜스크립트 ─────────────────────────────
def get_youtube_transcript(video_id: str) -> str:
    for attempt in range(3):
        try:
            run_url = f"https://api.apify.com/v2/acts/karamelo~youtube-transcripts/run-sync-get-dataset-items?token={APIFY_TOKEN}&memory=1024&timeout=120"
            payload = {"urls": [f"https://www.youtube.com/watch?v={video_id}"]}
            res = requests.post(run_url, json=payload, timeout=180)
            data = res.json()
            print(f"Apify YouTube 응답 (시도 {attempt+1}): {str(data)[:200]}")
            if data and len(data) > 0:
                item = data[0]
                captions = item.get("captions") or []
                texts = []
                for c in captions:
                    if c is None:
                        continue
                    if isinstance(c, str):
                        texts.append(c)
                    elif isinstance(c, dict):
                        texts.append(c.get("text", ""))
                if texts:
                    return " ".join(texts)
                print(f"captions 비어있음, 재시도 중... ({attempt+1}/3)")
        except Exception as e:
            print(f"YouTube 트랜스크립트 오류 (시도 {attempt+1}): {e}")
    return ""

# ── Instagram 캐션 ───────────────────────────────────
def get_instagram_data(url: str) -> dict:
    try:
        run_url = f"https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}&memory=1024&timeout=120"
        payload = {
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": 1,
        }
        res = requests.post(run_url, json=payload, timeout=180)
        data = res.json()
        print(f"Apify Instagram 응답: {str(data)[:300]}")
        if data and len(data) > 0:
            item = data[0]
            # 릴스 커버 이미지 우선순위: thumbnailUrl → displayUrl → images[0]
            thumbnail = (
                item.get("thumbnailUrl") or
                item.get("coverImageUrl") or
                item.get("displayUrl") or
                (item.get("images") or [None])[0] or
                ""
            )
            return {
                "caption":       item.get("caption") or item.get("text") or "",
                "thumbnail_url": thumbnail,
                "owner":         item.get("ownerUsername") or "",
                "likes":         item.get("likesCount") or 0,
            }
    except Exception as e:
        print(f"Instagram 오류: {e}")
    return {}

def upload_thumbnail(image_url: str, item_id: str) -> str:
    """이미지를 Supabase Storage에 업로드 후 public URL 반환"""
    try:
        res = requests.get(image_url, timeout=30)
        if res.status_code != 200:
            return image_url
        ext = "jpg"
        content_type = res.headers.get("Content-Type", "image/jpeg")
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        file_path = f"{item_id}.{ext}"
        supabase.storage.from_("thumbnails").upload(
            file_path,
            res.content,
            {"content-type": content_type, "upsert": "true"}
        )
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/thumbnails/{file_path}"
        print(f"썸네일 업로드 완료: {public_url}")
        return public_url
    except Exception as e:
        print(f"썸네일 업로드 오류: {e}")
        return image_url

def get_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"


    m = re.search(r"\[TAGS\]\s*(.+)", summary)
    if m:
        return [t.strip() for t in m.group(1).split(",") if t.strip()][:5]
    return []

def parse_title(summary: str) -> str:
    m = re.search(r"##\s*[🚀📸]\s*(.+?)(?:\s*\(Title\))?$", summary, re.MULTILINE)
    if m:
        return m.group(1).strip().strip("[]")
    return "제목 없음"

def parse_one_line(summary: str) -> str:
    m = re.search(r"(?:핵심 비유|핵심 메시지).*?\n-\s*(.+)", summary)
    if m:
        return m.group(1).strip()
    return ""

async def summarize(content: str, prompt_template: str) -> str:
    res = await ai.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt_template.format(content=content[:12000])}]
    )
    return res.choices[0].message.content

def save_to_db(data: dict) -> str:
    res = supabase.table("youtube_summaries").insert(data).execute()
    return res.data[0]["id"] if res.data else ""

# ── 텔레그램 핸들러 ──────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    print(f"수신된 메시지: {text}")
    print(f"is_youtube: {is_youtube(text)}, is_instagram: {is_instagram(text)}")

    # ── YouTube 처리 ──────────────────────────────────
    if is_youtube(text):
        video_id = extract_video_id(text)
        if not video_id:
            await update.message.reply_text("유효한 유튜브 링크를 찾을 수 없어요 😢")
            return

        msg = await update.message.reply_text("⏳ 트랜스크립트 가져오는 중...")
        transcript = get_youtube_transcript(video_id)
        if not transcript:
            await msg.edit_text("❌ 자막/트랜스크립트를 가져올 수 없는 영상이에요.")
            return

        await msg.edit_text("🤖 AI 요약 중... (약 30초 소요)")
        try:
            summary  = await summarize(transcript, YOUTUBE_PROMPT)
            title    = parse_title(summary)
            tags     = parse_tags(summary)
            one_line = parse_one_line(summary)
            item_id  = save_to_db({
                "youtube_url":   text,
                "title":         title,
                "thumbnail_url": get_thumbnail(video_id),
                "summary_text":  summary,
                "tags":          tags,
                "video_stt_url": transcript,
                "source_type":   "youtube",
            })
            reply = f"✅ 요약 완료!\n\n📌 *{title}*\n💡 {one_line}\n🏷️ {' '.join(f'#{t}' for t in tags)}"
            if DASHBOARD_URL and item_id:
                reply += f"\n\n🔗 [대시보드에서 보기]({DASHBOARD_URL}?card={item_id})"
            await msg.edit_text(reply, parse_mode="Markdown")
        except Exception as e:
            await msg.edit_text(f"❌ 오류 발생: {e}")

    # ── Instagram 처리 ────────────────────────────────
    elif is_instagram(text):
        msg = await update.message.reply_text("⏳ 인스타그램 게시물 가져오는 중...")
        ig_data = get_instagram_data(text)
        caption = ig_data.get("caption", "")
        if not caption:
            await msg.edit_text("❌ 캐션을 가져올 수 없는 게시물이에요.")
            return

        await msg.edit_text("🤖 AI 요약 중... (약 30초 소요)")
        try:
            summary  = await summarize(caption, INSTAGRAM_PROMPT)
            title    = parse_title(summary)
            tags     = parse_tags(summary)
            one_line = parse_one_line(summary)

            # 임시 저장 후 썸네일 업로드
            item_id  = save_to_db({
                "youtube_url":   text,
                "instagram_url": text,
                "title":         title,
                "thumbnail_url": ig_data.get("thumbnail_url", ""),
                "summary_text":  summary,
                "tags":          tags,
                "video_stt_url": caption,
                "source_type":   "instagram",
            })

            # 썸네일 Supabase Storage에 업로드
            if item_id and ig_data.get("thumbnail_url"):
                public_url = upload_thumbnail(ig_data["thumbnail_url"], item_id)
                supabase.table("youtube_summaries").update(
                    {"thumbnail_url": public_url}
                ).eq("id", item_id).execute()
            reply = f"✅ 요약 완료!\n\n📸 *{title}*\n💡 {one_line}\n🏷️ {' '.join(f'#{t}' for t in tags)}"
            if DASHBOARD_URL and item_id:
                reply += f"\n\n🔗 [대시보드에서 보기]({DASHBOARD_URL}?card={item_id})"
            await msg.edit_text(reply, parse_mode="Markdown")
        except Exception as e:
            await msg.edit_text(f"❌ 오류 발생: {e}")

    else:
        await update.message.reply_text("유튜브 또는 인스타그램 링크를 보내주세요! 🎬📸")

# ── 더미 웹서버 (Railway 종료 방지) ─────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run_web():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

# ── 실행 ─────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("봇 시작!")
    app.run_polling(drop_pending_updates=True)
