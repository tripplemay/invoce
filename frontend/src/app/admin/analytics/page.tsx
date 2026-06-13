'use client';
import { AreaChart, DonutChart } from '@tremor/react';
import Card from 'components/card';
import Link from 'next/link';
import { IconType } from 'react-icons';
import { MdAttachMoney, MdPendingActions, MdTrendingUp } from 'react-icons/md';
import { MOCK_CATEGORY, MOCK_STATS, MOCK_TREND } from 'lib/mock';

const yuan = (n: number) => `¥${n.toLocaleString('zh-CN')}`;

function MiniStat({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: IconType;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <Card extra="flex items-center gap-4 p-5">
      <div className={`flex h-14 w-14 items-center justify-center rounded-full ${accent}`}>
        <Icon className="text-2xl" />
      </div>
      <div>
        <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
        <p className="text-2xl font-bold text-navy-700 dark:text-white">{value}</p>
      </div>
    </Card>
  );
}

export default function AnalyticsPage() {
  return (
    <div className="mt-3 flex flex-col gap-5">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        <MiniStat
          icon={MdAttachMoney}
          label="区间总消费"
          value={yuan(MOCK_STATS.total)}
          accent="bg-brand-50 text-brand-500 dark:bg-brand-500/10"
        />
        <Link href="/admin/invoices">
          <MiniStat
            icon={MdPendingActions}
            label="待报销总额"
            value={yuan(MOCK_STATS.unreimbursed)}
            accent="bg-red-50 text-red-500 dark:bg-red-500/10"
          />
        </Link>
        <MiniStat
          icon={MdTrendingUp}
          label="最大单笔支出"
          value={yuan(MOCK_STATS.maxSingle)}
          accent="bg-green-50 text-green-500 dark:bg-green-500/10"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card extra="p-6">
          <h2 className="text-lg font-bold text-navy-700 dark:text-white">消费分类占比</h2>
          <DonutChart
            className="mt-6 h-72"
            data={MOCK_CATEGORY}
            category="金额"
            index="name"
            valueFormatter={yuan}
            colors={['indigo', 'cyan', 'emerald', 'amber']}
          />
        </Card>
        <Card extra="p-6">
          <h2 className="text-lg font-bold text-navy-700 dark:text-white">月度消费趋势</h2>
          <AreaChart
            className="mt-6 h-72"
            data={MOCK_TREND}
            index="month"
            categories={['金额']}
            valueFormatter={yuan}
            colors={['indigo']}
          />
        </Card>
      </div>
    </div>
  );
}
