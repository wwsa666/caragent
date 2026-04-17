from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import time
import asyncio

from agent.react_agent import ReactAgent

app = FastAPI(title="智能新能源车服 AI 管家 API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# initialize agent
agent = ReactAgent()

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Streaming endpoint for the chatbot.
    """
    def generate():
        try:
            # We must run the blocking generator properly. Fastapi runs sync generators in threadpool.
            # `execute_stream` is a synchronous generator yielding strings
            for chunk in agent.execute_stream(request.query):
                for char in chunk:
                    time.sleep(0.01)
                    yield char
        except Exception as e:
            yield f"发生错误: {str(e)}"
    
    return StreamingResponse(generate(), media_type="text/plain")

# Serve the static frontend files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    # run with: uvicorn api:app --reload
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
