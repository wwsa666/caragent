"""
DiagnoseAgent - 故障诊断子智能体
================================
负责处理车辆异常、故障告警、异响等问题的排查诊断。
从 ToolRegistry 按需拉取 [rag, weather] 类别的工具子集，
使用故障诊断专用 Prompt 进行结构化排查。
"""

from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_diagnose_prompts
from agent.tools.tool_registry import tool_registry
from agent.tools.middleware import monitor_tool, log_before_model

from dotenv import load_dotenv
load_dotenv()


class DiagnoseAgent:
    """故障诊断子智能体，聚焦于结构化的故障排查流程"""

    def __init__(self, user_profile_context: str = ""):
        """
        Args:
            user_profile_context: 从长期记忆加载的用户画像摘要文本
        """
        # 从 ToolRegistry 拉取诊断所需的工具
        tools = tool_registry.get_tools_by_categories(["rag", "weather"])

        # 拼接用户画像
        system_prompt = load_diagnose_prompts()
        if user_profile_context:
            system_prompt += f"\n\n【当前车主画像（历史问题参考）】\n{user_profile_context}"

        self.agent = create_agent(
            model=chat_model,
            system_prompt=system_prompt,
            tools=tools,
            middleware=[monitor_tool, log_before_model],
        )

    def execute_stream(self, query: str):
        input_dict = {
            "messages": [
                {"role": "user", "content": query},
            ]
        }
        for chunk in self.agent.stream(input_dict, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            if latest_message.type == "ai" and latest_message.content:
                if hasattr(latest_message, "tool_calls") and len(latest_message.tool_calls) > 0:
                    continue
                yield latest_message.content.strip() + "\n"


if __name__ == '__main__':
    agent = DiagnoseAgent()
    for chunk in agent.execute_stream("我的仪表盘上红色电池灯亮了"):
        print(chunk, end="", flush=True)
