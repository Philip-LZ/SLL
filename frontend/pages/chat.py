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
    page_title="SLL Chat - 智能对话",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="auto"
)

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 显示侧边栏
selected = show_sidebar()

# 页面标题
st.title("智能对话")

# 自定义CSS样式
st.markdown("""
<style>
    .chat-message {
        padding: 1.5rem;
        border-radius: 1rem;
        margin-bottom: 1rem;
        animation: fadeIn 0.5s ease-in-out;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .user-message {
        background-color: #F0F9FF;
        margin-left: 2rem;
    }
    .assistant-message {
        background-color: #F0FDF4;
        margin-right: 2rem;
    }
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 2rem;
    }
    .chat-input {
        border-radius: 1rem;
        border: 2px solid #E5E7EB;
        padding: 1rem;
        margin-top: 2rem;
        transition: all 0.3s ease;
    }
    .chat-input:focus {
        border-color: #2563EB;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .reasoning-container {
        background-color: #FFF7ED;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        font-style: italic;
    }
    .answer-container {
        background-color: #F0FDF4;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# 页面标题
st.title("💬 SLL Chat 智能对话")
st.markdown("<p style='color: #6B7280; font-size: 1.1rem;'>与 AI 助手进行自然、流畅的对话</p>", unsafe_allow_html=True)

# 登录模态窗口
def show_login_modal():
    with st.container():
        st.markdown("### 请先登录")
        email = st.text_input("邮箱", key="login_email")
        password = st.text_input("密码", type="password", key="login_password")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("登录", key="login_button"):
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/auth/login",
                        json={"email": email, "password": password}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.is_logged_in = True
                        st.session_state.user_token = data["token"]
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error("登录失败：邮箱或密码错误")
                except Exception as e:
                    st.error(f"登录失败：{str(e)}")
        
        with col2:
            if st.button("注册", key="register_button"):
                st.info("请联系管理员获取注册信息")

# 主聊天界面
chat_container = st.container()

# 显示聊天历史
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(f"<div class='chat-message {message['role']}-message'>{message['content']}</div>", unsafe_allow_html=True)

# 用户输入
if prompt := st.chat_input("请输入您的问题..."):
    # 检查登录状态
    if not st.session_state.is_logged_in:
        st.session_state.return_to = "pages/chat.py"
        st.switch_page("pages/login.py")
        st.stop()
        show_login_modal()
        st.stop()
        
    # 检查是否已经在处理请求
    if st.session_state.is_processing:
        st.warning("正在处理上一个请求，请稍候...")
        st.stop()
    
    # 设置处理标志
    st.session_state.is_processing = True
    
    # 添加用户消息到界面
    with chat_container:
        with st.chat_message("user"):
            st.markdown(f"<div class='chat-message user-message'>{prompt}</div>", unsafe_allow_html=True)
    
    # 添加用户消息到历史记录
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 调用后端API
    try:
        with st.chat_message("assistant"):
            reasoning_container = st.empty()
            answer_container = st.empty()
            full_response = ""
            reasoning_content = ""
            answer_content = ""
            # 添加容器样式
            st.markdown("""
            <style>
                .streamlit-expander {
                    margin: 0.5rem 0;
                }
                .stMarkdown {
                    animation: fadeIn 0.3s ease-out;
                }
            </style>
            """, unsafe_allow_html=True)
            
            # 准备请求数据
            data = {
                "message": prompt,
                "conversation_id": st.session_state.conversation_id,
                "messages": st.session_state.messages
            }
            
            # 发送请求到后端
            with requests.post(
                f"{BACKEND_URL}/api/chat",
                json=data,
                stream=True,
                timeout=1000 
            ) as response:
                if response.status_code == 200:
                    is_thinking = False
                    # 建立缓存，用于收集完整的响应
                    reasoning_buffer = []
                    answer_buffer = []
                    update_interval = 0.5  # 更新间隔（秒）
                    last_update = time.time()
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                # 解析SSE消息
                                line_text = line.decode('utf-8')
                                if line_text.startswith('data: '):
                                    json_str = line_text[6:]
                                    data = json.loads(json_str)
                                    # 处理不同类型的消息
                                    if data['type'] == 'conversation_id':
                                        st.session_state.conversation_id = data['content']
                                    elif data['type'] == 'reasoning':
                                        # 收集思考过程
                                        if not is_thinking:
                                            reasoning_buffer.append("*思考过程：*\n\n")
                                            is_thinking = True
                                        reasoning_buffer.append(data['content'])
                                        
                                        # 定期更新显示
                                        current_time = time.time()
                                        if current_time - last_update >= update_interval:
                                            reasoning_content = ''.join(reasoning_buffer)
                                            reasoning_container.markdown(
                                                f"<div class='reasoning-container'>{reasoning_content}</div>",
                                                unsafe_allow_html=True
                                            )
                                            last_update = current_time
                                            
                                    elif data['type'] == 'answer':
                                        # 完整显示思考过程
                                        if is_thinking:
                                            reasoning_content = ''.join(reasoning_buffer)
                                            reasoning_container.markdown(reasoning_content)
                                            is_thinking = False
                                        
                                        # 收集回答内容
                                        if not answer_buffer:
                                            answer_buffer.append("*回答：*\n\n")
                                        answer_buffer.append(data['content'])
                                        
                                        # 定期更新显示
                                        current_time = time.time()
                                        if current_time - last_update >= update_interval:
                                            answer_content = ''.join(answer_buffer)
                                            answer_container.markdown(
                                                f"<div class='answer-container'>{answer_content}</div>",
                                                unsafe_allow_html=True
                                            )
                                            last_update = current_time
                            except Exception as e:
                                st.error(f"处理响应时出错：{str(e)}")
                                continue
                    
                    # 确保最终显示完整的响应
                    if reasoning_buffer:
                        reasoning_content = ''.join(reasoning_buffer)
                        reasoning_container.markdown(
                            f"<div class='reasoning-container'>{reasoning_content}</div>",
                            unsafe_allow_html=True
                        )
                    if answer_buffer:
                        answer_content = ''.join(answer_buffer)
                        answer_container.markdown(
                            f"<div class='answer-container'>{answer_content}</div>",
                            unsafe_allow_html=True
                        )
                    
                    # 更新消息历史
                    full_response = ""
                    if reasoning_buffer:
                        full_response += ''.join(reasoning_buffer) + "\n\n"
                    if answer_buffer:
                        full_response += ''.join(answer_buffer)
                    if full_response:
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    except Exception as e:
        st.error(f"连接服务器时出错：{str(e)}")
    finally:
        # 重置处理标志
        st.session_state.is_processing = False