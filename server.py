from fastapi import FastAPI, Request, Response, BackgroundTasks
import httpx
from google import genai

app = FastAPI()

# 1. 토큰 및 키 설정
BOT_TOKEN = "d3e038aa279c2bbd69bee93678d6c6ba"
GEMINI_KEY = "AQ.Ab8RN6LEYTgrZ2GLhK_nBcUVe9WiooJ_MmU1BC0RIJAJ8l14zA"

client = genai.Client(api_key=GEMINI_KEY)
KAKAO_CALLBACK_URL = "https://kapi.kakao.com/v1/bot/callback"

async def process_and_reply(callback_token: str, content: str):
    # Gemini 답변 생성
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=f"당신은 AI 에이전트입니다. 질문에 간결하고 정확하게 답변하세요.\n\n사용자: {content}",
    )
    ai_answer = response.text

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
        await http_client.post(KAKAO_CALLBACK_URL, json=body, headers=headers)

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    op = payload.get("op")
    t = payload.get("t")
    d = payload.get("d", {})

    # 사용자 메시지(MESSAGE_CREATE) 수신 시 백그라운드로 처리 후 답장
    if op == 0 and t == "MESSAGE_CREATE":
        content = d.get("content", "")
        callback_token = d.get("callbackToken")
        if callback_token:
            background_tasks.add_task(process_and_reply, callback_token, content)

    # 1초 이내에 204 No Content 즉시 응답
    return Response(status_code=204)
