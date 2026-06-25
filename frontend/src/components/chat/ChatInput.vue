<template>
  <div class="chat-input-wrapper">
    <div class="chat-input-container">
      <div class="textarea-row">
        <textarea
          ref="textareaRef"
          v-model="input"
          @keydown.enter.exact.prevent="handleSend"
          placeholder="发送消息..."
          :disabled="loading"
          rows="2"
          class="chat-textarea"
        ></textarea>
        
        <button 
          class="send-arrow-btn" 
          @click="handleSend" 
          :disabled="!input.trim() || loading"
          title="发送"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="send-arrow-icon">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      
      <div class="input-actions-bar">

        
        <div class="actions-right">
          <span class="char-count" :class="{ limit: input.length > 500 }">
            {{ input.length }} / 500
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['send'])
const input = ref('')
const textareaRef = ref(null)

// 限制输入字数
watch(input, (newVal) => {
  if (newVal.length > 500) {
    input.value = newVal.slice(0, 500)
  }
})

const handleSend = () => {
  if (props.loading || !input.value.trim()) return
  emit('send', input.value.trim())
  input.value = ''
}

const prefill = (text) => {
  input.value = text
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.focus()
    }
  })
}

defineExpose({
  prefill,
})
</script>

<style scoped>
.chat-input-wrapper {
  width: 100%;
}

.chat-input-container {
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  background-color: var(--bg-secondary) !important;
  border-radius: var(--border-radius-lg);
  border: 1px solid var(--border-color);
  gap: 12px;
  position: relative;
  box-shadow: var(--shadow-md);
  transition: all var(--transition-fast) ease;
}

.chat-input-container:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-lg), 0 0 0 1px rgba(0, 133, 255, 0.05);
}

.textarea-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.chat-textarea {
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  color: var(--text-primary);
  font-family: var(--font-family);
  font-size: 13.5px;
  line-height: 1.5;
  width: 100%;
  padding-top: 4px;
}

.chat-textarea::placeholder {
  color: var(--text-muted);
  font-weight: 500;
}

.chat-textarea:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

/* 滚动条 */
.chat-textarea::-webkit-scrollbar {
  width: 4px;
}
.chat-textarea::-webkit-scrollbar-thumb {
  background: rgba(9, 11, 30, 0.08);
  border-radius: 2px;
}

.send-arrow-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-fast) ease;
  flex-shrink: 0;
  margin-bottom: 2px;
}

.send-arrow-btn:hover:not(:disabled) {
  color: var(--color-primary);
  background-color: var(--color-primary-bg);
}

.send-arrow-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.send-arrow-icon {
  width: 14px;
  height: 14px;
  stroke-width: 2.5;
}

.input-actions-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  border-top: 1px solid var(--border-color);
  padding-top: 10px;
}

.actions-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.action-link-btn {
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: color var(--transition-fast) ease;
  padding: 0;
}

.action-link-btn:hover {
  color: var(--color-primary);
}

.action-link-icon {
  width: 11px;
  height: 11px;
  color: var(--text-muted);
}

.action-link-btn:hover .action-link-icon {
  color: var(--color-primary);
}

.actions-right {
  display: flex;
  align-items: center;
}

.char-count {
  font-size: 10.5px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-weight: 600;
}

.char-count.limit {
  color: var(--color-warning);
}
</style>
