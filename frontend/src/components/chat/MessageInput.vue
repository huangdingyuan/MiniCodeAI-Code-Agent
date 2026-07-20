<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
  upload: [file: File]
  sendImage: [imageUrl: string, file: File]
}>()

const inputContent = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const imageInputRef = ref<HTMLInputElement | null>(null)

const handleSend = () => {
  const content = inputContent.value.trim()
  if (!content || props.disabled) return

  emit('send', content)
  inputContent.value = ''
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const triggerFileUpload = () => {
  fileInputRef.value?.click()
}

const triggerImageUpload = () => {
  imageInputRef.value?.click()
}

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    emit('upload', file)
    target.value = ''
  }
}

const handleImageSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    if (file.size > 10 * 1024 * 1024) {
      window.alert('图片大小不能超过 10MB')
      return
    }
    const reader = new FileReader()
    reader.onload = (event) => {
      const imageUrl = event.target?.result as string
      emit('sendImage', imageUrl, file)
    }
    reader.readAsDataURL(file)
    target.value = ''
  }
}

const isImageType = (filename: string) => {
  const ext = filename.split('.').pop()?.toLowerCase()
  return ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(ext || '')
}
</script>

<template>
  <div class="message-input">
    <div class="input-wrapper">
      <el-input
        v-model="inputContent"
        type="textarea"
        :rows="3"
        placeholder="发消息..."
        :disabled="disabled"
        @keydown="handleKeydown"
        resize="none"
        class="chat-input"
      />
      <div class="input-right">
        <input
          ref="imageInputRef"
          type="file"
          style="display: none"
          accept="image/png,image/jpg,image/jpeg,image/gif,image/bmp,image/webp"
          @change="handleImageSelect"
        />
        <el-button
          type="text"
          :disabled="disabled"
          @click="triggerImageUpload"
          class="upload-button"
        >
          <el-icon><Picture /></el-icon>
        </el-button>
        <input
          ref="fileInputRef"
          type="file"
          style="display: none"
          accept=".pdf,.md,.txt,.docx,.doc"
          @change="handleFileSelect"
        />
        <el-button
          type="text"
          :disabled="disabled"
          @click="triggerFileUpload"
          class="upload-button"
        >
          <el-icon><Plus /></el-icon>
        </el-button>
        <el-button
          type="primary"
          :disabled="disabled || !inputContent.trim()"
          @click="handleSend"
          class="send-button"
        >
          <span>发送</span>
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-input {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: #f5f7fa;
  border-radius: 20px;
  padding: 4px 4px 4px 12px;
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 8px 4px;
  font-size: 14px;
  resize: none;
}

.chat-input :deep(.el-textarea__inner):focus {
  background: transparent;
}

.input-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.upload-button {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #606266;
  font-size: 18px;
}

.upload-button:hover {
  color: #409eff;
}

.send-button {
  height: 36px;
  padding: 0 16px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}
</style>
