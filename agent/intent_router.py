"""
LLM 意图路由器 (Intent Router)
==============================
使用 qwen-flash 对用户输入进行轻量级意图分类，
输出 chat / report / diagnose 三个标签之一，
替代前端的关键词硬匹配，实现语义级的意图识别。
"""

from model.factory import chat_model
from utils.prompt_loader import load_intent_prompts
from utils.logger_handler import logger


class IntentRouter:
    """
    意图分类路由器。
    
    调用 LLM 判断用户输入属于哪种意图：
      - "chat"     → 日常问答（保养咨询、知识问答、天气查询等）
      - "report"   → 报告生成（运行报告、能耗总结等）
      - "diagnose" → 故障诊断（异常告警、故障排查等）
    """

    VALID_INTENTS = {"chat", "report", "diagnose"}

    def __init__(self):
        self.prompt_template = load_intent_prompts()

    def classify(self, query: str) -> str:
        """
        对用户 query 进行意图分类。
        
        Args:
            query: 用户输入的原始文本
            
        Returns:
            str: "chat" / "report" / "diagnose"
        """
        prompt = self.prompt_template.replace("{query}", query)

        try:
            response = chat_model.invoke(prompt)
            intent = response.content.strip().lower()

            # 防御性校验：确保输出是合法标签
            if intent not in self.VALID_INTENTS:
                logger.warning(
                    f"[IntentRouter] LLM 返回了非法意图标签: '{intent}'，回退到 chat"
                )
                intent = "chat"

            logger.info(f"[IntentRouter] query='{query[:30]}...' → intent={intent}")
            return intent

        except Exception as e:
            logger.error(f"[IntentRouter] 意图分类失败: {e}，回退到 chat")
            return "chat"


if __name__ == "__main__":
    router = IntentRouter()

    test_cases = [
        "帮我生成一份2月的运行报告",
        "我的仪表盘上红色电池灯亮了是怎么回事",
        "新能源车在零下10度怎么保养电池",
        "帮我查一下这个月的月报",
        "车子启动时有异响，抖动很厉害",
        "今天天气怎么样",
    ]

    print("=== 意图路由器测试 ===")
    for q in test_cases:
        intent = router.classify(q)
        print(f"  [{intent:>8}] {q}")
