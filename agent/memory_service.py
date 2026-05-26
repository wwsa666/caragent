"""
长期记忆与用户画像服务 (User Memory Service)
=============================================
基于 MongoDB 实现的车主长期记忆系统：
  - 每次对话结束后，调用 LLM 从对话中提取用户偏好标签
  - 标签持久化存储到 MongoDB 的 user_profiles 集合
  - 下次对话时，加载该用户的画像摘要，动态注入到 Agent 的 Prompt 中
  - 实现跨会话的"千人千面"个性化服务
"""

import json
from datetime import datetime
from typing import Optional

from pymongo import MongoClient
from model.factory import chat_model
from utils.prompt_loader import load_memory_prompts
from utils.logger_handler import logger


class UserMemoryService:
    """
    车主长期记忆管理。
    
    MongoDB 集合结构 (user_profiles):
    {
        "vin": "VIN1001",
        "preferences": ["喜欢开大功率空调", ...],
        "concerns": ["关注电池寿命", ...],
        "scenarios": ["日常通勤为主", ...],
        "issues": ["曾反馈充电异常", ...],
        "summary": "一句话画像摘要",
        "last_updated": "2025-03-15T10:30:00"
    }
    """

    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/",
                 db_name: str = "ev_service",
                 collection_name: str = "user_profiles"):
        try:
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.client[db_name]
            self.collection = self.db[collection_name]
            self.prompt_template = load_memory_prompts()
            logger.info("[UserMemoryService] 初始化成功")
        except Exception as e:
            logger.error(f"[UserMemoryService] 初始化失败: {e}")
            self.collection = None

    def load_profile(self, vin: str) -> str:
        """
        加载用户画像摘要文本，用于注入到 Agent 的 System Prompt 中。
        
        Args:
            vin: 车架号
            
        Returns:
            str: 画像摘要文本，如果不存在则返回空字符串
        """
        if self.collection is None:
            return ""

        try:
            profile = self.collection.find_one({"vin": vin})
            if not profile:
                logger.info(f"[UserMemoryService] VIN={vin} 暂无画像数据")
                return ""

            # 拼接画像摘要
            parts = []
            if profile.get("summary"):
                parts.append(f"画像概述：{profile['summary']}")
            if profile.get("preferences"):
                parts.append(f"驾驶偏好：{'、'.join(profile['preferences'])}")
            if profile.get("concerns"):
                parts.append(f"关注重点：{'、'.join(profile['concerns'])}")
            if profile.get("scenarios"):
                parts.append(f"用车场景：{'、'.join(profile['scenarios'])}")
            if profile.get("issues"):
                parts.append(f"历史问题：{'、'.join(profile['issues'])}")

            result = "\n".join(parts)
            logger.info(f"[UserMemoryService] 加载 VIN={vin} 画像: {result[:100]}...")
            return result

        except Exception as e:
            logger.error(f"[UserMemoryService] 加载画像失败: {e}")
            return ""

    def extract_and_save(self, vin: str, conversation: str) -> None:
        """
        从对话中提取用户偏好标签并持久化到 MongoDB。
        增量合并：新提取的标签会与已有标签合并（去重），而不是覆盖。
        
        Args:
            vin: 车架号
            conversation: 对话记录文本
        """
        if self.collection is None:
            return

        try:
            # 调用 LLM 提取偏好
            prompt = self.prompt_template.replace(
                "{vin}", vin
            ).replace(
                "{conversation}", conversation
            )

            response = chat_model.invoke(prompt)
            raw_text = response.content.strip()

            # 尝试解析 JSON
            # 处理可能被 markdown 包裹的 JSON
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            profile_data = json.loads(raw_text)

            # 检查是否有有效内容
            has_content = any([
                profile_data.get("preferences"),
                profile_data.get("concerns"),
                profile_data.get("scenarios"),
                profile_data.get("issues"),
            ])

            if not has_content:
                logger.info(f"[UserMemoryService] VIN={vin} 本次对话无可提取的画像信息")
                return

            # 增量合并到已有画像
            existing = self.collection.find_one({"vin": vin}) or {}

            merged = {
                "vin": vin,
                "preferences": list(set(
                    existing.get("preferences", []) + profile_data.get("preferences", [])
                )),
                "concerns": list(set(
                    existing.get("concerns", []) + profile_data.get("concerns", [])
                )),
                "scenarios": list(set(
                    existing.get("scenarios", []) + profile_data.get("scenarios", [])
                )),
                "issues": list(set(
                    existing.get("issues", []) + profile_data.get("issues", [])
                )),
                "summary": profile_data.get("summary", existing.get("summary", "")),
                "last_updated": datetime.now().isoformat(),
            }

            self.collection.update_one(
                {"vin": vin},
                {"$set": merged},
                upsert=True,
            )

            logger.info(f"[UserMemoryService] VIN={vin} 画像已更新: {merged['summary']}")

        except json.JSONDecodeError as e:
            logger.warning(f"[UserMemoryService] LLM 返回的画像 JSON 解析失败: {e}")
        except Exception as e:
            logger.error(f"[UserMemoryService] 画像提取/保存失败: {e}")


if __name__ == "__main__":
    service = UserMemoryService()

    # 测试加载
    profile = service.load_profile("VIN1001")
    print(f"当前画像: {profile if profile else '暂无'}")

    # 测试提取
    test_conversation = """
    用户：我平时经常在东北开车，冬天零下20度是常态，电池掉电特别快
    AI：根据您的使用场景，建议您...
    用户：我比较在意电池寿命，不想频繁换电池
    AI：理解您的顾虑...
    """
    service.extract_and_save("VIN1001", test_conversation)
    
    # 再次加载验证
    profile = service.load_profile("VIN1001")
    print(f"更新后画像: {profile}")
