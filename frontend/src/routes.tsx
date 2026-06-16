import {
  MdSpaceDashboard,
  MdReceiptLong,
  MdInsights,
  MdDownloadForOffline,
} from 'react-icons/md';

// Sidebar route configuration for the "invoce" app.
// Note: this drives the Sidebar/Navbar only — actual pages are file-based
// under src/app/admin/*. The auth routes are kept for a future login flow.
const routes = [
  {
    name: '工作台',
    layout: '/admin',
    path: '/dashboard',
    icon: <MdSpaceDashboard className="text-inherit h-5 w-5" />,
  },
  {
    name: '发票管理',
    layout: '/admin',
    path: '/invoices',
    icon: <MdReceiptLong className="text-inherit h-5 w-5" />,
  },
  {
    name: '消费分析',
    layout: '/admin',
    path: '/analytics',
    icon: <MdInsights className="text-inherit h-5 w-5" />,
  },
  {
    name: '导出任务',
    layout: '/admin',
    path: '/export-tasks',
    icon: <MdDownloadForOffline className="text-inherit h-5 w-5" />,
  },
];
export default routes;
