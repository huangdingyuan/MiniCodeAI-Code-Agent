<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import MessageList from './MessageList.vue'
import MessageInput from './MessageInput.vue'
import { chatApi, documentApi, imageApi } from '../../api'
import type { Message, Session } from '../../types'
import { sessionManager } from '../../utils/sessionManager'
import { ChatDotRound } from '@element-plus/icons-vue'

const currentSessionId = ref('')
const currentSessionTitle = ref('智能对话')
const messages = ref<Message[]>([])
const isLoading = ref(false)

const loadCurrentSession = () => {
  // 清理旧版不分用户的 localStorage 残留
  sessionManager.cleanupLegacyKeys()

  let session = sessionManager.getCurrentSession()
  if (!session) {
    const oldMessages = loadOldMessages()
    if (oldMessages.length > 1) {
      const now = Date.now()
      session = {
        id: `session_${now}`,
        title: '历史对话',
        messages: oldMessages,
        createdAt: now,
        updatedAt: now
      }
      sessionManager.saveSession(session)
      sessionManager.setCurrentSessionId(session.id)
    } else {
      session = sessionManager.createNewSession()
    }
  }
  currentSessionId.value = session.id
  currentSessionTitle.value = session.title
  messages.value = session.messages
}

const loadOldMessages = (): Message[] => {
  const legacy = sessionManager.getLegacyMessages()
  if (legacy && legacy.length > 0) {
    return legacy.map((m: Message) => ({ ...m, isStreaming: false }))
  }
  return []
}

const saveMessages = () => {
  const toSave = messages.value.filter(m => !m.isStreaming)
  sessionManager.updateSessionMessages(currentSessionId.value, toSave)
  currentSessionTitle.value = sessionManager.getSession(currentSessionId.value)?.title || '智能对话'
}

watch(
  messages,
  () => {
    saveMessages()
  },
  { deep: true }
)

onMounted(() => {
  loadCurrentSession()
})

