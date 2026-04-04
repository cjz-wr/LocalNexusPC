"""
端口检测工具
用于自动扫描可用的后端服务端口
"""

import socket
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def check_port(port):
    """检查端口是否开放"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result == 0

def test_backend_api(port):
    """测试后端 API 是否可用"""
    try:
        import httpx
        response = httpx.get(f'http://localhost:{port}/conversations', timeout=2)
        return response.status_code == 200
    except:
        return False

def scan_ports():
    """扫描常用端口"""
    common_ports = [8765, 8000, 8080, 5000, 3000, 9000]
    
    logger.info("正在扫描后端服务...")
    logger.info("-" * 50)
    
    available_ports = []
    
    for port in common_ports:
        if check_port(port):
            logger.info(f"✓ 端口 {port} 已开放")
            if test_backend_api(port):
                logger.info(f"  ✓ API 测试通过")
                available_ports.append(port)
            else:
                logger.warning(f"  ✗ API 测试失败（可能不是后端服务）")
        else:
            logger.debug(f"✗ 端口 {port} 未开放")
    
    logger.info("-" * 50)
    
    # 检查配置文件
    config_file = Path(__file__).parent / 'backend_port.json'
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
            configured_port = config.get('port')
            if configured_port:
                logger.info(f"\n配置文件中指定的端口：{configured_port}")
                if configured_port not in available_ports:
                    logger.warning(f"  ⚠ 该端口未在扫描结果中，可能需要手动启动后端")
    
    if available_ports:
        logger.info(f"\n找到 {len(available_ports)} 个可用的后端服务:")
        for port in available_ports:
            logger.info(f"  - http://localhost:{port}")
        
        # 更新配置文件
        with open(config_file, 'w') as f:
            json.dump({'port': available_ports[0]}, f, indent=2)
        logger.info(f"\n已将首选端口 {available_ports[0]} 写入配置文件")
    else:
        logger.warning("\n⚠ 未找到可用的后端服务")
        logger.warning("\n建议操作:")
        logger.warning("1. 确认 Python 后端已启动")
        logger.warning("2. 检查后端日志输出")
        logger.warning("3. 查看防火墙设置")
    
    return available_ports

if __name__ == '__main__':
    ports = scan_ports()
    input("\n按回车键退出...")
