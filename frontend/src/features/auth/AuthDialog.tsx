import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';

const loginSchema = z.object({
  email: z.string().email('Проверьте адрес почты'),
  password: z.string().min(1, 'Введите пароль'),
});

const registerSchema = z.object({
  full_name: z.string().min(2, 'Как к вам обращаться?'),
  phone: z
    .string()
    .refine((value) => (value.match(/\d/g) ?? []).length >= 10, 'Нужно минимум 10 цифр'),
  email: z.string().email('Проверьте адрес почты'),
  password: z.string().min(8, 'Минимум 8 символов'),
});

type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;

export function AuthDialog({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login');

  return (
    <Modal open={open} title={mode === 'login' ? 'Вход' : 'Регистрация'} onClose={onClose}>
      {mode === 'login' ? (
        <LoginForm onSuccess={onSuccess ?? onClose} />
      ) : (
        <RegisterForm onSuccess={onSuccess ?? onClose} />
      )}

      <p className="mt-5 text-center text-sm text-sand-600">
        {mode === 'login' ? 'Ещё нет аккаунта?' : 'Уже записывались у нас?'}{' '}
        <button
          type="button"
          className="font-medium text-clay-700 underline underline-offset-2"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? 'Зарегистрироваться' : 'Войти'}
        </button>
      </p>
    </Modal>
  );
}

export function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const { login } = useAuth();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login(values.email, values.password);
      onSuccess();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setError('password', { message: 'Неверный e-mail или пароль' });
        return;
      }
      toast.error('Не удалось войти, попробуйте позже');
    }
  });

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <Field
        label="E-mail"
        type="email"
        autoComplete="email"
        placeholder="client@salon.dev"
        error={errors.email?.message}
        {...register('email')}
      />
      <Field
        label="Пароль"
        type="password"
        autoComplete="current-password"
        error={errors.password?.message}
        {...register('password')}
      />
      <Button type="submit" fullWidth loading={isSubmitting}>
        Войти
      </Button>
    </form>
  );
}

export function RegisterForm({ onSuccess }: { onSuccess: () => void }) {
  const { register: registerUser } = useAuth();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await registerUser(values);
      onSuccess();
    } catch (error) {
      if (error instanceof ApiError && error.code === 'email_taken') {
        setError('email', { message: 'Такой e-mail уже зарегистрирован' });
        return;
      }
      toast.error('Не удалось зарегистрироваться, попробуйте позже');
    }
  });

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <Field
        label="Имя"
        autoComplete="name"
        placeholder="Алия Жумабаева"
        error={errors.full_name?.message}
        {...register('full_name')}
      />
      <Field
        label="Телефон"
        type="tel"
        autoComplete="tel"
        placeholder="+7 707 000 00 00"
        hint="Позвоним, если планы салона изменятся"
        error={errors.phone?.message}
        {...register('phone')}
      />
      <Field
        label="E-mail"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...register('email')}
      />
      <Field
        label="Пароль"
        type="password"
        autoComplete="new-password"
        hint="Минимум 8 символов"
        error={errors.password?.message}
        {...register('password')}
      />
      <Button type="submit" fullWidth loading={isSubmitting}>
        Зарегистрироваться
      </Button>
    </form>
  );
}
