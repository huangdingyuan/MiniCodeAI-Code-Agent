<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { Session } from '../../types'
import { sessionManager } from '../../utils/sessionManager'
import { ChatSquare, Delete, Plus } from '@element-plus/icons-vue'

const emit = defineEmits<{
  select: [session: Session]
  create: []
}>()

const sessions = ref<Session[]>([])
const currentSessionId = ref('')
const hoveredSessionId = ref('')

const loadSessions = () => {
  sessions.value = sessionManager.getAllSessions()
  currentSessionId.value = sessionManager.getCurrentSessionId()
}

const selectSession = (session: Session) => {
  sessionManager.setCurrentSessionId(session.id)
  currentSessionId.value = session.id
  emit('select', session)
}

const createNewSession = () => {
  emit('create')
}

const deleteSession = (id: string, e: Event) => {
  e.stopPropagation()
  sessionManager.deleteSession(id)
  loadSessions()
}

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - timestamp

  if (diff < 60000) {
    return '刚刚'
  } else if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  } else if (diff < 86400000) {
    return `${Math.floor(diff / 3600000)}小时前`
  } else if (diff < 604800000) {
    return `${Math.floor(diff / 86400000)}天前`
  } else {
    return `${date.getMonth() + 1}/${date.getDate()}`
  }
}

onMounted(() => {
  loadSessions()
})

watch(() => sessionManager.getAllSessions(), () => {
  loadSessions()
}, { deep: true })
</script>

<template>
  <div class="session-list">
    <div class="list-header">
      <el-icon><ChatSquare /></el-icon>
      <span>对话列表</span>
    </div>

    <div class="session-items">
      <div
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: currentSessionId === session.id }"
        @click="selectSession(session)"
        @mouseenter="hoveredSessionId = session.id"
        @mouseleave="hoveredSessionId = ''"
      >
        <div class="session-info">
          <div class="session-title">{{ session.title }}</div>
          <div class="session-time">{{ formatTime(session.updatedAt) }}</div>
        </div>
        <el-button
          v-if="hoveredSessionId === session.id"
          type="text"
          size="small"
          class="delete-btn"
          @click="deleteSession(session.id, $event)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="list-footer">
      <el-button
        type="primary"
        plain
        @click="createNewSession"
        class="new-session-btn"
      >
        <el-icon><Plus /></el-icon>
        <span>新对话</span>
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.session-list {
  width: 260px;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e4e7ed;
  height: 100%;
}

.list-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #e4e7ed;
}

.session-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.session-item:hover {
  background: #eef2f7;
}

.session-item.active {
  background: #fff;
  border: 1px solid #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.session-item.active .session-title {
  color: #409eff;
  font-weight: 500;
}

.session-item.active .session-time {
  color: #909399;
}

.session-info {
  flex: 1;
  overflow: hidden;
}

.session-title {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-time {
  font-size: 12px;
  color: #909399;
}

.delete-btn {
  color: #f56c6c;
  padding: 0;
  margin-left: 8px;
}

.list-footer {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.new-session-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
</style>
