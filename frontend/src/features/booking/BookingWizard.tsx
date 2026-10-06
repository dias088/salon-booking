import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useCreateAppointment, useMasters } from '@/api/queries';
import type { Service } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { StepConfirm } from '@/features/booking/StepConfirm';
import { StepMaster, type MasterChoice } from '@/features/booking/StepMaster';
import { StepService } from '@/features/booking/StepService';
import { StepSlot, type SlotChoice } from '@/features/booking/StepSlot';
import { Stepper } from '@/features/booking/Stepper';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { todayIso } from '@/lib/format';

export function BookingWizard({ initialService }: { initialService?: Service | null }) {
  const [step, setStep] = useState(initialService ? 1 : 0);
  const [service, setService] = useState<Service | null>(initialService ?? null);
  const [master, setMaster] = useState<MasterChoice>(null);
  const [anyMaster, setAnyMaster] = useState(true);
  const [date, setDate] = useState(todayIso());
  const [slot, setSlot] = useState<SlotChoice | null>(null);
  const [comment, setComment] = useState('');

  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const createAppointment = useCreateAppointment();

  // На шаге подтверждения нужен конкретный мастер — даже если клиент
  // выбрал «любого», слот уже закреплён за кем-то одним.
  const { data: mastersPage } = useMasters(service?.id);
  const slotMaster = mastersPage?.items.find((item) => item.id === slot?.masterId);

  const resetFrom = (changed: 'service' | 'master') => {
    setSlot(null);
    if (changed === 'service') {
      setMaster(null);
      setAnyMaster(true);
    }
  };

  const handleConfirm = async () => {
    if (!service || !slot) return;
    try {
      const appointment = await createAppointment.mutateAsync({
        service_id: service.id,
        master_id: slot.masterId,
        starts_at: slot.startsAt,
        comment: comment.trim() || null,
      });
      toast.success('Записали! Ждём вас в салоне');
      navigate(`/my?highlight=${appointment.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.isSlotTaken) {
        // Пока клиент думал, слот заняли. Сетка уже перезапрошена
        // в onSettled мутации — возвращаем на шаг выбора времени.
        setSlot(null);
        setStep(2);
        toast.error('Это время только что заняли. Выберите, пожалуйста, другое');
        return;
      }
      if (error instanceof ApiError) {
        toast.error(error.message);
        return;
      }
      toast.error('Не удалось записаться, попробуйте ещё раз');
    }
  };

  const canGoNext =
    (step === 0 && service !== null) ||
    (step === 1 && (anyMaster || master !== null)) ||
    (step === 2 && slot !== null);

  return (
    <div className="space-y-6">
      <Stepper current={step} onGoTo={setStep} />

      <div className="min-h-[18rem]">
        {step === 0 && (
          <StepService
            selected={service}
            onSelect={(value) => {
              setService(value);
              resetFrom('service');
              setStep(1);
            }}
          />
        )}

        {step === 1 && service && (
          <StepMaster
            service={service}
            selected={master}
            anyMaster={anyMaster}
            onSelect={(value) => {
              setMaster(value);
              setAnyMaster(value === null);
              resetFrom('master');
              setStep(2);
            }}
          />
        )}

        {step === 2 && service && (
          <StepSlot
            service={service}
            master={anyMaster ? null : master}
            date={date}
            selected={slot}
            onDateChange={(value) => {
              setDate(value);
              setSlot(null);
            }}
            onSelect={(value) => {
              setSlot(value);
              setStep(3);
            }}
          />
        )}

        {step === 3 && service && slot && (
          <StepConfirm
            service={service}
            master={slotMaster}
            startsAt={slot.startsAt}
            comment={comment}
            submitting={createAppointment.isPending}
            onCommentChange={setComment}
            onConfirm={() => {
              if (!user) return;
              void handleConfirm();
            }}
          />
        )}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-sand-200 pt-5">
        <Button
          variant="ghost"
          onClick={() => setStep((current) => Math.max(0, current - 1))}
          disabled={step === 0}
        >
          ← Назад
        </Button>
        {step < 3 && (
          <Button onClick={() => setStep((current) => current + 1)} disabled={!canGoNext}>
            Далее →
          </Button>
        )}
      </div>
    </div>
  );
}
