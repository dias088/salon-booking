import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { api, setAccessToken, setUnauthorizedHandler } from '@/lib/api';
import type { TokenResponse, User } from '@/api/types';

interface AuthContextValue {
  user: User | null;
  /** true, пока идёт первая попытка восстановить сессию по cookie. */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: RegisterData) => Promise<User>;
  logout: () => Promise<void>;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  phone: string;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const applySession = useCallback((data: TokenResponse) => {
    setAccessToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  // При старте пробуем поднять сессию из httpOnly cookie: access-токен
  // живёт только в памяти и после перезагрузки страницы теряется.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const restored = await api.restoreSession();
      if (cancelled) return;
      if (restored) {
        try {
          setUser(await api.get<User>('/api/auth/me'));
        } catch {
          setAccessToken(null);
        }
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Если refresh протух, сбрасываем пользователя — иначе интерфейс
  // продолжал бы показывать личный кабинет неавторизованному.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      void queryClient.clear();
    });
    return () => setUnauthorizedHandler(null);
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login: async (email, password) =>
        applySession(await api.post<TokenResponse>('/api/auth/login', { email, password })),
      register: async (data) =>
        applySession(await api.post<TokenResponse>('/api/auth/register', data)),
      logout: async () => {
        try {
          await api.post('/api/auth/logout');
        } finally {
          setAccessToken(null);
          setUser(null);
          queryClient.clear();
        }
      },
    }),
    [user, loading, applySession, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth вызван вне AuthProvider');
  return context;
}
