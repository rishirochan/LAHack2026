'use client';

import AuthGate from '@/auth/AuthGate';
import Sidebar from '@/components/Sidebar';
import { SessionsProvider } from '@/context/SessionsContext';
import { SidebarProvider, useSidebar } from '@/context/SidebarContext';

function DashboardFrame({ children }: { children: React.ReactNode }) {
  const { expanded } = useSidebar();

  return (
    <>
      <Sidebar />
      <main className={`min-h-screen p-8 transition-all duration-300 ${expanded ? 'ml-[240px]' : 'ml-[88px]'}`}>
        {children}
      </main>
    </>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <SidebarProvider>
        <SessionsProvider>
          <DashboardFrame>{children}</DashboardFrame>
        </SessionsProvider>
      </SidebarProvider>
    </AuthGate>
  );
}
