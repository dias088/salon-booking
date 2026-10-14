/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Адрес бэкенда. Пусто в разработке — там работает прокси Vite. */
  readonly VITE_API_URL?: string;

  // Бренд салона, см. src/config/brand.ts
  readonly VITE_BRAND_NAME?: string;
  readonly VITE_BRAND_MONOGRAM?: string;
  readonly VITE_BRAND_CITY?: string;
  readonly VITE_BRAND_HOURS?: string;
  readonly VITE_BRAND_PHONE?: string;
  readonly VITE_BRAND_FOOTER_NOTE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
