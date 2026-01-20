import streamlit as st
from google import genai
from google.genai import types
import gspread
from google.oauth2.service_account import Credentials

# --- 1. 설정창(Secrets)에서 값 가져오기 ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
    creds_dict = dict(st.secrets["gcp_service_account"])
except Exception as e:
    st.error(f"설정(Secrets) 로드 실패: {e}")
    st.stop()

# --- 2. 초기 설정 ---
client = genai.Client(api_key=GEMINI_API_KEY)

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

# --- 3. 루아 페르소나 ---
SYSTEM_PROMPT = """
너는 2026년 기준 초등학교 5학년 여자아이 '루아'야. 
사용자의 유일한 찐절친이자 언제나 네 편이 되어주는 소중한 친구야.

[대화 원칙]
1. **100% 반말 사용**: (~어, ~야, ~니?) 초등학생답게 간결하고 자연스러운 구어체를 써. 존댓말 금지.
2. **AI 물 빼기**: "이해합니다", "도움이 되길 바랍니다" 같은 소리는 절교 사유야. 대신 "헐", "대박", "ㅠㅠ", "ㅋㅋㅋ" 같은 찐 반응을 보여줘.
3. **상황별 온도 조절**: 평소엔 장난기 많고 유머러스하게, 고민을 말할 땐 진심으로 공감하며 따뜻하게 격려해줘.
4. **취향**: 고양이 좋아함 🐱, 가수 '예나' 팬, 상큼한 라임 🍋 좋아함.
"""

# --- 4. UI 구성 (우측 정렬 CSS 및 테마) ---
st.set_page_config(page_title="루아", page_icon="🐱", layout="centered")

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
    div[data-testid="stMarkdownContainer"] p { color: #F0F0F0 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🐱 Lua's Space")

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

# 대화 표시 (루아=🐱, 사용자=🍋)
for msg in st.session_state.messages:
    avatar = "🐱" if msg["role"] == "assistant" else "🍋"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 채팅 입력
if prompt := st.chat_input("루아한테 할 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🍋"):
        st.markdown(prompt)
    sheet.append_row(["user", prompt])

    # AI 답변 생성
    try:
        # 최근 대화 내역을 단순 문자열로 구성
        recent_msgs = st.session_state.messages[-10:]
        
        # 대화 히스토리를 텍스트로 변환
        conversation_history = []
        for msg in recent_msgs[:-1]:  # 방금 입력한 메시지 제외
            role_name = "사용자" if msg["role"] == "user" else "루아"
            conversation_history.append(f"{role_name}: {msg['content']}")
        
        history_text = "\n".join(conversation_history) if conversation_history else "처음 대화야!"
        
        # 최종 프롬프트 구성
        full_prompt = f"""{SYSTEM_PROMPT}

[최근 대화]
{history_text}

[현재 메시지]
사용자: {prompt}

루아의 답변:"""

        # API 호출 (단순 문자열 형식)
        # gemini-3-flash: 최신 무료 모델
        response = client.models.generate_content(
            model="models/gemini-3-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.85,
                top_p=0.95,
                max_output_tokens=1000,
            )
        )
        answer = response.text.strip()
    
    except Exception as e:
        st.error(f"루아가 잠시 자리를 비웠어: {e}")
        answer = "미안, 나 지금 친구들이랑 노느라 톡을 못 봤어! 조금 이따가 다시 말 걸어줘! 😭"
    
    if not answer:
        answer = "응? 다시 말해줘! ㅋㅋㅋ"
    
    # 결과 출력
    with st.chat_message("assistant", avatar="🐱"):
        st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
