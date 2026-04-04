"""
大写转换插件
将用户消息转换为大写
"""

# 插件信息
info = {
    'name': 'uppercase',
    'version': '1.0.0',
    'description': '将用户消息转换为大写'
}

def get_tools():
    return [{
        'name': 'to_uppercase',
        'description': '将输入文本转换为大写。',
        'parameters': {
            'type': 'object',
            'properties': {
                'text': {
                    'type': 'string',
                    'description': '要转换成大写的文本'
                }
            },
            'required': ['text'],
            'additionalProperties': False
        }
    }]

# 插件接口实现,供插件管理器调用
def execute_tool(tool_name: str, arguments: dict):
    if tool_name != 'to_uppercase':
        raise ValueError(f'Unsupported tool: {tool_name}')
    return (arguments or {}).get('text', '').upper()


def on_user_message(message: str, context: dict) -> str:
    """
    处理用户消息：转换为大写
    
    Args:
        message: 原始消息
        context: 上下文信息（包含 conversation_id 等）
    
    Returns:
        处理后的消息
    """
    return message.upper()

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
