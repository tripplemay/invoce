/** 消费分析聚合 API（服务端 SQL 聚合，前端只负责画图）。 */
import { api } from './auth';
import { DateRange } from './dateFilter';

export interface StatBucket {
  amount: number;
  count: number;
}
export interface CategoryStat {
  category: string;
  amount: number;
  count: number;
}
export interface MonthStat {
  month: string; // YYYY-MM
  amount: number;
  count: number;
}
export interface Stats {
  total: number;
  count: number;
  by_reimbursement: Record<string, StatBucket>;
  by_category: CategoryStat[];
  by_month: MonthStat[];
}

export function getStats(range: DateRange): Promise<Stats> {
  const p = new URLSearchParams();
  if (range.from) p.set('date_from', range.from);
  if (range.to) p.set('date_to', range.to);
  const q = p.toString();
  return api.get<Stats>(`/invoices/stats${q ? `?${q}` : ''}`);
}
