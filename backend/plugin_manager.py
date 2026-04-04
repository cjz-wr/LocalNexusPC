"""
插件管理器模块
负责加载和管理所有插件

设计目标：
1. 插件结构清晰，易于开发和维护
2. 支持插件启用/禁用功能，并持久化状态
3. 提供插件接口，允许插件在用户消息和 AI 响应中进行处理
4. 支持插件暴露工具（Function Calling），并正确处理工具调用
5. 插件加载和执行过程中的错误处理，确保系统稳定性
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional

class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins = {}
        self.plugins_dir = Path(__file__).parent / "plugins"
        self.enabled_plugins = set()
        self.load_plugin_status()
    
    def load_plugin_status(self):
        """从数据库加载插件启用状态"""
        import sqlite3
        from contextlib import contextmanager
        
        app_dir = Path.home() / ".localnexus"
        db_path = app_dir / "data.db"
        
        @contextmanager
        def get_db():
            conn = sqlite3.connect(db_path)
            try:
                yield conn
            finally:
                conn.close()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM plugin_status WHERE enabled = 1')
            rows = cursor.fetchall()
            self.enabled_plugins = {row[0] for row in rows}
    
    def save_plugin_status(self, name: str, enabled: bool):
        """保存插件启用状态到数据库"""
        import sqlite3
        from contextlib import contextmanager
        from datetime import datetime
        
        app_dir = Path.home() / ".localnexus"
        db_path = app_dir / "data.db"
        
        @contextmanager
        def get_db():
            conn = sqlite3.connect(db_path)
            try:
                yield conn
            finally:
                conn.close()
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO plugin_status (name, enabled)
                VALUES (?, ?)
            ''', (name, 1 if enabled else 0))
            conn.commit()
    
    async def load_plugins(self):
        """加载所有插件"""
        if not self.plugins_dir.exists():
            print(f"Plugins directory not found: {self.plugins_dir}", file=sys.stderr)
            return
        
        # 扫描 plugins 目录
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            
            try:
                await self.load_plugin(file)
            except Exception as e:
                print(f"Failed to load plugin {file.name}: {e}", file=sys.stderr)
    
    async def load_plugin(self, plugin_path: Path):
        """加载单个插件"""
        # 动态导入插件模块
        spec = importlib.util.spec_from_file_location(
            plugin_path.stem,
            plugin_path
        )
        
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {plugin_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 检查插件是否有必需的属性
        if not hasattr(module, 'info'):
            raise ValueError(f"Plugin {plugin_path.name} missing 'info' dict")
        
        info = module.info
        plugin_name = info.get('name', plugin_path.stem)
        
        # 存储插件信息
        self.plugins[plugin_name] = {
            'module': module,
            'info': info,
            'enabled': plugin_name in self.enabled_plugins
        }
        
        print(f"Loaded plugin: {plugin_name} v{info.get('version', '1.0')}")
    
    def get_plugins(self) -> List[Dict]:
        """获取所有插件信息"""
        result = []
        for name, plugin_data in self.plugins.items():
            info = plugin_data['info']
            result.append({
                'name': name,
                'version': info.get('version', '1.0'),
                'description': info.get('description', ''),
                'enabled': plugin_data['enabled']
            })
        return result
    
    def set_plugin_enabled(self, name: str, enabled: bool):
        """设置插件启用状态"""
        if name in self.plugins:
            self.plugins[name]['enabled'] = enabled
            self.save_plugin_status(name, enabled)
            
            if enabled:
                print(f"Plugin enabled: {name}")
            else:
                print(f"Plugin disabled: {name}")
    
    async def process_user_message(self, message: str, context: Dict) -> str:
        """处理用户消息（通过启用的插件）"""
        for name, plugin_data in self.plugins.items():
            if not plugin_data['enabled']:
                continue
            
            module = plugin_data['module']
            if hasattr(module, 'on_user_message'):
                try:
                    result = module.on_user_message(message, context)
                    if asyncio.iscoroutine(result):
                        message = await result
                    else:
                        message = result
                except Exception as e:
                    print(f"Plugin {name} on_user_message error: {e}", file=sys.stderr)
        
        return message
    
    async def process_ai_response(self, response: str, context: Dict) -> str:
        """处理 AI 响应（通过启用的插件）"""
        for name, plugin_data in self.plugins.items():
            if not plugin_data['enabled']:
                continue
            
            module = plugin_data['module']
            if hasattr(module, 'on_ai_response'):
                try:
                    result = module.on_ai_response(response, context)
                    if asyncio.iscoroutine(result):
                        response = await result
                    else:
                        response = result
                except Exception as e:
                    print(f"Plugin {name} on_ai_response error: {e}", file=sys.stderr)
        
        return response

    def get_plugin_tools(self) -> List[Dict]:
        """获取所有已启用插件暴露的工具定义"""
        tools = []
        for name, plugin_data in self.plugins.items():
            if not plugin_data['enabled']:
                continue

            module = plugin_data['module']
            if hasattr(module, 'get_tools'):
                try:
                    plugin_tools = module.get_tools() or []
                    for tool in plugin_tools:
                        if isinstance(tool, dict):
                            tools.append({"plugin_name": name, **tool})
                except Exception as e:
                    print(f"Plugin {name} get_tools error: {e}", file=sys.stderr)
        return tools

    async def execute_tool(self, plugin_name: str, tool_name: str, arguments: Dict[str, Any]):
        """执行指定插件暴露的工具"""
        plugin_data = self.plugins.get(plugin_name)
        if not plugin_data:
            raise ValueError(f"Plugin not found: {plugin_name}")
        if not plugin_data['enabled']:
            raise ValueError(f"Plugin is disabled: {plugin_name}")

        module = plugin_data['module']
        if hasattr(module, 'execute_tool'):
            result = module.execute_tool(tool_name, arguments)
        elif hasattr(module, 'on_tool_call'):
            result = module.on_tool_call(tool_name, arguments)
        else:
            raise ValueError(f"Plugin {plugin_name} does not expose callable tools")

        if asyncio.iscoroutine(result):
            return await result
        return result

# 需要导入 asyncio 用于检测协程
import asyncio
