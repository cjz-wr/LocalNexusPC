'''
路由模块
创建并配置 FastAPI 应用，并注册所有 HTTP 路由端点。
包含以下功能：
- 对话管理：创建、获取、删除对话，更新对话标题，获取对话消息，清空对话消息
- 设置管理：获取和保存设置，测试连接
- MCP 配置管理：获取、创建、更新、删除 MCP 配置，切换 MCP 配置启用状态
- 插件和工具管理：获取插件列表，更新插件状态，获取工具列表，更新工具状态
- 系统提示词管理：获取、创建、更新、删除系统提示词，设置/获取激活的系统提示词
- WebSocket 端点：处理聊天 WebSocket 连接，调用独立的 WebSocket 处理函数


'''

import json
import os
import uuid
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import load_settings, save_settings, get_db
from models import (
    ConversationCreate, TitleUpdate, PluginStatusUpdate,
    ToolStatusUpdate, Settings
)
from ai_clients import OpenAIClient
from plugin_manager import PluginManager
from tool_manager import ToolManager
from websocket_handler import handle_websocket_chat
from tts import init_tts_workers, stop_tts_workers, tts_worker_initialized
import logging

logger = logging.getLogger(__name__)

# 全局变量（在启动时设置）
app = None
plugin_manager = None
tool_manager = None
settings_cache = None
memory_store = None  # 新增：记忆存储实例

# 在文件顶部添加导入
try:
    from .treeMemoryStore import TreeMemoryStore
except ImportError:
    from treeMemoryStore import TreeMemoryStore


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(title="LocalNexus PC Backend")

    # CORS 配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    register_routes(app)

    # 注册启动/关闭事件
    @app.on_event("startup")
    async def startup_event():
        global plugin_manager, tool_manager, settings_cache, memory_store  # 新增 memory_store
        from config import init_database
        init_database()

        plugin_manager = PluginManager()
        await plugin_manager.load_plugins()

        # 初始化记忆存储（用户ID可配置，这里用固定值）
        memory_store = TreeMemoryStore(user_id="localnexus", db_path="./storage")
        logger.info("记忆存储已初始化")

        # 创建 tool_manager 时传入 memory_store
        tool_manager = ToolManager(plugin_manager=plugin_manager, memory_store=memory_store)
        await tool_manager.load_tools()

        settings_cache = load_settings()

        # 如果 TTS 可用且启用，初始化工作线程
        try:
            import edge_tts
            tts_settings = settings_cache.get('tts', {})
            if tts_settings.get('enabled', False):
                init_tts_workers()
                logger.info("流式 TTS 工作线程已在启动时初始化")
        except ImportError:
            pass

        port = os.environ.get('BACKEND_PORT', '8765')
        logger.info(f"PORT:{port}")
        logger.info("Backend server started")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("正在关闭后端服务...")
        if tool_manager:
            await tool_manager.close_all_sessions()
        # 停止 TTS 工作线程
        if tts_worker_initialized:  # 注意：需要从 tts 模块导入这个变量，但这里简单调用函数，函数内会判断
            await stop_tts_workers()
        logger.info("后端服务已关闭")

    return app


