<template>
  <el-container class="chat-container">
    <el-header class="chat-header">
      <h2>SLL Chat</h2>
      <el-button type="text" icon="el-icon-setting" @click="showSettings = true"></el-button>
    </el-header>
    
    <el-main class="chat-main">
      <div class="message-list" ref="messageList">
        <div v-for="(message, index) in messages" :key="index" 
             :class="['message', message.role === 'user' ? 'message-user' : 'message-assistant']">
          <el-avatar :size="40" :icon="message.role === 'user' ? 'el-icon-user' : 'el-icon-service'"></el-avatar>
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            <div class="message-time">{{ message.time }}</div>
          </div>
        </div>
      </div>
    </el-main>
    
    <el-footer class="chat-footer">
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        placeholder="输入消息..."
        @keyup.enter.native.exact="sendMessage"
        resize="none"
      ></el-input>
      <el-button type="primary" @click="sendMessage" :loading="sending">
        发送
      </el-button>
    </el-footer>

    <!-- 设置对话框 -->
    <el-dialog title="设置" :visible.sync="showSettings" width="30%">
      <el-form label-width="80px">
        <el-form-item label="主题">
          <el-switch v-model="darkMode" active-text="深色" inactive-text="浅色"></el-switch>
        </el-form-item>
      </el-form>
    </el-dialog>
  </el-container>
</template>

<script>
export default {
  name: 'Chat',
  data() {
    return {
      messages: [],
      inputMessage: '',
      sending: false,
      showSettings: false,
      darkMode: false
    }
  },
  methods: {
    async sendMessage() {
      if (!this.inputMessage.trim()) return
      
      const message = {
        role: 'user',
        content: this.inputMessage,
        time: new Date().toLocaleTimeString()
      }
      
      this.messages.push(message)
      this.sending = true
      this.inputMessage = ''
      
      try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        this.messages.push({
          role: 'assistant',
          content: '这是一个模拟的回复消息。',
          time: new Date().toLocaleTimeString()
        })
      } catch (error) {
        console.error('发送消息失败:', error)
      } finally {
        this.sending = false
      }
      
      this.$nextTick(() => {
        this.scrollToBottom()
      })
    },
    scrollToBottom() {
      const messageList = this.$refs.messageList
      messageList.scrollTop = messageList.scrollHeight
    }
  }
}
</script>

<style scoped>
.chat-container {
  height: 100vh;
  background-color: #f5f7fa;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.chat-main {
  padding: 20px;
  overflow-y: hidden;
}

.message-list {
  height: 100%;
  overflow-y: auto;
  padding-right: 10px;
}

.message {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.message-assistant {
  flex-direction: row;
}

.message-user {
  flex-direction: row-reverse;
}

.message-content {
  margin: 0 12px;
  max-width: 70%;
}

.message-text {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  word-wrap: break-word;
}

.message-user .message-text {
  background-color: #409eff;
  color: #fff;
  border-radius: 8px 2px 8px 8px;
}

.message-assistant .message-text {
  background-color: #fff;
  color: #333;
  border-radius: 2px 8px 8px 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  text-align: right;
}

.chat-footer {
  padding: 20px;
  background-color: #fff;
  box-shadow: 0 -2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.chat-footer .el-input {
  flex: 1;
}

.chat-footer .el-button {
  margin-top: 8px;
}

/* 滚动条样式 */
.message-list::-webkit-scrollbar {
  width: 6px;
}

.message-list::-webkit-scrollbar-thumb {
  background-color: #dcdfe6;
  border-radius: 3px;
}

.message-list::-webkit-scrollbar-track {
  background-color: transparent;
}
</style>