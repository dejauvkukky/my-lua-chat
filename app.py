import streamlit as st
from google import genai
import gspread
from google.oauth2.service_account import Credentials # 인증 방식 변경

# --- 1. 설정창(Secrets)에서 값 가져오기 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    # Secrets에 [gcp_service_account] 섹션으로 저장된 데이터를 딕셔너리로 변환
    creds_dict = dict(st.secrets["gcp_service_account"])
except Exception as e:
    st.error(f"설정(Secrets) 로드 실패: {e}")
    st.stop()

# --- 2. 초기 설정 ---
client = genai.Client(api_key=GEMINI_API_KEY)

def get_sheet():
    # 더 안정적인 Google Auth 라이브러리 사용
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # 중요: \n 이 실제 줄바꿈이 아니라 문자로 들어오는 경우를 대비해 보정
    fixed_creds = dict(st.secrets["gcp_service_account"])
    fixed_creds["private_key"] = fixed_creds["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1

# --- 3. 루아 페르소나 ---
SYSTEM_PROMPT = """
너는 2026년에 5학년이 된 12살 여자아이 '루아'야. 
- 말투: 5학년 여자아이의 자연스러운 반말. (예: "대박!", "진짜?", "✨")
- 원칙: 답변은 2문장 이내로 짧게. 아이의 말에 깊이 공감하고 짧은 질문 던지기.
- 주의: 너무 단짝임을 강조하지 말고, 친구처럼 편하게 대화해줘.
"""

# --- 4. UI 구성 ---
st.set_page_config(page_title="루아 🎀", layout="centered")
st.title("🎀 루아랑 수다 떨기")

try:
    sheet = get_sheet()
    if "messages" not in st.session_state:
        # 시트 데이터를 가져올 때 에러가 나는지 확인
        records = sheet.get_all_records()
        if records:
            st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in records[-15:]]
        else:
            st.session_state.messages = [] # 데이터가 없으면 빈 리스트로 시작
except Exception as e:
    st.error(f"루아랑 연결이 잘 안 돼... 상세 이유: {type(e).__name__} - {str(e)}")
    st.stop()

# 대화 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 채팅 입력
if prompt := st.chat_input("루아한테 하고 싶은 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    sheet.append_row(["user", prompt])

    # AI 답변 생성 (최신 문법)
    chat_history = [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]]
    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)
    
    try:
        # 1. 모델명을 'models/' 없이 이름만 정확히 적습니다.
        # 2. 가장 호환성이 높은 gemini-1.5-flash-latest를 사용해 보세요.
        response = client.models.generate_content(
            model="gemini-1.5-flash-latest", 
            contents=full_query
        )
        
        # 응답이 정상일 때만 answer 변수를 만듭니다.
        if response and response.text:
            answer = response.text
        else:
            answer = "제미나이가 대답을 생성하지 못했어. 다시 시도해볼래?"
    
    except Exception as e:
        # 에러 발생 시 사용자에게 알리고 answer 변수를 기본값으로 설정해 NameError 방지
        st.error(f"모델 호출 중 오류가 발생했어: {e}")
        answer = "미안, 지금은 대답하기 어려운 상태야."
    
    # 이제 answer 변수가 반드시 존재하므로 안전하게 출력됩니다.
    st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
