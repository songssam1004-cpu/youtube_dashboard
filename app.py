import streamlit as st
from supabase import create_client
import math

# ── 설정 ────────────────────────────────────────────
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["anon_key"]
COLS = 5
ROWS = 3
PAGE_SIZE = COLS * ROWS

# ── Supabase 클라이언트 ──────────────────────────────
@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_summaries(page, search="", tag=""):
    client = get_client()
    offset = (page - 1) * PAGE_SIZE
    q = client.table("youtube_summaries").select("*", count="exact")
    if search:
        q = q.ilike("title", f"%{search}%")
    if tag:
        q = q.contains("tags", [tag])
    res = q.order("created_at", desc=True).range(offset, offset + PAGE_SIZE - 1).execute()
    return res.data, res.count

def fetch_all_tags():
    client = get_client()
    res = client.table("youtube_summaries").select("tags").execute()
    tags = set()
    for row in res.data:
        if row.get("tags"):
            tags.update(row["tags"])
    return sorted(tags)

# ── 페이지 설정 ──────────────────────────────────────
st.set_page_config(page_title="내 유튜브 요약 대시보드", layout="wide", page_icon="🎬")

# ── 전역 CSS ─────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0f0f13; color: #e0e0e0; }
[data-testid="stMain"] { background: #0f0f13; }
[data-testid="stSidebar"] {
    background: #1a1a24 !important;
    border-right: 1px solid #2a2a3a;
    min-width: 220px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: #2a2a3a !important;
    color: #e0e0e0 !important;
    border: 1px solid #3a3a4a !important;
}
h1, h2, h3, h4 { color: #ffffff !important; }
p, span, label { color: #c0c0c0 !important; }

.yt-card {
    background: #1e1e2a;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    border: 1px solid #2a2a3a;
    margin-bottom: 8px;
}
.yt-thumb {
    width: 100%;
    aspect-ratio: 16/9;
    object-fit: cover;
    display: block;
}
.yt-thumb-placeholder {
    width: 100%;
    aspect-ratio: 16/9;
    background: linear-gradient(135deg, #2d2b55 0%, #1a1a2e 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
}
.yt-body { padding: 10px 12px 12px; }
.yt-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: #e8e8f0 !important;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    margin-bottom: 6px;
    min-height: 2.3em;
}
.yt-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.yt-tag {
    background: #2d2b55;
    color: #a78bfa !important;
    font-size: 0.68rem;
    padding: 2px 7px;
    border-radius: 20px;
    font-weight: 500;
    border: 1px solid #3d3b75;
}
.yt-date { font-size: 0.68rem; color: #666688 !important; }

.stButton button {
    background: #2d2b55 !important;
    color: #a78bfa !important;
    border: 1px solid #3d3b75 !important;
    border-radius: 8px !important;
    font-size: 0.75rem !important;
    transition: all .15s !important;
    width: 100%;
}
.stButton button:hover {
    background: #3d3b75 !important;
    border-color: #a78bfa !important;
    color: #ffffff !important;
}
.stTabs [data-baseweb="tab-list"] { background: #1e1e2a; border-bottom: 1px solid #2a2a3a; }
.stTabs [data-baseweb="tab"] { color: #888 !important; }
.stTabs [aria-selected="true"] { color: #a78bfa !important; border-bottom: 2px solid #a78bfa !important; }
.stTextArea textarea { background: #1e1e2a !important; color: #e0e0e0 !important; border: 1px solid #2a2a3a !important; }
hr { border-color: #2a2a3a !important; }
.stCaption { color: #666688 !important; }
.detail-box {
    background: #1e1e2a;
    border-radius: 12px;
    padding: 24px;
    border: 1px solid #2a2a3a;
    margin-top: 16px;
}
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ─────────────────────────────────
for k, v in [("page", 1), ("selected_id", None), ("prev_search", ""), ("prev_tag", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── 사이드바 ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 YT Summary")
    st.markdown("---")

    # 상세 보기 중이면 목록으로 돌아가기 버튼
    if st.session_state.selected_id:
        if st.button("← 목록으로", use_container_width=True):
            st.session_state.selected_id = None
            st.rerun()
        st.markdown("---")

    search_q = st.text_input("🔍 제목 검색", placeholder="검색어 입력...")
    all_tags = fetch_all_tags()
    selected_tag = ""
    if all_tags:
        tag_options = ["전체"] + all_tags
        tag_choice = st.selectbox("🏷️ 태그 필터", tag_options)
        selected_tag = "" if tag_choice == "전체" else tag_choice
    st.markdown("---")
    st.caption("🎬 나만의 유튜브 요약 대시보드")

# ── 검색/필터 변경 시 페이지 리셋 ────────────────────
if search_q != st.session_state.prev_search or selected_tag != st.session_state.prev_tag:
    st.session_state.page = 1
    st.session_state.selected_id = None
    st.session_state.prev_search = search_q
    st.session_state.prev_tag = selected_tag

# ══════════════════════════════════════════════════════
# 상세 보기 화면
# ══════════════════════════════════════════════════════
if st.session_state.selected_id:
    client = get_client()
    res = client.table("youtube_summaries").select("*").eq("id", st.session_state.selected_id).execute()
    if res.data:
        item = res.data[0]

        # 뒤로가기 버튼
        if st.button("← 목록으로 돌아가기"):
            st.session_state.selected_id = None
            st.rerun()

        st.markdown(f"## 📺 {item.get('title', '제목 없음')}")

        col_thumb, col_info = st.columns([1, 2])
        with col_thumb:
            if item.get("thumbnail_url"):
                st.image(item["thumbnail_url"], use_container_width=True)
        with col_info:
            tags = item.get("tags") or []
            if tags:
                st.markdown(" ".join(f"`#{t}`" for t in tags))
            st.markdown(f"📅 {(item.get('created_at') or '')[:10]}")
            if item.get("youtube_url"):
                st.markdown(f"[▶ YouTube에서 보기]({item['youtube_url']})")

        st.markdown("---")
        tab1, tab2 = st.tabs(["📝 AI 요약", "📄 전체 STT"])
        with tab1:
            st.markdown(item.get("summary_text") or "_요약 내용이 없습니다._")
        with tab2:
            st.text_area("전체 스크립트", item.get("video_stt_url") or "_STT 내용이 없습니다._", height=400)

    st.stop()

# ══════════════════════════════════════════════════════
# 목록 화면
# ══════════════════════════════════════════════════════
data, total = fetch_summaries(st.session_state.page, search_q, selected_tag)
total_pages = max(1, math.ceil((total or 0) / PAGE_SIZE))

st.markdown("### 📺 나의 유튜브 요약 대시보드")
st.caption(f"총 {total or 0}개의 요약 · {st.session_state.page}/{total_pages} 페이지")
st.markdown("---")

if not data:
    st.info("저장된 요약이 없습니다. 텔레그램 봇에 유튜브 링크를 보내보세요! 🚀")
else:
    for row_idx in range(ROWS):
        cols = st.columns(COLS, gap="medium")
        for col_idx in range(COLS):
            item_idx = row_idx * COLS + col_idx
            if item_idx >= len(data):
                break
            item = data[item_idx]
            with cols[col_idx]:
                thumb    = item.get("thumbnail_url", "")
                title    = item.get("title") or "제목 없음"
                tags     = item.get("tags") or []
                date_str = (item.get("created_at") or "")[:10]

                thumb_html = (
                    f'<img class="yt-thumb" src="{thumb}" onerror="this.style.display=\'none\'">'
                    if thumb else '<div class="yt-thumb-placeholder">🎬</div>'
                )
                tags_html = "".join(f'<span class="yt-tag">#{t}</span>' for t in tags[:3])

                st.markdown(f"""
                <div class="yt-card">
                    {thumb_html}
                    <div class="yt-body">
                        <div class="yt-title">{title}</div>
                        <div class="yt-tags">{tags_html}</div>
                        <div class="yt-date">📅 {date_str}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("자세히 보기", key=f"btn_{item['id']}", use_container_width=True):
                    st.session_state.selected_id = item["id"]
                    st.rerun()

# ── 페이지네이션 ─────────────────────────────────────
st.markdown("---")
if total_pages > 1:
    pg_cols = st.columns([1, 6, 1])
    with pg_cols[0]:
        if st.button("◀ 이전", disabled=st.session_state.page <= 1):
            st.session_state.page -= 1
            st.rerun()
    with pg_cols[1]:
        start    = max(1, st.session_state.page - 3)
        end      = min(total_pages, start + 6)
        btn_cols = st.columns(end - start + 1)
        for i, pg in enumerate(range(start, end + 1)):
            with btn_cols[i]:
                label = f"**{pg}**" if pg == st.session_state.page else str(pg)
                if st.button(label, key=f"pg_{pg}"):
                    st.session_state.page = pg
                    st.rerun()
    with pg_cols[2]:
        if st.button("다음 ▶", disabled=st.session_state.page >= total_pages):
            st.session_state.page += 1
            st.rerun()
