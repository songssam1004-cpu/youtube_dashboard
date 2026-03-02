import streamlit as st
from supabase import create_client
import math

# ── 설정 ────────────────────────────────────────────
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

def fetch_one(item_id: str):
    client = get_client()
    res = client.table("youtube_summaries").select("*").eq("id", item_id).execute()
    return res.data[0] if res.data else None

def fetch_all_tags():
    client = get_client()
    res = client.table("youtube_summaries").select("tags").execute()
    tags = set()
    for row in res.data:
        if row.get("tags"):
            tags.update(row["tags"])
    return sorted(tags)

def delete_summary(item_id: str):
    client = get_client()
    client.table("youtube_summaries").delete().eq("id", item_id).execute()

# ── 페이지 설정 ──────────────────────────────────────
st.set_page_config(page_title="내 유튜브 요약 대시보드", layout="wide", page_icon="🎬")

# ── 전역 CSS ─────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f5f7fa; }
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e8ecf0;
}
.yt-card {
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    border: 1px solid #eef0f3;
    height: 100%;
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
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ─────────────────────────────────
for k, v in [("page", 1), ("selected", None), ("confirm_delete", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── URL 파라미터로 특정 카드 자동 오픈 ──────────────
params = st.query_params
if "card" in params and not st.session_state.selected:
    item = fetch_one(params["card"])
    if item:
        st.session_state.selected = item

# ── 상세 페이지 뷰 ───────────────────────────────────
if st.session_state.selected:
    item = st.session_state.selected

    if st.button("← 목록으로 돌아가기"):
        st.session_state.selected = None
        st.query_params.clear()
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

# ── 사이드바 ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 YT Summary")
    st.markdown("---")
    st.radio("메뉴", ["🏠 홈", "🔖 태그 탐색", "⚙️ 설정"], label_visibility="collapsed")
    st.markdown("---")
    search_q = st.text_input("🔍 제목 검색", placeholder="검색어 입력...")
    all_tags = fetch_all_tags()
    selected_tag = ""
    if all_tags:
        tag_choice = st.selectbox("🏷️ 태그 필터", ["전체"] + all_tags)
        selected_tag = "" if tag_choice == "전체" else tag_choice
    st.markdown("---")
    st.button("👤 로그인", use_container_width=True)
    st.button("✨ 회원가입", use_container_width=True, type="primary")

# ── 검색/필터 변경 시 페이지 리셋 ────────────────────
for k, v in [("prev_search", ""), ("prev_tag", "")]:
    if k not in st.session_state:
        st.session_state[k] = v
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

# ── 카드 그리드 ──────────────────────────────────────
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
                tags  = item.get("tags") or []
                date  = (item.get("created_at") or "")[:10]

                thumb_html = (
                    f'<img class="yt-thumb" src="{thumb}">'
                    if thumb else
                    '<div class="yt-thumb-placeholder">🎬</div>'
                )
                tags_html = "".join(f'<span class="yt-tag">#{t}</span>' for t in tags[:5])

                st.markdown(f"""
                <div class="yt-card">
                    {thumb_html}
                    <div class="yt-body">
                        <div class="yt-title">{title}</div>
                        <div class="yt-tags">{tags_html}</div>
                        <div class="yt-date">📅 {date}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                col_detail, col_del = st.columns([3, 1])
                with col_detail:
                    if st.button("자세히 보기", key=f"btn_{item['id']}", use_container_width=True):
                        st.session_state.selected = item
                        st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"del_{item['id']}", use_container_width=True):
                        st.session_state.confirm_delete = item['id']
                        st.rerun()

                if st.session_state.confirm_delete == item['id']:
                    st.warning("정말 삭제할까요?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ 확인", key=f"yes_{item['id']}", use_container_width=True):
                            delete_summary(item['id'])
                            st.session_state.confirm_delete = None
                            st.rerun()
                    with c2:
                        if st.button("❌ 취소", key=f"no_{item['id']}", use_container_width=True):
                            st.session_state.confirm_delete = None
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
