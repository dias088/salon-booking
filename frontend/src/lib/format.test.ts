import { describe, expect, it } from 'vitest';

import {
  addDaysIso,
  formatDate,
  formatDuration,
  formatMoney,
  formatTime,
  plural,
  toIsoDate,
  weekdayIndex,
} from '@/lib/format';

describe('время приводится к поясу салона', () => {
  it('показывает время по Алматы, а не по поясу браузера', () => {
    // 2026-10-12T09:00:00Z — это 14:00 в Алматы (UTC+5).
    expect(formatTime('2026-10-12T09:00:00Z')).toBe('14:00');
  });

  it('не съезжает на сутки у позднего вечера', () => {
    // 20:30 UTC — это уже следующий день 01:30 по Алматы.
    expect(formatTime('2026-10-12T20:30:00Z')).toBe('01:30');
    expect(toIsoDate('2026-10-12T20:30:00Z')).toBe('2026-10-13');
  });

  it('выводит дату с русским месяцем в родительном падеже', () => {
    expect(formatDate('2026-10-12T09:00:00+05:00')).toBe('12 октября');
  });

  it('считает понедельник нулевым днём, как working_hours.weekday', () => {
    expect(weekdayIndex('2026-10-12T09:00:00+05:00')).toBe(0);
    expect(weekdayIndex('2026-10-18T09:00:00+05:00')).toBe(6);
  });
});

describe('addDaysIso', () => {
  it('перешагивает границу месяца', () => {
    expect(addDaysIso('2026-10-30', 3)).toBe('2026-11-02');
  });

  it('работает в обратную сторону', () => {
    expect(addDaysIso('2026-01-01', -1)).toBe('2025-12-31');
  });
});

describe('деньги и длительность', () => {
  // Intl разделяет разряды неразрывным пробелом — типографски это верно,
  // поэтому сравниваем через \s, а не ждём обычный пробел.
  it('форматирует цену из строки numeric без потери значения', () => {
    expect(formatMoney('9000.00')).toMatch(/^9\s000\s₸$/u);
    expect(formatMoney('62000.00')).toMatch(/^62\s000\s₸$/u);
  });

  it('не падает на мусоре вместо числа', () => {
    expect(formatMoney('не число')).toBe('—');
  });

  it('переводит минуты в часы', () => {
    expect(formatDuration(45)).toBe('45 мин');
    expect(formatDuration(60)).toBe('1 ч');
    expect(formatDuration(150)).toBe('2 ч 30 мин');
  });
});

describe('plural', () => {
  it.each([
    [1, 'запись'],
    [2, 'записи'],
    [5, 'записей'],
    [11, 'записей'],
    [21, 'запись'],
    [104, 'записи'],
  ])('%i -> %s', (count, expected) => {
    expect(plural(count, 'запись', 'записи', 'записей')).toBe(expected);
  });
});
