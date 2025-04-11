import logging
from typing import List


class PersonaGenerator:
    """角色生成器类，负责根据给定主题创建角色。
    
    这个类是一个简化版的角色生成器，用于生成针对特定主题的多个角色视角。
    它保留了基本的角色生成功能，包括一个默认的基础事实编写者角色和
    根据主题生成的额外角色。
    参数:
    model: 用于生成角色的语言模型
    max_num_persona: 要生成的最大额外角色数量，不包括默认角色。默认值为3。
    """

    def __init__(self, model, topic: str, max_num_persona: int = 3):
        self.model = model
        self.topic = topic
        self.max_num_persona = max_num_persona
        self.logger = logging.getLogger(__name__)

    def generate_personas(self) -> List[str]:
        """根据提供的主题生成一系列人物角色
        
        此方法生成一组针对特定主题的角色，包括一个默认的基础事实编写者角色
        和最多max_num_persona个额外的专门角色。
        
        参数:
            topic (str): 要生成人物角色的主题
            max_num_persona (int): 要生成的最大额外角色数量，不包括默认角色
            
        返回:
            List[str]: 角色描述列表，包括默认角色和主题相关的专门角色
        """
        try:
            # 生成主题相关的专门角色
            prompt = f"""请为主题'{self.topic}'生成{self.max_num_persona}个不同视角的编写者角色。每个角色描述应遵循以下格式：
            [角色标题]：[专业背景描述]。[关键词：该角色关注的核心概念和术语，用逗号分隔]

            要求：
            1. 每个角色应代表不同的专业背景或研究领域
            2. 角色标题应简洁明确地表明其专业身份
            3. 专业背景描述应突出该角色对主题的独特见解和关注重点
            4. 关键词部分应包含3-5个与该角色视角最相关的专业术语或概念

            示例格式：
            技术分析师：专注于[主题]相关技术发展趋势和创新应用的分析。关键词：创新技术，趋势，应用场景，技术评估
            政策研究员：关注[主题]相关的政策法规和监管框架。关键词：政策法规，监管要求，合规风险，政策影响

            请按照上述格式生成{self.max_num_persona}个角色描述，每个角色一行。注意不要生成其他内容，输出只包括角色描述。"""
            response = self.model(prompt)[0]  # DeepSeekModel返回列表，取第一个结果

            # 解析生成的角色列表
            personas = [line.strip() for line in response.split('\n') if line.strip()]
            personas = personas[:self.max_num_persona]  # 限制角色数量

            return personas

        except Exception as e:
            self.logger.error(f"生成角色时发生错误: {str(e)}")
            # 如果生成失败，至少返回默认角色
            return ["基础事实编写者：专注于全面覆盖主题的基本事实信息。"]


# if __name__ == '__main__':
#     from backend.SLL_longtext.models import DeepSeekModel
#     topic = "LLM为什么能实现回答用户的问题"
#     model = DeepSeekModel(api_key="sk-82736a81ee294720b1faf7519e30013e")
#     persona_generator = PersonaGenerator(model=model, topic=topic, max_num_persona=3)
#     personas = persona_generator.generate_personas()
#     for persona in personas:
#         print(persona)