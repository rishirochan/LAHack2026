'use client';

import { usePathname } from 'next/navigation';
import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react';

import { useRecentSessions, type SessionPreview } from '@/hooks/useSessions';

interface SessionsContextType {
  recentSessions: SessionPreview[];
  loading: boolean;
  error: string;
  refetch: () => Promise<void>;
}

const SessionsContext = createContext<SessionsContextType>({
  recentSessions: [],
  loading: false,
  error: '',
  refetch: async () => {},
});

export function SessionsProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { data, loading, error, refetch } = useRecentSessions(10);

  useEffect(() => {
    void refetch();
  }, [pathname, refetch]);

  useEffect(() => {
    const refreshSessions = () => {
      void refetch();
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshSessions();
      }
    };

    window.addEventListener('focus', refreshSessions);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('focus', refreshSessions);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refetch]);

  const value = useMemo(
    () => ({
      recentSessions: data ?? [],
      loading,
      error,
      refetch,
    }),
    [data, error, loading, refetch],
  );

  return (
    <SessionsContext.Provider value={value}>
      {children}
    </SessionsContext.Provider>
  );
}

export function useSessionsContext() {
  return useContext(SessionsContext);
}
