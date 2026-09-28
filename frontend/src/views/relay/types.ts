/** 继电器检修：列表与明细共用后端返回的结论口径，禁止在前端另算一套。 */
export interface ConclusionFlags {
  scrapped: boolean
  recheck: boolean
  unscheduled: boolean
  overdue: boolean
  due_soon: boolean
}

export interface Conclusion {
  label: string
  reasons: string[]
  due_date: string | null
  cycle_due_date?: string | null
  next_date: string | null
  days_left: number | null
  flags: ConclusionFlags
}

export interface MaintenanceHistoryItem {
  检修日期: string
  接点电阻?: string | null
  电气特性?: string | null
  备注?: string
}

export interface ScheduleRecord {
  下次检修日: string
  原排定日期?: string | null
  安排时间: string
  备注?: string
}

export interface RelayRow {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  继电器编号: string
  继电器型号: string
  所属设备: string
  电气特性?: string | null
  接点电阻?: string | null
  检修周期?: string | null
  检修日期?: string | null
  下次检修日?: string | null
  继电器状态?: string | null
  检修历史?: MaintenanceHistoryItem[]
  检修安排记录?: ScheduleRecord[]
  conclusion: Conclusion
}

export interface RelayPage {
  items: RelayRow[]
  total: number
  page: number
  size: number
  summary: Record<string, number> | null
}

export interface ActionResponse {
  ok: boolean
  message: string
  entry: RelayRow | null
}

export const CONCLUSION_LABELS = ['正常', '即将到期', '已到期', '未排检修', '待复检', '已报废'] as const
