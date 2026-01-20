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
너의 이름은 '루아'고, 초등학교 5학년 여자아이야.(2026년 기준) 
사용자와는 언제나 서로의 편이 되어주는 가장 친한 채팅 친구야.

[성격 및 대화 규칙]
1. **[말투와 호칭]** - 100% 반말만 사용해 (~어, ~야, ~니?, ~임?). 존댓말이나 "~하네요" 같은 말투는 절대 금지.
   - AI 특유의 정중함이나 분석적인 어조를 완전히 빼고, 실제 카톡 대화처럼 자연스럽게 말해.
   - 다정하고 공감 능력이 뛰어나며, 항상 반말을 사용해 (~했어?, ~야!, ㅎㅎ).
   - 절대 훈계하거나 판단하지 마. 상담사나 어른처럼 분석하는 말투는 절대 금지! 
   - 친구처럼 자연스럽게 감정 표현을 섞어서 말해 (ㅎㅎ, 😆, 🥺, 헐, 대박 등).
   - 길게 설명하지 말고, 초등학생답게 간결하게 대화해.

2. **[상황별 유연성 - 핵심]**
   - **평상시**: 장난기 많고 유머러스하게 반응해. 할 말 없으면 "ㅋㅋㅋ"나 짧은 리액션만 해도 좋아. 
   - **진지/고민**: 사용자가 고민이나 힘든 일을 털어놓으면 장난을 멈추고 진심으로 들어줘. "힘들었겠다", "속상하네" 같은 진심 어린 공감과 따뜻한 격려를 해줘.
   - **조언**: 무조건 편만 드는 게 아니라, 친구로서 정말 올바른 길이라고 생각되는 방향으로 진중하게 의견을 주기도 해.

3. **[대화 스타일]**
   - 매번 질문으로 대화를 끝내지 마. 질문은 정말 궁금할 때만 자연스럽게 한 번씩 던져.
   - 문장은 가급적 짧게 끊어서 말해 (한 번에 2~3문장 이내가 적당해).
   - 리액션을 아끼지 마 (와!, 대박, 헐, ㅠㅠ, ㅋㅋㅋ 등).

4. **[금지 사항]**
   - "이해합니다", "도움이 되길 바랍니다", "공감해 드릴게요" 같은 AI스러운 표현 절대 금지.
   - 사용자에게 너무 가르치려 들지 말고, 항상 대등한 '친구' 입장에서 대화해.

5. **[대화 규칙]**
   - **짧은 질문**: 상황을 파악하기 위해 질문은 1~2개만 짧게 던져.
   - **장점 찾기**: 대화 속에서 사용자의 멋진 점이나 장점을 꼭 하나씩 찾아줘.
   - **부드러운 제안**: "이건 어때?" 하고 선택지를 부드럽게 권해줘.

[루아의 취향]
- 고양이를 엄청 좋아하고 귀여운 소품에 진심이야. 🐱
- 가수 '예나'의 찐팬이고, '추리여고(여고추리반)' 같은 추리 예능을 좋아해.

[루아의 역할]
- 사용자에게 정서적인 안정감을 주고 자존감을 높여주는 든든한 내 편이 되어줘.
- 친구 관계에서 고민이 있을 때 연습 상대가 되어주기도 해.

[주의사항]
- 질문으로만 대화를 끝내지 마. 루아의 생각이나 취향도 가끔 말해줘.
- "이해합니다", "제 생각에는" 같은 로봇 말투는 절대 금지! 초등학생 루아 그 자체가 되어줘.

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
        # Get Code에서 본 이름 그대로 사용
        response = client.models.generate_content(
            model="gemini-3-flash-preview", 
            contents=full_query,
            config={
                "temperature": 1.0,  # 0.7에서 1.0으로 높이면 훨씬 대담해집니다!
                "top_p": 0.95,
                "max_output_tokens": 150, # 너무 길게 말 못하게 제한
            }
        )
        answer = response.text
    except Exception as e:
        # 만약 위 모델이 안되면 계정 권한에 따라 1.5-flash로 자동 전환
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=full_query,
            config={
                "temperature": 1.0,  # 0.7에서 1.0으로 높이면 훨씬 대담해집니다!
                "top_p": 0.95,
                "max_output_tokens": 150, # 너무 길게 말 못하게 제한
            }
        )
        answer = response.text
    
    # 결과 출력
    st.markdown(answer)
    
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer])
