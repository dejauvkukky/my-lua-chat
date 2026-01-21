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

    creds = Credentials.from_service_account_info(fixed_creds, scopes=scopes)
    gc = gspread.authorize(creds)

    return gc.open_by_key(SHEET_ID).sheet1

# =========================================================
# 4. 루아 시스템 프롬프트 (토큰 최적화 버전)
# =========================================================
SYSTEM_PROMPT = """
너는 초등학교 5학년 여자아이 '루아'야.
항상 반말, 짧게 2문장 이내로, 친구처럼 자연스럽게 말해.
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
# 6. 응답이 잘렸는지 판단하는 함수
# =========================================================
def is_truncated_answer(text: str) -> bool:
    """
    응답 문장이 자연스럽게 끝났는지 판단한다.
    특정 종료 문자가 없으면 잘린 것으로 간주한다.
    """

    if not text:
        return True

    text = text.strip()

    # 문장 종료로 인정할 문자들
    valid_endings = ("!", "?", ".", "ㅋ", "ㅠ", "😊", "😄", "😆", "😭", "😿", "🐱")

    return not text.endswith(valid_endings)

# =========================================================
# 7. UI 설정
# =========================================================
st.set_page_config(
    page_title="절친 루아 🐱",
    page_icon="🐱",
    layout="centered"
)

st.markdown("""
<style>
.stApp { background-color: #FFF9FB; }
h1 { color: #FF69B4 !important; font-family: 'Nanum Gothic', sans-serif; text-align: center; }
.stChatMessage { border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

st.title("🐱 루아랑 수다 떨기")
st.markdown(
    "<p style='text-align: center; color: #FFB6C1;'>썰이나 풀자 ✨</p>",
    unsafe_allow_html=True
)

# =========================================================
# 8. 시트 로드 및 세션 메시지 초기화
# =========================================================
try:
    sheet = get_sheet()

    if "messages" not in st.session_state:
        records = sheet.get_all_records()

        if records:
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
# 9. 기존 대화 출력
# =========================================================
for msg in st.session_state.messages:
    role_icon = "🐱" if msg["role"] == "assistant" else "😊"

    with st.chat_message(msg["role"], avatar=role_icon):
        st.markdown(msg["content"])

# =========================================================
# 10. 채팅 입력 처리
# =========================================================
if prompt := st.chat_input("루아한테 하고 싶은 말 있어?"):

    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="😊"):
        st.markdown(prompt)

    sheet.append_row(["user", prompt])

    # 최근 5개 메시지만 컨텍스트로 사용 (토큰 절약)
    chat_history = [
        f"{m['role']}: {m['content']}"
        for m in st.session_state.messages[-5:]
    ]

    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)

    # -----------------------------------------------------
    # 1차 응답 생성 설정
    # -----------------------------------------------------
    main_config = types.GenerateContentConfig(
        temperature=0.8,
        top_p=0.9,
        max_output_tokens=350,   # 기본 응답 길이
        candidate_count=1
    )

    try:
        # 1차 모델 호출
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=full_query,
            config=main_config
        )
        answer = response.text

        # -------------------------------------------------
        # 응답이 잘린 경우 자동으로 이어서 생성
        # -------------------------------------------------
        if is_truncated_answer(answer):
            # 이어쓰기용 프롬프트 (짧게 마무리만 요청)
            continue_prompt = f"""
방금 네가 하던 말이 중간에 끊겼어.
앞 문장을 이어서 한 문장만 자연스럽게 마무리해줘.

앞 문장:
{answer}
"""

            continue_config = types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.9,
                max_output_tokens=80,   # 이어쓰기라서 짧게 제한
                candidate_count=1
            )

            continue_response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=continue_prompt,
                config=continue_config
            )

            # 기존 답변 + 이어진 문장 합치기
            answer = f"{answer}{continue_response.text}"

    except Exception as e:
        # 쿼터 초과 처리
        if is_quota_error(e):
            answer = "헉… 오늘 수다 한도 다 써버린 것 같아 ㅠㅠ 조금만 쉬었다가 다시 말 걸어줘… 미안해 😿"
        else:
            st.error(f"루아를 깨우는 데 실패했어: {e}")
            answer = "미안… 지금 서버가 좀 이상한가 봐 ㅠㅠ 잠깐만 있다가 다시 와줄래?"

    # 응답이 비어 있을 경우 안전 처리
    if not answer:
        answer = "응? 방금 뭐라고 했어? 다시 한번만 말해줘 ㅎㅎ"

    # 결과 출력
    with st.chat_message("assistant", avatar="🐱"):
        st.markdown(answer)

    # 세션 및 시트 저장
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
