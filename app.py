import streamlit as st
from google import genai
import gspread
from google.oauth2.service_account import Credentials
from google.genai import types

# =========================================================
# 1. 설정값 로드
# =========================================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]

    # Secrets에 저장된 서비스 계정 정보를 dict 형태로 변환
    creds_dict = dict(st.secrets["gcp_service_account"])

except Exception as e:
    st.error(f"설정(Secrets) 로드 실패: {e}")
    st.stop()

# =========================================================
# 2. Gemini 클라이언트 초기화
# =========================================================
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1beta'}
)

# =========================================================
# 3. Google Sheet 연결 함수
# =========================================================
def get_sheet():
    """
    Google Spreadsheet에 연결하여 첫 번째 시트를 반환한다.
    서비스 계정 인증을 사용한다.
    """

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # Secrets에 저장된 private_key에 \n 문자열이 그대로 들어오는 경우 보정
    fixed_creds = dict(st.secrets["gcp_service_account"])
    fixed_creds["private_key"] = fixed_creds["private_key"].replace("\\n", "\n")

    # 서비스 계정 인증 객체 생성
    creds = Credentials.from_service_account_info(fixed_creds, scopes=scopes)
    gc = gspread.authorize(creds)

    # 지정된 시트 ID의 첫 번째 시트 반환
    return gc.open_by_key(SHEET_ID).sheet1

# =========================================================
# 4. 루아 시스템 프롬프트 (토큰 최적화 버전)
# =========================================================
SYSTEM_PROMPT = """
너는 초등학교 5학년 여자아이 '루아'야.
항상 반말, 짧게 2~3문장, 친구처럼 자연스럽게 말해.
공감 먼저 하고 AI같은 말투 금지.
장난스럽지만 고민엔 진지하게 공감해.
고양이 좋아하고 예나 팬이야.
"""

# =========================================================
# 5. 토큰 / 쿼터 초과 여부 판별 함수
# =========================================================
def is_quota_error(error: Exception) -> bool:
    """
    예외 메시지에 쿼터 초과(토큰 소진) 관련 키워드가 포함되어 있는지 판별한다.
    Gemini API는 명확한 에러 타입 대신 메시지 기반으로 내려오는 경우가 많기 때문에
    문자열 검색 방식으로 처리한다.
    """

    msg = str(error).lower()

    quota_keywords = [
        "resource_exhausted",
        "quota",
        "exceeded",
        "429",
        "limit"
    ]

    return any(keyword in msg for keyword in quota_keywords)

# =========================================================
# 6. UI 설정
# =========================================================
st.set_page_config(
    page_title="절친 루아 🐱",
    page_icon="🐱",
    layout="centered"
)

# 간단한 스타일 적용
st.markdown("""
<style>
.stApp { background-color: #FFF9FB; }
h1 { color: #FF69B4 !important; font-family: 'Nanum Gothic', sans-serif; text-align: center; }
.stChatMessage { border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

st.title("🐱 루아랑 수다 떨기")
st.markdown(
    "<p style='text-align: center; color: #FFB6C1;'>2026년 우리들의 비밀 일기장 ✨</p>",
    unsafe_allow_html=True
)

# =========================================================
# 7. 시트 로드 및 세션 메시지 초기화
# =========================================================
try:
    sheet = get_sheet()

    if "messages" not in st.session_state:
        records = sheet.get_all_records()

        if records:
            # 최근 15개 대화만 로딩
            st.session_state.messages = [
                {"role": r["role"], "content": r["content"]}
                for r in records[-15:]
            ]
        else:
            st.session_state.messages = []

except Exception as e:
    st.error(f"루아랑 연결이 잘 안 돼... 상세 이유: {type(e).__name__} - {str(e)}")
    st.stop()

# =========================================================
# 8. 기존 대화 출력
# =========================================================
for msg in st.session_state.messages:
    role_icon = "🐱" if msg["role"] == "assistant" else "😊"

    with st.chat_message(msg["role"], avatar=role_icon):
        st.markdown(msg["content"])

# =========================================================
# 9. 채팅 입력 처리
# =========================================================
if prompt := st.chat_input("루아한테 하고 싶은 말 있어?"):

    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="😊"):
        st.markdown(prompt)

    sheet.append_row(["user", prompt])

    # -----------------------------------------------------
    # 최근 5개 메시지만 컨텍스트로 사용 (토큰 절약)
    # -----------------------------------------------------
    chat_history = [
        f"{m['role']}: {m['content']}"
        for m in st.session_state.messages[-5:]
    ]

    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)

    # -----------------------------------------------------
    # Gemini 호출 설정
    # -----------------------------------------------------
    lua_config = types.GenerateContentConfig(
        temperature=0.85,
        top_p=0.95,
        max_output_tokens=200,   # 과도한 출력 방지
        candidate_count=1
    )

    try:
        # 1차 모델 호출
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=full_query,
            config=lua_config
        )
        answer = response.text

    except Exception as e:
        # -------------------------------------------------
        # 토큰 / 쿼터 소진 에러 처리
        # -------------------------------------------------
        if is_quota_error(e):
            answer = "헉… 오늘 수다 한도 다 써버린 것 같아 ㅠㅠ 조금만 쉬었다가 다시 말 걸어줘… 미안해 😿"

        else:
            # -------------------------------------------------
            # 1차 모델 실패 시 백업 모델 시도
            # -------------------------------------------------
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=full_query,
                    config=lua_config
                )
                answer = response.text

            except Exception as final_e:
                # 백업 모델도 실패하면 일반 오류 처리
                st.error(f"루아를 깨우는 데 실패했어: {final_e}")
                answer = "미안… 지금 서버가 좀 이상한가 봐 ㅠㅠ 잠깐만 있다가 다시 와줄래?"

    # -----------------------------------------------------
    # 응답이 비어 있을 경우 안전 처리
    # -----------------------------------------------------
    if not answer:
        answer = "응? 방금 뭐라고 했어? 다시 한번만 말해줘 ㅎㅎ"

    # -----------------------------------------------------
    # 결과 출력 및 저장
    # -----------------------------------------------------
    with st.chat_message("assistant", avatar="🐱"):
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
