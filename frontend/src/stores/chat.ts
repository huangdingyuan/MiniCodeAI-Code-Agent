import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message } from '../types'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: '你好！我是 MiniCodeAI 代码智能体。我可以帮助你理解代码、解答技术问题、分析文档。请上传相关文档后开始提问。',
      timestamp: Date.now()
    }
  ])

  const isLoading = ref(false)
  const sessionId = ref('session-' + Date.now())

  const addMessage = (message: Message) => {
    messages.value.push(message)
  }

  const clearMessages = () => {
    messages.value = []
  }

  const setLoading = (loading: boolean) => {
    isLoading.value = loading
  }

  return {
    messages,
    isLoading,
    sessionId,
    addMessage,
    clearMessages,
    setLoading
  }
})
