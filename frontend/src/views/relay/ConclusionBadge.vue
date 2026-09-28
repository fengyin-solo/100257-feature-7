<template>
  <span class="conclusion-badge" :class="`conclusion-${conclusion.code}`">
    {{ conclusion.label }}
  </span>
</template>

<script setup lang="ts">
import type { Conclusion } from './api'

defineProps<{ conclusion: Conclusion }>()
</script>

<style scoped>
.conclusion-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.5;
  border: 1px solid transparent;
  white-space: nowrap;
}
.conclusion-upcoming { background: #ecfdf3; color: #027a48; border-color: #abefc6; }
.conclusion-overdue { background: #fef3f2; color: #b42318; border-color: #fda29b; }
.conclusion-unscheduled { background: #fffaeb; color: #b54708; border-color: #fec84b; }
.conclusion-reinspect { background: #fef3f2; color: #c4320a; border-color: #f97066; }
.conclusion-scrapped { background: #f2f4f7; color: #475467; border-color: #d0d5dd; }
</style>
