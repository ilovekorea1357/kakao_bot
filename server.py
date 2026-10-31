import asyncio
import time
import httpx
from fastapi import FastAPI, Request, Response
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

# HTTP 연결 풀을 상시 유지하여 네트워크 연결 시간 단축
http_client = httpx.AsyncClient(
    timeout=10.0,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
)

chat_sessions = {}

# =========================================================
# 2. 대회 액션 API 호출 함수 (L-03)
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
# 3. 초경량 프롬프트 및 즉시 응답 처리
# =========================================================
SYSTEM_PROMPT = """쇼핑몰 상담원입니다. 1~2문장(80자 이내)으로 핵심만 즉시 답하세요.
1. 배송지 변경 요청 시 '주문번호'를 먼저 물어보세요.
2. 주소가 시/구 단위면 동·호수를 포함한 '상세주소'를 물어보세요.
3. 주문번호와 상세주소가 모두 확인되면 변경 접수가 완료되었다고 안내하세요."""

async def process_and_reply(callback_token: str, user_id: str, content: str):
    start_time = time.time()
    try:
        # 대화 내역 최근 4개만 유지 (속도 최적화)
        history = chat_sessions.setdefault(user_id, [])
        history.append(f"고객: {content}")
        if len(history) > 4:
            history[:] = history[-4:]

        prompt = f"{SYSTEM_PROMPT}\n\n" + "\n".join(history) + "\n상담원:"

        # Gemini 2.5 Flash 비동기 호출 (Thinking 완전 비활성화)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=100,
                temperature=0.1,
            )
        )
        ai_answer = (response.text or "주문번호를 알려주시면 확인해 드리겠습니다.").strip()
        history.append(f"상담원: {ai_answer}")

        llm_time = time.time() - start_time
        print(f"[1. Gemini 생성 완료] {llm_time:.2f}초 소요 | 답변: {ai_answer}")

        # 카카오 메시지 콜백 API 즉시 전송
        body = {
            "skillResponse": {
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": ai_answer}}]
                }
            }
        }
        headers = {
            "Authorization": f"KakaoAK {BOT_TOKEN}",
            "X-Bot-Callback-Token": callback_token,
            "Content-Type": "application/json"
        }
        resp = await http_client.post(KAKAO_CALLBACK_URL, json=body, headers=headers)
        total_time = time.time() - start_time
        print(f"[2. 카카오 전송 완료] 총 {total_time:.2f}초 | 상태코드: {resp.status_code}")

    except Exception as e:
        print(f"[에러 발생] {e}")

# =========================================================
# 4. 카카오 웹훅 엔드포인트 (0.01초 내 204 즉시 반환)
# =========================================================
@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.json()

    if payload.get("op") == 0 and payload.get("t") == "MESSAGE_CREATE":
        d = payload.get("d", {})
        callback_token = d.get("callbackToken")
        content = d.get("content", "")
        user_id = d.get("botUserKey", "user")

        if callback_token:
            # 대기 없이 이벤트 루프에서 즉시 비동기 실행
            asyncio.create_task(process_and_reply(callback_token, user_id, content))

    return Response(status_code=204)
