import { Layout } from 'antd'
import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'

const { Header, Content, Footer } = Layout

function App() {
  return (
    <Layout className="layout">
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <h1 style={{ color: '#fff', margin: 0 }}>SLL</h1>
      </Header>
      <Content style={{ padding: '0 50px', marginTop: 64 }}>
        <div style={{ padding: 24, minHeight: 380 }}>
          <Routes>
            <Route path="/" element={<Home />} />
          </Routes>
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        SLL ©{new Date().getFullYear()}
      </Footer>
    </Layout>
  )
}

export default App