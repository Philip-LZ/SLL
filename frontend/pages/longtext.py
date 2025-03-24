import streamlit as st
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time
from frontend.utils import show_sidebar

# 加载环境变量
load_dotenv()

# 设置页面配置
st.set_page_config(
    page_title="SLL - 长文本生成",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="auto"
)
# 显示侧边栏
selected = show_sidebar()

# 页面标题
st.title("长文本生成")

# 自定义CSS样式
st.markdown("""
<style>
    .longtext-container {
        max-width: 1000px;
        margin: 0 auto;
        padding: 2rem;
    }
    .input-section {
        background-color: #F9FAFB;
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }
    .result-section {
        background-color: #F0FDF4;
        padding: 2rem;
        border-radius: 1rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin-top: 2rem;
    }
    .processing-section {
        background-color: #FFF7ED;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        font-style: italic;
    }
    .outline-section {
        background-color: #F0F9FF;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .article-section {
        background-color: #FFFFFF;
        padding: 2rem;
        border-radius: 0.5rem;
        border: 1px solid #E5E7EB;
        margin: 1rem 0;
        line-height: 1.8;
    }
    .stButton>button {
        width: 100%;
        border-radius: 0.5rem;
        margin-top: 1rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# 页面标题
st.title("📝 SLL 长文本生成系统")
st.markdown("<p style='color: #6B7280; font-size: 1.1rem;'>基于AI的智能文章生成系统</p>", unsafe_allow_html=True)

# 主界面
with st.container():
    # 输入区域
    with st.container():
        st.markdown("<div class='input-section'>", unsafe_allow_html=True)
        topic = st.text_input("请输入研究主题", key="topic_input")
        if st.button("生成文章", key="generate_article"):
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
                        f"{BACKEND_URL}/api/generate_outline",
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
                            f"{BACKEND_URL}/api/generate_article",
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
