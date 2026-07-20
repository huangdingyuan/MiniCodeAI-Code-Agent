<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'
import ChatPanel from '../components/chat/ChatPanel.vue'
import SessionList from '../components/chat/SessionList.vue'
import DocumentPanel from '../components/documents/DocumentPanel.vue'

const router = useRouter()
const authStore = useAuthStore()

const userDropdownVisible = ref(false)
const avatarInput = ref<HTMLInputElement | null>(null)
const chatPanelRef = ref<InstanceType<typeof ChatPanel> | null>(null)

const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.header-user')) {
    userDropdownVisible.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  authStore.loadUserFromStorage()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const userInitial = computed(() => {
  return authStore.user?.username?.charAt(0)?.toUpperCase() || 'U'
})

const handleAvatarClick = () => {
  avatarInput.value?.click()
}

const handleAvatarChange = async (e: Event) => {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }

  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过 5MB')
    return
  }

  try {
    await authStore.updateAvatar(file)
    ElMessage.success('头像更新成功')
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.message || '头像更新失败'
    ElMessage.error(msg)
  }

  // 清空 input，避免选择同一文件不触发 change
  target.value = ''
}

const handleLogout = () => {
  authStore.logout()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const handleSelectSession = (session: any) => {
  chatPanelRef.value?.selectSession(session)
}

const handleCreateNewSession = () => {
  chatPanelRef.value?.createNewSession()
}
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <div class="header-content">
        <el-icon :size="24" color="#409EFF"><Monitor /></el-icon>
        <h1>MiniCodeAI 代码智能体</h1>

        <div class="header-user">
          <div class="user-info" @click="userDropdownVisible = !userDropdownVisible">
            <div class="avatar-wrapper" @click.stop="handleAvatarClick">
              <img
                v-if="authStore.user?.avatar"
                :src="authStore.user.avatar"
                class="avatar-img"
                alt="头像"
              />
              <div v-else class="avatar-placeholder">
                {{ userInitial }}
              </div>
              <div class="avatar-upload-hint">
                <el-icon :size="14"><Camera /></el-icon>
              </div>
            </div>
            <span class="username">{{ authStore.user?.username }}</span>
            <el-icon class="dropdown-arrow" :class="{ 'is-rotated': userDropdownVisible }"><ArrowDown /></el-icon>
          </div>

          <Transition name="dropdown-fade">
            <div v-if="userDropdownVisible" class="custom-dropdown" @click.stop>
              <div class="dropdown-user-section">
                <div class="dropdown-user-info">
                  <div class="dropdown-avatar">
                    <img
                      v-if="authStore.user?.avatar"
                      :src="authStore.user.avatar"
                      class="avatar-img"
                      alt="头像"
                    />
                    <div v-else class="avatar-placeholder small">
                      {{ userInitial }}
                    </div>
                  </div>
                  <div class="dropdown-user-details">
                    <div class="dropdown-username">{{ authStore.user?.username }}</div>
                    <div class="dropdown-email">{{ authStore.user?.email }}</div>
                  </div>
                </div>
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-action" @click="handleAvatarClick">
                <el-icon><Camera /></el-icon>
                <span>更换头像</span>
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-action logout-action" @click="handleLogout">
                <el-icon><SwitchButton /></el-icon>
                <span>退出登录</span>
              </div>
            </div>
          </Transition>

          <input
            ref="avatarInput"
            type="file"
            accept="image/*"
            style="display: none"
            @change="handleAvatarChange"
          />
        </div>
      </div>
    </header>

    <main class="app-main">
      <section class="chat-section">
        <SessionList @select="handleSelectSession" @create="handleCreateNewSession" />
        <ChatPanel ref="chatPanelRef" />
      </section>

      <section class="document-section">
        <DocumentPanel />
      </section>
    </main>
  </div>
</template>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f5f7fa;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-content h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-user {
  margin-left: auto;
  position: relative;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 12px;
  border-radius: 20px;
  transition: background 0.2s;
}

.user-info:hover {
  background: #f5f7fa;
}

.avatar-wrapper {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  cursor: pointer;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.avatar-placeholder.small {
  font-size: 14px;
}

.avatar-upload-hint {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 18px;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s;
}

.avatar-wrapper:hover .avatar-upload-hint {
  opacity: 1;
}

.username {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.dropdown-arrow {
  font-size: 12px;
  color: #909399;
}

.app-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  padding: 16px;
  gap: 16px;
}

.chat-section {
  flex: 1 1 0%;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  display: flex;
}

.document-section {
  flex: 0 0 380px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

@media (max-width: 1024px) {
  .app-main {
    flex-direction: column;
  }

  .document-section {
    width: 100%;
    height: 300px;
  }
}

.custom-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  min-width: 220px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  z-index: 1000;
  overflow: hidden;
}

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.dropdown-user-section {
  padding: 16px;
}

.dropdown-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dropdown-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
}

.dropdown-avatar .avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dropdown-avatar .avatar-placeholder.small {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}

.dropdown-user-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dropdown-username {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.dropdown-email {
  font-size: 12px;
  color: #909399;
}

.dropdown-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 0;
}

.dropdown-action {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  font-size: 14px;
  color: #303133;
  cursor: pointer;
  transition: background 0.2s;
}

.dropdown-action:hover {
  background: #f5f7fa;
}

.dropdown-action span {
  flex: 1;
}

.logout-action {
  color: #f56c6c;
}

.logout-action:hover {
  background: #fef0f0;
}

.is-rotated {
  transform: rotate(180deg);
}

.dropdown-arrow {
  transition: transform 0.2s;
}
</style>
