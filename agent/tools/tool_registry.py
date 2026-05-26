"""
MCP-Style 模块化工具注册中心
=============================
参考 MCP (Model Context Protocol) 思想设计的轻量级工具注册机制。
将工具按服务类别分组注册，各子 Agent 按需拉取工具子集，
实现工具与智能体的解耦，支持热插拔式扩展。

类别定义：
  - rag: 知识库检索类工具
  - weather: 天气与环境类工具
  - user_info: 用户/车辆信息获取类工具
  - data: 业务数据查询类工具
"""

from typing import Dict, List, Optional
from langchain_core.tools import BaseTool
from utils.logger_handler import logger


class ToolRegistry:
    """
    工具注册中心（单例模式）。
    
    用法：
      registry = ToolRegistry()
      registry.register("rag", rag_summarize)
      tools = registry.get_tools_by_categories(["rag", "weather"])
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._registry: Dict[str, List[BaseTool]] = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, category: str, tool: BaseTool) -> None:
        """将一个工具注册到指定类别下"""
        if category not in self._registry:
            self._registry[category] = []

        # 避免重复注册
        existing_names = [t.name for t in self._registry[category]]
        if tool.name not in existing_names:
            self._registry[category].append(tool)
            logger.info(f"[ToolRegistry] 注册工具: {tool.name} -> 类别: {category}")

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """获取某一类别下的所有工具"""
        return self._registry.get(category, [])

    def get_tools_by_categories(self, categories: List[str]) -> List[BaseTool]:
        """获取多个类别下的所有工具（合并去重）"""
        tools = []
        seen_names = set()
        for cat in categories:
            for tool in self._registry.get(cat, []):
                if tool.name not in seen_names:
                    tools.append(tool)
                    seen_names.add(tool.name)
        return tools

    def get_all_tools(self) -> List[BaseTool]:
        """获取注册中心内的全部工具"""
        return self.get_tools_by_categories(list(self._registry.keys()))

    def list_categories(self) -> List[str]:
        """列出所有已注册的工具类别"""
        return list(self._registry.keys())

    def list_all(self) -> Dict[str, List[str]]:
        """列出所有类别及其下的工具名，用于调试"""
        return {
            cat: [t.name for t in tools]
            for cat, tools in self._registry.items()
        }


# 全局单例
tool_registry = ToolRegistry()


if __name__ == "__main__":
    # 测试：需要先触发 agent_tools 的注册
    from agent.tools.agent_tools import _register_tools
    _register_tools()

    print("=== 工具注册中心 ===")
    for cat, names in tool_registry.list_all().items():
        print(f"  [{cat}] {', '.join(names)}")

    print(f"\n总计: {len(tool_registry.get_all_tools())} 个工具")
