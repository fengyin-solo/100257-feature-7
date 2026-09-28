<template>
  <div class="conclusion-wrap">
    <span class="conclusion-badge" :class="badgeClass" :title="reasonText">{{ label }}</span>
    <ul v-if="showReasons && reasons.length" class="conclusion-reasons">
      <li v-for="(reason, index) in reasons" :key="index">{{ reason }}</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { Conclusion } from './types'

const props = withDefaults(defineProps<{
  conclusion: Conclusion | null | undefined
  showReasons?: boolean
}>(), {
  showReasons: false,
})

const label = computed(() => props.conclusion?.label ?? '—')
const reasons = computed(() => props.conclusion?.reasons ?? [])
const reasonText = computed(() => reasons.value.join('；'))

const badgeClass = computed(() => {
  switch (props.conclusion?.label) {
    case '正常':
      return 'is-normal'
    case '即将到期':
      return 'is-due-soon'
    case '已到期':
      return 'is-overdue'
    case '未排检修':
      return 'is-unscheduled'
    case '待复检':
      return 'is-recheck'
    case '已报废':
      return 'is-scrapped'
    default:
      return ''
  }
})
</script>

<style scoped>
.conclusion-wrap { display: flex; flex-direction: column; gap: 4px; }
.conclusion-badge {
  display: inline-block;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 18px;
  border: 1px solid transparent;
  white-space: nowrap;
}
.conclusion-badge.is-normal { background: #ecfdf3; color: #067647; border-color: #abefc6; }
.conclusion-badge.is-due-soon { background: #fffaeb; color: #b54708; border-color: #fedf89; }
.conclusion-badge.is-overdue { background: #fef3f2; color: #b42318; border-color: #fda29b; }
.conclusion-badge.is-unscheduled { background: #eff4ff; color: #1d4ed8; border-color: #b2ccff; }
.conclusion-badge.is-recheck { background: #fdf4ff; color: #a21caf; border-color: #f0abfc; }
.conclusion-badge.is-scrapped { background: #f2f4f7; color: #475467; border-color: #d0d5dd; }
.conclusion-reasons { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12px; }
.conclusion-reasons li { margin: 2px 0; }
.conclusion-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
