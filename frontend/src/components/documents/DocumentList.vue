<script setup lang="ts">
import type { Document } from '../../types'

const props = defineProps<{
  documents: Document[]
}>()

const emit = defineEmits<{
  delete: [docId: string]
}>()

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const handleDelete = (docId: string) => {
  if (confirm('确定要删除这个文档吗？')) {
    emit('delete', docId)
  }
}
</script>

<template>
  <div class="document-list">
    <div v-if="documents.length === 0" class="empty-state">
      <el-icon :size="48" color="#c0c4cc"><Folder /></el-icon>
      <p>暂无文档</p>
    </div>

    <div v-else class="list-container">
      <div
        v-for="doc in documents"
        :key="doc.doc_id"
        class="document-item"
      >
        <div class="doc-icon">
          <el-icon :size="24" color="#409eff">
            <Document />
          </el-icon>
        </div>

        <div class="doc-info">
          <div class="doc-name">{{ doc.filename }}</div>
          <div class="doc-meta">
            <span>{{ formatFileSize(doc.file_size) }}</span>
            <span>•</span>
            <span>{{ formatDate(doc.upload_time) }}</span>
            <span v-if="doc.chunk_count">•</span>
            <span v-if="doc.chunk_count">{{ doc.chunk_count }} 个片段</span>
          </div>
          <div class="doc-status">
            <el-tag
              :type="doc.status === 'ready' ? 'success' : doc.status === 'parsing' ? 'warning' : 'danger'"
              size="small"
            >
              {{ doc.status === 'ready' ? '已就绪' : doc.status === 'parsing' ? '解析中' : '错误' }}
            </el-tag>
          </div>
        </div>

        <div class="doc-actions">
          <el-button
            type="danger"
            size="small"
            icon="Delete"
            circle
            @click="handleDelete(doc.doc_id)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.document-list {
  margin-top: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: #909399;
}

.empty-state p {
  margin-top: 12px;
  font-size: 14px;
}

.list-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.document-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  transition: all 0.3s;
}

.document-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
}

.doc-icon {
  flex-shrink: 0;
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.doc-status {
  display: flex;
  align-items: center;
}

.doc-actions {
  flex-shrink: 0;
}
</style>
