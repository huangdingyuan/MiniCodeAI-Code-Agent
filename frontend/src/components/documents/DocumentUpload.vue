<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  upload: [file: File]
}>()

const isDragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = true
}

const handleDragLeave = () => {
  isDragging.value = false
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragging.value = false
  
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

const handleClick = () => {
  fileInput.value?.click()
}

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  const files = target.files
  if (files && files.length > 0) {
    handleFile(files[0])
    target.value = '' // 清空 input，允许重复选择同一文件
  }
}

const handleFile = (file: File) => {
  // 验证文件类型（支持 MIME 类型和文件扩展名）
  const allowedMimeTypes = ['application/pdf', 'text/markdown', 'text/plain', 'image/png', 'image/jpeg', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']
  const allowedExtensions = ['.pdf', '.md', '.txt', '.png', '.jpg', '.jpeg', '.docx', '.doc']
  
  const fileName = file.name.toLowerCase()
  const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext))
  
  if (!allowedMimeTypes.includes(file.type) && !hasValidExtension) {
    alert('不支持的文件类型，请上传 PDF、Markdown、TXT、Word 或图片文件')
    return
  }
  
  // 验证文件大小 (50MB)
  const maxSize = 50 * 1024 * 1024
  if (file.size > maxSize) {
    alert('文件大小不能超过 50MB')
    return
  }
  
  emit('upload', file)
}
</script>

<template>
  <div class="document-upload">
    <div
      class="upload-area"
      :class="{ 'is-dragging': isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="handleClick"
    >
      <el-icon :size="32" color="#409eff"><Upload /></el-icon>
      <div class="upload-text">
        <p class="upload-title">拖拽文件到此处，或点击上传</p>
        <p class="upload-hint">支持 PDF、Markdown、TXT、Word、PNG、JPG 格式，最大 50MB</p>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept=".pdf,.md,.txt,.docx,.doc,.png,.jpg,.jpeg"
        style="display: none"
        @change="handleFileChange"
      />
    </div>
  </div>
</template>

<style scoped>
.document-upload {
  margin-bottom: 16px;
}

.upload-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-area:hover {
  border-color: #409eff;
  background: #f0f7ff;
}

.upload-area.is-dragging {
  border-color: #409eff;
  background: #ecf5ff;
}

.upload-text {
  margin-top: 12px;
}

.upload-title {
  font-size: 14px;
  color: #606266;
  margin: 0 0 4px 0;
}

.upload-hint {
  font-size: 12px;
  color: #909399;
  margin: 0;
}
</style>
