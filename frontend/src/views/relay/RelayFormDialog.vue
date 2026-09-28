<template>
  <div v-if="open" class="modal-mask" @click.self="close">
    <div class="modal-card">
      <header class="modal-head">
        <h3>{{ title }}</h3>
        <button class="link" type="button" @click="close">关闭</button>
      </header>

      <p v-if="target" class="modal-sub">
        {{ target.继电器编号 }} · {{ target.继电器型号 }} · {{ target.所属设备 }}
        <span v-if="target.检修日期">（上次检修日：{{ target.检修日期 }}）</span>
      </p>

      <form class="modal-form" @submit.prevent="submit">
        <template v-if="mode === 'edit'">
          <label class="form-item">
            <span>接点电阻（Ω，允许 0~0.1）</span>
            <input v-model="form.接点电阻" placeholder="例如 0.05，留空将按待复检处理" />
          </label>
          <label class="form-item">
            <span>检修周期</span>
            <input v-model="form.检修周期" placeholder="例如 6个月 / 12个月" />
          </label>
          <label class="form-item">
            <span>下次检修日<em>*</em></span>
            <input v-model="form.下次检修日" type="date" required />
            <small>不允许早于上次检修日</small>
          </label>
        </template>

        <template v-else-if="mode === 'maintenance'">
          <label class="form-item">
            <span>本次检修日期<em>*</em></span>
            <input v-model="form.检修日期" type="date" required />
          </label>
          <label class="form-item">
            <span>接点电阻（Ω，允许 0~0.1）</span>
            <input v-model="form.接点电阻" placeholder="留空或越界将按待复检处理" />
          </label>
          <label class="form-item">
            <span>下次检修日</span>
            <input v-model="form.下次检修日" type="date" />
            <small>不填时可勾选按检修周期顺延；早于本次日期无法保存</small>
          </label>
          <label class="form-check">
            <input v-model="rollover" type="checkbox" :disabled="!supportsCycle" />
            <span>按检修周期（{{ target?.检修周期 || '未配置' }}）自动顺延下次检修日</span>
          </label>
          <label class="form-item">
            <span>备注</span>
            <input v-model="form.备注" placeholder="检修情况说明（可选）" />
          </label>
        </template>

        <template v-else>
          <label class="form-item">
            <span>下次检修日<em>*</em></span>
            <input v-model="form.下次检修日" type="date" required />
            <small>同一台继电器重复安排时，以最近一次提交为准</small>
          </label>
          <label class="form-item">
            <span>备注</span>
            <input v-model="form.备注" placeholder="排期说明（可选）" />
          </label>
        </template>

        <p v-if="serverError" class="form-error">{{ serverError }}</p>

        <footer class="modal-foot">
          <button class="btn ghost" type="button" @click="close">取消</button>
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '保存' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import type { RelayRow } from './types'

export type DialogMode = 'edit' | 'maintenance' | 'schedule'

const props = defineProps<{
  open: boolean
  mode: DialogMode
  target: RelayRow | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submitted', values: Record<string, string>): void
}>()

const titles: Record<DialogMode, string> = {
  edit: '补录台账 / 下次检修日',
  maintenance: '登记检修记录',
  schedule: '安排下次检修',
}
const title = computed(() => titles[props.mode])

const form = reactive<Record<string, string>>({
  接点电阻: '',
  检修周期: '',
  检修日期: '',
  下次检修日: '',
  备注: '',
})
const rollover = ref(false)
const submitting = ref(false)
const serverError = ref('')

const supportsCycle = computed(() => {
  const text = props.target?.检修周期
  return Boolean(text && /\d/.test(text))
})

watch(() => props.open, (open) => {
  if (!open || !props.target) return
  serverError.value = ''
  rollover.value = false
  form.接点电阻 = props.target.接点电阻 ?? ''
  form.检修周期 = props.target.检修周期 ?? ''
  form.检修日期 = ''
  form.下次检修日 = props.target.下次检修日 ?? ''
  form.备注 = ''
})

function close() {
  if (!submitting.value) emit('close')
}

function submit() {
  serverError.value = ''
  const values: Record<string, string> = {}
  if (props.mode === 'edit') {
    values.接点电阻 = form.接点电阻.trim()
    values.检修周期 = form.检修周期.trim()
    values.下次检修日 = form.下次检修日.trim()
  } else if (props.mode === 'maintenance') {
    if (!form.检修日期) {
      serverError.value = '请填写本次检修日期'
      return
    }
    values.检修日期 = form.检修日期
    values.接点电阻 = form.接点电阻.trim()
    values.下次检修日 = form.下次检修日.trim()
    values.备注 = form.备注.trim()
    values.按周期顺延 = rollover.value ? '1' : ''
  } else {
    if (!form.下次检修日) {
      serverError.value = '请选择下次检修日'
      return
    }
    values.下次检修日 = form.下次检修日
    values.备注 = form.备注.trim()
  }
  submitting.value = true
  emit('submitted', values)
}

function stopLoading() {
  submitting.value = false
}

function fail(message: string) {
  submitting.value = false
  serverError.value = message
}

defineExpose({ stopLoading, fail })
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
  width: 460px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-sub { margin: 8px 0 12px; font-size: 12px; color: var(--muted); }
.modal-form { display: flex; flex-direction: column; gap: 10px; }
.form-item { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.form-item em { color: #b42318; font-style: normal; }
.form-item small { color: var(--muted); font-size: 11px; }
.form-item input, .form-check span { font-size: 13px; }
.form-check { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #344054; }
.form-error { margin: 0; font-size: 12px; color: #b42318; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
</style>
