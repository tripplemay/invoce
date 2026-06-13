'use client';
import Card from 'components/card';

export default function DashboardPage() {
  return (
    <div className="mt-3 grid h-full grid-cols-1 gap-5">
      <Card extra="w-full h-full p-6">
        <h1 className="text-2xl font-bold text-navy-700 dark:text-white">
          工作台
        </h1>
        <p className="mt-2 text-base text-gray-600 dark:text-gray-400">
          建设中
        </p>
      </Card>
    </div>
  );
}
