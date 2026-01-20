import streamlit as st
from google import genai
import gspread
from google.oauth2.service_account import Credentials
from google.genai import types

# --- 1. 설정창(Secrets) 로드 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    creds_dict = dict(st.secrets["gcp_service_account"])
except Exception as e:
    st.error(f"설정(Secrets) 로드 실패: {e}")
    st.stop()

# --- 2. 초기 설정 및 캐싱 ---
# 502 에러 방지를 위해 클라이언트 생성을 캐싱함
@st.cache_resource
def get_client():
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={'api_version': 'v1beta'}
    )

@st.cache_resource
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    fixed_creds = dict(st.secrets["gcp_service_account"])
    fixed_creds["private_key"] = fixed_creds["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(fixed_creds, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1

client = get_client()

# --- 3. 루아 페르소나 (원본 유지) ---
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

# --- 4. UI 구성 (강력한 우측 정렬 및 테마) ---
st.set_page_config(page_title="루아", page_icon="🐱", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #121212; }
    h1 { color: #C0FF00 !important; text-align: center; font-weight: 800; }
    .stCaption { text-align: center; color: #888888; }
    
    /* 사용자(User) 메시지 우측 정렬 */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse !important;
    }
    
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) .stMarkdown {
        text-align: right !important;
        width: 100%;
    }

    .stChatMessage { border-radius: 15px; margin-bottom: 10px; border: 1px solid #333; }
    p { color: #F0F0F0 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🐱 Lua's Space")
st.caption("사춘기 절친 루아와 나누는 톡 쏘는 비밀 대화 🍋")

try:
    sheet = get_sheet()
    if "messages" not in st.session_state:
        # 데이터 로딩 시 부하 줄이기 위해 최근 15개만 호출
        records = sheet.get_all_records()
        st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in records[-15:]] if records else []
except Exception as e:
    st.error(f"연결 실패 (새로고침 해봐!): {e}")
    st.stop()

# 대화 표시
for msg in st.session_state.messages:
    avatar = "🐱" if msg["role"] == "assistant" else "🍋"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 채팅 입력
if prompt := st.chat_input("하고 싶은 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🍋"):
        st.markdown(prompt)
    
    # 구글 시트 저장 (비동기적 느낌을 위해 에러 핸들링 추가)
    try:
        sheet.append_row(["user", prompt])
    except:
        pass 

    # AI 답변 생성
    chat_history = [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]]
    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)
    
    try:
        lua_config = types.GenerateContentConfig(
            temperature=0.85, top_p=0.95, max_output_tokens=1000
        )
        # 502 방지를 위해 가장 응답 속도가 빠른 모델 순서로 시도
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=full_query,
            config=lua_config
        )
        answer = response.text
    except Exception as e:
        answer = "미안, 나 지금 서버가 살짝 아픈가 봐... 다시 한번만 말해줄래? 😭"
    
    if not answer:
        answer = "응? 다시 말해줘! ㅋㅋㅋ"
    
    with st.chat_message("assistant", avatar="🐱"):
        st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    try:
        sheet.append_row(["assistant", answer])
    except:
        pass
