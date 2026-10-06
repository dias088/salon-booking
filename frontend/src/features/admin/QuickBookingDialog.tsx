import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { useAdminCreateAppointment } from '@/api/adminQueries';
import { useCatalog } from '@/api/queries';
import type { Master } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { SALON_TZ, formatDateWithWeekday } from '@/lib/format';

const schema = z.object({
  service_id: z.coerce.number().int().positive('Выберите услугу'),
  full_name: z.string().min(2, 'Как зовут клиента?'),
  phone: z
    .string()
    .refine((value) => (value.match(/\d/g) ?? []).length >= 10, 'Нужно минимум 10 цифр'),
  comment: z.string().max(500).optional(),
});

type Values = z.infer<typeof schema>;

export interface QuickBookingTarget {
  master: Master;
  date: string;
  time: string;
}

/** Смещение пояса салона в формате ISO: +05:00. */
function salonOffset(date: string): string {
  const probe = new Date(`${date}T12:00:00Z`);
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: SALON_TZ,
    timeZoneName: 'longOffset',
  });
  const name = formatter.formatToParts(probe).find((part) => part.type === 'timeZoneName');
  return (name?.value ?? 'GMT+05:00').replace('GMT', '') || '+05:00';
}

export function QuickBookingDialog({
  target,
  onClose,
}: {
  target: QuickBookingTarget | null;
  onClose: () => void;
}) {
  const { data: catalog } = useCatalog();
  const createAppointment = useAdminCreateAppointment();
  const toast = useToast();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (target) reset({ full_name: '', phone: '', comment: '' });
  }, [target, reset]);

  if (!target) return null;

  // Мастер уже выбран колонкой календаря, поэтому показываем только те
  // услуги, которые он действительно оказывает.
  const offered = new Set(target.master.services.map((item) => item.service_id));
  const services = (catalog ?? [])
    .flatMap((category) => category.services)
    .filter((service) => offered.has(service.id));

  const onSubmit = handleSubmit(async (values) => {
    try {
      await createAppointment.mutateAsync({
        service_id: values.service_id,
        master_id: target.master.id,
        starts_at: `${target.date}T${target.time}:00${salonOffset(target.date)}`,
        comment: values.comment?.trim() || null,
        client: { full_name: values.full_name, phone: values.phone },
      });
      toast.success('Записали клиента');
      onClose();
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.message);
        return;
      }
      toast.error('Не удалось создать запись');
    }
  });

  return (
    <Modal open title="Запись по телефону" onClose={onClose}>
      <p className="mb-4 rounded-xl bg-sand-100 px-3.5 py-2.5 text-sm text-sand-700">
        {target.master.full_name} · {formatDateWithWeekday(`${target.date}T12:00:00`)} ·{' '}
        <span className="tabular font-medium">{target.time}</span>
      </p>

      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="quick-service" className="block text-sm font-medium text-sand-800">
            Услуга
          </label>
          <select
            id="quick-service"
            className="h-11 w-full rounded-xl border border-sand-300 bg-white px-3 text-sm text-sand-900"
            defaultValue=""
            {...register('service_id')}
          >
            <option value="" disabled>
              Выберите услугу
            </option>
            {services.map((service) => (
              <option key={service.id} value={service.id}>
                {service.name}
              </option>
            ))}
          </select>
          {errors.service_id && (
            <p className="text-sm text-red-600">{errors.service_id.message}</p>
          )}
        </div>

        <Field
          label="Имя клиента"
          placeholder="Гульнара Ким"
          error={errors.full_name?.message}
          {...register('full_name')}
        />
        <Field
          label="Телефон"
          type="tel"
          placeholder="+7 707 000 00 00"
          hint="Если клиент уже есть в базе, запись привяжется к нему"
          error={errors.phone?.message}
          {...register('phone')}
        />
        <Field label="Комментарий" placeholder="Необязательно" {...register('comment')} />

        <Button type="submit" fullWidth loading={isSubmitting}>
          Записать
        </Button>
      </form>
    </Modal>
  );
}
