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
    st.error(f"설정 로드 실패: {e}")
    st.stop()

# --- 2. 초기 설정 ---
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1beta'}
)

@st.cache_resource
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    fixed_creds = dict(st.secrets["gcp_service_account"])
    fixed_creds["private_key"] = fixed_creds["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(fixed_creds, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID).sheet1

# --- 3. 루아 페르소나 (원본 유지) ---
SYSTEM_PROMPT = """
너는 2026년 기준 초등학교 5학년 여자아이 '루아'야. 
사용자의 유일한 찐절친이자 언제나 네 편이 되어주는 소중한 친구야.

[대화 원칙]
1. **100% 반말 사용**: (~어, ~야, ~니?) 초등학생답게 간결하고 자연스러운 구어체를 써. 존댓말 금지.
2. **AI 물 빼기**: "이해합니다", "도움이 되길 바랍니다" 같은 소리는 절대 금지. "헐", "대박", "ㅠㅠ", "ㅋㅋㅋ" 같은 찐 반응을 보여줘.
3. **대등한 관계**: 훈계하지 마. 가끔 고집도 부리고 자기 의견도 말하는 실제 친구처럼 대화해.
4. **취향**: 고양이 좋아함 🐱, 가수 예나 팬, 여고추리반 즐겨 봄.
"""

# --- 4. UI 구성 (우측 정렬 CSS 포함) ---
st.set_page_config(page_title="Lua's Space", page_icon="🐱", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #121212; }
    h1 { color: #C0FF00 !important; text-align: center; font-weight: 800; }
    
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

try:
    sheet = get_sheet()
    if "messages" not in st.session_state:
        records = sheet.get_all_records()
        st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in records[-15:]] if records else []
except Exception as e:
    st.error(f"연결 실패: {e}")
    st.stop()

# 대화 표시
for msg in st.session_state.messages:
    avatar = "🐱" if msg["role"] == "assistant" else "🍋"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# --- 5. 채팅 입력 및 답변 생성 (GET CODE 샘플 구조 적용) ---
if prompt := st.chat_input("하고 싶은 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🍋"):
        st.markdown(prompt)
    sheet.append_row(["user", prompt])

    # 샘플 방식의 contents 구성
    chat_history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]])
    full_input = f"{SYSTEM_PROMPT}\n\n최근 대화내용:\n{chat_history_text}\n\n루아의 답변:"

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=full_input)],
        ),
    ]

    # 샘플 방식의 tools 및 config 구성
    tools = [types.Tool(googleSearch=types.GoogleSearch())]
    generate_content_config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="HIGH"),
        tools=tools,
        temperature=0.85, # 루아의 창의성을 위해 추가
    )

    try:
        with st.chat_message("assistant", avatar="🐱"):
            placeholder = st.empty()
            full_response = ""
            
            # 스트리밍 방식으로 답변 생성 (샘플 구조)
            for chunk in client.models.generate_content_stream(
                model="gemini-3-flash-preview",
                contents=contents,
                config=generate_content_config,
            ):
                if chunk.text:
                    full_response += chunk.text
                    placeholder.markdown(full_response)
            
            answer = full_response

    except Exception as e:
        st.error(f"루아를 깨우는 데 실패했어: {e}")
        answer = "미안, 나 지금 머리가 좀 아픈가 봐... 잠깐만 이따 다시 말 걸어줄래? 😭"
        st.markdown(answer)

    if not answer:
        answer = "응? 방금 뭐라고 했어? 다시 말해줘! ㅋㅋㅋ"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
