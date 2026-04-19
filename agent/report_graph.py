"""
LangGraph StateGraph 报告生成工作流（interrupt + MongoDB 存档版）
================================================================
核心机制：
  - ask_user 节点调用 interrupt() 暂停执行，状态存入 MongoDB（存档退出）
  - 前端用户选择后，通过 Command(resume=answer) 从 MongoDB 读档恢复执行
  - 服务器全程无死等线程，支持跨请求、跨重启的状态持久化

节点编排：
  [ask_user] --interrupt()--> [fetch_data] --> [generate_report] --> END
"""

import uuid
from typing import TypedDict, Optional, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import interrupt, Command
from model.factory import chat_model
from agent.tools.agent_tools import generate_external_data, external_data
from rag.rag_service import RagSummarizeService
from utils.logger_handler import logger


# ==================== 1. 状态定义 ====================

class ReportState(TypedDict):
    """报告工作流贯穿全生命周期的状态"""
    vin: str                            # 车架号
    user_choice: Optional[dict]         # 用户在 interrupt 后回传的选择 {time_range, month, dimensions}
    raw_data: Optional[dict]            # 从 CSV 拉取的结构化数据
    report_text: str                    # LLM 最终生成的报告 Markdown
    error: Optional[str]               # 错误信息


# ==================== 2. 常量 ====================

DIMENSION_MAP = {
    "driving_habit": ["驾驶偏好"],
    "energy": ["百公里电耗", "能耗击败率"],
    "battery": ["电池健康度(SOH)"],
    "mileage": ["月度行驶里程(km)"],
    "duration": ["月度驾驶时长(小时)"],
}

ALL_MONTHS = [f"2025-{str(m).zfill(2)}" for m in range(1, 13)]

QUARTER_MAP = {
    "Q1": ALL_MONTHS[0:3],
    "Q2": ALL_MONTHS[3:6],
    "Q3": ALL_MONTHS[6:9],
    "Q4": ALL_MONTHS[9:12],
}


# ==================== 3. 节点函数 ====================

def ask_user(state: ReportState) -> dict:
    """
    节点1: 向用户抛出报告配置问题。
    
    调用 interrupt() 后：
      - LangGraph 将当前 State 序列化存入 MongoDB（存档）
      - stream/invoke 立即返回，当前线程结束
      - 前端收到 interrupt 的 payload，渲染选项供用户选择
      - 用户选择后，前端调用 resume API，LangGraph 从 MongoDB 读档
      - interrupt() 的返回值 = Command(resume=answer) 中的 answer
    """
    logger.info(f"[ReportGraph] ask_user: 等待用户选择报告配置 (VIN={state['vin']})")

    # interrupt() 暂停执行，将问题结构抛给前端
    # 当 resume 时，user_answer 就是用户的选择
    user_answer = interrupt({
        "question": "请选择您想要的报告配置：",
        "time_range_options": [
            {"value": "single_month", "label": "单月报告"},
            {"value": "quarter", "label": "季度报告"},
            {"value": "half_year", "label": "半年报告"},
            {"value": "full_year", "label": "全年报告"},
        ],
        "month_options": [
            {"value": f"2025-{str(m).zfill(2)}", "label": f"2025年{m}月"} for m in range(1, 13)
        ],
        "dimension_options": [
            {"value": "driving_habit", "label": "驾驶习惯", "icon": "fa-solid fa-car"},
            {"value": "energy", "label": "能耗水平", "icon": "fa-solid fa-bolt"},
            {"value": "battery", "label": "电池健康", "icon": "fa-solid fa-battery-three-quarters"},
            {"value": "mileage", "label": "行驶里程", "icon": "fa-solid fa-road"},
            {"value": "duration", "label": "驾驶时长", "icon": "fa-solid fa-clock"},
        ],
    })

    logger.info(f"[ReportGraph] ask_user: 用户已回答 -> {user_answer}")
    return {"user_choice": user_answer}


