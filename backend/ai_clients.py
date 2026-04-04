'''

OpenAI API 封装
设计目标：
1. 封装 OpenAI API 调用，提供简化的接口供 WebSocket
2. 支持流式响应
3. 支持工具调用（Function Calling），并正确处理工具调用的流式响应
4. 错误处理和异常捕获，确保调用稳定性

'''

from openai import AsyncOpenAI
from typing import List, Dict, Optional, Any


class OpenAIClient:
    """OpenAI API 客户端（支持 Function Calling）"""

    def __init__(self, settings: Dict):
        self.api_key = settings.get('api_key', '')
        self.base_url = settings.get('base_url', 'https://api.openai.com/v1')
        self.model = settings.get('model', 'gpt-3.5-turbo')
        self.max_tokens = settings.get('max_tokens', 2048)
        self.temperature = settings.get('temperature', 0.7)
        self.client = None

    async def get_client(self):
        """获取或创建异步 OpenAI 客户端"""
        if self.client is None:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=180.0
            )
        return self.client

    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.close()

    async def create_chat_completion(self, messages: List[Dict], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """非流式获取单轮响应，支持 tool_calls"""
        client = await self.get_client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False
            )
            message = response.choices[0].message
            result = {
                "role": message.role,
                "content": message.content or ""
            }
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            return result
        except Exception as e:
            raise Exception(f"OpenAI API 错误：{str(e)}")

    async def stream_chat(self, messages: List[Dict], tools: Optional[List[Dict[str, Any]]] = None):
        """流式聊天，支持工具调用"""
        client = await self.get_client()
        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=True
            )
            tool_calls = {}
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield {"type": "content", "content": delta.content}
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            index = tool_call_delta.index
                            if index not in tool_calls:
                                tool_calls[index] = {
                                    "id": tool_call_delta.id or "",
                                    "type": tool_call_delta.type or "function",
                                    "function": {
                                        "name": tool_call_delta.function.name or "" if tool_call_delta.function else "",
                                        "arguments": tool_call_delta.function.arguments or "" if tool_call_delta.function else ""
                                    }
                                }
                            else:
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tool_calls[index]["function"]["name"] += tool_call_delta.function.name
                                    if tool_call_delta.function.arguments:
                                        tool_calls[index]["function"]["arguments"] += tool_call_delta.function.arguments
                                if tool_call_delta.id:
                                    tool_calls[index]["id"] = tool_call_delta.id
            # 发送完成的工具调用
            for tool_call in tool_calls.values():
                yield {"type": "tool_call", "tool_call": tool_call}
        except Exception as e:
            raise Exception(f"OpenAI API 错误：{str(e)}")