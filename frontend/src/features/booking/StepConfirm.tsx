import { useState } from 'react';

import type { Master, Service } from '@/api/types';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { AuthDialog } from '@/features/auth/AuthDialog';
import { useAuth } from '@/lib/auth';
import { formatDateWithWeekday, formatDuration, formatMoney, formatTime } from '@/lib/format';

export function StepConfirm({
  service,
  master,
  startsAt,
  comment,
  submitting,
  onCommentChange,
  onConfirm,
}: {
  service: Service;
  /** Конкретный мастер, уже выбранный для слота. */
  master: Master | undefined;
  startsAt: string;
  comment: string;
  submitting: boolean;
  onCommentChange: (value: string) => void;
  onConfirm: () => void;
}) {
  const { user, loading } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  const offer = master?.services.find((item) => item.service_id === service.id);
  const price = offer?.price ?? service.price;
  const duration = offer?.duration_min ?? service.duration_min;

  return (
    <div className="space-y-5">
      <Card className="space-y-4">
        <Row label="Услуга" value={service.name} />
        {master && (
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-sand-600">Мастер</span>
            <span className="flex items-center gap-2.5">
              <Avatar name={master.full_name} photoUrl={master.photo_url} className="size-8" />
              <span className="font-medium text-sand-900">{master.full_name}</span>
            </span>
          </div>
        )}
        <Row label="Когда" value={formatDateWithWeekday(startsAt)} />
        <Row label="Время" value={`${formatTime(startsAt)} · ${formatDuration(duration)}`} />
        <div className="flex items-center justify-between gap-4 border-t border-sand-200 pt-4">
          <span className="text-sm text-sand-600">Стоимость</span>
          <span className="tabular text-lg font-semibold text-clay-700">
            {formatMoney(price)}
          </span>
        </div>
      </Card>

      <div className="space-y-1.5">
        <label htmlFor="booking-comment" className="block text-sm font-medium text-sand-800">
          Комментарий мастеру
        </label>
        <textarea
          id="booking-comment"
          rows={3}
          maxLength={500}
          value={comment}
          onChange={(event) => onCommentChange(event.target.value)}
          placeholder="Например: хочу убрать только секущиеся концы"
          className="w-full rounded-xl border border-sand-300 bg-white px-3.5 py-2.5 text-sm text-sand-900 placeholder:text-sand-400 focus:border-clay-400 focus:outline-none focus:ring-2 focus:ring-clay-200"
        />
        <p className="text-sm text-sand-500">Необязательно</p>
      </div>

      {loading ? (
        <div className="skeleton h-13" />
      ) : user ? (
        <>
          <Button size="lg" fullWidth loading={submitting} onClick={onConfirm}>
            Записаться
          </Button>
          <p className="text-center text-sm text-sand-500">
            Отменить запись можно не позднее чем за 2 часа до начала
          </p>
        </>
      ) : (
        <>
          <Button size="lg" fullWidth onClick={() => setAuthOpen(true)}>
            Войти и записаться
          </Button>
          <p className="text-center text-sm text-sand-500">
            Нужно, чтобы вы могли потом посмотреть и отменить запись
          </p>
        </>
      )}

      <AuthDialog
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onSuccess={() => setAuthOpen(false)}
      />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-sand-600">{label}</span>
      <span className="text-right font-medium text-sand-900">{value}</span>
    </div>
  );
}
