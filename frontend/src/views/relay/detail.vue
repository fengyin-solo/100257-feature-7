<template>
  <section class="page" data-module="relay-detail">
    <header class="page-head">
      <div>
        <h2>继电器检修明细</h2>
        <p class="page-desc">
          结论、原因与列表页使用同一套后端口径；补录下次检修日不会清除已有检修历史。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/relay">返回列表</RouterLink>
      </div>
    </header>

    <ErrorBlock
      v-if="loadError"
      title="明细读取失败"
      :reason="loadError"
      :loading="loading"
      @retry="load"
    />

    <template v-else-if="row">
      <div class="detail-grid">
        <article class="detail-card detail-conclusion">
          <h3>检修结论</h3>
          <ConclusionBadge :conclusion="row.conclusion" show-reasons />
          <dl class="mini-meta">
            <div><dt>实际到期日</dt><dd>{{ row.conclusion.due_date || '—' }}</dd></div>
            <div><dt>周期推算到期</dt><dd>{{ row.conclusion.cycle_due_date || '—' }}</dd></div>
            <div><dt>排定下次检修</dt><dd>{{ row.conclusion.next_date || '未排检修' }}</dd></div>
            <div><dt>距到期天数</dt><dd>{{ row.conclusion.days_left === null ? '—' : row.conclusion.days_left }}</dd></div>
          </dl>
        </article>

        <article class="detail-card">
          <h3>台账信息</h3>
          <dl class="info-list">
            <div><dt>继电器编号</dt><dd>{{ row.继电器编号 }}</dd></div>
            <div><dt>继电器型号</dt><dd>{{ row.继电器型号 }}</dd></div>
            <div><dt>所属设备</dt><dd>{{ row.所属设备 }}</dd></div>
            <div><dt>电气特性</dt><dd>{{ row.电气特性 || '—' }}</dd></div>
            <div>
              <dt>接点电阻</dt>
              <dd :class="{ 'cell-warn': row.conclusion.flags.recheck }">
                {{ row.接点电阻 === null || row.接点电阻 === '' ? '未填写（待复检）' : `${row.接点电阻} Ω` }}
              </dd>
            </div>
            <div><dt>检修周期</dt><dd>{{ row.检修周期 || '—' }}</dd></div>
            <div><dt>上次检修日</dt><dd>{{ row.检修日期 || '—' }}</dd></div>
            <div>
              <dt>下次检修日</dt>
              <dd>
                <span v-if="row.下次检修日">{{ row.下次检修日 }}</span>
                <span v-else class="tag-unscheduled">未排检修</span>
              </dd>
            </div>
            <div><dt>设备状态</dt><dd>{{ row.status }}</dd></div>
          </dl>
          <div class="detail-actions">
            <button class="btn primary" type="button" :disabled="row.conclusion.flags.scrapped" @click="openDialog('edit')">补录/修改台账</button>
            <button class="btn" type="button" :disabled="row.conclusion.flags.scrapped" @click="openDialog('maintenance')">登记检修</button>
            <button class="btn" type="button" :disabled="row.conclusion.flags.scrapped" @click="openDialog('schedule')">安排检修</button>
            <button class="btn ghost" type="button" :disabled="row.conclusion.flags.scrapped" @click="runAction('记录偏移')">标记特性偏移</button>
            <button class="btn ghost danger" type="button" :disabled="row.conclusion.flags.scrapped" @click="runAction('申请报废')">申请报废</button>
          </div>
          <p v-if="actionMessage" class="action-msg" :class="actionOk ? 'ok-text' : 'error-text'">{{ actionMessage }}</p>
        </article>
      </div>

      <div class="history-grid">
        <article class="detail-card">
          <h3>检修历史（{{ history.length }} 条，补录不会清除）</h3>
          <table class="data-table inner-table">
            <thead>
              <tr><th>检修日期</th><th>接点电阻(Ω)</th><th>电气特性</th><th>备注</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in history" :key="index">
                <td>{{ item.检修日期 }}</td>
                <td>{{ item.接点电阻 || '未填写' }}</td>
                <td>{{ item.电气特性 || '—' }}</td>
                <td>{{ item.备注 || '—' }}</td>
              </tr>
              <tr v-if="!history.length">
                <td colspan="4" class="empty-state">暂无检修历史</td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="detail-card">
          <h3>检修安排记录（重复安排以最近一次为准）</h3>
          <table class="data-table inner-table">
            <thead>
              <tr><th>安排时间</th><th>排定检修日</th><th>原排定日期</th><th>备注</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in schedules" :key="index">
                <td>{{ item.安排时间 }}</td>
                <td>{{ item.下次检修日 }}</td>
                <td>{{ item.原排定日期 || '首次安排' }}</td>
                <td>{{ item.备注 || '—' }}</td>
              </tr>
              <tr v-if="!schedules.length">
                <td colspan="4" class="empty-state">暂无排期记录</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
    </template>

    <RelayFormDialog
      ref="dialogRef"
      :open="dialog.open"
      :mode="dialog.mode"
      :target="row"
      @close="dialog.open = false"
      @submitted="handleSubmit"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import ConclusionBadge from './ConclusionBadge.vue'
