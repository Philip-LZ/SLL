import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging():
    # 创建日志目录结构
    log_root = Path(__file__).resolve().parent / 'logs'
    log_dirs = [log_root / name for name in ('api', 'chat', 'error')]
    for dir_path in log_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # 配置根日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 控制台处理程序
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # API调用日志处理程序
    api_logger = logging.getLogger('api')
    api_logger.propagate = False  # 防止日志传播到根记录器
    api_handler = RotatingFileHandler(
        log_root / 'api' / f'api_{datetime.now().strftime("%Y%m%d")}.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(formatter)
    api_logger.addHandler(api_handler)

    # 聊天记录处理程序
    chat_logger = logging.getLogger('chat')
    chat_logger.propagate = False  # 防止日志传播到根记录器
    chat_handler = RotatingFileHandler(
        log_root / 'chat' / f'chat_{datetime.now().strftime("%Y%m%d")}.log',
        maxBytes=10485760,
        backupCount=10
    )
    chat_handler.setLevel(logging.INFO)
    chat_handler.setFormatter(formatter)
    chat_logger.addHandler(chat_handler)

    # 错误日志处理程序
    error_logger = logging.getLogger('error')
    error_logger.propagate = False  # 防止日志传播到根记录器
    error_handler = RotatingFileHandler(
        log_root / 'error' / f'error_{datetime.now().strftime("%Y%m%d")}.log',
        maxBytes=10485760,
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_logger.addHandler(error_handler)

    return {
        'default': logger,
        'api': api_logger,
        'chat': chat_logger,
        'error': error_logger
    }
