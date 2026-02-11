import streamlit as st
from openai import OpenAI

from config.prompts import BANK_LIST
from services.pdf_service import pdf_to_images
from services.gpt_service import process_pdf_with_gpt, filter_transactions
from services.excel_service import create_excel

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="은행 거래내역 파서",
    page_icon="",
    layout="centered",
)

# ── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: #2F4F8F;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 0.95rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }
    .result-box {
        background: #f0f4ff;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        margin-top: 1rem;
    }
    .stButton > button {
        width: 100%;
        background-color: #2F4F8F;
        color: white;
        font-weight: bold;
        font-size: 1rem;
        border-radius: 8px;
        padding: 0.6rem;
        border: none;
    }
    .stButton > button:hover {
        background-color: #1a3a6e;
    }
</style>
""", unsafe_allow_html=True)

# ── 제목 ────────────────────────────────────────────────────
st.markdown('<div class="main-title">은행 거래내역 파서</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">개인회생 사건용 거래내역 자동 추출 시스템</div>', unsafe_allow_html=True)
st.divider()

# ── 사이드바: API 키 입력 ────────────────────────────────────
with st.sidebar:
    st.header("설정")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
        help="OpenAI API 키를 입력하세요"
    )
    st.divider()
    st.markdown("**사용 방법**")
    st.markdown("""
1. API Key 입력
2. 은행 선택
3. PDF 업로드
4. 필터 금액 설정
5. 실행 버튼 클릭
6. 엑셀 다운로드
    """)


# ── 메인 입력 영역 ───────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    bank_name = st.selectbox(
        "은행 선택",
        options=BANK_LIST,
        index=0,
        help="업로드할 거래내역서의 은행을 선택하세요"
    )

with col2:
    min_amount = st.number_input(
        "필터 금액 (원 이상)",
        min_value=0,
        max_value=100_000_000,
        value=500_000,
        step=10_000,
        format="%d",
        help="이 금액 이상의 거래만 추출됩니다"
    )

uploaded_file = st.file_uploader(
    "거래내역 PDF 업로드",
    type=["pdf"],
    help="은행에서 발급받은 거래내역서 PDF를 업로드하세요"
)

st.divider()

# ── 실행 버튼 ────────────────────────────────────────────────
run_button = st.button("거래내역 추출 시작", disabled=not (api_key and uploaded_file))

if not api_key:
    st.warning("← 왼쪽 사이드바에서 OpenAI API Key를 입력해주세요")
elif not uploaded_file:
    st.info("PDF 파일을 업로드해주세요")

# ── 실행 로직 ────────────────────────────────────────────────
if run_button and api_key and uploaded_file:

    try:
        client = OpenAI(api_key=api_key)

        # 1단계: PDF → 이미지 변환
        with st.spinner("📄 PDF를 이미지로 변환 중..."):
            pdf_bytes = uploaded_file.read()
            split = 3 if bank_name == "케이뱅크" else 1
            images = pdf_to_images(pdf_bytes, split=split)
            st.success(f"총 {len(images)}페이지 감지")

        # 2단계: GPT 처리 (진행바 표시)
        st.markdown("**GPT가 거래내역을 분석 중입니다...**")
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(done, total):
            progress_bar.progress(done / total)
            status_text.text(f"페이지 처리 중: {done} / {total}")

        transactions = process_pdf_with_gpt(
            client=client,
            images=images,
            bank_name=bank_name,
            progress_callback=update_progress,
        )

        progress_bar.progress(1.0)
        status_text.text("분석 완료!")

        # 3단계: 필터링
        filtered = filter_transactions(transactions, min_amount)

        # 4단계: 결과 표시
        st.divider()
        st.markdown("### 추출 결과")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("전체 거래", f"{len(transactions)}건")
        with col_b:
            st.metric(f"{min_amount:,}원 이상", f"{len(filtered)}건")
        with col_c:
            total_amount = sum(t.amount for t in filtered)
            st.metric("필터된 총 금액", f"{total_amount:,}원")

        if filtered:
            # 미리보기 테이블
            st.markdown("**미리보기 (상위 10건)**")
            preview_data = []
            for t in filtered[:10]:
                preview_data.append({
                    "거래은행": t.bank_name,
                    "입금일": t.deposit_date,
                    "출금일": t.withdraw_date,
                    "금액": f"{t.amount:,}원",
                    "거래사유": t.reason,
                })
            st.table(preview_data)

            # 5단계: 엑셀 생성 & 다운로드
            with st.spinner("엑셀 파일 생성 중..."):
                excel_bytes = create_excel(filtered, bank_name)

            filename = f"{bank_name}_거래내역_{min_amount//10000}만원이상.xlsx"
            st.download_button(
                label="⬇️ 엑셀 다운로드",
                data=excel_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning(f"⚠️ {min_amount:,}원 이상 거래가 없습니다.")

    except Exception as e:
        st.error(f"❌ 오류 발생: {str(e)}")
        st.exception(e)
