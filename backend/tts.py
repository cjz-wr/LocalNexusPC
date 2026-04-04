'''
TTS 模块：使用 edge-tts 进行文本转语音，支持异步生成和本地播放
设计目标：
1. 使用 edge-tts 生成高质量的语音，支持多种声音和参数配置
2. 生成和播放分离，使用线程和队列实现非阻然播放
3. 音频播放支持本地播放和远程播放，支持多种音频播放方式
'''

import asyncio
import threading
import queue
import io
import logging
import time
from typing import Dict

import edge_tts

# 导入音频播放模块
try:
    import pygame
    AUDIO_PLAYBACK_AVAILABLE = True
except ImportError:
    AUDIO_PLAYBACK_AVAILABLE = False
    logging.warning("pygame not installed. Local audio playback will be disabled.")

logger = logging.getLogger(__name__)

# 全局队列和线程变量
tts_gen_queue = queue.Queue()
tts_play_queue = queue.Queue()
tts_gen_thread = None
tts_play_thread = None
tts_worker_initialized = False


def init_tts_workers():
    """初始化 TTS 工作线程和音频播放"""
    global tts_gen_thread, tts_play_thread, tts_worker_initialized

    if tts_worker_initialized:
        return

    # 初始化 pygame 音频系统（如果可用）
    if AUDIO_PLAYBACK_AVAILABLE:
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            logger.info("Pygame mixer initialized for TTS playback")
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")

    # 启动生成线程
    tts_gen_thread = threading.Thread(target=tts_generator_worker, daemon=True)
    tts_gen_thread.start()

    # 启动播放线程（独立于生成线程，实现非阻塞）
    tts_play_thread = threading.Thread(target=tts_player_worker, daemon=True)
    tts_play_thread.start()

    tts_worker_initialized = True
    logger.info("TTS 工作线程已初始化")


def tts_player_worker():
    """TTS 播放线程：从播放队列获取音频并播放，不阻塞生成线程"""
    while True:
        item = tts_play_queue.get()

        if item is None:
            break

        audio_bytes, sentence = item

        try:
            if audio_bytes and AUDIO_PLAYBACK_AVAILABLE:
                logger.debug(f"TTS 开始播放：{sentence[:30]}... 音频大小：{len(audio_bytes)}")
                try:
                    audio_io = io.BytesIO(audio_bytes)
                    pygame.mixer.music.load(audio_io)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    logger.debug(f"TTS 播放完成：{sentence[:30]}...")
                except Exception as e:
                    logger.error(f"播放 TTS 音频失败：{e}")
            elif not audio_bytes:
                logger.warning("TTS 播放队列为空")
            elif not AUDIO_PLAYBACK_AVAILABLE:
                logger.warning("音频播放不可用，无法播放 TTS")
        except Exception as e:
            logger.error(f"TTS 播放异常：{e}", exc_info=True)
        finally:
            tts_play_queue.task_done()


def tts_generator_worker():
    """TTS 生成线程：从队列获取句子并生成音频，放入播放队列"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        item = tts_gen_queue.get()

        if item is None:
            break

        sentence, tts_config = item

        try:
            voice = tts_config.get('voice', 'zh-CN-XiaoxiaoNeural')
            rate = tts_config.get('rate', '+0%')
            pitch = tts_config.get('pitch', '+0Hz')
            volume = tts_config.get('volume', '+0%')

            communicate = edge_tts.Communicate(sentence, voice, rate=rate, pitch=pitch, volume=volume)

            async def generate_audio():
                audio_bytes = b''
                async for chunk in communicate.stream():
                    if chunk.get('type') == 'audio':
                        audio_bytes += chunk.get('data', b'')
                return audio_bytes

            audio_bytes = loop.run_until_complete(generate_audio())

            if audio_bytes:
                logger.debug(f"TTS 句子生成完成：{sentence[:30]}... 音频大小：{len(audio_bytes)}")
                tts_play_queue.put((audio_bytes, sentence))
            else:
                logger.warning("TTS 生成返回空音频")
        except Exception as e:
            logger.error(f"TTS 生成失败：{e}", exc_info=True)
        finally:
            tts_gen_queue.task_done()


async def stream_tts_sentence(sentence: str, tts_config: Dict):
    """将单个句子加入 TTS 生成队列"""
    if not tts_worker_initialized:
        init_tts_workers()
    tts_gen_queue.put((sentence, tts_config))
    logger.debug(f"句子已加入 TTS 队列：{sentence[:50]}...")


async def stop_tts_workers():
    """停止所有 TTS 工作线程"""
    global tts_worker_initialized

    if not tts_worker_initialized:
        return

    logger.info("正在停止 TTS 工作线程...")

    tts_gen_queue.put(None)
    if tts_gen_thread and tts_gen_thread.is_alive():
        tts_gen_thread.join(timeout=5.0)

    tts_play_queue.put(None)
    if tts_play_thread and tts_play_thread.is_alive():
        tts_play_thread.join(timeout=5.0)

    tts_worker_initialized = False
    logger.info("TTS 工作线程已停止")