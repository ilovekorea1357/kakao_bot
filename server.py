from fastapi import FastAPI, Request, Response, BackgroundTasks
import httpx
from google import genai

app = FastAPI()

# 1. 토큰 및 키 설정 (본인의 실제 토큰 입력 필수)
BOT_TOKEN = "d3e038aa279c2bbd69bee93678d6c6ba"
GEMINI_KEY = "AQ.Ab8RN6LEYTgrZ2GLhK_nBcUVe9WiooJ_MmU1BC0RIJAJ8l14zA"
KAKAO_CALLBACK_URL = "https://kapi.kakao.com/v1/bot/callback"

client = genai.Client(api_key=GEMINI_KEY)

async def process_and_reply(callback_token: str, content: str):
    try:
        # Gemini 답변 생성
        response = client.models.generate_content(
            model="gemini-3.0-flash",
            contents=f"당신은 AI 에이전트입니다. 간결하게 답변하세요: {content}",
        )
        ai_answer = response.text or "답변을 생성하지 못했습니다."

        # 카카오 메시지 콜백 API 호출
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
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(KAKAO_CALLBACK_URL, json=body, headers=headers)
            print(f"[카카오 응답 결과] status={resp.status_code}, response={resp.text}")
    except Exception as e:
        print(f"[처리 에러] {e}")

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    print(f"[수신 이벤트] {payload.get('t')}")

    op = payload.get("op")
    t = payload.get("t")
    d = payload.get("d", {})

    if op == 0 and t == "MESSAGE_CREATE":
        content = d.get("content", "")
        callback_token = d.get("callbackToken")
        if callback_token:
            background_tasks.add_task(process_and_reply, callback_token, content)

    return Response(status_code=204)
