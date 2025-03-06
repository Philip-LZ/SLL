import streamlit as st
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 初始化会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None

# 设置页面配置
st.set_page_config(
    page_title="SLL Chat",
    page_icon="💬",
    layout="wide"
)

# 页面标题
st.title("欢迎使用 SLL Chat 智能对话系统")

# 主要内容
st.markdown("""
## 👋 欢迎

SLL Chat 是一个智能对话系统，它可以：

- 💬 进行自然语言对话
- 🤖 提供智能问答服务
- 🔄 保持上下文连贯性
- ⚡ 实时流式响应

## 🚀 开始使用

点击左侧导航栏中的 "Home" 开始对话

## 💡 使用提示

- 输入框支持多行文本
- 可以随时清空对话重新开始
- 所有的对话都会保持上下文连贯
""")

# 版权信息
st.sidebar.markdown("---")
st.sidebar.markdown("© 2024 SLL Chat. All rights reserved.")
