import { defineStore } from 'pinia'
import { clearDocuments, deleteDocument, getDocuments, uploadDocuments } from '@/api/documents'
import { useAuthStore } from '@/stores/auth'

export const useDocumentStore = defineStore('documents', {
  state: () => ({
    documents: [],
    loading: false,
    uploading: false,
    error: null,
  }),
  getters: {
    privateDocuments: (state) => {
      const authStore = useAuthStore()
      const currentUserId = authStore.user?.id == null ? null : String(authStore.user.id)
      return state.documents.filter((doc) => (
        doc.visibility === 'private' && (!currentUserId || String(doc.user_id) === currentUserId)
      ))
    },
    publicDocuments: (state) => state.documents.filter((doc) => doc.visibility === 'public'),
  },
  actions: {
    async fetchDocuments() {
      this.loading = true
      this.error = null
      try {
        const data = await getDocuments()
        this.documents = data.documents || []
      } catch (err) {
        console.error(err)
        this.error = '加载文档列表失败'
      } finally {
        this.loading = false
      }
    },
    async uploadFiles(files, visibility = 'private', category = 'general') {
      if (!files || files.length === 0) return null
      this.uploading = true
      this.error = null
      try {
        const data = await uploadDocuments(files, visibility, category)
        this.documents = data.documents || []
        return data
      } catch (err) {
        console.error(err)
        this.error = err.response?.data?.detail || err.message || '上传失败'
        throw err
      } finally {
        this.uploading = false
      }
    },
    async deleteDocument(documentId) {
      this.loading = true
      this.error = null
      try {
        const data = await deleteDocument(documentId)
        this.documents = data.documents || []
        return data
      } catch (err) {
        console.error(err)
        this.error = err.response?.data?.detail || err.message || '删除文档失败'
        throw err
      } finally {
        this.loading = false
      }
    },
    async clearDocuments(scope = 'mine') {
      this.loading = true
      this.error = null
      try {
        const data = await clearDocuments(scope)
        this.documents = data.documents || []
        return data
      } catch (err) {
        console.error(err)
        this.error = err.response?.data?.detail || err.message || '清空知识库失败'
        throw err
      } finally {
        this.loading = false
      }
    },
  },
})
