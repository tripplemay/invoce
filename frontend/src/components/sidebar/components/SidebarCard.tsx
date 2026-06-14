'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BsArrowsAngleExpand } from 'react-icons/bs';
import { listInvoices } from 'lib/invoices';
import { Invoice } from 'lib/types';

const yuan = (n: number) =>
  `¥${n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;

// 「待报销」业务小卡：展示待报销发票总额，点击跳转发票列表。
const SidebarCard = (props: { [x: string]: any }) => {
  const { mini, hovered } = props;
  const [total, setTotal] = useState(0);

  useEffect(() => {
    let active = true;
    listInvoices('unreimbursed')
      .then((invoices: Invoice[]) => {
        if (!active) return;
        const sum = invoices.reduce(
          (acc, i) => acc + (parseFloat(i.total_amount ?? '0') || 0),
          0,
        );
        setTotal(sum);
      })
      .catch(() => {
        if (active) setTotal(0);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <Link
      href="/admin/invoices"
      className={`relative flex h-[300px] w-[240px] flex-col items-center rounded-[20px] bg-gradient-to-br from-brand-400 to-brand-600 ${
        mini === false
          ? ''
          : mini === true && hovered === true
          ? ''
          : 'xl:justify-center xl:mx-3.5'
      }`}
    >
      <BsArrowsAngleExpand
        className={`h-6 w-6 my-[100px] mx-5 text-white ${
          mini === true && hovered === false ? 'block' : 'hidden'
        }`}
      />
      <div
        className={`mt-auto mb-auto flex flex-col items-center ${
          mini === false
            ? 'block'
            : mini === true && hovered === true
            ? 'block'
            : 'hidden'
        }`}
      >
        <p className="text-xs font-medium text-white">待报销总额</p>
        <h4 className="mt-[4px] text-3xl font-bold text-white">{yuan(total)}</h4>
      </div>
    </Link>
  );
};

export default SidebarCard;
