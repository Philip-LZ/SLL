import React, { useState } from 'react';
import { Layout, Input, Button, Card, Typography, Spin } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

const { Content } = Layout;
const { TextArea } = Input;
const { Title, Paragraph } = Typography;

function LongText() {
  const [topic, setTopic] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedContent, setGeneratedContent] = useState('');

  const handleGenerate = () => {
    if (!topic.trim()) return;
    
    setIsGenerating(true);
    // TODO: 在这里添加与后端API的集成
    setIsGenerating(false);
  };

  return (
    <Content style={{ 
      background: '#343541',
      padding: '20px',
      minHeight: '100vh'
    }}>
      <Card
        style={{
          maxWidth: '800px',
          margin: '0 auto',
          background: '#444654'
        }}
        bodyStyle={{
          padding: '24px'
        }}
      >
        <Title level={4} style={{ color: '#fff', marginBottom: '24px' }}>
          <FileTextOutlined style={{ marginRight: '8px' }} />
          长文本生成
        </Title>

        <div style={{ marginBottom: '24px' }}>
          <TextArea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="请输入要生成的文章主题..."
            autoSize={{ minRows: 3, maxRows: 6 }}
            style={{
              background: '#40414f',
              border: 'none',
              color: '#fff'
            }}
          />
        </div>

        <Button
          type="primary"
          onClick={handleGenerate}
          loading={isGenerating}
          block
        >
          生成文章
        </Button>

        {isGenerating && (
          <div style={{ textAlign: 'center', margin: '24px 0' }}>
            <Spin tip="正在生成文章..." />
          </div>
        )}

        {generatedContent && (
          <Card
            style={{
              marginTop: '24px',
              background: '#40414f'
            }}
          >
            <Paragraph style={{ color: '#fff' }}>
              {generatedContent}
            </Paragraph>
          </Card>
        )}
      </Card>
    </Content>
  );
}

export default LongText;