def fetch_data(state: ReportState) -> dict:
    """节点2: 根据用户选择，从 CSV 数据中拉取并过滤数据"""
    choice = state["user_choice"]
    vin = state["vin"]
    time_range = choice.get("time_range", "single_month")
    month = choice.get("month", "2025-02")
    dimensions = choice.get("dimensions", ["driving_habit", "energy", "battery"])

    logger.info(f"[ReportGraph] fetch_data: vin={vin}, time_range={time_range}, dims={dimensions}")

    generate_external_data()

    # 校验 VIN
    if vin not in external_data:
        return {"error": f"未找到车架号 {vin} 的数据记录，请核实。", "raw_data": None}

    # 确定月份列表
    if time_range == "single_month":
        target_months = [month]
    elif time_range == "quarter":
        m = int(month.split("-")[1])
        q = f"Q{(m - 1) // 3 + 1}"
        target_months = QUARTER_MAP[q]
    elif time_range == "half_year":
        m = int(month.split("-")[1])
        target_months = ALL_MONTHS[0:6] if m <= 6 else ALL_MONTHS[6:12]
    else:
        target_months = ALL_MONTHS

    # 拉取 + 按维度过滤
    selected_fields = set()
    for dim in dimensions:
        selected_fields.update(DIMENSION_MAP.get(dim, []))

    result = {}
    vin_data = external_data.get(vin, {})
    for m in target_months:
        if m in vin_data:
            month_data = vin_data[m]
            filtered = {k: v for k, v in month_data.items() if k in selected_fields} if selected_fields else month_data
            result[m] = filtered

    if not result:
        return {"error": f"在指定时间范围内未找到 {vin} 的数据记录。", "raw_data": None}

    return {"raw_data": result, "error": None}


def generate_report(state: ReportState) -> dict:
    """节点3: 调用 LLM 生成 Markdown 报告"""
    vin = state["vin"]
    raw_data = state["raw_data"]
    choice = state["user_choice"]
    time_range = choice.get("time_range", "single_month")
    dimensions = choice.get("dimensions", [])

    logger.info(f"[ReportGraph] generate_report: 为 {vin} 生成报告")

    dim_names = {
        "driving_habit": "驾驶习惯分析", "energy": "能耗水平分析",
        "battery": "电池健康度分析", "mileage": "行驶里程统计", "duration": "驾驶时长统计",
    }
    time_desc = {
        "single_month": "单月", "quarter": "季度", "half_year": "半年度", "full_year": "全年度",
    }

    selected_dim_desc = "、".join([dim_names.get(d, d) for d in dimensions])
    time_range_desc = time_desc.get(time_range, time_range)

    # RAG 知识补充
    rag_context = ""
    if "energy" in dimensions or "battery" in dimensions:
        try:
            rag = RagSummarizeService()
            rag_context = rag.rag_summarize("新能源汽车电池保养与能耗优化建议")
            rag_context = f"\n\n【参考知识库资料】\n{rag_context}"
        except Exception as e:
            logger.warning(f"[ReportGraph] RAG 检索失败: {e}")

    prompt = f"""你是专业的新能源汽车报告编撰助手。请根据以下车辆运行数据，生成一份{time_range_desc}车况分析报告。

【车架号】{vin}
【报告类型】{time_range_desc}报告
【分析维度】{selected_dim_desc}
【数据记录】
{str(raw_data)}
{rag_context}

输出要求：
1. 使用中文，遵循 Markdown 语法
2. 标题为《{time_range_desc}车况运行监控与保养建议报告》
3. 根据用户选择的维度进行针对性分析，不要分析未选择的维度
4. 对数据做拟人化解读，不要直接堆砌生硬数据
5. 在报告末尾给出具体、实用的保养或驾驶建议
6. 如有多月数据，需要分析趋势变化并给出洞察
"""

    response = chat_model.invoke(prompt)
    return {"report_text": response.content.strip()}


# ==================== 4. 路由函数 ====================

