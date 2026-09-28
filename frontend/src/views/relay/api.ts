/** 继电器检修模块的类型、接口封装。
 *
 * 结论文案由后端统一给出（conclusion.label / reasons），列表与明细共用同一份结构，
 * 前端不再自行判断，避免两处结论不一致。
 */
import { request } from '@/api/client'

export type ConclusionCode = 'scrapped' | 'reinspect' | 'unscheduled' | 'overdue' | 'upcoming'

export interface Conclusion {
  code: ConclusionCode
  label: string
  reasons: string[]
  due_date: string | null
  resistance_ohm: number | null
  resistance_ok: boolean
}

export interface HistoryEvent {
  type: string
  title: string
  detail: string
  created_at: string
}

export interface RelayRow {
  id: number
  继电器编号: string
  继电器型号: string
  所属设备: string
  电气特性: string
  接点电阻: string
  检修周期: string
  上次检修日: string
  下次检修日: string
  继电器状态: string
  conclusion: Conclusion
  history?: HistoryEvent[]
}

export interface PagePayload {
  items: RelayRow[]
  total: number
  page: number
  size: number
}

export interface SummaryPayload {
  labels: Record<ConclusionCode, string>
  counts: Record<ConclusionCode, string> & { total: string }
}

export interface ActionPayload {
  ok: boolean
  message: string
  entry: RelayRow | null
}

export interface ListParams {
  keyword?: string
  status?: string
  conclusion?: ConclusionCode | ''
  page?: number
  size?: number
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    if (body.detail) return body.detail
  } catch {
    // 返回体不是 JSON 时退回通用说明
  }
  return `服务异常（HTTP ${response.status}），数据未能读取，请稍后重试`
}

export async function fetchRelayPage(params: ListParams): Promise<PagePayload> {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.status) query.set('status', params.status)
  if (params.conclusion) query.set('conclusion', params.conclusion)
  query.set('page', String(params.page ?? 1))
  query.set('size', String(params.size ?? 20))

  let response: Response
  try {
    response = await request(`/api/relay?${query.toString()}`)
  } catch (error) {
    // 网络中断 / 后端不可达：request() 已包了一层说明，这里点明重试入口
    throw new Error(
      `${error instanceof Error ? error.message : '请求未送达'}。可能是网络中断或检修服务暂时不可用，请点击“重试”重新加载`,
    )
  }
  if (!response.ok) {
    throw new Error(`${await readErrorMessage(response)}。请调整条件后点击“重试”`)
  }
  return (await response.json()) as PagePayload
}

export async function fetchRelaySummary(): Promise<SummaryPayload> {
  const response = await request('/api/relay/summary')
  if (!response.ok) {
    throw new Error(`统计数据读取失败（HTTP ${response.status}）`)
  }
  return (await response.json()) as SummaryPayload
}

export async function fetchRelayDetail(id: number): Promise<RelayRow> {
  let response: Response
  try {
    response = await request(`/api/relay/${id}`)
  } catch (error) {
    throw new Error(
      `${error instanceof Error ? error.message : '请求未送达'}。可能是网络中断或检修服务暂时不可用，请点击“重试”重新加载`,
    )
  }
  if (response.status === 404) {
    throw new Error(`继电器 ${id} 不存在或已归档，请返回列表确认后再进入`)
  }
  if (!response.ok) {
    throw new Error(`${await readErrorMessage(response)}。请稍后点击“重试”`)
  }
  return (await response.json()) as RelayRow
}

async function postAction(
  id: number,
  path: 'schedule' | 'inspections',
  values: Record<string, string>,
): Promise<ActionPayload> {
  const response = await request(`/api/relay/${id}/${path}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    return { ok: false, message: await readErrorMessage(response), entry: null }
  }
  return (await response.json()) as ActionPayload
}

export function scheduleInspection(id: number, nextDate: string): Promise<ActionPayload> {
  return postAction(id, 'schedule', { 下次检修日: nextDate })
}

export function saveInspectionRecord(
  id: number,
  values: { 检修日期: string; 接点电阻: string; 电气特性?: string; 继电器状态?: string },
): Promise<ActionPayload> {
  return postAction(id, 'inspections', values)
}
