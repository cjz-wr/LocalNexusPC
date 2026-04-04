"""
Tool manager for LocalNexus PC.

MCP servers are treated as tool providers.
插件提供的工具会自动注册，工具名称会根据插件名称进行前缀处理以避免冲突。
"""

from __future__ import annotations

import os
import json
import asyncio
import logging
import sqlite3
import time
import importlib.util
import inspect
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from contextlib import AsyncExitStack
from pydantic import BaseModel
from plugin_manager import PluginManager

# Check if mcp library is available
try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.types import TextContent
    from anyio import ClosedResourceError
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    from anyio import ClosedResourceError
    logging.warning("mcp library not installed. MCP tool servers will be disabled.")

# 在文件顶部添加导入
try:
    from .builtin_tools import MemoryQueryTool
except ImportError:
    from builtin_tools import MemoryQueryTool

APP_DIR = Path.home() / ".localnexus"
APP_DIR.mkdir(exist_ok=True)
DB_PATH = APP_DIR / "data.db"

logger = logging.getLogger(__name__)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def normalize_tool_name(name: str, fallback: str = "tool") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in (name or fallback))
    if not cleaned:
        cleaned = fallback
    if not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = f"tool_{cleaned}"
    return cleaned[:64]


def stringify_result(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        return str(value)


class Tool:
    """工具基类。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        *,
        original_name: Optional[str] = None,
        provider_name: str = "",
        source_type: str = "unknown",
        source_id: str = "",
        enabled: bool = True,
    ):
        self.name = name
        self.original_name = original_name or name
        self.display_name = original_name or name
        self.description = description or "No description provided."
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.provider_name = provider_name or source_id or source_type
        self.source_type = source_type
        self.source_id = source_id
        self.enabled = enabled

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "provider_name": self.provider_name,
        }

    async def execute(self, arguments: Dict[str, Any]) -> str:
        raise NotImplementedError


class MCPTool(Tool):
    """通过 MCP 工具服务器远程调用的工具（使用官方 MCP 库）。"""

    def __init__(self, *, session: ClientSession, tool_def: Any, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.tool_def = tool_def

    async def execute(self, arguments: Dict[str, Any]) -> str:
        """调用 MCP 服务器的工具。"""
        try:
            result = await self.session.call_tool(self.original_name, arguments=arguments or {})
            if result.content and len(result.content) > 0:
                # 通常 MCP 返回的内容是 TextContent 对象列表
                first = result.content[0]
                if isinstance(first, TextContent):
                    return first.text
                else:
                    # 如果不是 TextContent，尝试序列化整个对象
                    try:
                        return json.dumps([c.model_dump() for c in result.content], ensure_ascii=False)
                    except AttributeError:
                        # 如果 model_dump 不可用，使用 __dict__ 方式
                        return json.dumps([{k: v for k, v in c.__dict__.items() if not k.startswith('_')} for c in result.content], ensure_ascii=False)
            return ""
        except Exception as e:
            logger.error(f"MCP tool {self.original_name} execution failed: {e}")
            raise


class PluginTool(Tool):
    """由本地插件提供的工具。"""

    def __init__(self, *, plugin_manager, plugin_name: str, **kwargs):
        super().__init__(**kwargs)
        self.plugin_manager = plugin_manager
        self.plugin_name = plugin_name

    async def execute(self, arguments: Dict[str, Any]) -> str:
        result = await self.plugin_manager.execute_tool(self.plugin_name, self.original_name, arguments or {})
        return stringify_result(result)


class ToolManager:
    def __init__(self, plugin_manager=None, memory_store=None):
        self.plugin_manager = plugin_manager
        self.memory_store = memory_store          # 新增
        self.tools = []
        self._tool_index = {}
        self.mcp_sessions = {}
        self._mcp_loading_locks = {}
        self._load_settings()
        self._register_builtin_tools()            # 新增

    def _register_builtin_tools(self):
        """注册内置工具（如记忆查询）"""
        if self.memory_store:
            tool = MemoryQueryTool(self.memory_store)
            self._register_tool(tool)
        else:
            logging.warning("未提供 memory_store，内置记忆查询工具不可用")

    def _load_settings(self) -> Dict[str, Any]:
        settings_path = APP_DIR / "settings.json"
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_tool_status_map(self) -> Dict[str, bool]:
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, enabled FROM tools")
                rows = cursor.fetchall()
            return {row["name"]: bool(row["enabled"]) for row in rows}
        except sqlite3.Error:
            return {}

    def set_tool_enabled(self, tool_name: str, enabled: bool):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO tools (name, enabled)
                VALUES (?, ?)
                """,
                (tool_name, 1 if enabled else 0),
            )
            conn.commit()

    def _make_unique_name(self, raw_name: str, source_id: str) -> str:
        candidate = normalize_tool_name(raw_name)
        if candidate not in self._tool_index:
            return candidate

        prefixed = normalize_tool_name(f"{source_id}_{raw_name}")
        if prefixed not in self._tool_index:
            return prefixed

        suffix = 2
        while True:
            numbered = normalize_tool_name(f"{prefixed}_{suffix}")
            if numbered not in self._tool_index:
                return numbered
            suffix += 1

    def _register_tool(self, tool: Tool):
        self.tools.append(tool)
        self._tool_index[tool.name] = tool

    async def close_all_sessions(self):
        """关闭所有 MCP 会话，使用锁保证安全"""
        for config_id, info in list(self.mcp_sessions.items()):
            try:
                await info["stack"].aclose()
                logger.info(f"Closed MCP session for {config_id}")
            except Exception as e:
                logger.error(f"Error closing MCP session {config_id}: {e}")
            finally:
                # 无论成功与否，都从字典中移除
                self.mcp_sessions.pop(config_id, None)

    async def load_tools(self, settings: Optional[Dict[str, Any]] = None):
        """加载所有工具（本地插件 + MCP 服务器）。"""
        # 先关闭旧的 MCP 会话
        await self.close_all_sessions()

        settings = settings or self._load_settings()
        status_map = self._get_tool_status_map()
        self.tools.clear()
        self._tool_index.clear()

        mcp_configs = settings.get("mcp_configs", {}) or {}
        enabled_configs = settings.get("enabled_mcp_configs", []) or []
        for config_id in enabled_configs:
            config = mcp_configs.get(config_id)
            if config:
                await self._load_mcp_server_tools(config_id, config, status_map)

        self._load_plugin_tools(status_map)

    async def _load_mcp_server_tools(self, config_id: str, config: Dict[str, Any], status_map: Dict[str, bool]):
        """加载单个 MCP 服务器的工具，带并发锁"""
        # 防止并发重复加载
        if config_id in self._mcp_loading_locks:
            async with self._mcp_loading_locks[config_id]:
                return await self._do_load_mcp_server_tools(config_id, config, status_map)
        else:
            self._mcp_loading_locks[config_id] = asyncio.Lock()
            async with self._mcp_loading_locks[config_id]:
                return await self._do_load_mcp_server_tools(config_id, config, status_map)

    async def _do_load_mcp_server_tools(self, config_id: str, config: Dict[str, Any], status_map: Dict[str, bool]):
        """实际加载逻辑（原 _load_mcp_server_tools 的内容）"""
        if not MCP_AVAILABLE:
            logger.warning("MCP library not available. Skipping MCP server connection.")
            return

        server_url = config.get("server_url", "").strip()
        auth_token = config.get("auth_token", "").strip()
        if not server_url:
            logger.warning(f"MCP config {config_id}: no server_url, skip")
            return

        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        stack = AsyncExitStack()
        try:
            # 建立 SSE 连接
            streams = await stack.enter_async_context(sse_client(url=server_url, headers=headers))
            session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            tools = tools_result.tools
            logger.info(f"MCP server {config_id} connected, found {len(tools)} tools")

            # 保存会话信息，以便后续关闭
            self.mcp_sessions[config_id] = {"stack": stack, "session": session}

            # 注册工具（先移除该配置已有的工具，再重新注册）
            # 这里简单做法：重新加载时，先删除该配置的所有工具，再添加新的
            tools_to_remove = [t for t in self.tools if t.source_id == config_id]
            for t in tools_to_remove:
                self.tools.remove(t)
                if t.name in self._tool_index:
                    del self._tool_index[t.name]

            for tool in tools:
                raw_name = tool.name
                if not raw_name:
                    continue

                tool_name = self._make_unique_name(raw_name, config_id)
                enabled = status_map.get(tool_name, True)
                mcp_tool = MCPTool(
                    name=tool_name,
                    original_name=raw_name,
                    description=tool.description or "",
                    parameters=tool.inputSchema or {"type": "object", "properties": {}},
                    provider_name=config.get("name", config_id),
                    source_type="mcp",
                    source_id=config_id,
                    enabled=enabled,
                    session=session,
                    tool_def=tool,
                )
                self._register_tool(mcp_tool)

        except Exception as e:
            logger.error(f"Failed to load MCP server {config_id} ({server_url}): {e}")
            # 如果连接失败，确保清理已分配的资源
            await stack.aclose()
            # 不保存失败的会话

    def _load_plugin_tools(self, status_map: Dict[str, bool]):
        if not self.plugin_manager or not hasattr(self.plugin_manager, "get_plugin_tools"):
            return

        for tool_def in self.plugin_manager.get_plugin_tools():
            raw_name = tool_def.get("name")
            if not raw_name:
                continue

            plugin_name = tool_def.get("plugin_name", "plugin")
            tool_name = self._make_unique_name(raw_name, plugin_name)
            enabled = status_map.get(tool_name, True)
            tool = PluginTool(
                name=tool_name,
                original_name=raw_name,
                description=tool_def.get("description", ""),
                parameters=tool_def.get("parameters") or {"type": "object", "properties": {}},
                provider_name=plugin_name,
                source_type="plugin",
                source_id=plugin_name,
                enabled=enabled,
                plugin_manager=self.plugin_manager,
                plugin_name=plugin_name,
            )
            self._register_tool(tool)

    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self.tools if tool.enabled]

    def get_serialized_tools(self) -> List[Dict[str, Any]]:
        return [tool.to_dict() for tool in self.tools]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """执行工具，自动处理 MCP 会话重连"""
        tool = self._tool_index.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool {tool_name} not found")
        if not tool.enabled:
            raise ValueError(f"Tool {tool_name} is disabled")

        # 对于 MCP 工具，增加重试逻辑
        if isinstance(tool, MCPTool):
            config_id = tool.source_id
            last_error = None
            for attempt in range(self.MCP_RETRY_MAX + 1):
                try:
                    # 确保会话可用（如果已关闭则先重建）
                    if not self._is_mcp_session_alive(config_id):
                        logger.info(f"MCP session for {config_id} is dead, reconnecting...")
                        await self._reconnect_mcp_config(config_id)

                    return await tool.execute(arguments)

                except ClosedResourceError as e:
                    last_error = e
                    logger.warning(f"MCP tool {tool_name} attempt {attempt+1} failed: ClosedResourceError")
                    if attempt < self.MCP_RETRY_MAX:
                        # 等待后重试
                        await asyncio.sleep(self.MCP_RETRY_DELAY)
                        # 重建会话
                        await self._reconnect_mcp_config(config_id)
                        # 重新获取工具对象（因为会话重建后，工具列表可能变化）
                        tool = self._tool_index.get(tool_name)
                        if not tool:
                            raise ValueError(f"Tool {tool_name} lost after reconnection")
                        continue
                    else:
                        raise Exception(f"MCP tool {tool_name} failed after {self.MCP_RETRY_MAX+1} attempts: {e}") from e

                except Exception as e:
                    # 其他异常直接抛出
                    logger.error(f"MCP tool {tool_name} execution error: {e}")
                    raise

            # 理论上不会执行到这里
            raise last_error

        # 非 MCP 工具直接执行
        return await tool.execute(arguments or {})

    def _is_mcp_session_alive(self, config_id: str) -> bool:
        """检查 MCP 会话是否存活（简单判断：会话对象存在且未关闭）"""
        info = self.mcp_sessions.get(config_id)
        if not info:
            return False
        # 通过检查流是否被关闭来判断（anyio 没有直接提供，但可尝试发送一个空请求）
        # 这里采用乐观假设，如果会话存在则认为是活的，实际验证通过 _reconnect 时的异常来触发
        return True

    async def _reconnect_mcp_config(self, config_id: str):
        """重建指定 MCP 配置的会话，并重新加载其工具"""
        # 关闭旧会话
        if config_id in self.mcp_sessions:
            try:
                await self.mcp_sessions[config_id]["stack"].aclose()
            except Exception as e:
                logger.error(f"Error closing old session for {config_id}: {e}")
            finally:
                del self.mcp_sessions[config_id]

        # 从数据库重新加载该配置
        settings = self._load_settings()
        mcp_configs = settings.get("mcp_configs", {})
        config = mcp_configs.get(config_id)
        if not config:
            logger.error(f"MCP config {config_id} not found in settings, cannot reconnect")
            return

        # 重新加载该配置的工具（会创建新会话并注册工具）
        status_map = self._get_tool_status_map()
        await self._load_mcp_server_tools(config_id, config, status_map)
        logger.info(f"Reconnected MCP config {config_id} and reloaded tools")