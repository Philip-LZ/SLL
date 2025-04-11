import streamlit as st
from dotenv import load_dotenv
import os
from streamlit_float import *
from utils import show_sidebar

# 加载环境变量
load_dotenv()

# 初始化会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = "主页"

# 设置页面配置
st.set_page_config(
    page_title="SLLRunner Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="auto"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        color: #1E3A8A;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    h2 {
        color: #2563EB;
        font-size: 1.8rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .stMarkdown p {
        font-size: 1.1rem;
        line-height: 1.6;
        color: #374151;
    }
    .stMarkdown ul {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    .stMarkdown li {
        font-size: 1.1rem;
        line-height: 1.6;
        margin-bottom: 0.5rem;
        color: #374151;
    }
    .stSidebar .sidebar-content {
        background-color: #F3F4F6;
        padding: 2rem 1rem;
    }
    .sidebar .sidebar-content {
        background-color: #F3F4F6;
    }
    /* 导航菜单样式 */
    .nav-link {
        margin: 0.2rem 0;
        border-radius: 0.5rem;
        transition: all 0.3s ease;
    }
    .nav-link:hover {
        background-color: #E5E7EB;
        transform: translateX(5px);
    }
    .nav-link.active {
        background-color: #2563EB !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# 显示侧边栏
selected = show_sidebar()

if st.session_state.current_page == "主页":
    # 页面标题和内容容器
    st.markdown("<h1 style='text-align: center;'>欢迎使用 SLLRunner Chat 智能对话系统</h1>", unsafe_allow_html=True)

    # 主要内容使用卡片式布局
    st.markdown("""
    <div style='background-color: #F9FAFB; padding: 2rem; border-radius: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);'>
        <h2>👋 欢迎</h2>
        <p style='font-size: 1.1rem; line-height: 1.6; color: #374151;'>
            SLLRunner Chat 是一个智能对话系统，它可以：
        </p>
        <ul style='list-style-type: none; padding-left: 1rem;'>
            <li style='margin: 1rem 0;'>💬 <strong>进行自然语言对话</strong> - 智能理解并回应您的问题</li>
            <li style='margin: 1rem 0;'>🤖 <strong>提供智能问答服务</strong> - 准确、专业的解答</li>
            <li style='margin: 1rem 0;'>🔄 <strong>保持上下文连贯性</strong> - 自然流畅的对话体验</li>
            <li style='margin: 1rem 0;'>⚡ <strong>实时流式响应</strong> - 快速、即时的反馈</li>
        </ul>
    </div>
    
    <div style='background-color: #F0F9FF; padding: 2rem; border-radius: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-top: 2rem;'>
        <h2>🚀 开始使用</h2>
        <ol style='padding-left: 1.5rem;'>
            <li style='margin: 0.8rem 0; font-size: 1.1rem;'>点击左侧导航栏中的 <strong style='color: #2563EB;'>"智能对话"</strong> 开始对话</li>
            <li style='margin: 0.8rem 0; font-size: 1.1rem;'>在 <strong style='color: #2563EB;'>"长文本生成"</strong> 中使用文章生成功能</li>
        </ol>
    </div>
    
    <div style='background-color: #F0FDF4; padding: 2rem; border-radius: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-top: 2rem;'>
        <h2>💡 使用提示</h2>
        <ul style='list-style-type: none; padding-left: 0;'>
            <li style='margin: 0.8rem 0; font-size: 1.1rem;'>✏️ 输入框支持多行文本</li>
            <li style='margin: 0.8rem 0; font-size: 1.1rem;'>🔄 可以随时清空对话重新开始</li>
            <li style='margin: 0.8rem 0; font-size: 1.1rem;'>🔗 所有的对话都会保持上下文连贯</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
