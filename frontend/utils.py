import streamlit as st
from streamlit_option_menu import option_menu

def show_sidebar():
    # 根据当前页面设置默认选中项
    current_page = st.session_state.get('current_page', '主页')
    page_indices = {
        '主页': 0,
        '智能对话': 1,
        '长文本生成': 2
    }
    default_index = page_indices.get(current_page, 0)
    
    with st.sidebar:
        selected = option_menu(
            menu_title="导航菜单",
            options=["主页", "智能对话", "长文本生成"],
            icons=["house", "chat-dots", "file-text"],
            menu_icon="cast",
            default_index=default_index,
            styles={
                "container": {"padding": "0.5rem", "background-color": "transparent"},
                "icon": {"font-size": "1.2rem", "margin-right": "0.5rem"},
                "nav-link": {
                    "font-size": "1rem",
                    "text-align": "left",
                    "margin": "0.2rem 0",
                    "padding": "0.8rem",
                    "border-radius": "0.5rem",
                    "--hover-color": "#E5E7EB"
                },
                "nav-link-selected": {"background-color": "#2563EB"}
            }
        )

        if selected != st.session_state.current_page:
            st.session_state.current_page = selected
            if selected == "智能对话":
                st.switch_page("pages/chat.py")
            elif selected == "长文本生成":
                st.switch_page("pages/longtext.py")
            elif selected == "主页":
                st.switch_page("streamlit_app.py")

    return selected