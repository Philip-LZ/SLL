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
    page_title="SLLRunner - 用户登录",
    page_icon="🔐",
    layout="wide"
)

# 设置后端API地址
BACKEND_URL = "http://localhost:8000"

# 页面标题
st.title("SLLRunner 用户登录")

# 主界面
with st.container():
    st.markdown("### 请登录以继续")
    
    # 登录表单
    with st.form("login_form"):
        email = st.text_input("邮箱")
        password = st.text_input("密码", type="password")
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("登录")
        with col2:
            if st.form_submit_button("注册"):
                st.switch_page("pages/register.py")
        
        if submitted:
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
                    
                    # 如果有返回页面，则跳转回去
                    if st.session_state.return_to:
                        return_to = st.session_state.return_to
                        st.session_state.return_to = None
                        st.switch_page(return_to)
                    else:
                        st.switch_page("pages/chat.py")
                else:
                    st.error("登录失败：邮箱或密码错误")
            except Exception as e:
                st.error(f"登录失败：{str(e)}")
    
    # 注册提示
    st.markdown("---")
    st.info("如需注册账号，请联系管理员获取注册信息。")