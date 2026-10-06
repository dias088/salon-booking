import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Stepper } from '@/features/booking/Stepper';

describe('Stepper', () => {
  it('показывает все четыре шага визарда', () => {
    render(<Stepper current={0} onGoTo={vi.fn()} />);

    for (const title of ['Услуга', 'Мастер', 'Время', 'Подтверждение']) {
      expect(screen.getByText(new RegExp(title))).toBeInTheDocument();
    }
  });

  it('помечает текущий шаг для скринридера', () => {
    render(<Stepper current={2} onGoTo={vi.fn()} />);

    expect(screen.getByRole('button', { current: 'step' })).toHaveTextContent('Время');
  });

  it('позволяет вернуться на пройденный шаг', async () => {
    const onGoTo = vi.fn();
    render(<Stepper current={2} onGoTo={onGoTo} />);

    await userEvent.click(screen.getByText(/Услуга/));

    expect(onGoTo).toHaveBeenCalledWith(0);
  });

  it('не пускает вперёд через непройденные шаги', async () => {
    const onGoTo = vi.fn();
    render(<Stepper current={0} onGoTo={onGoTo} />);

    const future = screen.getByText(/Подтверждение/).closest('button');
    expect(future).toBeDisabled();

    await userEvent.click(future!, { pointerEventsCheck: 0 });
    expect(onGoTo).not.toHaveBeenCalled();
  });
});