def should_continue(state: ReportState) -> str:
    if state.get("error"):
        return "error_end"
    return "continue"


# ==================== 5. 构建 StateGraph ====================

def build_report_graph():
    """构建并编译工作流，使用 MongoDBSaver 做状态持久化"""
    workflow = StateGraph(ReportState)

    # 添加节点
    workflow.add_node("ask_user", ask_user)
    workflow.add_node("fetch_data", fetch_data)
    workflow.add_node("generate_report", generate_report)

    # 编排边
    workflow.add_edge(START, "ask_user")
    workflow.add_edge("ask_user", "fetch_data")
    workflow.add_conditional_edges("fetch_data", should_continue, {
        "continue": "generate_report",
        "error_end": END,
    })
    workflow.add_edge("generate_report", END)

    # 使用 MongoDB 做 checkpoint 持久化
    # serverSelectionTimeoutMS 缩短为 5 秒，避免 MongoDB 未启动时长时间阻塞
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    checkpointer = MongoDBSaver(
        client=client,
        db_name="ev_service",
    )

    return workflow.compile(checkpointer=checkpointer)


# ==================== 6. 对外接口封装 ====================

class ReportGraph:
    """
    LangGraph 报告工作流封装。
    
    典型调用流程：
      1. result = start_report(vin, thread_id)   # 触发 → interrupt → 存档退出
      2. report = resume_report(thread_id, answer) # 读档 → 恢复 → 生成报告
    """

    def __init__(self):
        self.graph = build_report_graph()

    def start_report(self, vin: str, thread_id: str) -> dict:
        """
        启动报告工作流。执行到 ask_user 节点时会触发 interrupt()，
        LangGraph 自动将状态存入 MongoDB，stream 结束，本方法立即返回。
        
        返回值: interrupt 抛出的 payload（包含提问内容和选项列表）
        """
        initial_state: ReportState = {
            "vin": vin,
            "user_choice": None,
            "raw_data": None,
            "report_text": "",
            "error": None,
        }
        config = {"configurable": {"thread_id": thread_id}}

        # stream 会在 interrupt() 处自动停止
        interrupt_payload = None
        for chunk in self.graph.stream(initial_state, config=config, stream_mode="updates"):
            # 当 interrupt 触发时，chunk 会包含 __interrupt__ 信息
            if "__interrupt__" in chunk:
                # interrupt 的 value 就是我们在 ask_user 中传给 interrupt() 的字典
                interrupt_payload = chunk["__interrupt__"][0].value
                break

        return interrupt_payload

    def resume_report(self, thread_id: str, user_answer: dict) -> str:
        """
        恢复报告工作流。从 MongoDB 读取之前存档的状态，
        将用户的选择注入后继续执行 fetch_data → generate_report。
        
        返回值: LLM 生成的报告 Markdown 文本
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Command(resume=...) 会让 interrupt() 返回 user_answer
        result = self.graph.invoke(Command(resume=user_answer), config=config)

        if result.get("error"):
            return f"⚠️ 报告生成失败：{result['error']}"

        return result.get("report_text", "报告生成异常，未获取到内容。")


# ==================== 测试入口 ====================
if __name__ == "__main__":
    rg = ReportGraph()
    tid = f"test-{uuid.uuid4().hex[:8]}"

    print("=== Phase 1: start_report (触发 interrupt) ===")
    payload = rg.start_report(vin="VIN1001", thread_id=tid)
    print(f"收到提问: {payload['question']}")
    print(f"时间选项: {[o['label'] for o in payload['time_range_options']]}")
    print(f"维度选项: {[o['label'] for o in payload['dimension_options']]}")

    print("\n=== Phase 2: resume_report (用户选择后恢复) ===")
    answer = {
        "time_range": "single_month",
        "month": "2025-02",
        "dimensions": ["driving_habit", "energy"]
    }
    report = rg.resume_report(thread_id=tid, user_answer=answer)
    print(report)
