'use client';

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  MOCK_AUTH_STORAGE_KEY,
  type MockUser,
} from '@/auth/mock-auth';

interface AuthContextValue {
  user: MockUser | null;
  isHydrated: boolean;
  login: (nextUser: MockUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MockUser | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(MOCK_AUTH_STORAGE_KEY);
      if (stored) {
        setUser(JSON.parse(stored) as MockUser);
      }
    } catch {
      window.localStorage.removeItem(MOCK_AUTH_STORAGE_KEY);
    } finally {
      setIsHydrated(true);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isHydrated,
      login: (nextUser) => {
        setUser(nextUser);
        window.localStorage.setItem(
          MOCK_AUTH_STORAGE_KEY,
          JSON.stringify(nextUser),
        );
      },
      logout: () => {
        setUser(null);
        window.localStorage.removeItem(MOCK_AUTH_STORAGE_KEY);
      },
    }),
    [isHydrated, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}
