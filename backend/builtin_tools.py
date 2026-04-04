# backend/builtin_tools.py
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MemoryQueryTool:
    """内置记忆查询工具"""
    def __init__(self, memory_store):
        self.name = "query_memory"
        self.display_name = "查询记忆"
        self.description = "根据自然语言查询或关键词搜索历史记忆。"
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "查询文本，可以是自然语言问题或关键词"
                },
                "root_category": {
                    "type": "string",
                    "description": "可选，限定记忆类别（Work, Tech, Life 等）",
                    "enum": ["Work", "Tech", "Learning", "Health", "Finance", "Ideas", "Life", "General", "UserInfo"]
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回的记忆条数，默认 3",
                    "default": 3
                }
            },
            "required": ["query"]
        }
        self.source_type = "builtin"
        self.source_id = "memory"
        self.enabled = True
        self.memory_store = memory_store

    def to_openai_tool(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }

    def to_dict(self):
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "provider_name": "系统"
        }

    async def execute(self, arguments: Dict[str, Any]) -> str:
        query = arguments.get("query", "")
        root_category = arguments.get("root_category")
        top_k = arguments.get("top_k", 3)

        if not query:
            return "查询词不能为空。"

        try:
            memories = self.memory_store.query_memories(
                root_category=root_category,
                text_query=query,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"记忆查询失败: {e}")
            return f"记忆查询出错：{str(e)}"

        if not memories:
            return "未找到相关记忆。"

        lines = ["【相关记忆】"]
        for i, mem in enumerate(memories, 1):
            title = mem.get("title", "无标题")
            summary = mem.get("summary", "")
            facts = mem.get("key_facts", [])
            facts_str = "；".join(facts) if facts else ""
            lines.append(f"{i}. {title}：{summary} {facts_str}".strip())
        return "\n".join(lines)