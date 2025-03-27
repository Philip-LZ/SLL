import streamlit as st

def init_session_state():
    """初始化所有必要的会话状态变量"""
    # 用户认证相关状态
    if 'is_logged_in' not in st.session_state:
        st.session_state.is_logged_in = False
    if 'user_token' not in st.session_state:
        st.session_state.user_token = None
    if 'return_to' not in st.session_state:
        st.session_state.return_to = None

    # 聊天相关状态
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'conversation_id' not in st.session_state:
        st.session_state.conversation_id = None
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False

    # 长文本生成相关状态
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

    # 导航相关状态
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "主页"