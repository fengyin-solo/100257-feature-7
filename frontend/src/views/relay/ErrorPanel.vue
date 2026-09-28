<template>
  <div class="error-panel" role="alert">
    <p class="error-title">{{ title }}</p>
    <p class="error-reason">{{ reason }}</p>
    <button class="btn primary" type="button" :disabled="loading" @click="$emit('retry')">
      {{ loading ? '重试中…' : '重试' }}
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; reason: string; loading?: boolean }>()
defineEmits<{ (e: 'retry'): void }>()
</script>

<style scoped>
.error-panel {
  background: #fff;
  border: 1px solid #fda29b;
  border-radius: 8px;
  padding: 24px;
  text-align: center;
}
.error-title { margin: 0 0 6px; font-weight: 600; color: #b42318; }
.error-reason { margin: 0 0 14px; color: #64748b; font-size: 13px; line-height: 1.6; }
.btn { border: 1px solid var(--border); background: #fff; border-radius: 6px; padding: 6px 18px; cursor: pointer; }
.btn.primary { background: var(--brand); border-color: var(--brand); color: #fff; }
.btn:disabled { opacity: 0.6; cursor: default; }
</style>
