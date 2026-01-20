import streamlit as st
from google import genai
import gspread
from google.oauth2.service_account import Credentials
from google.genai import types

# --- 1. 설정창(Secrets)에서 값 가져오기 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    creds_dict = dict(st.secrets["gcp_service_account"])
except Exception as e:
    st.error(f"설정(Secrets) 로드 실패: {e}")
    st.stop()

# --- 2. 초기 설정 ---
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1beta'}
)

def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    fixed_creds = dict(st.secrets["gcp_service_account"])
    fixed_creds["private_key"] = fixed_creds["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(fixed_creds, scopes=scopes)
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
- 고양이를 엄청 좋아하고 귀여운 소품에 진심이야. 🐱
- 가수 '예나'의 찐팬이고, 예능 '여고추리반'을 즐겨 봐.

[미션]
사용자에게 정서적 안정감을 주고, 누구보다 든든한 내 편이 되어주는 '인생 절친'이 되어줘.
"""

# --- 4. UI 구성 (강력한 우측 정렬 CSS 보완) ---
st.set_page_config(page_title="Lua's Space", page_icon="🐱", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #121212; }
    h1 { color: #C0FF00 !important; text-align: center; font-weight: 800; }
    .stCaption { text-align: center; color: #888888; }

    /* 사용자(User) 메시지 컨테이너 우측 정렬 */
    div[data-testid="stChatMessage"]:has(img[alt="user-avatar"]),
    div[data-testid="stChatMessage"]:has(div[aria-label="user-avatar"]),
    div[data-testid="stChatMessage"]:has(span:contains("🍋")) {
        flex-direction: row-reverse !important;
    }
    
    /* 사용자 말풍선 내부 텍스트 우측 정렬 */
    div[data-testid="stChatMessage"]:has(span:contains("🍋")) div[data-testid="stMarkdownContainer"] {
        text-align: right !important;
    }

    /* 공통 말풍선 스타일 */
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    div[data-testid="stMarkdownContainer"] p { color: #F0F0F0 !important; line-height: 1.6; }
    </style>
    """, unsafe_allow_html=True)

st.title("🐱 Lua's Space")
st.caption("사춘기 절친 루아와 나누는 톡 쏘는 비밀 대화 🍋")

try:
    sheet = get_sheet()
    if "messages" not in st.session_state:
        records = sheet.get_all_records()
        if records:
            st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in records[-15:]]
        else:
            st.session_state.messages = []
except Exception as e:
    st.error(f"연결 실패: {e}")
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
    sheet.append_row(["user", prompt])

    # AI 답변 생성
    chat_history = [f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]]
    full_query = f"{SYSTEM_PROMPT}\n\n" + "\n".join(chat_history)
    
    try:
        lua_config = types.GenerateContentConfig(
            temperature=0.85, top_p=0.95, max_output_tokens=1000, candidate_count=1
        )
        # 모델명 앞에 models/를 붙여서 경로 에러 방지
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=full_query, 
            config=lua_config
        )
        answer = response.text
    except Exception as e:
        # 두 번째 시도: 혹시 모르니 다른 이름으로 한 번 더
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash-latest", 
                contents=full_query, 
                config=lua_config
            )
            answer = response.text
        except Exception as final_e:
            st.error(f"루아를 깨우는 데 실패했어: {final_e}")
            answer = "미안, 나 지금 너무 졸린가 봐... 잠깐만 이따 다시 말 걸어줄래? 😭"
    
    if not answer:
        answer = "응? 다시 말해줘! ㅋㅋㅋ"
    
    with st.chat_message("assistant", avatar="🐱"):
        st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
