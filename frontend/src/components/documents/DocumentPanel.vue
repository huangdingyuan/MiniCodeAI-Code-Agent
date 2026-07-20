<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import DocumentUpload from './DocumentUpload.vue'
import DocumentList from './DocumentList.vue'
import { documentApi } from '../../api'
import type { Document } from '../../types'

const documents = ref<Document[]>([])
const loading = ref(false)

// 加载文档列表
const loadDocuments = async () => {
  loading.value = true
  try {
    documents.value = await documentApi.list()
  } catch (error) {
    console.error('加载文档失败:', error)
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

// 处理上传
const handleUpload = async (file: File) => {
  try {
    const result = await documentApi.upload(file)
    ElMessage.success(`文档 ${file.name} 上传成功`)

    // 添加到列表
    const newDoc: Document = {
      doc_id: result.doc_id,
      filename: result.filename,
      file_type: file.name.split('.').pop() || 'unknown',
      file_size: file.size,
      upload_time: new Date().toISOString(),
      status: 'parsing'
    }
    documents.value.unshift(newDoc)

    // 模拟解析完成（实际应该通过 WebSocket 或轮询获取状态）
    setTimeout(() => {
      const doc = documents.value.find(d => d.doc_id === result.doc_id)
      if (doc) {
        doc.status = 'ready'
        doc.chunk_count = Math.floor(Math.random() * 20) + 5
      }
    }, 2000)
  } catch (error: any) {
    console.error('上传失败:', error)
    ElMessage.error(error.response?.data?.detail || '上传失败')
  }
}

// 处理删除
const handleDelete = async (docId: string) => {
  try {
    await documentApi.delete(docId)
    documents.value = documents.value.filter(doc => doc.doc_id !== docId)
    ElMessage.success('文档已删除')
  } catch (error: any) {
    console.error('删除失败:', error)
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

// 组件挂载时加载文档
onMounted(() => {
  loadDocuments()
})
</script>

<template>
  <div class="document-panel">
    <div class="panel-header">
      <el-icon><Folder /></el-icon>
      <span>文档管理</span>
    </div>

    <div class="panel-content">
      <DocumentUpload @upload="handleUpload" />
      <DocumentList :documents="documents" @delete="handleDelete" />
    </div>
  </div>
</template>

<style scoped>
.document-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}
</style>
