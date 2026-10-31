from fastapi import FastAPI, Request, Response, BackgroundTasks
import httpx
from google import genai
from google.genai import types

app = FastAPI()

# 1. 토큰 및 키 설정 (본인의 실제 봇 토큰 입력)
BOT_TOKEN = "d3e038aa279c2bbd69bee93678d6c6ba"
GEMINI_KEY = "AQ.Ab8RN6LEYTgrZ2GLhK_nBcUVe9WiooJ_MmU1BC0RIJAJ8l14zA"
KAKAO_CALLBACK_URL = "https://kapi.kakao.com/v1/bot/callback"

client = genai.Client(api_key=GEMINI_KEY)

async def process_and_reply(callback_token: str, content: str):
    try:
        # 추론 시간(Thinking)을 0으로 끄고 글자 수를 제한하여 속도 대폭 단축
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=150
        )
        
        # 비동기(aio) 모델 호출
        response = await client.aio.models.generate_content(
            model="gemini-3.0-flash",
            contents=f"당신은 AI 에이전트입니다. 간결하고 친절하게 답변하세요: {content}",
            config=config
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
    op = payload.get("op")
    t = payload.get("t")
    d = payload.get("d", {})

    # 메시지 수신 시 백그라운드 태스크로 넘기고 1초 안에 204 즉시 응답
    if op == 0 and t == "MESSAGE_CREATE":
        content = d.get("content", "")
        callback_token = d.get("callbackToken")
        if callback_token:
            background_tasks.add_task(process_and_reply, callback_token, content)

    return Response(status_code=204)
