'use client';
import { AreaChart, DonutChart } from '@tremor/react';
import Card from 'components/card';
import MiniStatistics from 'components/card/MiniStatistics';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { MdAttachMoney, MdPendingActions, MdTrendingUp } from 'react-icons/md';
import { listInvoices } from 'lib/invoices';
import { Invoice } from 'lib/types';

const yuan = (n: number) =>
  `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
const amount = (i: Invoice) => parseFloat(i.total_amount ?? '0') || 0;

export default function AnalyticsPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  useEffect(() => {
    listInvoices()
      .then(setInvoices)
      .catch(() => undefined);
  }, []);

  const { total, unreimbursed, maxSingle, byCategory, byMonth } =
    useMemo(() => {
      const withAmount = invoices.filter((i) => i.total_amount != null);
      const total = withAmount.reduce((s, i) => s + amount(i), 0);
      const unreimbursed = withAmount
        .filter((i) => i.reimbursement_status === 'unreimbursed')
        .reduce((s, i) => s + amount(i), 0);
      const maxSingle = withAmount.reduce((m, i) => Math.max(m, amount(i)), 0);

      const catMap: Record<string, number> = {};
      for (const i of withAmount) {
        const c = i.category ?? '其他';
        catMap[c] = (catMap[c] ?? 0) + amount(i);
      }
      const byCategory = Object.entries(catMap).map(([name, 金额]) => ({
        name,
        金额,
      }));

      const monthMap: Record<string, number> = {};
      for (const i of withAmount) {
        if (!i.issue_date) continue;
        const m = i.issue_date.slice(0, 7);
        monthMap[m] = (monthMap[m] ?? 0) + amount(i);
      }
      const byMonth = Object.entries(monthMap)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([month, 金额]) => ({ month, 金额 }));

      return { total, unreimbursed, maxSingle, byCategory, byMonth };
    }, [invoices]);

  return (
    <div className="mt-3 flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <MiniStatistics
          name="区间总消费"
          value={yuan(total)}
          icon={<MdAttachMoney />}
          iconBg="bg-brand-50 text-brand-500 dark:bg-brand-500/10"
        />
        <Link href="/admin/invoices">
          <MiniStatistics
            name="待报销总额"
            value={yuan(unreimbursed)}
            icon={<MdPendingActions />}
            iconBg="bg-red-50 text-red-500 dark:bg-red-500/10"
          />
        </Link>
        <MiniStatistics
          name="最大单笔支出"
          value={yuan(maxSingle)}
          icon={<MdTrendingUp />}
          iconBg="bg-green-50 text-green-500 dark:bg-green-500/10"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card extra="p-6">
          <h2 className="text-lg font-bold text-navy-700 dark:text-white">
            消费分类占比
          </h2>
          {byCategory.length === 0 ? (
            <p className="mt-6 text-sm text-gray-400">暂无数据</p>
          ) : (
            <DonutChart
              className="mt-6 h-72"
              data={byCategory}
              category="金额"
              index="name"
              valueFormatter={yuan}
              colors={['indigo', 'cyan', 'emerald', 'amber', 'rose', 'violet']}
            />
          )}
        </Card>
        <Card extra="p-6">
          <h2 className="text-lg font-bold text-navy-700 dark:text-white">
            月度消费趋势
          </h2>
          {byMonth.length === 0 ? (
            <p className="mt-6 text-sm text-gray-400">暂无数据</p>
          ) : (
            <AreaChart
              className="mt-6 h-72"
              data={byMonth}
              index="month"
              categories={['金额']}
              valueFormatter={yuan}
              colors={['indigo']}
            />
          )}
        </Card>
      </div>
    </div>
  );
}
