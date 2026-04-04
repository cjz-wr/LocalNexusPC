"""
LocalNexus PC Backend
入口文件，启动服务器
"""

import os
import logging

from routes import create_app

# 配置日志（可在入口统一配置）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('BACKEND_PORT', '8765'))
    logger.info(f"PORT:{port}")
    logger.info("Starting server on port {port}")
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
