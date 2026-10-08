import { type ButtonHTMLAttributes, forwardRef } from 'react';

import { cn } from '@/lib/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const VARIANTS: Record<Variant, string> = {
  // Акцентная тень в тон кнопке, а не чёрная: кнопка «светится» своим цветом.
  primary: [
    'bg-clay-600 text-white shadow-accent',
    'hover:bg-clay-700 hover:-translate-y-px hover:shadow-lift',
    'active:translate-y-0 active:bg-clay-800 active:shadow-card',
  ].join(' '),
  secondary:
    'bg-white text-sand-800 border border-sand-200 shadow-card hover:border-sand-300 hover:bg-sand-50 active:bg-sand-100',
  ghost: 'text-sand-700 hover:bg-sand-100 active:bg-sand-200',
  danger: 'bg-white text-red-700 border border-red-200 hover:bg-red-50 active:bg-red-100',
};

const SIZES: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-sm rounded-lg',
  md: 'h-11 px-5 text-sm rounded-xl',
  lg: 'h-13 px-7 text-base rounded-xl',
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
        'inline-flex items-center justify-center gap-2 font-medium',
        'transition-all duration-150 ease-out',
        // Отключённая кнопка не должна подпрыгивать под курсором.
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
        'disabled:translate-y-0 disabled:shadow-none',
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
