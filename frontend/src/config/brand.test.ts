import { describe, expect, it } from 'vitest';

import { brand, brandFooterLine, brandTagline } from './brand';

describe('бренд', () => {
  it('по умолчанию берёт значения демо-салона', () => {
    expect(brand.name).toBe('Салон красоты');
    expect(brand.city).toBe('Алматы');
  });

  it('красит акцентом последнее слово названия', () => {
    // «Салон красоты» -> «Салон» + «красоты». Так логотип работает
    // и для «Студия Локон», и для односложного «Барбершоп».
    expect(brand.head).toBe('Салон');
    expect(brand.accent).toBe('красоты');
  });

  it('берёт монограмму из первой буквы названия', () => {
    expect(brand.monogram).toBe('С');
  });

  it('собирает подпись над заголовком', () => {
    expect(brandTagline).toBe('Алматы · ежедневно 9:00–21:00');
  });

  it('собирает строку подвала', () => {
    expect(brandFooterLine).toBe('Салон красоты · Алматы · ежедневно 9:00–21:00');
  });

  it('не показывает телефон, если он не задан', () => {
    expect(brand.phone).toBe('');
  });
});
