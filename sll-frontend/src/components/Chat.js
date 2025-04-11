import React, { useState } from 'react';
import { Layout, Input, Button, List, Avatar } from 'antd';
import { SendOutlined } from '@ant-design/icons';

const { Content } = Layout;

function Chat() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');

  const handleSend = () => {
    if (!inputValue.trim()) return;
    
    const newMessage = {
      type: 'user',
      content: inputValue,
      timestamp: new Date().toISOString(),
    };

    setMessages([...messages, newMessage]);
    setInputValue('');

    // TODO: 在这里添加与后端API的集成
  };

  return (
    <Content style={{ 
      background: '#343541',
      padding: '20px',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <List
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px 0'
        }}
        dataSource={messages}
        renderItem={(message) => (
          <List.Item
            style={{
              background: message.type === 'user' ? '#444654' : '#343541',
              padding: '20px',
              borderBottom: '1px solid #2f3336'
            }}
          >
            <List.Item.Meta
              avatar={<Avatar style={{ background: message.type === 'user' ? '#1677ff' : '#10a37f' }}>
                {message.type === 'user' ? 'U' : 'A'}
              </Avatar>}
              description={<span style={{ color: '#fff' }}>{message.content}</span>}
            />
          </List.Item>
        )}
      />
      <div style={{
        display: 'flex',
        padding: '20px',
        background: '#444654',
        borderRadius: '8px',
        marginTop: '20px'
      }}>
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入消息..."
          style={{
            background: '#40414f',
            border: 'none',
            color: '#fff'
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          style={{ marginLeft: '10px' }}
        />
      </div>
    </Content>
  );
}

export default Chat;