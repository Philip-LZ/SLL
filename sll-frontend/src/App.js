import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Layout } from 'antd';
import Chat from './components/Chat';
import LongText from './components/LongText';

const { Content } = Layout;

function App() {
  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Content>
          <Routes>
            <Route path="/" element={<Chat />} />
            <Route path="/longtext" element={<LongText />} />
          </Routes>
        </Content>
      </Layout>
    </Router>
  );
}

export default App;
