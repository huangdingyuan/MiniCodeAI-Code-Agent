<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import MessageItem from './MessageItem.vue'
import type { Message } from '../../types'

const props = defineProps<{
  messages: Message[]
  loading: boolean
}>()

const messagesContainer = ref<HTMLElement | null>(null)

// 自动滚动到底部
watch(
  () => props.messages,
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="message-list" ref="messagesContainer">
    <div v-if="messages.length === 0" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
      <p>开始对话吧！</p>
    </div>

    <MessageItem
      v-for="message in messages"
      :key="message.id"
      :message="message"
    />

    <div v-if="loading" class="loading-indicator">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在思考...</span>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-state p {
  margin-top: 16px;
  font-size: 14px;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  color: #909399;
  font-size: 14px;
}
</style>
