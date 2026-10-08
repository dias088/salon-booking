import { useState } from 'react';

import {
  useAdminCategories,
  useAdminServices,
  useDeleteService,
  useSaveService,
} from '@/api/adminQueries';
import type { Service } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { formatDuration, formatMoney } from '@/lib/format';

export function AdminServicesPage() {
  const { data, isPending } = useAdminServices();
  const { data: categories } = useAdminCategories();
  const [editing, setEditing] = useState<Service | 'new' | null>(null);

  const deleteService = useDeleteService();
  const toast = useToast();

  const onDelete = async (service: Service) => {
    try {
      await deleteService.mutateAsync(service.id);
      toast.success(
        'Услуга удалена. Если по ней были визиты — она скрыта, чтобы не потерять историю',
      );
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось удалить');
    }
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-sand-900">Услуги</h1>
        <Button onClick={() => setEditing('new')}>Добавить услугу</Button>
      </header>

      {isPending ? (
        <RowsSkeleton rows={5} />
      ) : (
        <div className="overflow-x-auto surface">
          <table className="w-full min-w-[42rem] text-sm">
            <thead className="border-b border-sand-200 text-left text-sand-500">
              <tr>
                <Th>Название</Th>
                <Th>Категория</Th>
                <Th className="text-right">Длительность</Th>
                <Th className="text-right">Цена</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((service) => (
                <tr key={service.id} className="border-b border-sand-100 last:border-0">
                  <Td>
                    <span className="font-medium text-sand-900">{service.name}</span>
                    {!service.is_active && (
                      <Badge className="ml-2 border-sand-200 bg-sand-100 text-sand-500">
                        скрыта
                      </Badge>
                    )}
                  </Td>
                  <Td className="text-sand-600">{service.category_name}</Td>
                  <Td className="tabular text-right text-sand-700">
                    {formatDuration(service.duration_min)}
                  </Td>
                  <Td className="tabular text-right font-medium text-sand-900">
                    {formatMoney(service.price)}
                  </Td>
                  <Td className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setEditing(service)}>
                        Изменить
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => void onDelete(service)}>
                        Удалить
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <ServiceDialog
          service={editing === 'new' ? null : editing}
          categories={categories ?? []}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function ServiceDialog({
  service,
  categories,
  onClose,
}: {
  service: Service | null;
  categories: { id: number; name: string }[];
  onClose: () => void;
}) {
  const save = useSaveService();
  const toast = useToast();
  const [form, setForm] = useState({
    name: service?.name ?? '',
    category_id: service?.category_id ?? categories[0]?.id ?? 0,
    duration_min: service?.duration_min ?? 60,
    price: service?.price ?? '5000.00',
    description: service?.description ?? '',
    is_active: service?.is_active ?? true,
  });

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await save.mutateAsync({
        id: service?.id,
        name: form.name,
        category_id: Number(form.category_id),
        duration_min: Number(form.duration_min),
        price: String(form.price),
        description: form.description || null,
        is_active: form.is_active,
      });
      toast.success(service ? 'Услуга обновлена' : 'Услуга добавлена');
      onClose();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось сохранить');
    }
  };

  return (
    <Modal open title={service ? 'Изменить услугу' : 'Новая услуга'} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field
          label="Название"
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
        <div className="space-y-1.5">
          <label htmlFor="service-category" className="block text-sm font-medium text-sand-800">
            Категория
          </label>
          <select
            id="service-category"
            value={form.category_id}
            onChange={(event) => setForm({ ...form, category_id: Number(event.target.value) })}
            className="h-11 w-full rounded-xl border border-sand-300 bg-white px-3 text-sm"
          >
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Field
            label="Длительность, мин"
            type="number"
            step={5}
            min={5}
            hint="Кратно пяти"
            value={form.duration_min}
            onChange={(event) => setForm({ ...form, duration_min: Number(event.target.value) })}
          />
          <Field
            label="Цена, ₸"
            type="number"
            step="100"
            min={0}
            value={form.price}
            onChange={(event) => setForm({ ...form, price: event.target.value })}
          />
        </div>
        <Field
          label="Описание"
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
        />
        <label className="flex items-center gap-2.5 text-sm text-sand-800">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
            className="size-4 rounded border-sand-300"
          />
          Показывать в каталоге
        </label>
        <Button type="submit" fullWidth loading={save.isPending}>
          Сохранить
        </Button>
      </form>
    </Modal>
  );
}

function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th className={`px-4 py-3 font-medium ${className ?? ''}`}>{children}</th>;
}

function Td({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-3 ${className ?? ''}`}>{children}</td>;
}
