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
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False

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
    # 检查是否已经在处理请求
    if st.session_state.is_processing:
        st.warning("正在处理上一个请求，请稍候...")
        st.stop()
    
    # 设置处理标志
    st.session_state.is_processing = True
    
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
                                            reasoning_container.markdown(reasoning_content)
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
                                            answer_container.markdown(answer_content)
                                            last_update = current_time
                            except Exception as e:
                                st.error(f"处理响应时出错：{str(e)}")
                                continue
                    
                    # 确保最终显示完整的响应
                    if reasoning_buffer:
                        reasoning_content = ''.join(reasoning_buffer)
                        reasoning_container.markdown(reasoning_content)
                    if answer_buffer:
                        answer_content = ''.join(answer_buffer)
                        answer_container.markdown(answer_content)
                    
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