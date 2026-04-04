'''
WebSocket 处理模块

设计目标：
1. 处理来自前端的 WebSocket 消聊天消息，支持多轮对话和工具调用
2. 与 OpenAI 客户端集成，支持流式响应和工具调用
3. 与插件系统集成，允许插件在用户消息和 AI 响应中进行处理
4. 支持 TTS 配置，允许在聊天过程中进行文本转语音
'''

import asyncio
import json
import uuid
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import WebSocket

from config import get_db, load_settings
from ai_clients import OpenAIClient
from tts import stream_tts_sentence
from plugin_manager import PluginManager
from tool_manager import ToolManager

logger = logging.getLogger(__name__)

# 预设模型最大token数
MODEL_MAX_TOKENS = {
    "gpt-3.5-turbo": 4096,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "qwen3-max-2026-01-23": 8192,
}

def get_model_max_tokens(model: str) -> int:
    """获取模型的最大token数"""
    if model in MODEL_MAX_TOKENS:
        return MODEL_MAX_TOKENS[model]
    else:
        # 尝试从模型名中推断
        if "8k" in model.lower():
            return 8192
        elif "32k" in model.lower():
            return 32768
        elif "128k" in model.lower():
            return 128000
        else:
            logger.warning(f"未知模型 {model}，使用默认最大token数 4096")
            return 4096

# key: conversation_id, value: {"new_tokens": int, "total_tokens": int, "last_refine_time": timestamp}
conversation_token_tracker = {}

def count_tokens(messages: List[Dict], model: str) -> int:
    """估算消息列表消耗的 token 数"""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        # 如果没有安装tiktoken，使用简单估算
        total_str = " ".join(str(msg.get("content", "")) for msg in messages)
        # 简单估算：一个token约等于4个字符
        return len(total_str) // 4

    tokens_per_message = 3
    num_tokens = 0
    for msg in messages:
        num_tokens += tokens_per_message
        for key, value in msg.items():
            if isinstance(value, str):
                num_tokens += len(encoding.encode(value))
    num_tokens += 3
    return num_tokens


def count_string_tokens(text: str, model: str) -> int:
    """估算单个字符串的 token 数"""
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        # 如果没有安装tiktoken，使用简单估算
        # 简单估算：一个token约等于4个字符
        return len(text) // 4

    return len(encoding.encode(text))


def trim_conversation_history(conversation_id: str, sliding_threshold: int, chat_model: str):
    """删除最早的非系统消息，直到总 token 低于阈值"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, role, content FROM messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp ASC
        """, (conversation_id,))
        all_msgs = [{"id": row["id"], "role": row["role"], "content": row["content"]} for row in cursor.fetchall()]
        
        # 计算当前总tokens
        total_tokens = count_tokens(all_msgs, chat_model)
        
        if total_tokens <= sliding_threshold:
            return  # 不需要清理
        
        # 从最旧开始删除，直到 token 数达标
        removed_count = 0
        for msg in all_msgs:
            if msg["role"] != "system":  # 不删除系统消息
                # 计算删除这条消息后的总tokens
                msg_tokens = count_string_tokens(msg["content"], chat_model)
                total_tokens -= msg_tokens
                
                # 删除数据库中的对应消息
                cursor.execute("DELETE FROM messages WHERE id = ?", (msg["id"],))
                removed_count += 1
                
                if total_tokens <= sliding_threshold * 0.8:  # 清理到阈值的80%
                    break
        
        if removed_count > 0:
            conn.commit()
            logger.info(f"滑动窗口清理：删除了 {removed_count} 条历史消息")


def count_chinese_chars(s: str) -> int:
    """统计字符串中的中文字符数量（\u4e00-\u9fff）"""
    return len(re.findall(r'[\u4e00-\u9fff]', s))


