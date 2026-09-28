<template>
  <section class="page detail-page" data-module="relay-detail">
    <header class="page-head">
      <div>
        <h2>继电器检修明细</h2>
        <p class="page-desc">结论由后端按检修周期、上次检修日、接点电阻与排期统一推导，与列表页保持一致。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/relay">返回列表</RouterLink>
      </div>
    </header>

    <ErrorPanel
      v-if="errorMessage && !row"
      title="继电器明细加载失败"
      :reason="errorMessage"
      :loading="loading"
      @retry="load"
    />

    <template v-else-if="row">
      <div class="detail-head">
        <div>
          <h3>{{ row.继电器编号 }} <span class="model-text">{{ row.继电器型号 }}</span></h3>
          <p class="belong-text">{{ row.所属设备 }}</p>
        </div>
        <div class="head-side">
          <ConclusionBadge :conclusion="row.conclusion" />
          <div class="head-actions">
            <button class="btn primary" type="button" @click="openDialog('schedule')">安排 / 补录检修</button>
            <button class="btn" type="button" @click="openDialog('inspect')">登记检修完成</button>
          </div>
        </div>
      </div>

      <article class="detail-card">
        <h4>台账信息</h4>
        <dl class="detail-grid">
          <div><dt>电气特性</dt><dd>{{ row.电气特性 || '—' }}</dd></div>
          <div>
            <dt>接点电阻</dt>
            <dd :class="{ 'cell-warn': !row.conclusion.resistance_ok }">
              {{ row.接点电阻 || '（空，待复检）' }}
            </dd>
          </div>
          <div><dt>检修周期</dt><dd>{{ row.检修周期 || '—' }}</dd></div>
          <div><dt>上次检修日</dt><dd>{{ row.上次检修日 || '—' }}</dd></div>
          <div>
            <dt>下次检修日</dt>
            <dd :class="row.下次检修日 ? '' : 'cell-unscheduled'">
              {{ row.下次检修日 || '未排检修' }}
            </dd>
          </div>
          <div><dt>按周期推算到期日</dt><dd>{{ row.conclusion.due_date || '无法推算（周期或上次检修日缺失）' }}</dd></div>
          <div><dt>继电器状态</dt><dd>{{ row.继电器状态 }}</dd></div>
        </dl>
      </article>

      <article class="detail-card">
        <h4>检修结论说明</h4>
        <p class="conclusion-line">
          当前结论：<ConclusionBadge :conclusion="row.conclusion" />
          <span class="conclusion-same-note">（与列表页结论为同一判定结果）</span>
        </p>
        <ul class="reason-list">
          <li v-for="(reason, index) in row.conclusion.reasons" :key="index">{{ reason }}</li>
        </ul>
      </article>

      <article class="detail-card">
        <h4>检修历史</h4>
        <p class="history-note">补录下次检修日或重复安排检修都会追加记录，原有历史保留不覆盖。</p>
        <ul class="history-list">
          <li v-for="(event, index) in row.history ?? []" :key="index" class="history-item">
            <span class="history-dot" :class="`dot-${event.type}`"></span>
            <div>
              <p class="history-title">{{ event.title }}<span class="history-time">{{ event.created_at }}</span></p>
              <p class="history-detail">{{ event.detail }}</p>
            </div>
          </li>
          <li v-if="!(row.history ?? []).length" class="empty-state">暂无检修历史记录</li>
        </ul>
      </article>
    </template>

    <p v-if="errorMessage && row" class="error-text inline-error">
      {{ errorMessage }}
      <button class="link retry-link" type="button" @click="load">重试</button>
    </p>

    <ActionDialog
      v-if="dialog && row"
      :mode="dialog"
      :row="row"
      @close="dialog = null"
      @saved="onSaved"
    />

    <p v-if="savedToast" class="saved-toast">{{ savedToast }}，检修历史已保留，明细已刷新</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchRelayDetail, type RelayRow } from './api'
import ActionDialog from './ActionDialog.vue'
import ConclusionBadge from './ConclusionBadge.vue'
import ErrorPanel from './ErrorPanel.vue'

const route = useRoute()

const row = ref<RelayRow | null>(null)
const errorMessage = ref('')
const loading = ref(false)
const dialog = ref<'schedule' | 'inspect' | null>(null)
const savedToast = ref('')

async function load() {
  const id = Number(route.params.id)
  if (!Number.isInteger(id)) {
    errorMessage.value = '继电器编号无效，请从列表页重新进入'
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    row.value = await fetchRelayDetail(id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '继电器明细读取失败'
  } finally {
    loading.value = false
  }
}

function openDialog(mode: 'schedule' | 'inspect') {
  dialog.value = mode
}

async function onSaved(message: string) {
  dialog.value = null
  savedToast.value = message
  window.setTimeout(() => {
    savedToast.value = ''
  }, 4000)
  await load()
}

onMounted(load)
</script>

<style scoped>
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.detail-head h3 { margin: 0; font-size: 18px; }
.model-text { font-size: 13px; color: var(--muted); font-weight: 400; margin-left: 8px; }
.belong-text { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
.head-side { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
.head-actions { display: flex; gap: 8px; }

.detail-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.detail-card h4 { margin: 0 0 12px; font-size: 14px; }
.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 24px;
  margin: 0;
}
.detail-grid dt { font-size: 12px; color: var(--muted); }
.detail-grid dd { margin: 2px 0 0; font-size: 13px; }
.cell-warn { color: #c4320a; }
.cell-unscheduled { color: #b54708; font-weight: 600; }

.conclusion-line { margin: 0 0 8px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.conclusion-same-note { color: var(--muted); font-size: 12px; }
.reason-list { margin: 0; padding-left: 18px; color: #344054; font-size: 13px; line-height: 1.8; }

.history-note { font-size: 12px; color: var(--muted); margin: 0 0 10px; }
.history-list { list-style: none; margin: 0; padding: 0; }
.history-item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px dashed var(--border); }
.history-item:last-child { border-bottom: none; }
.history-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 7px; background: var(--brand); flex: none; }
.dot-inspect { background: #12b76a; }
.dot-schedule { background: #f79009; }
.dot-scrap { background: #667085; }
.dot-create { background: #1f6feb; }
.history-title { margin: 0; font-size: 13px; font-weight: 600; }
.history-time { margin-left: 10px; color: var(--muted); font-weight: 400; font-size: 12px; }
.history-detail { margin: 2px 0 0; font-size: 12px; color: #475467; line-height: 1.6; }
.inline-error { margin-top: 8px; }
.retry-link { margin-left: 6px; }
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
