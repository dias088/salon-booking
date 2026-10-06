import { type ButtonHTMLAttributes, forwardRef } from 'react';

import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-clay-600 text-white hover:bg-clay-700 active:bg-clay-800 shadow-sm',
  secondary:
    'bg-white text-sand-800 border border-sand-300 hover:bg-sand-100 active:bg-sand-200',
  ghost: 'text-sand-700 hover:bg-sand-100 active:bg-sand-200',
  danger: 'bg-white text-red-700 border border-red-200 hover:bg-red-50 active:bg-red-100',
};

const SIZES: Record<Size, string> = {
  sm: 'h-9 px-3 text-sm rounded-lg',
  md: 'h-11 px-4 text-sm rounded-xl',
  lg: 'h-13 px-6 text-base rounded-xl',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, fullWidth, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      // disabled при loading, иначе двойной клик отправит две записи.
      disabled={props.disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
});
