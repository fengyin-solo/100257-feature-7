<template>
  <div class="modal-mask" @click.self="close">
    <div class="modal-card" role="dialog" :aria-label="title">
      <header class="modal-head">
        <h3>{{ title }}</h3>
        <button class="link" type="button" @click="close">关闭</button>
      </header>
      <p class="modal-target">继电器：{{ row.继电器编号 }} · {{ row.继电器型号 }} · {{ row.所属设备 }}</p>

      <form class="modal-form" @submit.prevent="submit">
        <template v-if="mode === 'schedule'">
          <label class="form-item">
            <span>下次检修日 <em>*</em></span>
            <input v-model="nextDate" type="date" required />
          </label>
          <p class="form-hint">
            上次检修日：{{ row.上次检修日 || '（暂无）' }}；排期不能早于上次检修日。重复安排时以最近一次为准，历史排期仍会保留。
          </p>
        </template>

        <template v-else>
          <label class="form-item">
            <span>检修日期 <em>*</em></span>
            <input v-model="inspectDate" type="date" :max="today" required />
          </label>
          <label class="form-item">
            <span>接点电阻（Ω）</span>
            <input v-model="resistance" placeholder="如 0.03 或 30mΩ；留空按待复检处理" />
          </label>
          <p class="form-hint">
            允许范围 0～0.05Ω；为空、无法识别或超出范围不会拦截保存，但该继电器会被标为“待复检”。
            检修日期早于上次检修日（{{ row.上次检修日 || '暂无' }}）时记录无法保存。
          </p>
        </template>

        <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>

        <footer class="modal-foot">
          <button class="btn" type="button" @click="close">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '保存中…' : '保存' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import {
  saveInspectionRecord,
  scheduleInspection,
  type RelayRow,
} from './api'

const props = defineProps<{ mode: 'schedule' | 'inspect'; row: RelayRow }>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', message: string): void
}>()

const today = new Date().toISOString().slice(0, 10)
const nextDate = ref(props.row.下次检修日 || '')
const inspectDate = ref(today)
const resistance = ref('')
const errorMessage = ref('')
const submitting = ref(false)

const title = computed(() => (props.mode === 'schedule' ? '安排 / 补录下次检修日' : '登记检修完成记录'))

function close() {
  emit('close')
}

async function submit() {
  errorMessage.value = ''
  submitting.value = true
  try {
    const result =
      props.mode === 'schedule'
        ? await scheduleInspection(props.row.id, nextDate.value)
        : await saveInspectionRecord(props.row.id, {
            检修日期: inspectDate.value,
            接点电阻: resistance.value.trim(),
          })
    if (!result.ok) {
      // 日期倒挂 / 格式不对：后端说明哪两个日期对不上，原样展示
      errorMessage.value = result.message
      return
    }
    emit('saved', result.message)
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : '请求未送达，可能是网络中断或服务暂不可用，请重试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(16, 24, 40, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal-card {
  background: #fff;
  border-radius: 10px;
  width: 460px;
  max-width: calc(100vw - 32px);
  padding: 18px 20px;
}
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-target { margin: 8px 0 14px; font-size: 12px; color: var(--muted); }
.form-item { display: block; margin-bottom: 12px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item em { color: #b42318; font-style: normal; }
.form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.form-hint { font-size: 12px; color: var(--muted); line-height: 1.6; margin: 0 0 12px; }
.form-error { font-size: 12px; color: #b42318; margin: 0 0 12px; line-height: 1.6; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; }
.btn { border: 1px solid var(--border); background: #fff; border-radius: 6px; padding: 6px 12px; cursor: pointer; }
.btn.primary { background: var(--brand); border-color: var(--brand); color: #fff; }
.btn:disabled { opacity: 0.6; cursor: default; }
.link { border: none; background: none; color: var(--brand); cursor: pointer; padding: 0; }
</style>
