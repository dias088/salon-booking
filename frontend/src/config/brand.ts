/**
 * Бренд салона.
 *
 * Всё, что меняется от клиента к клиенту, живёт здесь и читается из
 * переменных окружения. Чтобы поднять проект для другого салона,
 * достаточно задать VITE_BRAND_* при сборке — код и вёрстку не трогаем.
 *
 * На Vercel это поля в Settings → Environment Variables, локально —
 * frontend/.env.local.
 */

/** Берём значение из окружения, пустую строку считаем незаполненной. */
function env(key: string, fallback: string): string {
  const value = import.meta.env[key as keyof ImportMetaEnv];
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

const name = env('VITE_BRAND_NAME', 'Салон красоты');

/**
 * Последнее слово названия красим акцентом: «Салон **красоты**».
 * Так логотип работает и для «Студия Локон», и для «Барбершоп Топор»,
 * без отдельной переменной под каждую половину.
 */
function splitName(full: string): { head: string; accent: string } {
  const parts = full.trim().split(/\s+/);
  if (parts.length === 1) return { head: '', accent: parts[0] ?? '' };
  return { head: parts.slice(0, -1).join(' '), accent: parts.at(-1) ?? '' };
}

export const brand = {
  /** Полное название — для title страницы и подвала. */
  name,
  /** Название, разбитое для логотипа в шапке. */
  ...splitName(name),
  /** Монограмма в квадрате. По умолчанию — первая буква названия. */
  monogram: env('VITE_BRAND_MONOGRAM', name.trim().charAt(0).toUpperCase()),
  city: env('VITE_BRAND_CITY', 'Алматы'),
  /** Часы работы одной строкой: «9:00–21:00». */
  hours: env('VITE_BRAND_HOURS', '9:00–21:00'),
  /** Телефон для подвала. Пустая строка — блок не показываем. */
  phone: env('VITE_BRAND_PHONE', ''),
  /**
   * Приписка в подвале. Для учебного демо — «Учебный проект»,
   * для настоящего клиента её стоит очистить.
   */
  footerNote: env('VITE_BRAND_FOOTER_NOTE', 'Учебный проект.'),
} as const;

/** «Алматы · ежедневно 9:00–21:00» — подпись над заголовком на главной. */
export const brandTagline = `${brand.city} · ежедневно ${brand.hours}`;

/** «Салон красоты · Алматы · ежедневно с 9:00 до 21:00» — строка подвала. */
export const brandFooterLine = [brand.name, brand.city, `ежедневно ${brand.hours}`].join(' · ');
