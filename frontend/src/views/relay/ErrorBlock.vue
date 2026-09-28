<template>
  <div class="error-block" role="alert">
    <p class="error-title">{{ title }}</p>
    <p class="error-detail">{{ reason }}</p>
    <p class="error-hint">{{ hint }}</p>
    <button class="btn primary" type="button" :disabled="loading" @click="emit('retry')">
      {{ loading ? '重试中…' : '重试' }}
    </button>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  reason: string
  hint?: string
  loading?: boolean
}>(), {
  title: '数据加载失败',
  hint: '请确认后端服务已启动、网络连接正常后重试；若多次失败请联系值班管理员。',
  loading: false,
})

const emit = defineEmits<{ (e: 'retry'): void }>()
</script>

<style scoped>
.error-block {
  background: #fff;
  border: 1px solid #fda29b;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 12px;
  text-align: center;
}
.error-title { margin: 0 0 6px; font-weight: 600; color: #b42318; }
.error-detail { margin: 0 0 6px; font-size: 13px; color: #344054; }
.error-hint { margin: 0 0 12px; font-size: 12px; color: var(--muted); }
.error-block .btn { min-width: 88px; }
</style>
