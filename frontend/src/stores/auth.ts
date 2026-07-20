import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '../api'
import type { User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string>(localStorage.getItem('auth_token') || '')

  const isAuthenticated = computed(() => !!token.value)

  const login = async (username: string, password: string): Promise<boolean> => {
    const response = await authApi.login({ username, password })
    const { access_token, user: userInfo } = response

    user.value = userInfo
    token.value = access_token
    localStorage.setItem('auth_token', access_token)
    localStorage.setItem('user_info', JSON.stringify(userInfo))
    return true
  }

  const register = async (username: string, email: string, password: string): Promise<boolean> => {
    await authApi.register({ username, email, password })
    return true
  }

  const updateAvatar = async (file: File) => {
    // 调用后端 API 持久化头像到数据库
    const response = await authApi.uploadAvatar(file)
    if (user.value) {
      user.value = { ...user.value, avatar: response.avatar }
      localStorage.setItem('user_info', JSON.stringify(user.value))
    }
  }

  const logout = () => {
    user.value = null
    token.value = ''
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')
  }

  const loadUserFromStorage = () => {
    const storedToken = localStorage.getItem('auth_token')
    const storedUser = localStorage.getItem('user_info')

    if (storedToken && storedUser) {
      try {
        token.value = storedToken
        user.value = JSON.parse(storedUser)
      } catch (e) {
        logout()
      }
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    login,
    register,
    updateAvatar,
    logout,
    loadUserFromStorage
  }
})
