import streamlit as st
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time
from frontend.session_state import init_session_state

# 加载环境变量
load_dotenv()

# 初始化会话状态
init_session_state()

# 设置页面配置
st.set_page_config(
    page_title="SLLRunner - 用户注册",
    page_icon="📝",
    layout="wide"
)

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 页面标题
st.title("SLLRunner 用户注册")

# 主界面
with st.container():
    st.markdown("### 创建新账户")
    
    # 注册表单
    with st.form("register_form"):
        username = st.text_input("用户名")
        email = st.text_input("邮箱")
        password = st.text_input("密码", type="password")
        password_confirm = st.text_input("确认密码", type="password")
        submitted = st.form_submit_button("注册")
        
        if submitted:
            # 表单验证
            if not username or not email or not password or not password_confirm:
                st.error("请填写所有必填字段")
            elif password != password_confirm:
                st.error("两次输入的密码不一致")
            else:
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/auth/register",
                        json={
                            "username": username,
                            "email": email,
                            "password": password
                        }
                    )
                    
                    if response.status_code == 200:
                        st.success("注册成功！正在跳转到登录页面...")
                        time.sleep(2)
                        st.switch_page("pages/login.py")
                    else:
                        error_data = response.json()
                        st.error(f"注册失败：{error_data.get('detail', '未知错误')}")
                except Exception as e:
                    st.error(f"注册失败：{str(e)}")
    
    # 登录链接
    st.markdown("---")
    st.info("已有账号？[点击这里登录](登录页面)")
    if st.button("返回登录"):
        st.switch_page("pages/login.py")