import { defineStore } from 'pinia'
import { getCurrentUser, loginUser, logoutUser, registerUser } from '@/api/auth'
import { getAuthToken, setAuthToken } from '@/api/http'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getAuthToken(),
    user: null,
    loading: false,
    error: null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => state.user?.role === 'admin',
  },
  actions: {
    async register(username, password) {
      this.loading = true
      this.error = null
      try {
        const data = await registerUser(username, password)
        this.token = data.access_token
        this.user = data.user
        return data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Registration failed'
        throw err
      } finally {
        this.loading = false
      }
    },
    async login(username, password) {
      this.loading = true
      this.error = null
      try {
        const data = await loginUser(username, password)
        this.token = data.access_token
        this.user = data.user
        return data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message || 'Login failed'
        throw err
      } finally {
        this.loading = false
      }
    },
    async fetchCurrentUser() {
      if (!this.token) return null

      this.loading = true
      this.error = null
      try {
        this.user = await getCurrentUser()
        return this.user
      } catch (err) {
        setAuthToken(null)
        this.token = null
        this.user = null
        this.error = err.response?.data?.detail || err.message || 'Session expired'
        throw err
      } finally {
        this.loading = false
      }
    },
    async logout() {
      this.loading = true
      this.error = null
      try {
        await logoutUser()
      } finally {
        setAuthToken(null)
        this.token = null
        this.user = null
        this.loading = false
      }
    },
  },
})
