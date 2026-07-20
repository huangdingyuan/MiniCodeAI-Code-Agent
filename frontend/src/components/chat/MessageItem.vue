<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import type { Message } from '../../types'

const props = defineProps<{
  message: Message
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch (__) {}
    }
    return ''
  }
})

const formattedTime = computed(() => {
  const date = new Date(props.message.timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

const renderedContent = computed(() => {
  return md.render(props.message.content)
})

const isUser = computed(() => props.message.role === 'user')

const hasThinking = computed(() =>
  props.message.thinkingSteps && props.message.thinkingSteps.length > 0
)

const hasRetrievedDocs = computed(() =>
  props.message.retrievedDocuments && props.message.retrievedDocuments.length > 0
)

const hasToolCalls = computed(() =>
  props.message.toolCalls && props.message.toolCalls.length > 0
)
</script>

<template>
  <div class="message-item" :class="{ 'is-user': isUser, 'is-assistant': !isUser }">
    <div class="message-avatar">
      <el-icon v-if="isUser" :size="20" color="#fff"><User /></el-icon>
      <el-icon v-else :size="20" color="#fff"><Monitor /></el-icon>
    </div>

    <div class="message-content">
      <div class="message-header">
        <span class="message-role">{{ isUser ? '你' : 'AI 助手' }}</span>
        <span class="message-time">{{ formattedTime }}</span>
      </div>

      <!-- FR-13 工具调用展示 -->
      <div v-if="hasToolCalls" class="message-tools">
        <div
          v-for="(call, index) in message.toolCalls"
          :key="index"
          class="tool-call-item"
        >
          <div class="tool-call-header">
            <el-icon><Tools /></el-icon>
            <span class="tool-name">{{ call.tool }}</span>
            <el-tag v-if="call.status === 'calling'" type="warning" size="small">调用中</el-tag>
            <el-tag v-else-if="call.status === 'done'" type="success" size="small">完成</el-tag>
            <el-tag v-else type="danger" size="small">错误</el-tag>
          </div>
          <div class="tool-call-input">
            <span class="tool-label">输入:</span>
            <code>{{ call.input }}</code>
          </div>
          <div v-if="call.output" class="tool-call-output">
            <span class="tool-label">输出:</span>
            <pre>{{ call.output }}</pre>
          </div>
        </div>
      </div>

      <div v-if="message.content" class="message-body" v-html="renderedContent"></div>

      <div v-if="message.imageUrl" class="message-image">
        <img :src="message.imageUrl" alt="发送的图片" />
      </div>

      <!-- 引用来源（含页码 FR-11） -->
      <div v-if="message.citations && message.citations.length > 0" class="message-citations">
        <div class="citations-title">
          <el-icon><Document /></el-icon>
          <span>引用来源</span>
          <span class="citations-count">({{ message.citations.length }})</span>
        </div>
        <div class="citations-list">
          <div
            v-for="(citation, index) in message.citations"
            :key="index"
            class="citation-item"
          >
            <span class="citation-index">{{ index + 1 }}</span>
            <span class="citation-filename">{{ citation.filename }}</span>
            <span
              v-if="citation.page !== undefined && citation.page !== null"
              class="citation-page"
            >
              第 {{ citation.page }} 页
            </span>
            <span v-if="citation.relevance_score" class="citation-score">
              匹配度: {{ (citation.relevance_score * 100).toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message-item.is-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.is-user .message-avatar {
  background: #409eff;
}

.is-assistant .message-avatar {
  background: #67c23a;
}

.message-content {
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

.message-role {
  font-weight: 500;
  color: #606266;
}

.message-body {
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  font-size: 14px;
  word-wrap: break-word;
}

.is-user .message-body {
  background: #409eff;
  color: #fff;
}

.is-assistant .message-body {
  background: #fff;
  color: #303133;
  border: 1px solid #e4e7ed;
}

.message-body :deep(pre) {
  background: #f6f8fa;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 8px 0;
}

.message-body :deep(code) {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.message-body :deep(p) {
  margin: 0;
}

.message-body :deep(p + p) {
  margin-top: 8px;
}

.message-image {
  max-width: 300px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.message-image img {
  width: 100%;
  height: auto;
  display: block;
}

/* FR-12 思考过程 */
.message-thinking {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #67c23a;
  font-weight: 500;
  margin-bottom: 6px;
}

.thinking-steps {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thinking-step {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
}

.step-icon {
  color: #67c23a;
  font-size: 12px;
}

/* FR-12 检索文档 */
.message-retrieving {
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 12px;
}

.retrieving-title {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #409eff;
  font-weight: 500;
  margin-bottom: 6px;
}

.retrieving-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.retrieving-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  background: #fff;
  border-radius: 4px;
  flex-wrap: wrap;
}

.doc-index {
  width: 18px;
  height: 18px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
}

.doc-filename {
  flex: 1;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-page {
  color: #e6a23c;
  font-size: 11px;
  background: #fdf6ec;
  padding: 2px 6px;
  border-radius: 3px;
}

.doc-score {
  color: #67c23a;
  font-size: 11px;
  font-weight: 500;
}

/* FR-13 工具调用 */
.message-tools {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-call-item {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.tool-name {
  font-weight: 500;
  color: #409eff;
}

.tool-call-input,
.tool-call-output {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.tool-label {
  color: #909399;
  font-size: 11px;
}

.tool-call-input code {
  background: #f6f8fa;
  padding: 4px 6px;
  border-radius: 3px;
  color: #c7254e;
  font-family: 'Consolas', 'Monaco', monospace;
}

.tool-call-output pre {
  background: #f6f8fa;
  padding: 6px;
  border-radius: 3px;
  max-height: 150px;
  overflow-y: auto;
  margin: 0;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 引用来源 */
.message-citations {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 12px;
  margin-top: 8px;
}

.citations-title {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #606266;
  font-weight: 500;
  margin-bottom: 6px;
}

.citations-count {
  color: #909399;
  font-weight: normal;
}

.citations-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.citation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
  padding: 4px 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.citation-index {
  width: 18px;
  height: 18px;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
}

.citation-filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-page {
  color: #e6a23c;
  font-size: 11px;
  background: #fdf6ec;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
}

.citation-score {
  color: #67c23a;
  font-size: 11px;
  font-weight: 500;
  flex-shrink: 0;
}
</style>
