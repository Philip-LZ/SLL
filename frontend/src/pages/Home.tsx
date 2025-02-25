import { useState, useEffect, useRef } from 'react';
import { Input, Button, List, message } from 'antd';
import { SendOutlined } from '@ant-design/icons';

interface Message {
  text: string;
  isUser: boolean;
  type?: 'reasoning' | 'answer';
}

const Home = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const userMessage: Message = {
      text: inputText,
      isUser: true
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputText,
          conversation_id: conversationId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('无法获取响应流');
      }
      
      let currentMessage: Message = {
        text: '',
        isUser: false,
        type: 'reasoning'
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              switch (data.type) {
                case 'reasoning':
                  if (!currentMessage.text) {
                    setMessages(prev => [...prev, currentMessage]);
                  }
                  currentMessage.text += data.content;
                  setMessages(prev => [...prev.slice(0, -1), { ...currentMessage }]);
                  break;

                case 'start_answer':
                  currentMessage = {
                    text: '',
                    isUser: false,
                    type: 'answer'
                  };
                  setMessages(prev => [...prev, currentMessage]);
                  break;

                case 'answer':
                  currentMessage.text += data.content;
                  setMessages(prev => [...prev.slice(0, -1), { ...currentMessage }]);
                  break;

                case 'done':
                  setConversationId(data.conversation_id);
                  setIsLoading(false);
                  return;
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e);
            }
          }
        }
      }
    } catch (error) {
      setIsLoading(false);
      message.error('发送消息失败：' + (error instanceof Error ? error.message : '未知错误'));
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <List
        className="message-list"
        itemLayout="horizontal"
        dataSource={messages}
        renderItem={(item) => (
          <List.Item style={{
            justifyContent: item.isUser ? 'flex-end' : 'flex-start',
            padding: '8px 16px'
          }}>
            <div style={{
              background: item.isUser ? '#1890ff' : item.type === 'reasoning' ? '#f5f5f5' : '#e6f7ff',
              color: item.isUser ? 'white' : 'black',
              padding: '8px 12px',
              borderRadius: '8px',
              maxWidth: '70%',
              whiteSpace: 'pre-wrap'
            }}>
              {item.type === 'reasoning' && '思考中：'}
              {item.text}
            </div>
          </List.Item>
        )}
        style={{
          height: 'calc(100vh - 250px)',
          overflowY: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: '4px',
          marginBottom: '16px'
        }}
        ref={listRef}
      />
      <div style={{ display: 'flex', gap: '8px' }}>
        <Input
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onPressEnter={handleSend}
          placeholder="请输入消息..."
          disabled={isLoading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={isLoading}
        >
          发送
        </Button>
      </div>
    </div>
  );
};

export default Home;