'''
模型定义
'''

from pydantic import BaseModel
from typing import Optional, Dict, List


class ConversationCreate(BaseModel):
    title: Optional[str] = None


class MessageCreate(BaseModel):
    role: str
    content: str


class TitleUpdate(BaseModel):
    title: str


class PluginStatusUpdate(BaseModel):
    enabled: bool


class ToolStatusUpdate(BaseModel):
    enabled: bool


class Settings(BaseModel):
    protocol: str = "openai"
    openai: Optional[Dict] = None
    mcp: Optional[Dict] = None          # 保留向后兼容（单配置模式）
    mcp_configs: Optional[Dict] = None   # 多配置存储
    enabled_mcp_configs: Optional[List[str]] = None  # 启用的配置 ID 列表
    tts: Optional[Dict] = None
    memory_enabled: Optional[bool] = True   # 新增