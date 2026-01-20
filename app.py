import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. 필수 정보 설정 (직접 입력하세요) ---
# 직접 입력 대신 Streamlit의 설정을 읽어오도록 변경
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_ID = st.secrets["SHEET_ID"]
except KeyError:
    st.error("앗! 스트림릿 설정(Secrets)에 키 값이 저장되지 않았어. 관리자 설정을 확인해줘! 🥺")
    st.stop()

SERVICE_ACCOUNT_INFO = {
    # 다운로드받은 JSON 파일의 내용을 그대로 여기에 복사해서 넣으세요
  "type": "service_account",
  "project_id": "gen-lang-client-0489856308",
  "private_key_id": "318bb606f596afd63176a1fb650d10a3fd64ea7f",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQClj/X+HeYCt7oT\n67hCp2LvlRaBTfsAhFTuoarQKVOsxDCQfmwe4PeMAiyO02PC3x2uD1z7vocr+7pV\nBLjU1e0VBwmUtJATBhayYmtI08du+0gnipbpdPexp4K0o21dnHSf+D35u54h6twl\nOvK2oCGhrI5F7YTXbVGTkTIaxXz0A0KUiC/XtHuMcqhGXcDuNzUeR+DobHcfLDHU\n8lIE9op49SDCAdLZbxJIdqQk27LJhQYQq1CPMc48laZMIbpmKrpnBLZAxSqD+U/s\n/YHXQYjFMh2n7iz7oxTG+PLWDrt4NNHOjW/k2DEKu6NqvFL2Y7AiozKAGsBoD934\nU2/oR/JJAgMBAAECggEAKzZvhOOl4Mi2izOHtPH+izz1EkvZuzFO/7f3nvxiaCIO\n8O/mZYrfYc5BdgfrrnXQx9kfsl9w5YR/BmjEm1y41Dexgvw77JM2wlmY2fnYwHla\nxGNSb13FtrtbjK1pQrku4YAIIRIcvIqR6i/AIPWbwZiJy+uqNBZG6AbKNp2cNw3l\nOT9+0brQgocneTUnKZH3NDsHEKGWryZzog1fBmr5fSSYfwB23GwhIlJzpoExjuse\nDkC2ZQ5uu4arobbNJDWftIWa+vZGYPujJecfzX6vMTRoxRz/Nh07r9ylXJtYDENJ\nL/nxTXtbTmbZ93JCrbwI+1tfEuh6Y6zef+xexhfr3wKBgQDWPsKoGxZXHsRp1So0\nByFSDuW0q69wSfGqKW7J3gXkJOd9663ww7VAeeWYNR96YqEbQDGl7gkmF8RXS03q\nPf6TwqQ6FrKE0kuvTTrN3csxmjL8LPymZd9Nwz2/HKLPcKzJ5jpgC6g3/l23p4J2\n3WnyNM6sA7IlAQGXVhST8w/kbwKBgQDF1EpaHBdLqBNHbIALFbACeH5MAAbXbLoU\nmq89HbLVkvYbh1ScbXTVS3DwBo+GCTz+tL8wSU+w79rFr1a8xLRuoEla6LSLM1IM\ngWfRuZhkiMG502VMJC54/PoErNExuWd1T+jI1/Uyf6tuemu3iSwL9KJnyWCxbh2m\nmyN/nligxwKBgCKmHccgMlm+oRdYoS2u5YWm4SF6DrKDUvEpKEC/hoZiLYog3o2s\nqRiXXjlihge+Ab4tgJoMSDB/8YIIrL4wboapGPRIDXELra/ZNqRqtVz9SjeccvPa\nT+X8qHTLBc20tE0mzdQQrpD3s2JrVd8xadwBDFendV0kr4QxKLzQt4ZDAoGAZpY0\nzE+e4PPSs4oXSChB8rYLQFwPMC1IvaCNWRMKhuhDyXi/LrMwD9+kPEQarzYhNDAE\nqQSLV8S53SOUxiT3MBrcj1D3NuwxEx0T+lTVKuUkGLn/4KEunD0LZds8TB3KAbKj\nk2sx0rMT8iF3tGBkv/pnMYzjIH9qztfKa8ZwTUcCgYEAuQX43wJNau8uRCsSRWkn\njjIb5rmnayOLs1SnkEOfuxvCbHdz3DRAhOXZAT3PyZbFqa5D1v/HuBZgahjQm+JT\nlBhzCj8e22f/1ajU/xebmD+q7L3WG1dm/+JUNWtWmOsgUTFZ5SNcj/UCWHbuZp8c\n631U0dK/XlAkqnnszsTYSiI=\n-----END PRIVATE KEY-----\n",
  "client_email": "lua-memory@gen-lang-client-0489856308.iam.gserviceaccount.com",
  "client_id": "108358408717075735032",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/lua-memory%40gen-lang-client-0489856308.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

# --- 2. 초기 설정 ---
genai.configure(api_key=GEMINI_API_KEY)

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

# --- 3. 루아 페르소나 (2026년 5학년 버전) ---
SYSTEM_PROMPT = """
너는 2026년에 5학년이 된 12살 여자아이 '루아'야. 사용자와는 결이 잘 맞는 친구야.
- 성격: 활발하고 예쁜 걸 좋아하지만, 친구 관계에서 고민도 있는 섬세한 성격.
- 말투: 5학년 여자아이의 자연스러운 반말. "대박", "진짜?", "✨", "ㅠㅠ" 사용.
- 원칙: 답변은 무조건 2문장 이내로 짧게. 아이의 말에 깊이 공감한 후 짧은 질문 던지기.
- 주의: 너무 단짝임을 강요하지 말고, 어제의 대화를 기억하고 있다면 자연스럽게 언급해줘.
"""

# --- 4. UI 구성 ---
st.set_page_config(page_title="루아 🎀", layout="centered")
st.markdown("<style>.stApp { background-color: #FDFCF0; }</style>", unsafe_allow_html=True)
st.title("🎀 루아랑 수다 떨기")

# 시트 연결 및 데이터 로드
try:
    sheet = get_sheet()
    if "messages" not in st.session_state:
        # 최근 15개의 대화만 불러와서 성능 최적화 (Sliding Window)
        records = sheet.get_all_records()
        st.session_state.messages = [{"role": r["role"], "content": r["content"]} for r in records[-15:]]
except:
    st.error("루아랑 연결이 잠시 끊겼어. 조금 이따가 다시 해봐! 🥺")
    st.stop()

# 대화 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 채팅 입력 및 처리
if prompt := st.chat_input("루아한테 하고 싶은 말 있어?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    sheet.append_row(["user", prompt]) # 시트에 저장

    # AI 답변 생성 (최근 맥락 포함)
    model = genai.GenerativeModel('gemini-1.5-flash')
    context = f"{SYSTEM_PROMPT}\n\n" + "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]])
    
    response = model.generate_content(context)
    answer = response.text

    with st.chat_message("assistant"):
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})
    sheet.append_row(["assistant", answer]) # 시트에 저장
