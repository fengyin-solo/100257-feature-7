<template>
  <section class="page" data-module="relay">
    <header class="page-head">
      <div>
        <h2>继电器检修管理</h2>
        <p class="page-desc">
          围绕继电器编号、检修周期、上次检修日、接点电阻维护台账；结论同时看周期与上次检修日，
          没排检修、待复检、已到期等边界情况单独标出来。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出继电器检修清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card" :class="{ active: filters.conclusion === item.code }">
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
        <span>继电器状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in techStatuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>检修结论</span>
        <select v-model="filters.conclusion">
          <option value="">全部</option>
          <option v-for="code in conclusionOrder" :key="code" :value="code">
            {{ conclusionLabels[code] }}
          </option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <ErrorPanel
      v-if="errorMessage && !rows.length"
      title="继电器列表加载失败"
      :reason="errorMessage"
      :loading="loading"
      @retry="reload"
    />

    <table v-else class="data-table">
      <thead>
        <tr>
          <th>继电器编号</th>
          <th>继电器型号</th>
          <th>所属设备</th>
          <th>接点电阻</th>
          <th>检修周期</th>
          <th>上次检修日</th>
          <th>下次检修日</th>
          <th>继电器状态</th>
          <th>检修结论</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td><RouterLink class="link" :to="`/relay/${row.id}`">{{ row.继电器编号 }}</RouterLink></td>
          <td>{{ row.继电器型号 || '—' }}</td>
          <td>{{ row.所属设备 || '—' }}</td>
          <td :class="{ 'cell-warn': !row.conclusion.resistance_ok }">
            {{ row.接点电阻 || '（空）' }}
          </td>
          <td>{{ row.检修周期 || '—' }}</td>
          <td>{{ row.上次检修日 || '—' }}</td>
          <td :class="nextDateCellClass(row)">
            {{ row.下次检修日 || '未排检修' }}
          </td>
          <td>{{ row.继电器状态 }}</td>
          <td><ConclusionBadge :conclusion="row.conclusion" /></td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDialog('schedule', row)">安排检修</button>
            <button class="link" type="button" @click="openDialog('inspect', row)">登记检修</button>
            <RouterLink class="link" :to="`/relay/${row.id}`">明细</RouterLink>
          </td>
        </tr>
        <tr v-if="!loading && !rows.length">
          <td colspan="10" class="empty-state">没有符合条件的继电器检修记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条继电器检修记录</span>
      <span v-if="errorMessage" class="error-text">
        {{ errorMessage }}
        <button class="link retry-link" type="button" @click="reload">重试</button>
      </span>
    </footer>

    <ActionDialog
      v-if="dialog"
      :mode="dialog.mode"
      :row="dialog.row"
      @close="dialog = null"
      @saved="onSaved"
    />

    <p v-if="savedToast" class="saved-toast">{{ savedToast }}，检修历史已保留，列表已刷新</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  fetchRelayPage,
  fetchRelaySummary,
  type ConclusionCode,
  type RelayRow,
  type SummaryPayload,
} from './api'
import ActionDialog from './ActionDialog.vue'
import ConclusionBadge from './ConclusionBadge.vue'
import ErrorPanel from './ErrorPanel.vue'

const techStatuses = ['特性合格', '特性偏移', '接点氧化', '已报废']
const conclusionOrder: ConclusionCode[] = ['overdue', 'unscheduled', 'reinspect', 'upcoming', 'scrapped']

const rows = ref<RelayRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const loading = ref(false)
const summary = ref<SummaryPayload | null>(null)

const filters = reactive({
  keyword: '',
  status: '',
  conclusion: '' as ConclusionCode | '',
})

const dialog = ref<{ mode: 'schedule' | 'inspect'; row: RelayRow } | null>(null)
const savedToast = ref('')

const conclusionLabels = computed<Record<ConclusionCode, string>>(
  () =>
    summary.value?.labels ?? {
      overdue: '已到期',
      unscheduled: '未排检修',
      reinspect: '待复检',
      upcoming: '未到期',
      scrapped: '已报废',
    },
)

const statCards = computed(() => [
  { label: '继电器总数', value: summary.value?.counts.total ?? rows.value.length, code: '' as const },
  { label: '已到期', value: summary.value?.counts.overdue ?? 0, code: 'overdue' as const },
  { label: '未排检修', value: summary.value?.counts.unscheduled ?? 0, code: 'unscheduled' as const },
  { label: '待复检', value: summary.value?.counts.reinspect ?? 0, code: 'reinspect' as const },
  { label: '未到期', value: summary.value?.counts.upcoming ?? 0, code: 'upcoming' as const },
  { label: '已报废', value: summary.value?.counts.scrapped ?? 0, code: 'scrapped' as const },
])

function nextDateCellClass(row: RelayRow): string {
  if (!row.下次检修日) return 'cell-unscheduled'
  return ''
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  filters.conclusion = ''
  void reload()
}

function exportRows() {
  window.open('/api/relay/export', '_blank')
}

function openDialog(mode: 'schedule' | 'inspect', row: RelayRow) {
  errorMessage.value = ''
  dialog.value = { mode, row }
}

async function onSaved(message: string) {
  dialog.value = null
  savedToast.value = message
  window.setTimeout(() => {
    savedToast.value = ''
  }, 4000)
  await reload()
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await fetchRelayPage({
      keyword: filters.keyword.trim(),
      status: filters.status,
      conclusion: filters.conclusion,
    })
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '继电器检修列表读取失败'
  } finally {
    loading.value = false
  }
  // 统计卡片独立加载：失败不阻断列表，卡片退回展示 0
  try {
    summary.value = await fetchRelaySummary()
  } catch {
    summary.value = null
  }
}

onMounted(reload)
</script>

<style scoped>
.cell-warn { color: #c4320a; }
.cell-unscheduled { color: #b54708; font-weight: 600; }
.stat-card { cursor: pointer; }
.stat-card.active { border-color: var(--brand); box-shadow: 0 0 0 1px var(--brand); }
.retry-link { margin-left: 6px; }
.filter-item select { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; min-width: 120px; }
.page-actions { display: flex; gap: 8px; }
.saved-toast {
  position: fixed;
  right: 20px;
  bottom: 20px;
  margin: 0;
  background: #ecfdf3;
  border: 1px solid #abefc6;
  color: #027a48;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  z-index: 60;
}
</style>
