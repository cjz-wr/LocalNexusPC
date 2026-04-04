"""
时间戳插件
在用户消息前添加时间戳
"""

from datetime import datetime

# 插件信息
info = {
    'name': 'timestamp',
    'version': '1.0.0',
    'description': '在用户消息前添加时间戳'
}

def get_tools():
    return [{
        'name': 'get_current_timestamp',
        'description': '获取当前本地时间戳。',
        'parameters': {
            'type': 'object',
            'properties': {},
            'additionalProperties': False
        }
    }]

def execute_tool(tool_name: str, arguments: dict):
    if tool_name != 'get_current_timestamp':
        raise ValueError(f'Unsupported tool: {tool_name}')
    return {'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

def on_user_message(message: str, context: dict) -> str:
    """
    处理用户消息：在消息前添加时间戳
    
    Args:
        message: 原始消息
        context: 上下文信息（包含 conversation_id 等）
    
    Returns:
        处理后的消息
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f"[{timestamp}] {message}"

def on_ai_response(response: str, context: dict) -> str:
    """
    处理 AI 响应：不做处理
    
    Args:
        response: AI 的原始响应
        context: 上下文信息
    
    Returns:
        处理后的响应
    """
    return response
