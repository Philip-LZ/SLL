"""启动程序，用于运行SLL.py中的知识生成系统。

需要的环境变量：
    - ALI_MODEL_API_KEY： Aliyun model API key
    - BOSHA_API_KEY： Bosha Search API key
"""

import os
import logging
from argparse import ArgumentParser
from dotenv import load_dotenv
from SLL import SLLConfig, SLL

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # 加载环境变量
    load_dotenv()

    # 检查必要的环境变量
    required_env_vars = ['ALI_MODEL_API_KEY', 'BOSHA_API_KEY']
    for var in required_env_vars:
        if not os.getenv(var):
            logger.error(f'缺少环境变量: {var}')
            return

    # 解析命令行参数
    parser = ArgumentParser(description='运行SLL知识生成系统')
    parser.add_argument('--output-dir', type=str, default='./results/deepseek',
                      help='输出目录路径')
    parser.add_argument('--max-conv-turns', type=int, default=3,
                      help='最大对话轮次')
    parser.add_argument('--max-perspectives', type=int, default=3,
                      help='最大视角数量')
    parser.add_argument('--search-top-k', type=int, default=3,
                      help='每次搜索返回的结果数量')
    parser.add_argument('--temperature', type=float, default=1.0,
                      help='生成文本的温度参数')
    parser.add_argument('--top-p', type=float, default=0.9,
                      help='生成文本的top-p参数')
    parser.add_argument('--model', type=str, default='deepseek-v3',
                      help='使用的DeepSeek模型')
    args = parser.parse_args()

    # 创建配置对象
    config = SLLConfig(
        output_dir=args.output_dir,
        max_conv_turns=args.max_conv_turns,
        max_perspectives=args.max_perspectives,
        search_top_k=args.search_top_k,
        temperature=args.temperature,
        top_p=args.top_p,
        model=args.model
    )

    try:
        # 初始化SLL实例
        sll = SLL(config)

        # 获取用户输入的主题
        topic = input('请输入要研究的主题: ')
        sanitized_topic = topic

        # 创建输出目录
        topic_dir = os.path.join(config.output_dir, sanitized_topic)
        os.makedirs(topic_dir, exist_ok=True)

        # 处理主题
        logger.info(f'开始处理主题: {topic}')
        result = sll.process_topic(topic)

        # 保存结果
        for key, content in result.items():
            file_path = os.path.join(topic_dir, f'{key}.json')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(str(content))

        logger.info(f'处理完成，结果已保存到: {topic_dir}')

    except Exception as e:
        logger.error(f'处理过程中出现错误: {str(e)}')
        raise

if __name__ == '__main__':
    main()