'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/auth/AuthProvider';

export default function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { user, isHydrated } = useAuth();

  useEffect(() => {
    if (!isHydrated || user) {
      return;
    }

    router.replace('/');
  }, [isHydrated, router, user]);

  if (!isHydrated || !user) {
    return (
      <div className="min-h-screen bg-cream-100 flex items-center justify-center px-6">
        <div className="bg-white border border-cream-300 rounded-3xl shadow-sm px-8 py-10 text-center max-w-md w-full">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-navy-500/10 text-navy-500 flex items-center justify-center text-sm font-semibold mb-4">
            AI
          </div>
          <h1 className="font-serif text-2xl font-semibold text-slate-900 mb-2">
            Loading your practice space
          </h1>
          <p className="text-slate-500">
            Checking your login state before we open the dashboard.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
