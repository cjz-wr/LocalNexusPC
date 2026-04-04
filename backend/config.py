'''
配置模块：负责应用的配置管理和数据库初始化
设计目标：
1. 管理应用的配置文件，支持加载和保存设置
2. 初始化 SQLite 数据库，创建必要的表结构
3. 提供数据库连接的上下文管理器，简化数据库操作
4. 支持配置迁移和版本兼容，确保设置在更新后仍然
兼容
5. 提供数据库操作的封装，简化数据库操作
'''

import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import uuid
from datetime import datetime

# 应用目录
APP_DIR = Path.home() / ".localnexus"
APP_DIR.mkdir(exist_ok=True)

DB_PATH = APP_DIR / "data.db"
SETTINGS_PATH = APP_DIR / "settings.json"


def init_database():
    """初始化数据库表"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 对话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        ''')

        # 插件状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS plugin_status (
                name TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1
            )
        ''')

        # 工具状态表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tools (
                name TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1
            )
        ''')

        # AI系统提示词表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_prompts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 检查是否已经有提示词数据，如果没有则添加默认提示词
        cursor.execute("SELECT COUNT(*) FROM system_prompts")
        prompt_count = cursor.fetchone()[0]
        
        if prompt_count == 0:
            # 添加默认提示词
            default_prompt_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO system_prompts (id, name, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                default_prompt_id,
                "通用AI助手",
                "你是一个有用的AI助手，尽可能详细、准确地回答用户的问题。",
                datetime.now(),
                datetime.now()
            ))
            
        conn.commit()


def load_settings() -> dict:
    """加载设置"""
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            settings = json.load(f)

        # 自动迁移：仅在旧版本还没有 mcp_configs 字段时转换一次
        if 'mcp' in settings and 'mcp_configs' not in settings:
            settings['mcp_configs'] = {
                'mcp_0': {
                    'id': 'mcp_0',
                    'name': '本地 MCP',
                    'server_url': settings['mcp'].get('server_url', 'http://localhost:8080'),
                    'model': settings['mcp'].get('model', 'default'),
                    'auth_token': settings['mcp'].get('auth_token', '')
                }
            }
            settings['enabled_mcp_configs'] = ['mcp_0']
            save_settings(settings)
            
        # 自动迁移：添加 memory 相关配置
        if 'memory' not in settings:
            settings['memory'] = {
                "refine_model": "gpt-3.5-turbo",
                "refine_model_api_key": "",
                "refine_model_base_url": "",
                "trigger_token_percent": 0.5,
                "sliding_window_percent": 0.85
            }
            save_settings(settings)

        return settings

    # 默认设置
    default_settings = {
        "protocol": "openai",
        "openai": {
            "api_key": "",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-3.5-turbo",
            "max_tokens": 2048,
            "temperature": 0.7
        },
        "mcp": {
            "server_url": "http://localhost:8080",
            "model": "default",
            "auth_token": ""
        },
        "mcp_configs": {
            "mcp_0": {
                "id": "mcp_0",
                "name": "本地 MCP",
                "server_url": "http://localhost:8080",
                "model": "default",
                "auth_token": ""
            }
        },
        "enabled_mcp_configs": ["mcp_0"],
        "tts": {
            "enabled": False,
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%"
        },
        "active_system_prompt_id": None,  # 新增：默认无激活的系统提示词
        "memory_enabled": True,  # 新增：记忆功能默认启用
        "memory": {  # 新增：记忆管理配置
            "refine_model": "gpt-3.5-turbo",
            "refine_model_api_key": "",
            "refine_model_base_url": "",
            "trigger_token_percent": 0.5,
            "sliding_window_percent": 0.85
        }
    }
    save_settings(default_settings)
    return default_settings


def save_settings(settings: dict):
    """保存设置"""
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()