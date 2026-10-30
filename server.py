from fastapi import FastAPI, Request
from google import genai
import uvicorn

app = FastAPI()

# 복사한 키 입력
client = genai.Client(api_key="AQ.Ab8RN6LEYTgrZ2GLhK_nBcUVe9WiooJ_MmU1BC0RIJAJ8l14zA")

SYSTEM_PROMPT = "당신은 AI 에이전트입니다. 사용자의 질문에 친절하고 간결하게 답변하세요."

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_utterance = body.get("userRequest", {}).get("utterance", "")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{SYSTEM_PROMPT}\n\n사용자: {user_utterance}",
    )
    ai_answer = response.text

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": ai_answer
                    }
                }
            ]
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
