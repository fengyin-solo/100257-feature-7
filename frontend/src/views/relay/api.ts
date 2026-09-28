import { request } from '@/api/client'
import type { ActionResponse, RelayPage, RelayRow } from './types'

const ENDPOINT = '/api/relay'

export interface ListParams {
  keyword?: string
  conclusion?: string
  page?: number
  size?: number
}

/** 把网络中断、服务异常与业务校验失败统一翻译成可读原因，供重试入口展示。 */
export async function explainFailure(response: Response): Promise<string> {
  let detail = ''
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    detail = payload.detail ?? payload.message ?? ''
  } catch {
    detail = ''
  }
  if (response.status === 404) {
    return `数据不存在或已归档（404）${detail ? `：${detail}` : ''}`
  }
  if (response.status >= 500) {
    return `服务暂时不可用（${response.status}），可能是后端中断或重启中${detail ? `：${detail}` : ''}`
  }
  if (response.status >= 400) {
    return `请求未被接受（${response.status}）${detail ? `：${detail}` : ''}`
  }
  return detail || '数据读取失败'
}

export async function fetchRelayList(params: ListParams = {}): Promise<RelayPage> {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.conclusion) query.set('conclusion', params.conclusion)
  query.set('page', String(params.page ?? 1))
  query.set('size', String(params.size ?? 20))
  const response = await request(`${ENDPOINT}?${query.toString()}`)
  if (!response.ok) {
    throw new Error(await explainFailure(response))
  }
  return (await response.json()) as RelayPage
}

export async function fetchRelayDetail(id: number): Promise<RelayRow> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) {
    throw new Error(await explainFailure(response))
  }
  return (await response.json()) as RelayRow
}

export async function submitRelayAction(
  path: string,
  values: Record<string, string>,
  method: 'POST' | 'PUT' = 'POST',
): Promise<ActionResponse> {
  const response = await request(path, {
    method,
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    const reason = await explainFailure(response)
    return { ok: false, message: reason, entry: null }
  }
  return (await response.json()) as ActionResponse
}

export async function updateRelay(id: number, values: Record<string, string>): Promise<ActionResponse> {
  const response = await request(`${ENDPOINT}/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    return { ok: false, message: await explainFailure(response), entry: null }
  }
  return (await response.json()) as ActionResponse
}

export function schedulePath(id: number): string {
  return `${ENDPOINT}/${id}/schedule`
}

export function maintenancePath(id: number): string {
  return `${ENDPOINT}/${id}/maintenance`
}

export function statusActionPath(id: number): string {
  return `${ENDPOINT}/${id}/actions`
}
