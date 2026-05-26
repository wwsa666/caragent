from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import time
import uuid
from typing import Optional

from agent.supervisor import AgentSupervisor
from agent.report_graph import ReportGraph

app = FastAPI(title="智能新能源车服 AI 管家 API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Multi-Agent Supervisor 与 LangGraph 报告工作流
supervisor = AgentSupervisor()
report_graph = ReportGraph()


# ==================== 统一对话入口（Supervisor 路由） ====================

class ChatRequest(BaseModel):
    query: str
    vin: str = "VIN1001"    # 前端传入当前用户 VIN

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    统一对话端点。
    
    由 Supervisor 内部的 IntentRouter 自动识别意图：
      - chat     → ChatAgent（日常问答）
      - diagnose → DiagnoseAgent（故障诊断）
      - report   → 返回提示，引导用户使用报告按钮
    """
    def generate():
        try:
            for chunk in supervisor.execute_stream(request.query, vin=request.vin):
                for char in chunk:
                    time.sleep(0.01)
                    yield char
        except Exception as e:
            yield f"发生错误: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")


# ==================== LangGraph 报告工作流 ====================

class ReportStartRequest(BaseModel):
    vin: str

class ReportResumeRequest(BaseModel):
    thread_id: str
    answer: dict    # 用户选择: {time_range, month, dimensions}

@app.post("/api/report/start")
async def report_start(request: ReportStartRequest):
    """
    启动报告生成工作流。
    
    LangGraph 执行到 ask_user 节点时触发 interrupt()：
      - 状态自动存入 MongoDB（存档）
      - stream 结束，本请求立即返回（无死等线程）
    
    返回: {thread_id, type: "interrupt", payload: {question, options...}}
    """
    thread_id = f"report-{uuid.uuid4().hex[:12]}"

    try:
        payload = report_graph.start_report(vin=request.vin, thread_id=thread_id)

        if payload is None:
            return JSONResponse(
                status_code=500,
                content={"error": "工作流未能正确触发 interrupt，请检查后台日志。"}
            )

        return JSONResponse(content={
            "thread_id": thread_id,
            "type": "interrupt",
            "payload": payload,
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"启动报告工作流失败: {str(e)}"}
        )

@app.post("/api/report/resume")
async def report_resume(request: ReportResumeRequest):
    """
    恢复报告生成工作流。
    
    从 MongoDB 读取之前存档的状态（读档），注入用户选择后继续执行。
    现在包含 Review 审查节点，确保数据一致性。
    流式返回 LLM 生成的 Markdown 报告。
    """
    def generate():
        try:
            report_text = report_graph.resume_report(
                thread_id=request.thread_id,
                user_answer=request.answer,
            )
            # 逐字流式输出
            for char in report_text:
                time.sleep(0.01)
                yield char
        except Exception as e:
            yield f"⚠️ 报告恢复执行失败: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")


# ==================== 静态资源 ====================

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
