<template>
  <section class="page" data-module="relay">
    <header class="page-head">
      <div>
        <h2>继电器检修管理</h2>
        <p class="page-desc">
          围绕继电器编号、型号、接点电阻、检修周期与检修日期做台账维护；
          结论同时由检修周期与上次检修日推算，列表与明细口径一致。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出继电器检修清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article
        v-for="item in statCards"
        :key="item.label"
        class="stat-card stat-clickable"
        :class="{ 'stat-active': filters.conclusion === item.label }"
        @click="toggleConclusion(item.label)"
      >
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>继电器编号</span>
        <input v-model="filters.keyword" placeholder="按继电器编号检索" />
      </label>
      <label class="filter-item">
        <span>检修结论</span>
        <select v-model="filters.conclusion">
          <option value="">全部结论</option>
          <option v-for="label in conclusionLabels" :key="label" :value="label">{{ label }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <ErrorBlock
      v-if="loadError"
      :reason="loadError"
      :loading="loading"
      @retry="reload"
    />

    <table v-else class="data-table">
      <thead>
        <tr>
          <th>继电器编号</th>
          <th>继电器型号</th>
          <th>所属设备</th>
          <th>接点电阻(Ω)</th>
          <th>检修周期</th>
          <th>上次检修日</th>
          <th>下次检修日</th>
          <th>检修结论</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-clickable': true }" @click="openDetail(row.id)">
          <td>{{ row.继电器编号 }}</td>
          <td>{{ row.继电器型号 }}</td>
          <td>{{ row.所属设备 }}</td>
          <td>
            <span :class="{ 'cell-warn': row.conclusion.flags.recheck }">
              {{ row.接点电阻 === null || row.接点电阻 === '' ? '未填写' : row.接点电阻 }}
            </span>
          </td>
          <td>{{ row.检修周期 || '—' }}</td>
          <td>{{ row.检修日期 || '—' }}</td>
          <td>
            <span v-if="row.下次检修日">{{ row.下次检修日 }}</span>
            <span v-else class="tag-unscheduled">未排检修</span>
          </td>
          <td @click.stop>
            <ConclusionBadge :conclusion="row.conclusion" />
          </td>
          <td class="row-actions" @click.stop>
            <button class="link" type="button" @click="openDialog('edit', row)">补录/修改</button>
            <button class="link" type="button" @click="openDialog('maintenance', row)">登记检修</button>
            <button class="link" type="button" @click="openDialog('schedule', row)">安排检修</button>
            <RouterLink class="link" :to="`/relay/${row.id}`">明细</RouterLink>
          </td>
        </tr>
        <tr v-if="!loading && !rows.length">
          <td colspan="9" class="empty-state">
            当前筛选条件下没有继电器记录，可调整结论筛选或重置条件后重试
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条继电器检修记录</span>
      <span v-if="actionMessage" :class="actionOk ? 'ok-text' : 'error-text'">{{ actionMessage }}</span>
    </footer>

    <RelayFormDialog
      ref="dialogRef"
      :open="dialog.open"
      :mode="dialog.mode"
      :target="dialog.target"
      @close="dialog.open = false"
      @submitted="handleSubmit"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import ConclusionBadge from './ConclusionBadge.vue'
import ErrorBlock from './ErrorBlock.vue'
import RelayFormDialog, { type DialogMode } from './RelayFormDialog.vue'
import {
  fetchRelayList,
  maintenancePath,
  schedulePath,
  submitRelayAction,
  updateRelay,
} from './api'
import { CONCLUSION_LABELS as labels } from './types'
import type { RelayRow } from './types'

const router = useRouter()
const conclusionLabels = [...labels]

const rows = ref<RelayRow[]>([])
const total = ref(0)
const summary = ref<Record<string, number>>({})
const loading = ref(false)
const loadError = ref('')
const actionMessage = ref('')
const actionOk = ref(true)

const filters = reactive<{ keyword: string; conclusion: string }>({ keyword: '', conclusion: '' })

const statCards = computed(() => conclusionLabels.map((label) => ({
  label,
  value: summary.value[label] ?? 0,
})))

const dialog = reactive<{ open: boolean; mode: DialogMode; target: RelayRow | null }>({
  open: false,
  mode: 'edit',
  target: null,
})
const dialogRef = ref<InstanceType<typeof RelayFormDialog> | null>(null)

function toggleConclusion(label: string) {
  filters.conclusion = filters.conclusion === label ? '' : label
  void reload()
}

function resetFilters() {
  filters.keyword = ''
  filters.conclusion = ''
  void reload()
}

function exportRows() {
  window.open('/api/relay/export/all', '_blank')
}

function openDetail(id: number) {
  void router.push(`/relay/${id}`)
}

function openDialog(mode: DialogMode, row: RelayRow) {
  actionMessage.value = ''
  dialog.mode = mode
  dialog.target = row
  dialog.open = true
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const page = await fetchRelayList({
      keyword: filters.keyword.trim() || undefined,
      conclusion: filters.conclusion || undefined,
    })
    rows.value = page.items
    total.value = page.total
    summary.value = page.summary ?? {}
  } catch (error) {
    // 失败时保留已有数据不强行清空，但页面主体给出重试入口与原因
    rows.value = []
    loadError.value = error instanceof Error ? error.message : '继电器列表读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function handleSubmit(values: Record<string, string>) {
  if (!dialog.target) return
  actionMessage.value = ''
  const id = dialog.target.id
  let result
  if (dialog.mode === 'edit') {
    result = await updateRelay(id, values)
  } else if (dialog.mode === 'maintenance') {
    result = await submitRelayAction(maintenancePath(id), values)
  } else {
    result = await submitRelayAction(schedulePath(id), values)
  }
  if (result.ok) {
    actionOk.value = true
    actionMessage.value = result.message
    dialog.open = false
    dialogRef.value?.stopLoading()
    await reload()
  } else {
    actionOk.value = false
    actionMessage.value = ''
    dialogRef.value?.fail(result.message)
  }
}

onMounted(reload)
</script>

<style scoped>
.stat-clickable { cursor: pointer; }
.stat-clickable:hover { border-color: var(--brand); }
.stat-active { border-color: var(--brand); box-shadow: 0 0 0 1px var(--brand); }
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
tr.row-clickable { cursor: pointer; }
.ok-text { color: #067647; }
.filter-item select { font-size: 13px; padding: 4px 6px; }
</style>