const handleSend = async (content: string) => {
  const userMessage: Message = {
    id: Date.now().toString(),
    role: 'user',
    content,
    timestamp: Date.now()
  }
  messages.value.push(userMessage)

  const aiMessageId = (Date.now() + 1).toString()
  const aiMessage: Message = {
    id: aiMessageId,
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    isStreaming: true,
    thinkingSteps: [],
    retrievedDocuments: [],
    toolCalls: [],
  }
  messages.value.push(aiMessage)

  isLoading.value = true

  try {
    const chatHistory = messages.value
      .filter(m => m.id !== aiMessageId)
      .map(m => ({ role: m.role, content: m.content }))

    const response = await chatApi.streamMessage({
      message: content,
      session_id: currentSessionId.value,
      chat_history: chatHistory
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

    const updateMsg = (updates: Partial<Message>) => {
      const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
      if (msgIndex !== -1) {
        messages.value[msgIndex] = { ...messages.value[msgIndex], ...updates }
      }
    }

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'thinking') {
                // FR-12 思考过程
                const aiMsg = messages.value.find(m => m.id === aiMessageId)
                if (aiMsg) {
                  const steps = aiMsg.thinkingSteps || []
                  steps.push(data.content)
                  updateMsg({ thinkingSteps: steps })
                  await nextTick()
                }
              } else if (data.type === 'retrieving') {
                // FR-12 检索结果展示
                updateMsg({
                  retrievedDocuments: data.documents || [],
                })
                await nextTick()
              } else if (data.type === 'tool_call') {
                // FR-13 工具调用开始
                const aiMsg = messages.value.find(m => m.id === aiMessageId)
                if (aiMsg) {
                  const calls = aiMsg.toolCalls || []
                  calls.push({
                    tool: data.tool,
                    input: data.input,
                    status: 'calling',
                  })
                  updateMsg({ toolCalls: calls })
                  await nextTick()
                }
              } else if (data.type === 'tool_result') {
                // FR-13 工具调用完成
                const aiMsg = messages.value.find(m => m.id === aiMessageId)
                if (aiMsg && aiMsg.toolCalls && aiMsg.toolCalls.length > 0) {
                  const lastCall = aiMsg.toolCalls[aiMsg.toolCalls.length - 1]
                  lastCall.output = data.content
                  lastCall.status = 'done'
                  updateMsg({ toolCalls: [...aiMsg.toolCalls] })
                  await nextTick()
                }
              } else if (data.type === 'generating') {
                fullContent += data.content
                updateMsg({
                  content: fullContent,
                  isStreaming: true,
                })
                await nextTick()
              } else if (data.type === 'citations') {
                updateMsg({ citations: data.citations || [] })
              } else if (data.type === 'done') {
                updateMsg({ isStreaming: false })
                // FR-16 后端返回的 session_id 可能与前端不一致（首次对话时）
                if (data.session_id) {
                  currentSessionId.value = data.session_id
                }
              } else if (data.type === 'error') {
                updateMsg({
                  content: data.content,
                  isStreaming: false,
                })
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('对话失败:', error)
    const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
    if (msgIndex !== -1) {
      messages.value[msgIndex].content = '对话服务出错，请稍后重试。'
      messages.value[msgIndex].isStreaming = false
    }
  } finally {
    isLoading.value = false
  }
}

const handleSendImage = async (imageUrl: string, file: File) => {
  isLoading.value = true

  const userMessage: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: '',
    timestamp: Date.now(),
    imageUrl
  }
  messages.value.push(userMessage)

  const aiMessageId = (Date.now() + 1).toString()
  const aiMessage: Message = {
    id: aiMessageId,
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    isStreaming: true
  }
  messages.value.push(aiMessage)

  try {
    const recognition = await imageApi.recognize(file)
    const imageContent = recognition.content || '图片内容识别结果'

    const chatHistory = messages.value
      .filter(m => m.id !== aiMessageId)
      .map(m => ({ role: m.role, content: m.content }))

    const response = await chatApi.streamMessage({
      message: `请分析这张图片的内容：${imageContent}`,
      session_id: currentSessionId.value,
      chat_history: chatHistory
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
              const aiMsg = msgIndex !== -1 ? messages.value[msgIndex] : null
              if (data.type === 'generating') {
                fullContent += data.content
                if (aiMsg) {
                  aiMsg.content = fullContent
                  aiMsg.isStreaming = true
                }
                await nextTick()
              } else if (data.type === 'citations') {
                if (aiMsg) {
                  aiMsg.citations = data.citations || []
                }
              } else if (data.type === 'done') {
                if (aiMsg) {
                  aiMsg.isStreaming = false
                }
              } else if (data.type === 'error') {
                if (aiMsg) {
                  aiMsg.content = data.content
                  aiMsg.isStreaming = false
                }
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    }
  } catch (error: any) {
    console.error('图片识别或分析失败:', error)
    const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
    const aiMsg = msgIndex !== -1 ? messages.value[msgIndex] : null
    if (aiMsg) {
      let errorMsg = '图片识别或分析失败，请稍后重试。'
      if (error.response) {
        const status = error.response.status
        if (status === 401) {
          errorMsg = '请先登录后再发送图片。'
        } else if (status === 400) {
          errorMsg = '不支持的图片格式，请上传 PNG/JPG/JPEG 格式的图片。'
        } else if (error.response.data && error.response.data.error) {
          errorMsg = error.response.data.error
        } else {
          errorMsg = `图片上传失败 (${status})`
        }
      } else if (error.message) {
        errorMsg = `图片处理失败: ${error.message}`
      }
      aiMsg.content = errorMsg
      aiMsg.isStreaming = false
    }
  } finally {
    isLoading.value = false
  }
}

const handleUpload = async (file: File) => {
  isLoading.value = true

  const userMessage: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: `📎 上传文件: ${file.name} (${(file.size / 1024).toFixed(1)}KB)`,
    timestamp: Date.now()
  }
  messages.value.push(userMessage)

  const aiMessageId = (Date.now() + 1).toString()
  const aiMessage: Message = {
    id: aiMessageId,
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    isStreaming: true
  }
  messages.value.push(aiMessage)

  try {
    await documentApi.upload(file)

    const chatHistory = messages.value
      .filter(m => m.id !== aiMessageId)
      .map(m => ({ role: m.role, content: m.content }))

    const response = await chatApi.streamMessage({
      message: `请帮我分析这个文件的内容：${file.name}`,
      session_id: currentSessionId.value,
      chat_history: chatHistory
    })

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()
    let fullContent = ''

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
              const aiMsg = msgIndex !== -1 ? messages.value[msgIndex] : null
              if (data.type === 'generating') {
                fullContent += data.content
                if (aiMsg) {
                  aiMsg.content = fullContent
                  aiMsg.isStreaming = true
                }
                await nextTick()
              } else if (data.type === 'citations') {
                if (aiMsg) {
                  aiMsg.citations = data.citations || []
                }
              } else if (data.type === 'done') {
                if (aiMsg) {
                  aiMsg.isStreaming = false
                }
              } else if (data.type === 'error') {
                if (aiMsg) {
                  aiMsg.content = data.content
                  aiMsg.isStreaming = false
                }
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('文件上传或分析失败:', error)
    const msgIndex = messages.value.findIndex(m => m.id === aiMessageId)
    const aiMsg = msgIndex !== -1 ? messages.value[msgIndex] : null
    if (aiMsg) {
      aiMsg.content = '文件上传或分析失败，请稍后重试。'
      aiMsg.isStreaming = false
    }
  } finally {
    isLoading.value = false
  }
}

const handleSelectSession = (session: Session) => {
  currentSessionId.value = session.id
  currentSessionTitle.value = session.title
  messages.value = [...session.messages]
}

const handleCreateNewSession = () => {
  const newSession = sessionManager.createNewSession()
  currentSessionId.value = newSession.id
  currentSessionTitle.value = newSession.title
  messages.value = [...newSession.messages]
}

defineExpose({
  selectSession: handleSelectSession,
  createNewSession: handleCreateNewSession
})
</script>

<template>
  <div class="chat-panel">
    <div class="chat-header">
      <el-icon><ChatDotRound /></el-icon>
      <span>{{ currentSessionTitle }}</span>
    </div>

    <MessageList :messages="messages" :loading="isLoading" />

    <MessageInput @send="handleSend" @upload="handleUpload" @send-image="handleSendImage" :disabled="isLoading" />
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  flex: 1;
  background: #f5f7fa;
}

.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  background: #f5f7fa;
}
</style>
