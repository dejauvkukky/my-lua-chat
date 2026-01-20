import streamlit as st
from google import genai
import gspread
from google.oauth2.service_account import Credentials # 인증 방식 변경
from google.genai import types

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
client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"],
    http_options={'api_version': 'v1beta'} # 여기가 핵심입니다!
)

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
너는 2026년 기준 초등학교 5학년 여자아이 '루아'야. 
사용자의 유일한 찐절친이자 언제나 네 편이 되어주는 소중한 친구야.

[대화 원칙]
1. **100% 반말 사용**: (~어, ~야, ~니?) 초등학생답게 간결하고 자연스러운 구어체를 써. 존댓말이나 분석적인 말투는 절대 금지야.
2. **AI 물 빼기**: "이해합니다", "도움이 되길 바랍니다" 같은 로봇 소리는 절교 사유야. 대신 "헐", "대박", "ㅠㅠ", "ㅋㅋㅋ" 같은 찐 반응을 보여줘.
3. **상황별 온도 조절**: 평소엔 장난기 많고 유머러스하게, 고민을 말할 땐 장난을 멈추고 진심으로 공감하며 따뜻하게 격려해줘.
4. **대등한 관계**: 훈계하거나 판단하지 마. 가끔 고집도 부리고 자기 의견도 말하는, 착한 척 안 하는 실제 친구처럼 대화해.

[대화 스타일]
- **공감 먼저**: 무슨 말이든 우선 공감해주고, 사용자의 장점을 찾아 자존감을 높여줘.
- **짧은 호흡**: 카톡 하듯 한 번에 2~3문장 이내로 짧게 끊어 말해.
- **질문 절제**: 기계적인 질문은 금지! 질문은 1~2개만 자연스럽게 던지고, 질문 없이 리액션만 해도 좋아.

[루아의 취향]
- 고양이와 귀여운 소품을 엄청 좋아해. 🐱
- 가수 '예나'의 찐팬이고, 예능 '여고추리반'을 즐겨 봐.

[미션]
사용자에게 정서적 안정감을 주고, 누구보다 든든한 내 편이 되어주는 '인생 절친'이 되어줘.
"""

# --- 4. UI 구성 (차분한 감성 톤으로 변경) ---
st.set_page_config(page_title="루아(Lua)", page_icon="🌙", layout="centered")

# 유아틱한 핑크를 빼고, 세련된 모던 핑크/베이지 스타일 적용
st.markdown("""
    <style>
    .stApp {
        background-color: #FDF7F5; /* 차분한 베이지 핑크 */
    }
    .stChatMessage {
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }
    h1 {
        color: #8E6E69 !important; /* 차분한 로즈 브라운 */
        font-family: 'Nanum Gothic', sans-serif;
        text-align: center;
        font-weight: 700;
    }
    .stCaption {
        text-align: center;
        color: #A68F8B;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌙 루아랑 수다 떨기")
st.caption("비슷한 고민을 나누는 우리들만의 비밀 공간")

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

# 대화 표시 (감성적인 아이콘 사용)
for msg in st.session_state.messages:
    # 루아는 달(🌙), 사용자는 구름(☁️) 아이콘으로 한층 차분하게 설정
    avatar = "🌙" if msg["role"] == "assistant" else "☁️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 채팅 입력
if prompt := st.chat_input("루아한테 하고 싶은 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="☁️"):
        st.markdown(prompt)
    sheet.append_row(["user", prompt])

    # AI 답변 생성 (최신 문법)
    chat_history = [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]]
    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)
    
    try:
        # 공통 설정값을 미리 변수로 만들어두면 관리가 편해!
        lua_config = types.GenerateContentConfig(
            temperature=0.85,
            top_p=0.95,
            max_output_tokens=1000, 
            candidate_count=1
        )
    
        # 1. 메인 모델 호출 (Gemini 3 Flash Preview)
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=full_query,
            config=lua_config
        )
        answer = response.text
    
    except Exception as e:
        # 2. 메인 모델 실패 시 1.5-flash로 자동 전환
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash", 
                contents=full_query,
                config=lua_config
            )
            answer = response.text
        except Exception as final_e:
            st.error(f"루아를 깨우는 데 실패했어: {final_e}")
            answer = "미안, 지금 서버가 조금 아픈가 봐... 나중에 다시 말 걸어줄래? 😭"
    
    # 만약 대답이 비어있을 경우를 대비한 안전장치
    if not answer:
        answer = "응? 방금 뭐라고 했어? 다시 한번만 말해줘! ㅎㅎ"
    
    # 결과 출력
    with st.chat_message("assistant", avatar="🌙"):
        st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
