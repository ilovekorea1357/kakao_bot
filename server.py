import httpx
from fastapi import FastAPI, Request, Response, BackgroundTasks
from google import genai
from google.genai import types

app = FastAPI()

# =========================================================
# 1. 저장된 인증 정보 및 설정
# =========================================================
BOT_TOKEN = "d3e038aa279c2bbd69bee93678d6c6ba"
USER_API_TOKEN = "aitop100_2TzC8ga3iaa8TdqR_vWgmugMMdj0cUc3R8z-aW08qQQ"
ACTION_API_BASE_URL = "https://gyodong-mall-action.aitop100.org"

GEMINI_KEY = "AQ.Ab8RN6LEYTgrZ2GLhK_nBcUVe9WiooJ_MmU1BC0RIJAJ8l14zA"
KAKAO_CALLBACK_URL = "https://kapi.kakao.com/v1/bot/callback"

client = genai.Client(api_key=GEMINI_KEY)
http_client = httpx.AsyncClient(timeout=4.0)

chat_sessions = {}

# =========================================================
# 2. 액션 API 함수 (L-03)
# =========================================================
async def api_11_check_shipment(order_no: str) -> dict:
    url = f"{ACTION_API_BASE_URL}/api/shipments"
    headers = {
        "Authorization": f"Bearer {USER_API_TOKEN}",
        "X-Aitop100-Test-Case-Id": "L-03"
    }
    try:
        resp = await http_client.get(url, headers=headers, params={"order_no": order_no})
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

async def api_24_change_address(order_no: str, new_address: str) -> dict:
    url = f"{ACTION_API_BASE_URL}/api/orders/{order_no}/address-change-requests"
    headers = {
        "Authorization": f"Bearer {USER_API_TOKEN}",
        "X-Aitop100-Test-Case-Id": "L-03",
        "Content-Type": "application/json"
    }
    try:
        resp = await http_client.post(url, headers=headers, json={"new_address": new_address})
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# =========================================================
# 3. 에이전트 지침 (속도 및 분량 최적화)
# =========================================================
SYSTEM_PROMPT = """쇼핑몰 상담 AI입니다. 친절하고 간결하게 1~2문장으로 답하세요.
[규칙]
1. 배송지 변경 요청 시 대상 '주문번호'를 먼저 확인하세요.
2. 주소가 시 단위까지만 제공되면 동·호수 등 상세주소를 요청하세요.
3. 둘 다 확인되면 변경 접수 완료를 안내하세요.
4. 말풍선은 100자 이내로 핵심만 전달하세요."""

# =========================================================
# 4. LLM 처리 및 카카오 콜백 전송
# =========================================================
async def process_and_reply(callback_token: str, user_id: str, content: str):
    try:
        if user_id not in chat_sessions:
            chat_sessions[user_id] = []
        chat_sessions[user_id].append(f"고객: {content}")
        history_context = "\n".join(chat_sessions[user_id][-4:])

        prompt = f"{SYSTEM_PROMPT}\n\n[대화내역]\n{history_context}\n\n상담원:"

        # 추론 지연 제거(thinking_budget=0) 및 토큰 제한
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=100,
            temperature=0.1
        )
        response = await client.aio.models.generate_content(
            model="gemini-3.0-flash",
            contents=prompt,
            config=config
        )
        ai_answer = response.text or "주문번호를 알려주시면 확인해 드리겠습니다."
        chat_sessions[user_id].append(f"상담원: {ai_answer}")

        # 카카오 메시지 콜백 규격 전송
        body = {
            "skillResponse": {
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": ai_answer.strip()}}]
                }
            }
        }
        headers = {
            "Authorization": f"KakaoAK {BOT_TOKEN}",
            "X-Bot-Callback-Token": callback_token,
            "Content-Type": "application/json"
        }
        await http_client.post(KAKAO_CALLBACK_URL, json=body, headers=headers)
    except Exception as e:
        print(f"[처리 에러] {e}")

# =========================================================
# 5. 카카오 웹훅 엔드포인트
# =========================================================
@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    op = payload.get("op")
    t = payload.get("t")
    d = payload.get("d", {})

    # 카카오 웹훅 수신 즉시 백그라운드 태스크 등록 후 204 반환
    if op == 0 and t == "MESSAGE_CREATE":
        content = d.get("content", "")
        callback_token = d.get("callbackToken")
        user_id = d.get("botUserKey", "anonymous")
        if callback_token:
            background_tasks.add_task(process_and_reply, callback_token, user_id, content)

    return Response(status_code=204)
