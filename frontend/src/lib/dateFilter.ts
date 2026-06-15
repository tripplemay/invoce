/** 发票按开票日期(issue_date)范围筛选的纯逻辑（与 UI 解耦，便于推理/测试）。
 *  issue_date 是 'YYYY-MM-DD' 字符串，按字典序比较即可正确判范围，无需解析、无时区坑。 */
import { Invoice } from './types';

/** 闭区间日期范围（含端点）。某端为 null = 该端开放；两端皆 null = 不限（全部时间）。 */
export interface DateRange {
  from: string | null; // 'YYYY-MM-DD'
  to: string | null;
}

export const EMPTY_RANGE: DateRange = { from: null, to: null };

export type DatePreset = 'thisMonth' | 'lastMonth' | 'thisQuarter' | 'thisYear' | 'all';

export const PRESET_LABELS: Record<DatePreset, string> = {
  thisMonth: '本月',
  lastMonth: '上月',
  thisQuarter: '本季度',
  thisYear: '本年',
  all: '全部时间',
};

const pad = (n: number): string => String(n).padStart(2, '0');

/** 本地 Date → 'YYYY-MM-DD'（用本地年月日，避免 toISOString 的 UTC 偏移导致日期 ±1）。 */
export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** 'YYYY-MM-DD' → 本地 Date（用于喂日历组件）；空值返回 null。 */
export function fromISODate(s: string | null): Date | null {
  if (!s) return null;
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

/** 计算预设区间（today 可注入便于测试）。月/季/年取完整自然区间的首末日。 */
export function presetRange(preset: DatePreset, today: Date = new Date()): DateRange {
  const y = today.getFullYear();
  const m = today.getMonth();
  switch (preset) {
    case 'thisMonth':
      return { from: toISODate(new Date(y, m, 1)), to: toISODate(new Date(y, m + 1, 0)) };
    case 'lastMonth':
      return { from: toISODate(new Date(y, m - 1, 1)), to: toISODate(new Date(y, m, 0)) };
    case 'thisQuarter': {
      const q = Math.floor(m / 3);
      return { from: toISODate(new Date(y, q * 3, 1)), to: toISODate(new Date(y, q * 3 + 3, 0)) };
    }
    case 'thisYear':
      return { from: toISODate(new Date(y, 0, 1)), to: toISODate(new Date(y, 11, 31)) };
    case 'all':
    default:
      return { ...EMPTY_RANGE };
  }
}

/** 范围是否激活（任一端有值）。 */
export function isRangeActive(range: DateRange): boolean {
  return Boolean(range.from || range.to);
}

/** 规范化：from > to 时自动交换两端。 */
export function normalizeRange(range: DateRange): DateRange {
  const { from, to } = range;
  if (from && to && from > to) return { from: to, to: from };
  return range;
}

/** 某发票开票日期是否落在范围内（字符串字典序比较）。
 *  范围未激活 → 全部命中；开票日期为空（未抽取）→ 范围激活时不命中。 */
export function isInDateRange(issueDate: string | null, range: DateRange): boolean {
  if (!isRangeActive(range)) return true;
  if (!issueDate) return false;
  if (range.from && issueDate < range.from) return false;
  if (range.to && issueDate > range.to) return false;
  return true;
}

/** 价税合计求和（total_amount 为 string|null）。 */
export function sumAmount(invoices: Invoice[]): number {
  return invoices.reduce((s, i) => s + (i.total_amount ? Number(i.total_amount) : 0), 0);
}