def split_sentences(text: str, min_chars: int = 15):
    """
    将文本切分为完整句子，同时过滤过短的句子（短句会继续累积）。
    返回 (句子列表，剩余未完成部分)
    """
    sentences = []
    buffer = ""
    # 句子结束符集合（中英文标点）
    end_punctuations = set("。！？；\n!?.;")
    for ch in text:
        buffer += ch
        if ch in end_punctuations:
            # 遇到结束符，检查当前 buffer 的中文字符数
            if count_chinese_chars(buffer) >= min_chars:
                # 达到阈值，输出句子并清空缓冲区
                sentences.append(buffer.strip())
                buffer = ""
            # 否则，保留 buffer（短句继续累积）
    return sentences, buffer


async def handle_websocket_chat(
    websocket: WebSocket,
    plugin_manager: Optional[PluginManager],
    tool_manager: ToolManager,
    settings_cache: Dict,
    memory_store   # 新增
):
    """处理 WebSocket 聊天消息"""
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)

            conversation_id = request.get('conversation_id')
            user_message = request.get('message')
            request_id = request.get('id', str(uuid.uuid4()))

            if not conversation_id or not user_message:
                await websocket.send_json({"type": "error", "content": "缺少 conversation_id 或 message"})
                continue

            # 获取最新设置
            settings = load_settings()
            settings['protocol'] = 'openai'
            # 创建 OpenAI 客户端
            openai_client = OpenAIClient(settings.get('openai', {}))

            # 获取记忆配置
            mem_cfg = settings.get("memory", {})
            refine_model = mem_cfg.get("refine_model", "gpt-3.5-turbo")
            refine_model_api_key = mem_cfg.get("refine_model_api_key", "")
            refine_model_base_url = mem_cfg.get("refine_model_base_url", "")
            trigger_ratio = mem_cfg.get("trigger_token_percent", 0.5)
            sliding_ratio = mem_cfg.get("sliding_window_percent", 0.85)

            # 获取聊天模型的最大 token
            chat_model = settings.get("openai", {}).get("model", "gpt-3.5-turbo")
            max_tokens_model = get_model_max_tokens(chat_model)
            trigger_threshold = int(max_tokens_model * trigger_ratio)
            sliding_threshold = int(max_tokens_model * sliding_ratio)

            # 在函数开头初始化该会话的 token 计数器（如果不存在）
            if conversation_id not in conversation_token_tracker:
                conversation_token_tracker[conversation_id] = {
                    "new_tokens": 0,
                    "total_tokens": 0,
                    "last_refine_time": 0
                }
            tracker = conversation_token_tracker[conversation_id]

            # 插件处理用户消息
            if plugin_manager:
                user_message = await plugin_manager.process_user_message(user_message, {"conversation_id": conversation_id})

            # 计算用户消息的tokens
            user_tokens = count_string_tokens(user_message, chat_model)
            tracker["new_tokens"] += user_tokens
            tracker["total_tokens"] += user_tokens

            # 保存用户消息到数据库
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO messages (id, conversation_id, role, content, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), conversation_id, 'user', user_message, datetime.now()))
                cursor.execute('''
                    UPDATE conversations SET updated_at = ? WHERE id = ?
                ''', (datetime.now(), conversation_id))
                conn.commit()

            # 检查是否需要滑动窗口清理
            if tracker["total_tokens"] >= sliding_threshold:
                trim_conversation_history(conversation_id, sliding_threshold, chat_model)
                # 重新计算总tokens
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT role, content FROM messages
                        WHERE conversation_id = ?
                        ORDER BY timestamp ASC
                    ''', (conversation_id,))
                    remaining_msgs = [{"role": row['role'], "content": row['content']} for row in cursor.fetchall()]
                    tracker["total_tokens"] = count_tokens(remaining_msgs, chat_model)

            # 获取最近 20 条消息作为上下文
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT role, content FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                    LIMIT 20
                ''', (conversation_id,))
                messages = [{"role": row['role'], "content": row['content']} for row in cursor.fetchall()]

            # 获取当前激活的提示词内容
            active_prompt_content = None
            try:
                settings = load_settings()
                active_id = settings.get("active_system_prompt_id")
                if active_id:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT content FROM system_prompts WHERE id = ?", (active_id,))
                        row = cursor.fetchone()
                        if row:
                            active_prompt_content = row["content"]
            except Exception as e:
                logger.error(f"Failed to get active prompt: {e}")

            # 在 user_message 之后，获取历史消息之前添加
            memory_context = ""
            if settings_cache.get('memory_enabled', True):
                try:
                    memories = memory_store.query_memories(text_query=user_message, top_k=3)
                    if memories:
                        memory_lines = ["以下是与当前问题可能相关的历史记忆："]
                        for mem in memories:
                            memory_lines.append(f"- {mem['title']}: {mem['summary']}")
                        memory_context = "\n".join(memory_lines)
                except Exception as e:
                    logger.error(f"记忆查询失败: {e}")

            # 构建消息列表（放在获取历史消息之后）
            current_messages = []
            if active_prompt_content:
                current_messages.append({"role": "system", "content": active_prompt_content})
            if memory_context:
                current_messages.append({"role": "system", "content": memory_context})
            # 添加历史消息
            current_messages.extend(messages)

            await websocket.send_json({"type": "start", "request_id": request_id})

            # TTS 配置
            tts_config = None
            try:
                import edge_tts
                tts_settings = settings.get('tts', {})
                if tts_settings.get('enabled', False):
                    from tts import init_tts_workers
                    init_tts_workers()
                    tts_config = tts_settings
                    logger.info("流式 TTS 已启用")
            except ImportError:
                pass

            try:
                # 准备工具列表
                openai_tools = tool_manager.get_tools_for_openai()
                
                max_rounds = 8
                final_response = ""
                round_count = 0

                # 在循环开始前初始化句子缓冲区
                sentence_buffer = ""

                while round_count < max_rounds:
                    round_count += 1
                    logger.info(f"工具调用轮次 {round_count}")

                    tool_calls_accumulated = []
                    # 流式获取模型响应
                    async for event in openai_client.stream_chat(current_messages, openai_tools or None):
                        if event["type"] == "content":
                            content = event["content"]
                            final_response += content
                            await websocket.send_json({
                                "type": "token",
                                "content": content,
                                "source": "openai",
                                "source_id": "openai"
                            })

                            # ---------- TTS 实时切分 ----------
                            if tts_config:
                                sentence_buffer += content
                                sentences, remaining = split_sentences(sentence_buffer, min_chars=15)
                                for s in sentences:
                                    # 将完整句子送入 TTS 队列（不阻塞当前协程）
                                    asyncio.create_task(stream_tts_sentence(s, tts_config))
                                sentence_buffer = remaining
                        elif event["type"] == "tool_call":
                            tool_calls_accumulated.append(event["tool_call"])
                            await websocket.send_json({
                                "type": "tool_call_start",
                                "tool_call": event["tool_call"],
                                "round": round_count
                            })

                    if not tool_calls_accumulated:
                        break

                    # 将助手的 tool_calls 消息添加到历史
                    current_messages.append({
                        "role": "assistant",
                        "content": final_response if final_response else None,
                        "tool_calls": tool_calls_accumulated
                    })

                    # 执行所有工具
                    for tool_call in tool_calls_accumulated:
                        function_info = tool_call.get('function', {})
                        tool_name = function_info.get('name', '')
                        raw_arguments = function_info.get('arguments') or '{}'
                        try:
                            arguments = json.loads(raw_arguments)
                            if not isinstance(arguments, dict):
                                arguments = {"value": arguments}
                        except json.JSONDecodeError:
                            arguments = {"raw_input": raw_arguments}

                        try:
                            result = await tool_manager.execute_tool(tool_name, arguments)
                            await websocket.send_json({
                                "type": "tool_call_result",
                                "tool_name": tool_name,
                                "result": result,
                                "round": round_count
                            })
                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.get('id'),
                                "content": result
                            })
                        except Exception as tool_error:
                            error_message = f"工具 {tool_name} 执行失败：{tool_error}"
                            logger.error(error_message, exc_info=True)
                            await websocket.send_json({
                                "type": "tool_call_result",
                                "tool_name": tool_name,
                                "error": error_message,
                                "round": round_count
                            })
                            current_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.get('id'),
                                "content": error_message
                            })

                # 流式循环结束（所有 token 已发送）
                # 如果还有未播放的句子（缓冲区剩余），且满足长度阈值，则播放
                if tts_config and sentence_buffer:
                    if count_chinese_chars(sentence_buffer) >= 15:
                        asyncio.create_task(stream_tts_sentence(sentence_buffer, tts_config))
                    else:
                        logger.debug(f"丢弃过短的剩余句子：{sentence_buffer}")

                # 插件处理 AI 响应
                if plugin_manager and final_response:
                    final_response = await plugin_manager.process_ai_response(final_response, {"conversation_id": conversation_id})

                # 计算AI响应的tokens
                ai_tokens = count_string_tokens(final_response, chat_model)
                tracker["new_tokens"] += ai_tokens
                tracker["total_tokens"] += ai_tokens

                # 检查是否需要滑动窗口清理
                if tracker["total_tokens"] >= sliding_threshold:
                    trim_conversation_history(conversation_id, sliding_threshold, chat_model)
                    # 重新计算总tokens
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT role, content FROM messages
                            WHERE conversation_id = ?
                            ORDER BY timestamp ASC
                        ''', (conversation_id,))
                        remaining_msgs = [{"role": row['role'], "content": row['content']} for row in cursor.fetchall()]
                        tracker["total_tokens"] = count_tokens(remaining_msgs, chat_model)

                # 保存 AI 响应到数据库
                if final_response:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO messages (id, conversation_id, role, content, timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (str(uuid.uuid4()), conversation_id, 'assistant', final_response, datetime.now()))
                        cursor.execute('''
                            UPDATE conversations SET updated_at = ? WHERE id = ?
                        ''', (datetime.now(), conversation_id))
                        conn.commit()
                    logger.info(f"已保存 AI 响应到数据库，长度 {len(final_response)}")
                    
                    # 在保存完 AI 响应后（位于 try 块末尾，finally 之前）
                    if final_response and settings_cache.get('memory_enabled', True):
                        # 获取本轮对话的消息（最近 20 条）
                        with get_db() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                SELECT role, content FROM messages
                                WHERE conversation_id = ?
                                ORDER BY timestamp ASC
                                LIMIT 20
                            ''', (conversation_id,))
                            recent_messages = [{"role": row['role'], "content": row['content']} for row in cursor.fetchall()]

                        # 检查是否达到触发阈值，如果是则触发记忆提炼
                        if tracker["new_tokens"] >= trigger_threshold:
                            # 异步提炼（不阻塞）
                            asyncio.create_task(refine_memory_async(recent_messages, conversation_id, settings, refine_model, refine_model_api_key, refine_model_base_url))
                            tracker["new_tokens"] = 0  # 重置累计新 token
                else:
                    logger.warning("AI 响应为空，未保存")

                await websocket.send_json({"type": "end", "request_id": request_id})

            except Exception as e:
                logger.error(f"Chat error: {e}", exc_info=True)
                await websocket.send_json({"type": "error", "content": f"AI 响应失败：{str(e)}"})

    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
    finally:
        await websocket.close()


async def refine_memory_async(messages: List[Dict], conversation_id: str, settings: Dict, refine_model: str, refine_model_api_key: str, refine_model_base_url: str):
    """异步提炼对话为记忆"""
    try:
        from RefineMemory import RefineMemory
        if not settings.get('memory_enabled', True):
            return

        openai_cfg = settings.get('openai', {})
        api_key = refine_model_api_key or openai_cfg.get('api_key')
        base_url = refine_model_base_url or openai_cfg.get('base_url', 'https://api.openai.com/v1')
        model = refine_model or openai_cfg.get('model', 'gpt-3.5-turbo')

        if not api_key:
            logger.warning("未配置 OpenAI API Key，跳过记忆提炼")
            return

        import uuid
        dialog_ids = [str(uuid.uuid4()) for _ in range(len(messages))]

        cleaner = RefineMemory(messages, user_id="localnexus", min_chars=3)
        memories = await cleaner.getFromOpenAI(
            key=api_key,
            model=model,
            url=base_url,
            dialog_ids=dialog_ids
        )
        if memories:
            logger.info(f"记忆提炼完成，新增 {len(memories)} 条记忆")
    except Exception as e:
        logger.error(f"记忆提炼失败: {e}", exc_info=True)