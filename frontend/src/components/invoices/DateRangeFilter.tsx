'use client';

import Calendar from 'react-calendar';
import { MdChevronLeft, MdChevronRight } from 'react-icons/md';
import Dropdown from 'components/dropdown';
import {
  DatePreset,
  DateRange,
  EMPTY_RANGE,
  PRESET_LABELS,
  fromISODate,
  isRangeActive,
  normalizeRange,
  presetRange,
  toISODate,
} from 'lib/dateFilter';

const PRESETS: DatePreset[] = [
  'thisMonth',
  'lastMonth',
  'thisQuarter',
  'thisYear',
  'all',
];

interface Props {
  range: DateRange;
  onChange: (range: DateRange) => void;
}

/** 开票日期范围筛选：按钮显示当前范围，点开是预设快捷键 + react-calendar 范围日历。 */
export default function DateRangeFilter({ range, onChange }: Props) {
  const active = isRangeActive(range);
  const label = active
    ? `${range.from ?? '…'} ~ ${range.to ?? '…'}`
    : '全部日期';

  // react-calendar 范围选择需要 [Date, Date]；两端齐全才回显选中区间。
  const calValue: [Date, Date] | null =
    range.from && range.to
      ? [fromISODate(range.from)!, fromISODate(range.to)!]
      : null;

  function handleCalChange(value: any): void {
    if (Array.isArray(value) && value[0] && value[1]) {
      onChange(
        normalizeRange({ from: toISODate(value[0]), to: toISODate(value[1]) }),
      );
    }
  }

  return (
    <Dropdown
      button={
        <button
          type="button"
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            active
              ? 'bg-brand-500 text-white dark:bg-brand-400'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-navy-700 dark:text-gray-300'
          }`}
        >
          <span aria-hidden>📅</span>
          <span>开票日期：{label}</span>
        </button>
      }
      classNames="top-12 right-0 w-max"
    >
      <div className="w-[330px] rounded-2xl bg-white p-4 shadow-xl dark:bg-navy-700">
        <div className="mb-3 flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onChange(presetRange(p))}
              className="dark:hover:bg-brand-500/10 rounded-lg bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600 transition hover:bg-brand-50 hover:text-brand-600 dark:bg-navy-800 dark:text-gray-300 dark:hover:text-brand-400"
            >
              {PRESET_LABELS[p]}
            </button>
          ))}
          {active && (
            <button
              type="button"
              onClick={() => onChange(EMPTY_RANGE)}
              className="rounded-lg px-3 py-1 text-xs font-medium text-gray-400 transition hover:text-red-500"
            >
              清除
            </button>
          )}
        </div>
        <Calendar
          selectRange
          view="month"
          value={calValue}
          onChange={handleCalChange}
          locale="zh-CN"
          prevLabel={<MdChevronLeft className="mx-auto h-5 w-5" />}
          nextLabel={<MdChevronRight className="mx-auto h-5 w-5" />}
          prev2Label={null}
          next2Label={null}
        />
      </div>
    </Dropdown>
  );
}
