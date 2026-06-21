'use client';
import Card from 'components/card';
import MiniStatistics from 'components/card/MiniStatistics';
import LineAreaChart from 'components/charts/LineAreaChart';
import PieChart from 'components/charts/PieChart';
import DateRangeFilter from 'components/invoices/DateRangeFilter';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { MdAttachMoney, MdReceiptLong, MdRequestQuote } from 'react-icons/md';
import { DateRange, EMPTY_RANGE, isRangeActive } from 'lib/dateFilter';
import { Stats, getStats } from 'lib/stats';

const yuan = (n: number) =>
  `¥${n.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
// Horizon 品牌色板（饼图分类，Top-N 合并后扇区数 ≤ 色板长度，不撞色）
const PALETTE = ['#4318FF', '#6AD2FF', '#05CD99', '#FFB547', '#EE5D50', '#707EAE'];
const TOP_N = 6;

const FUNNEL: { key: string; label: string; ring: string; dot: string }[] = [
  { key: 'unreimbursed', label: '待报销', ring: 'border-red-100 dark:border-red-500/20', dot: 'bg-red-500' },
  { key: 'submitted', label: '报销中', ring: 'border-amber-100 dark:border-amber-500/20', dot: 'bg-amber-500' },
  { key: 'reimbursed', label: '已到账', ring: 'border-green-100 dark:border-green-500/20', dot: 'bg-green-500' },
];

export default function AnalyticsPage() {
  const [range, setRange] = useState<DateRange>(EMPTY_RANGE);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    getStats(range)
      .then((s) => active && setStats(s))
      .catch(() => active && setError(true))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [range]);

  const charts = useMemo(() => {
    if (!stats) return null;
    // 饼图：金额前 N 类，其余并入「其他」，避免 6 色板撞色 + 图例过长
    const top = stats.by_category.slice(0, TOP_N);
    const restAmount = stats.by_category
      .slice(TOP_N)
      .reduce((s, c) => s + c.amount, 0);
    const pieLabels = top.map((c) => c.category);
    const pieSeries = top.map((c) => c.amount);
    if (restAmount > 0) {
      pieLabels.push('其他');
      pieSeries.push(restAmount);
    }
    const pieOptions = {
      labels: pieLabels,
      colors: PALETTE,
      legend: { position: 'bottom', labels: { colors: '#A3AED0' } },
      dataLabels: { enabled: false },
      stroke: { width: 0 },
      tooltip: { theme: 'dark', y: { formatter: (v: number) => yuan(v) } },
    };

    // 月度趋势：月份已由后端连续补零，等距类目轴不再失真
    const areaSeries = [{ name: '金额', data: stats.by_month.map((m) => m.amount) }];
    const areaOptions = {
      chart: { toolbar: { show: false } },
      colors: ['#4318FF'],
      stroke: { curve: 'smooth' },
      dataLabels: { enabled: false },
      tooltip: { theme: 'dark', y: { formatter: (v: number) => yuan(v) } },
      xaxis: {
        categories: stats.by_month.map((m) => m.month),
        labels: { style: { colors: '#A3AED0', fontSize: '12px' } },
        axisBorder: { show: false },
        axisTicks: { show: false },
      },
      yaxis: {
        labels: { formatter: (v: number) => yuan(v), style: { colors: '#A3AED0' } },
      },
      legend: { show: false },
      grid: { show: false },
    };

    return {
      pieSeries,
      pieOptions,
      areaSeries,
      areaOptions,
      hasPie: pieSeries.length > 0,
      hasArea: areaSeries[0].data.length > 0,
    };
  }, [stats]);

  const avg = stats && stats.count > 0 ? stats.total / stats.count : 0;
  const rangeLabel = isRangeActive(range)
    ? `${range.from ?? '…'} ~ ${range.to ?? '…'}`
    : '全部时间';

  return (
    <div className="mt-3 flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-navy-700 dark:text-white">
            消费分析
          </h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            统计区间：{rangeLabel} · 仅含已识别金额的发票
          </p>
        </div>
        <DateRangeFilter range={range} onChange={setRange} />
      </div>

      {error ? (
        <Card extra="p-6">
          <p className="text-sm text-red-500">加载失败，请重试。</p>
          <button
            type="button"
            onClick={() => setRange({ ...range })}
            className="mt-3 self-start rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 dark:bg-brand-400"
          >
            重试
          </button>
        </Card>
      ) : loading ? (
        <Card extra="p-6">
          <p className="text-sm text-gray-400">加载中…</p>
        </Card>
      ) : !stats || stats.count === 0 ? (
        <Card extra="p-10 text-center">
          <p className="text-base font-medium text-navy-700 dark:text-white">
            该区间还没有发票数据
          </p>
          <p className="mt-1 text-sm text-gray-500">
            换个时间区间，或先去上传 / 收集发票。
          </p>
          <Link
            href="/admin/dashboard"
            className="mt-4 inline-block rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 dark:bg-brand-400"
          >
            去上传发票
          </Link>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <MiniStatistics
              name="区间总消费"
              value={yuan(stats.total)}
              icon={<MdAttachMoney />}
              iconBg="bg-brand-50 text-brand-500 dark:bg-brand-500/10"
            />
            <MiniStatistics
              name="发票张数"
              value={`${stats.count} 张`}
              icon={<MdReceiptLong />}
              iconBg="bg-brand-50 text-brand-500 dark:bg-brand-500/10"
            />
            <MiniStatistics
              name="笔均金额"
              value={yuan(avg)}
              icon={<MdRequestQuote />}
              iconBg="bg-green-50 text-green-500 dark:bg-green-500/10"
            />
          </div>

          {/* 报销漏斗：未报 / 报销中 / 已到账 金额 + 张数，点卡片去发票列表 */}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            {FUNNEL.map((f) => {
              const b = stats.by_reimbursement[f.key] ?? { amount: 0, count: 0 };
              return (
                <Link key={f.key} href="/admin/invoices">
                  <Card extra={`border p-5 transition hover:shadow-xl ${f.ring}`}>
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${f.dot}`} />
                      <span className="text-sm text-gray-600 dark:text-gray-300">
                        {f.label}
                      </span>
                    </div>
                    <p className="mt-2 text-xl font-bold text-navy-700 dark:text-white">
                      {yuan(b.amount)}
                    </p>
                    <p className="text-xs text-gray-400">{b.count} 张</p>
                  </Card>
                </Link>
              );
            })}
          </div>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card extra="p-6">
              <h2 className="text-lg font-bold text-navy-700 dark:text-white">
                消费分类占比
              </h2>
              {charts?.hasPie ? (
                <div className="mt-6 h-72">
                  <PieChart
                    chartData={charts.pieSeries}
                    chartOptions={charts.pieOptions}
                  />
                </div>
              ) : (
                <p className="mt-6 text-sm text-gray-400">暂无数据</p>
              )}
            </Card>
            <Card extra="p-6">
              <h2 className="text-lg font-bold text-navy-700 dark:text-white">
                月度消费趋势
              </h2>
              {charts?.hasArea ? (
                <div className="mt-6 h-72">
                  <LineAreaChart
                    chartData={charts.areaSeries}
                    chartOptions={charts.areaOptions}
                  />
                </div>
              ) : (
                <p className="mt-6 text-sm text-gray-400">暂无数据</p>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
