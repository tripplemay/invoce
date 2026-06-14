import React from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

// 项目内共享按钮：统一各处裸 <button> 的样式与尺寸。
// （Horizon 模板未提供通用 Button 组件，故本地自建。）
const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-500 text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-brand-400',
  secondary:
    'border border-gray-200 text-navy-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:text-white dark:hover:bg-navy-700',
  ghost:
    'text-gray-500 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-50',
};

const SIZES: Record<Size, string> = {
  sm: 'px-4 py-2',
  md: 'px-5 py-2.5',
  lg: 'px-6 py-3',
};

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export default function Button({
  variant = 'primary',
  size = 'md',
  type = 'button',
  className = '',
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={`linear inline-flex items-center justify-center rounded-xl text-sm font-medium transition ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    />
  );
}