import ErrorBlock from './ErrorBlock.vue'
import RelayFormDialog, { type DialogMode } from './RelayFormDialog.vue'
import {
  fetchRelayDetail,
  maintenancePath,
  schedulePath,
  statusActionPath,
  submitRelayAction,
  updateRelay,
} from './api'
import type { RelayRow } from './types'

const route = useRoute()

const row = ref<RelayRow | null>(null)
const loading = ref(false)
const loadError = ref('')
const actionMessage = ref('')
const actionOk = ref(true)

const history = computed(() => row.value?.检修历史 ?? [])
const schedules = computed(() => row.value?.检修安排记录 ?? [])

const dialog = reactive<{ open: boolean; mode: DialogMode }>({ open: false, mode: 'edit' })
const dialogRef = ref<InstanceType<typeof RelayFormDialog> | null>(null)

const entryId = computed(() => Number(route.params.id))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    row.value = await fetchRelayDetail(entryId.value)
  } catch (error) {
    row.value = null
    loadError.value = error instanceof Error ? error.message : '继电器明细读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function openDialog(mode: DialogMode) {
  actionMessage.value = ''
  dialog.mode = mode
  dialog.open = true
}

async function refreshAfterAction(result: { ok: boolean; message: string; entry: RelayRow | null }) {
  if (result.ok && result.entry) {
    actionOk.value = true
    actionMessage.value = result.message
    dialog.open = false
    dialogRef.value?.stopLoading()
    // 重新拉取明细，确认检修历史完整保留
    await load()
  } else {
    actionOk.value = false
    actionMessage.value = ''
    dialogRef.value?.fail(result.message)
  }
}

async function handleSubmit(values: Record<string, string>) {
  const id = entryId.value
  if (dialog.mode === 'edit') {
    await refreshAfterAction(await updateRelay(id, values))
  } else if (dialog.mode === 'maintenance') {
    await refreshAfterAction(await submitRelayAction(maintenancePath(id), values))
  } else {
    await refreshAfterAction(await submitRelayAction(schedulePath(id), values))
  }
}

async function runAction(action: string) {
  actionMessage.value = ''
  const result = await submitRelayAction(statusActionPath(entryId.value), { action })
  if (result.ok) {
    actionOk.value = true
    actionMessage.value = result.message
    await load()
  } else {
    actionOk.value = false
    actionMessage.value = result.message
  }
}

onMounted(load)
</script>

<style scoped>
.detail-grid, .history-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.history-grid { grid-template-columns: 1fr 1fr; }
.detail-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
}
.detail-card h3 { margin: 0 0 10px; font-size: 14px; }
.info-list { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 0; }
.info-list dt, .mini-meta dt { color: var(--muted); font-size: 12px; }
.info-list dd, .mini-meta dd { margin: 2px 0 0; font-size: 13px; }
.mini-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; margin: 12px 0 0; }
.cell-warn { color: #a21caf; font-weight: 600; }
.tag-unscheduled {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  background: #eff4ff;
  color: #1d4ed8;
  border: 1px solid #b2ccff;
}
.detail-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.btn[disabled] { opacity: 0.5; cursor: not-allowed; }
.btn.danger { color: #b42318; border-color: #fda29b; }
.action-msg { margin: 10px 0 0; font-size: 12px; }
.inner-table { margin-top: 4px; }
.ok-text { color: #067647; }
@media (max-width: 960px) {
  .detail-grid, .history-grid { grid-template-columns: 1fr; }
}
</style>
