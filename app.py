import streamlit as st
from supabase import create_client
import math

# ── 설정 (Streamlit secrets에서 로드) ───────────────
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["anon_key"]
COLS = 5
ROWS = 3
PAGE_SIZE = COLS * ROWS  # 15

# ── Supabase 클라이언트 ──────────────────────────────
@st.cache_resource
def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_summaries(page: int, search: str = "", tag: str = ""):
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
/* 전체 배경 */
[data-testid="stAppViewContainer"] { background: #f5f7fa; }

/* 사이드바 */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e8ecf0;
    min-width: 220px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] .stMarkdown h2 { color: #1a1a2e; }

/* 카드 */
.yt-card {
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    cursor: pointer;
    transition: transform .18s, box-shadow .18s;
    border: 1px solid #eef0f3;
    height: 100%;
}
.yt-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.13);
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
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
}
.yt-body { padding: 10px 12px 12px; }
.yt-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: #1a1a2e;
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
    background: #eef2ff;
    color: #4f46e5;
    font-size: 0.68rem;
    padding: 2px 7px;
    border-radius: 20px;
    font-weight: 500;
}
.yt-date { font-size: 0.68rem; color: #9ca3af; }

/* 페이지네이션 */
.pagination { display: flex; justify-content: center; gap: 8px; margin-top: 24px; }
.page-btn {
    padding: 6px 14px;
    border-radius: 8px;
    border: 1px solid #d1d5db;
    background: #fff;
    cursor: pointer;
    font-size: 0.85rem;
    color: #374151;
}
.page-btn.active {
    background: #4f46e5;
    color: #fff;
    border-color: #4f46e5;
    font-weight: 600;
}

/* 모달 오버레이 */
.modal-backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 999;
    display: flex; align-items: center; justify-content: center;
}
.modal-box {
    background: #fff;
    border-radius: 16px;
    padding: 32px;
    max-width: 720px;
    width: 90%;
    max-height: 85vh;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ─────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = 1
if "selected" not in st.session_state:
    st.session_state.selected = None
if "show_stt" not in st.session_state:
    st.session_state.show_stt = False

# ── 사이드바 (고정 네비게이션) ───────────────────────
with st.sidebar:
    st.markdown("## 🎬 YT Summary")
    st.markdown("---")

    menu = st.radio("메뉴", ["🏠 홈", "🔖 태그 탐색", "⚙️ 설정"], label_visibility="collapsed")
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
if "prev_search" not in st.session_state:
    st.session_state.prev_search = ""
if "prev_tag" not in st.session_state:
    st.session_state.prev_tag = ""
if search_q != st.session_state.prev_search or selected_tag != st.session_state.prev_tag:
    st.session_state.page = 1
    st.session_state.prev_search = search_q
    st.session_state.prev_tag = selected_tag

# ── 데이터 로드 ──────────────────────────────────────
data, total = fetch_summaries(st.session_state.page, search_q, selected_tag)
total_pages = max(1, math.ceil((total or 0) / PAGE_SIZE))

# ── 헤더 ─────────────────────────────────────────────
st.markdown("### 📺 나의 유튜브 요약 대시보드")
st.caption(f"총 {total or 0}개의 요약 · {st.session_state.page}/{total_pages} 페이지")
st.markdown("---")

# ── 카드 그리드 (5열 × 3행) ─────────────────────────
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
                thumb = item.get("thumbnail_url", "")
                title = item.get("title") or "제목 없음"
                tags = item.get("tags") or []
                date_str = (item.get("created_at") or "")[:10]

                thumb_html = (
                    f'<img class="yt-thumb" src="{thumb}" onerror="this.style.display=\'none\'">'
                    if thumb else
                    '<div class="yt-thumb-placeholder">🎬</div>'
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
                    st.session_state.selected = item
                    st.session_state.show_stt = False
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
        # 페이지 번호 버튼 (최대 7개 표시)
        start = max(1, st.session_state.page - 3)
        end = min(total_pages, start + 6)
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

# ── 상세 모달 ─────────────────────────────────────────
if st.session_state.selected:
    item = st.session_state.selected
    with st.container():
        st.markdown("---")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"## 📺 {item.get('title', '제목 없음')}")
        with c2:
            if st.button("✕ 닫기", key="close_modal"):
                st.session_state.selected = None
                st.rerun()

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

        # 요약 탭 / STT 탭
        tab1, tab2 = st.tabs(["📝 AI 요약", "📄 전체 STT"])
        with tab1:
            summary = item.get("summary_text") or "_요약 내용이 없습니다._"
            st.markdown(summary)
        with tab2:
            stt = item.get("video_stt_url") or "_STT 내용이 없습니다._"
            st.text_area("전체 스크립트", stt, height=400)
