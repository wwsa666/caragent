from utils.config_handler import prompts_conf
from utils.path_tool import get_abs_path
from utils.logger_handler import logger


def _load_prompt_file(config_key: str, label: str) -> str:
    """通用的 Prompt 文件加载函数"""
    try:
        prompt_path = get_abs_path(prompts_conf[config_key])
    except KeyError as e:
        logger.error(f"[{label}]在yaml配置项中没有{config_key}配置项")
        raise e

    try:
        return open(prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[{label}]解析提示词出错, {str(e)}")
        raise e


def load_system_prompts():
    return _load_prompt_file("main_prompt_path", "load_system_prompts")


def load_rag_prompts():
    return _load_prompt_file("rag_summarize_prompt_path", "load_rag_prompts")


def load_report_prompts():
    return _load_prompt_file("report_prompt_path", "load_report_prompts")


def load_intent_prompts():
    return _load_prompt_file("intent_prompt_path", "load_intent_prompts")


def load_diagnose_prompts():
    return _load_prompt_file("diagnose_prompt_path", "load_diagnose_prompts")


def load_review_prompts():
    return _load_prompt_file("review_prompt_path", "load_review_prompts")


def load_memory_prompts():
    return _load_prompt_file("memory_prompt_path", "load_memory_prompts")