def register_routes(app: FastAPI):
    """注册所有 HTTP 路由端点"""

    @app.get("/conversations")
    async def get_conversations():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, created_at, updated_at
                FROM conversations
                ORDER BY updated_at DESC
            ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @app.post("/conversations")
    async def create_conversation(conv: ConversationCreate):
        conv_id = str(uuid.uuid4())
        title = conv.title or "新对话"
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (conv_id, title, datetime.now(), datetime.now()))
            conn.commit()
        return {"id": conv_id, "title": title}

    @app.delete("/conversations/{conversation_id}")
    async def delete_conversation(conversation_id: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
            conn.commit()
        return {"success": True}

    @app.put("/conversations/{conversation_id}/title")
    async def update_conversation_title(conversation_id: str, title_update: TitleUpdate):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ?
            ''', (title_update.title, datetime.now(), conversation_id))
            conn.commit()
        return {"success": True}

    @app.get("/conversations/{conversation_id}/messages")
    async def get_conversation_messages(conversation_id: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, role, content, timestamp
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            ''', (conversation_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @app.post("/conversations/{conversation_id}/clear")
    async def clear_conversation_messages(conversation_id: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE conversation_id = ?', (conversation_id,))
            cursor.execute('''
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
            ''', (datetime.now(), conversation_id))
            conn.commit()
        return {"success": True}

    # ==================== System Prompts Management API ====================

    @app.get("/system-prompts")
    async def get_system_prompts():
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, content, created_at, updated_at FROM system_prompts ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @app.post("/system-prompts")
    async def create_system_prompt(data: Dict[str, str]):
        name = data.get("name", "").strip()
        content = data.get("content", "").strip()
        if not name or not content:
            raise HTTPException(status_code=400, detail="名称和内容不能为空")
        prompt_id = str(uuid.uuid4())
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO system_prompts (id, name, content) VALUES (?, ?, ?)",
                (prompt_id, name, content)
            )
            conn.commit()
        return {"id": prompt_id, "name": name, "content": content}

    @app.put("/system-prompts/{prompt_id}")
    async def update_system_prompt(prompt_id: str, data: Dict[str, str]):
        name = data.get("name", "").strip()
        content = data.get("content", "").strip()
        if not name or not content:
            raise HTTPException(status_code=400, detail="名称和内容不能为空")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE system_prompts SET name = ?, content = ?, updated_at = ? WHERE id = ?",
                (name, content, datetime.now(), prompt_id)
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="提示词不存在")
            conn.commit()
        return {"success": True}

    @app.delete("/system-prompts/{prompt_id}")
    async def delete_system_prompt(prompt_id: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="提示词不存在")
            # 如果删除的是当前激活的提示词，清除激活状态
            settings = load_settings()
            if settings.get("active_system_prompt_id") == prompt_id:
                settings["active_system_prompt_id"] = None
                save_settings(settings)
            conn.commit()
        return {"success": True}

    @app.get("/system-prompts/active")
    async def get_active_system_prompt():
        settings = load_settings()
        active_id = settings.get("active_system_prompt_id")
        if not active_id:
            return {"id": None, "name": None, "content": None}
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, content FROM system_prompts WHERE id = ?", (active_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            else:
                # 如果激活的ID无效，清除设置
                settings["active_system_prompt_id"] = None
                save_settings(settings)
                return {"id": None, "name": None, "content": None}

    @app.post("/system-prompts/active")
    async def set_active_system_prompt(data: Dict[str, str]):
        prompt_id = data.get("id")
        if prompt_id is None:
            # 传入 null 表示清除激活
            settings = load_settings()
            settings["active_system_prompt_id"] = None
            save_settings(settings)
            return {"success": True}
        # 验证 ID 存在
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM system_prompts WHERE id = ?", (prompt_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="提示词不存在")
        settings = load_settings()
        settings["active_system_prompt_id"] = prompt_id
        save_settings(settings)
        return {"success": True}

    # ==================== Settings Management API ====================

    @app.get("/settings")
    async def get_settings():
        settings = load_settings()
        settings['protocol'] = 'openai'
        return settings

    @app.post("/settings")
    async def save_settings_endpoint(settings: Settings):
        global settings_cache, tool_manager
        existing_settings = load_settings()
        settings_dict = settings.model_dump(exclude_none=True)
        merged_settings = {**existing_settings, **settings_dict}
        merged_settings['protocol'] = 'openai'
        merged_settings['mcp_configs'] = settings_dict.get('mcp_configs', existing_settings.get('mcp_configs', {}))
        merged_settings['enabled_mcp_configs'] = settings_dict.get('enabled_mcp_configs', existing_settings.get('enabled_mcp_configs', []))
        merged_settings['memory_enabled'] = settings_dict.get('memory_enabled', existing_settings.get('memory_enabled', True))  # 保留记忆设置
        save_settings(merged_settings)
        settings_cache = merged_settings
        # 重新加载工具
        await tool_manager.load_tools(merged_settings)
        return {"success": True}

    @app.post("/test-connection")
    async def test_connection(settings: Settings):
        try:
            protocol = settings.protocol or 'openai'
            if protocol != 'openai':
                return {"success": False, "error": "当前版本仅支持 OpenAI 聊天协议"}

            client = OpenAIClient(settings.openai or {})
            openai_client = await client.get_client()
            await openai_client.chat.completions.create(
                model=client.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            await client.close()
            return {"success": True, "message": "OpenAI API 连接成功"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== MCP Config Management API ====================

    @app.get("/mcp-configs")
    async def get_mcp_configs():
        try:
            settings = load_settings()
            mcp_configs = settings.get('mcp_configs', {})
            enabled_mcp_configs = settings.get('enabled_mcp_configs', [])
            return {"configs": mcp_configs, "enabled_mcp_configs": enabled_mcp_configs}
        except Exception as e:
            logger.error(f"获取 MCP 配置失败：{e}")
            raise HTTPException(status_code=500, detail=f"获取配置失败：{str(e)}")

    @app.post("/mcp-configs")
    async def create_mcp_config(config: Dict):
        try:
            settings = load_settings()
            if 'mcp_configs' not in settings:
                settings['mcp_configs'] = {}
            config_index = len(settings['mcp_configs'])
            config_id = f"mcp_{config_index}"
            settings['mcp_configs'][config_id] = {
                "id": config_id,
                "name": config.get('name', f'MCP 配置 {config_index}'),
                "server_url": config.get('server_url', 'http://localhost:8080'),
                "model": config.get('model', 'default'),
                "auth_token": config.get('auth_token', '')
            }
            if 'enabled_mcp_configs' not in settings:
                settings['enabled_mcp_configs'] = []
            if config_id not in settings['enabled_mcp_configs']:
                settings['enabled_mcp_configs'].append(config_id)
            save_settings(settings)
            logger.info(f"创建 MCP 配置：{config_id} - {settings['mcp_configs'][config_id]['name']}")
            return {"success": True, "config_id": config_id}
        except Exception as e:
            logger.error(f"创建 MCP 配置失败：{e}")
            raise HTTPException(status_code=500, detail=f"创建配置失败：{str(e)}")

    @app.put("/mcp-configs/{config_id}")
    async def update_mcp_config(config_id: str, config: Dict):
        try:
            settings = load_settings()
            if 'mcp_configs' not in settings or config_id not in settings['mcp_configs']:
                raise HTTPException(status_code=404, detail="配置不存在")
            if 'name' in config:
                settings['mcp_configs'][config_id]['name'] = config['name']
            if 'server_url' in config:
                settings['mcp_configs'][config_id]['server_url'] = config['server_url']
            if 'model' in config:
                settings['mcp_configs'][config_id]['model'] = config['model']
            if 'auth_token' in config:
                settings['mcp_configs'][config_id]['auth_token'] = config['auth_token']
            save_settings(settings)
            logger.info(f"更新 MCP 配置：{config_id} - {settings['mcp_configs'][config_id]['name']}")
            return {"success": True}
        except Exception as e:
            logger.error(f"更新 MCP 配置失败：{e}")
            raise HTTPException(status_code=500, detail=f"更新配置失败：{str(e)}")

    @app.delete("/mcp-configs/{config_id}")
    async def delete_mcp_config(config_id: str):
        try:
            settings = load_settings()
            if 'mcp_configs' not in settings or config_id not in settings['mcp_configs']:
                raise HTTPException(status_code=404, detail="配置不存在")
            del settings['mcp_configs'][config_id]
            if 'enabled_mcp_configs' in settings and config_id in settings['enabled_mcp_configs']:
                settings['enabled_mcp_configs'].remove(config_id)
            save_settings(settings)
            logger.info(f"删除 MCP 配置：{config_id}")
            return {"success": True}
        except Exception as e:
            logger.error(f"删除 MCP 配置失败：{e}")
            raise HTTPException(status_code=500, detail=f"删除配置失败：{str(e)}")

    @app.post("/mcp-configs/toggle-enabled")
    async def toggle_mcp_config_enabled(config_id: str, enabled: bool):
        try:
            settings = load_settings()
            if 'mcp_configs' not in settings or config_id not in settings['mcp_configs']:
                raise HTTPException(status_code=404, detail="配置不存在")
            if 'enabled_mcp_configs' not in settings:
                settings['enabled_mcp_configs'] = []
            if enabled:
                if config_id not in settings['enabled_mcp_configs']:
                    settings['enabled_mcp_configs'].append(config_id)
                logger.info(f"启用 MCP 配置：{config_id} - {settings['mcp_configs'][config_id]['name']}")
            else:
                if config_id in settings['enabled_mcp_configs']:
                    settings['enabled_mcp_configs'].remove(config_id)
                logger.info(f"禁用 MCP 配置：{config_id} - {settings['mcp_configs'][config_id]['name']}")
            save_settings(settings)
            return {"success": True}
        except Exception as e:
            logger.error(f"切换 MCP 配置启用状态失败：{e}")
            raise HTTPException(status_code=500, detail=f"切换配置失败：{str(e)}")

    # ==================== Plugin and Tool APIs ====================

    @app.get("/plugins")
    async def get_plugins():
        if not plugin_manager:
            return []
        plugins = []
        for plugin_info in plugin_manager.get_plugins():
            plugins.append({
                "name": plugin_info['name'],
                "version": plugin_info['version'],
                "description": plugin_info['description'],
                "enabled": plugin_info['enabled']
            })
        return plugins

    @app.put("/plugins/{plugin_name}/status")
    async def update_plugin_status(plugin_name: str, status: PluginStatusUpdate):
        if not plugin_manager:
            raise HTTPException(status_code=500, detail="插件管理器未初始化")
        plugin_manager.set_plugin_enabled(plugin_name, status.enabled)
        return {"success": True}

    @app.get("/tools")
    async def get_tools():
        """获取当前可用的工具列表（本地插件 + MCP 远程工具）。"""
        # 使用全局 tool_manager 获取工具
        return tool_manager.get_serialized_tools()

    @app.put("/tools/{tool_name}/status")
    async def update_tool_status(tool_name: str, status: ToolStatusUpdate):
        """启用或禁用指定工具。"""
        tool_manager.set_tool_enabled(tool_name, status.enabled)
        return {"success": True}

    # ==================== WebSocket Endpoint ====================

    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        # 调用独立的 WebSocket 处理函数，传递必要的全局对象
        await handle_websocket_chat(
            websocket,
            plugin_manager=plugin_manager,
            tool_manager=tool_manager,
            settings_cache=settings_cache,
            memory_store=memory_store   # 新增
        )