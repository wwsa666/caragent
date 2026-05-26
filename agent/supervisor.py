"""
Multi-Agent Supervisor 调度器
==============================
整合意图路由器 + 各专职子智能体的统一调度中枢。
流程：
  1. IntentRouter 分类用户意图
  2. 根据意图路由到对应子 Agent (ChatAgent / DiagnoseAgent)
  3. 对话结束后，异步提取用户偏好存入长期记忆
  4. 报告类意图由 API 层直接走 ReportGraph（不经过 Supervisor）
"""

from agent.intent_router import IntentRouter
from agent.react_agent import ChatAgent
from agent.diagnose_agent import DiagnoseAgent
from agent.memory_service import UserMemoryService
from utils.logger_handler import logger


class AgentSupervisor:
    """
    多智能体调度器。
    
    对外暴露统一的 execute_stream() 接口，
    内部自动进行意图识别 → 路由到子 Agent → 异步保存记忆。
    """

    def __init__(self):
        self.router = IntentRouter()
        self.memory = UserMemoryService()
        logger.info("[Supervisor] 初始化完成（意图路由器 + 记忆服务）")

    def execute_stream(self, query: str, vin: str = "VIN1001"):
        """
        统一的流式对话入口。
        
        Args:
            query: 用户输入
            vin: 当前用户的车架号
            
        Yields:
            str: 流式输出的文本块
        """
        # ===== Step 1: 意图识别 =====
        intent = self.router.classify(query)
        logger.info(f"[Supervisor] VIN={vin}, intent={intent}, query='{query[:50]}...'")

        # ===== Step 2: 加载用户画像 =====
        user_profile = self.memory.load_profile(vin)

        # ===== Step 3: 路由到子 Agent =====
        if intent == "report":
            # 报告类意图：提示用户使用报告按钮
            yield "📊 检测到您想要生成报告，请点击右上角的**「生成报告」**按钮，我将为您启动定制化报告工作流。\n"
            return

        elif intent == "diagnose":
            # 故障诊断子智能体
            agent = DiagnoseAgent(user_profile_context=user_profile)
            logger.info("[Supervisor] 路由到 → DiagnoseAgent")

        else:
            # 日常问答子智能体（默认）
            agent = ChatAgent(user_profile_context=user_profile)
            logger.info("[Supervisor] 路由到 → ChatAgent")

        # ===== Step 4: 执行子 Agent 并流式输出 =====
        full_response = ""
        for chunk in agent.execute_stream(query):
            full_response += chunk
            yield chunk

        # ===== Step 5: 异步提取记忆（对话完成后） =====
        try:
            conversation_text = f"用户（VIN={vin}）：{query}\nAI：{full_response}"
            self.memory.extract_and_save(vin, conversation_text)
        except Exception as e:
            # 记忆提取失败不影响主流程
            logger.warning(f"[Supervisor] 记忆提取失败（不影响主流程）: {e}")


if __name__ == "__main__":
    supervisor = AgentSupervisor()

    test_queries = [
        ("新能源车在零下10度怎么保养电池", "VIN1001"),
        ("帮我生成一份2月的运行报告", "VIN1001"),
        ("仪表盘上红色电池灯亮了", "VIN1002"),
    ]

    for query, vin in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query} (VIN={vin})")
        print(f"{'='*60}")
        for chunk in supervisor.execute_stream(query, vin=vin):
            print(chunk, end="", flush=True)
