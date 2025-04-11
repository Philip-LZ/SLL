import React, { useState } from 'react';
import { Layout, Input, Button, List, Avatar, Select } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const { Content } = Layout;
const { Search } = Input;
const { Option } = Select;

function Chat() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const navigate = useNavigate();

  const handleSearch = (value) => {
    if (!value.trim()) return;
    
    const newMessage = {
      type: 'user',
      content: value,
      timestamp: new Date().toISOString(),
    };

    setMessages([...messages, newMessage]);
    // TODO: 在这里添加与后端API的集成
  };

  const handleFunctionChange = (value) => {
    if (value === 'longtext') {
      navigate('/longtext');
    }
  };

  return (
    <Content style={{ 
      background: '#ffffff',
      padding: '20px',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{
        maxWidth: '800px',
        margin: '40px auto 20px',
        width: '100%',
        display: 'flex',
        gap: '10px'
      }}>
        <Search
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onSearch={handleSearch}
          placeholder="请输入您的问题..."
          enterButton={<SendOutlined />}
          size="large"
          style={{ flex: 1 }}
        />
        <Select
          defaultValue="chat"
          style={{ width: 120 }}
          onChange={handleFunctionChange}
          size="large"
        >
          <Option value="chat">智能对话</Option>
          <Option value="longtext">长文生成</Option>
        </Select>
      </div>
      
      <List
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px 0',
          maxWidth: '800px',
          margin: '0 auto',
          width: '100%'
        }}
        dataSource={messages}
        renderItem={(message) => (
          <List.Item
            style={{
              background: message.type === 'user' ? '#f7f7f8' : '#ffffff',
              padding: '20px',
              borderBottom: '1px solid #e5e7eb'
            }}
          >
            <List.Item.Meta
              avatar={<Avatar style={{ background: message.type === 'user' ? '#1677ff' : '#10a37f' }}>
                {message.type === 'user' ? 'U' : 'A'}
              </Avatar>}
              description={<span style={{ color: '#333333' }}>{message.content}</span>}
            />
          </List.Item>
        )}
      />
    </Content>
  );
}

export default Chat;