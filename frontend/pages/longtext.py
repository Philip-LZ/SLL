import streamlit as st
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time
from frontend.utils import show_sidebar
from frontend.session_state import init_session_state

# 加载环境变量
load_dotenv()

# 初始化会话状态
init_session_state()

# 设置页面配置
st.set_page_config(
    page_title="SLLRunner - 长文本生成",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="auto"
)

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 显示侧边栏
selected = show_sidebar()

# 页面标题
st.title("长文本生成")

# 自定义CSS样式
st.markdown("""
<style>
    :root {
        --primary-color: #2563eb;
        --success-bg: #f0fdf4;
        --warning-bg: #fffbeb;
        --error-bg: #fef2f2;
        --text-primary: #1f2937;
        --text-secondary: #4b5563;
    }

    .longtext-container {
        max-width: min(1000px, 90%);
        margin: 0 auto;
        padding: 2rem;
    }

    .input-section {
        background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
        padding: 2.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05),
                    0 2px 4px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 2rem;
        border: 1px solid #e5e7eb;
    }

    .result-section {
        background: var(--success-bg);
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-top: 2rem;
        border: 1px solid #bbf7d0;
    }

    .processing-section {
        background: var(--warning-bg);
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1.5rem 0;
        position: relative;
        overflow: hidden;
    }

    .processing-section::after {
        content: "";
        position: absolute;
        left: -100%;
        top: 0;
        width: 200%;
        height: 100%;
        background: linear-gradient(
            90deg,
            transparent 25%,
            rgba(255,255,255,0.4) 50%,
            transparent 75%
        );
        animation: shimmer 2s infinite;
    }

    @keyframes shimmer {
        100% { left: 200%; }
    }

    .outline-section {
        background: var(--warning-bg);
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin: 1.5rem 0;
        border-left: 4px solid #f59e0b;
    }

    .article-section {
        background: white;
        padding: 2.5rem;
        border-radius: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        margin: 2rem 0;
        line-height: 1.75;
        font-size: 1.05rem;
        color: var(--text-primary);
    }

    .article-section h2 {
        color: var(--primary-color);
        margin-top: 2rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }

    .stButton>button {
        width: 100%;
        padding: 1rem;
        border-radius: 0.75rem;
        background: var(--primary-color);
        color: white;
        font-weight: 600;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: none;
        margin: 1.5rem 0;
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1),
                    0 4px 6px -4px rgba(0, 0, 0, 0.1);
        background: #1d4ed8;
    }

    @media (max-width: 768px) {
        .longtext-container {
            padding: 1rem;
        }
        
        .input-section,
        .result-section {
            padding: 1.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# 页面标题
st.title("📝 SLLRunner 长文本生成系统")
st.markdown("<p style='color: #6B7280; font-size: 1.1rem;'>基于AI的智能文章生成系统</p>", unsafe_allow_html=True)

# 主界面
with st.container():
    # 输入区域
    with st.container():
        st.markdown("<div class='input-section'>", unsafe_allow_html=True)
        topic = st.text_input("请输入研究主题", key="topic_input")
        if st.button("生成文章", key="run_article_polishing_module"):
            # 检查登录状态
            # 检查登录状态
            if not st.session_state.is_logged_in:
                st.session_state.return_to = "pages/longtext.py"
                st.switch_page("pages/login.py")
                st.stop()
                
            if not topic:
                st.warning("请输入研究主题")
                st.stop()
            
            if st.session_state.is_processing:
                st.warning("正在处理中，请稍候...")
                st.stop()
            
            st.session_state.is_processing = True
            st.session_state.topic = topic
            
            try:
                # 创建显示区域
                with st.container():
                    st.markdown("<div class='processing-section'>", unsafe_allow_html=True)
                    progress_container = st.empty()
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='outline-section'>", unsafe_allow_html=True)
                    outline_container = st.empty()
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div class='article-section'>", unsafe_allow_html=True)
                    article_container = st.empty()
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    # 第一步：生成大纲
                    progress_container.markdown("*正在生成大纲...*")
                    response = requests.post(
                        f"{BACKEND_URL}/api/run_outline_generation_module",
                        json={"topic": topic},
                        timeout=3000,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        # 更新会话状态和显示内容
                        if 'outline' in result:
                            st.session_state.outline = result['outline']
                            st.session_state.research_data = result.get('research_data', [])
                            outline_container.markdown(f"### 文章大纲：\n\n{result['outline']}")
                        
                        # 第二步：生成文章
                        progress_container.markdown("*正在生成文章...*")
                        response = requests.post(
                            f"{BACKEND_URL}/api/run_article_polishing_module",
                            json={
                                "topic": st.session_state.topic,
                                "outline": st.session_state.outline,
                                "research_data": st.session_state.research_data
                            },
                            timeout=3000,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            if 'polished_article' in result:
                                st.session_state.article = result['polished_article']
                                article_container.markdown(f"### 生成的文章：\n\n{result['polished_article']}")
                            
                            progress_container.markdown("*文章生成完成！*")
                        else:
                            st.error(f"生成文章时出错：{response.status_code}")
                            if response.headers.get('content-type') == 'application/json':
                                error_data = response.json()
                                if 'error' in error_data:
                                    st.error(error_data['error'])
                    else:
                        st.error(f"生成大纲时出错：{response.status_code}")
                        if response.headers.get('content-type') == 'application/json':
                            error_data = response.json()
                            if 'error' in error_data:
                                st.error(error_data['error'])
                                
            except Exception as e:
                st.error(f"连接服务器时出错：{str(e)}")
        st.markdown("</div>", unsafe_allow_html=True)

    # 重新开始按钮
    if st.button("重新开始", key="restart"):
        st.session_state.topic = ""
        st.session_state.questions = []
        st.session_state.outline = ""
        st.session_state.research_data = []
        st.session_state.article = ""
