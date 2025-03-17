import streamlit as st
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time

# 加载环境变量
load_dotenv()

# 设置页面配置
st.set_page_config(
    page_title="SLL - 长文本生成",
    page_icon="📝",
    layout="wide"
)

# 初始化会话状态
if 'topic' not in st.session_state:
    st.session_state.topic = ""
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'outline' not in st.session_state:
    st.session_state.outline = ""
if 'research_data' not in st.session_state:
    st.session_state.research_data = []
if 'article' not in st.session_state:
    st.session_state.article = ""
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'step' not in st.session_state:
    st.session_state.step = 'outline'  # 可能的值: 'outline', 'article'

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 页面标题
st.title("SLL 长文本生成系统")

# 主界面
main_container = st.container()

with main_container:
    # 主题输入
    topic = st.text_input("请输入研究主题", key="topic_input")
    
    # 生成文章按钮
    if st.button("生成文章", key="generate_article"):
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
            progress_container = st.empty()
            questions_container = st.empty()
            outline_container = st.empty()
            article_container = st.empty()
            
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
        finally:
            st.session_state.is_processing = False
    
    # 重新开始按钮
    if st.button("重新开始", key="restart"):
        st.session_state.topic = ""
        st.session_state.questions = []
        st.session_state.outline = ""
        st.session_state.research_data = []
        st.session_state.article = ""
