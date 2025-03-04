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
    page_title="SLL Chat - 主页",
    page_icon="💬",
    layout="wide"
)

# 初始化会话状态
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 页面标题
st.title("SLL Chat 智能对话系统")

# 侧边栏
with st.sidebar:
    st.header("对话设置")
    if st.button("清空对话", key="clear"):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.experimental_rerun()

# 主聊天界面
chat_container = st.container()

# 显示聊天历史
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

# 用户输入
if prompt := st.chat_input("请输入您的问题..."):
    # 添加用户消息到界面
    with chat_container:
        with st.chat_message("user"):
            st.write(prompt)
    
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
                                        # 在思考容器中显示思考过程
                                        if not is_thinking:
                                            reasoning_content = "*思考过程：*\n\n"
                                            is_thinking = True
                                        reasoning_content = reasoning_content.rstrip() + data['content']
                                        reasoning_container.markdown(reasoning_content)
                                    elif data['type'] == 'answer':
                                        time.sleep(0.5)
                                        # 确保思考过程完整显示
                                        if is_thinking:
                                            reasoning_container.markdown(reasoning_content) 
                                            is_thinking = False
                                        
                                        # 在答案容器中显示回答内容
                                        if not answer_content:
                                            answer_content = "*回答：*\n\n"
                                        answer_content += data['content']
                                        answer_container.markdown(answer_content)
                            except Exception as e:
                                st.error(f"处理响应时出错：{str(e)}")
                                continue
            
            # 更新消息历史，合并思考过程和答案
            full_response = ""
            if reasoning_content:
                full_response += reasoning_content + "\n\n"
            if answer_content:
                full_response += answer_content
            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    except Exception as e:
        st.error(f"连接服务器时出错：{str(e)}")