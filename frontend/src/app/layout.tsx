import type { Metadata } from 'next';
import '@/index.css';
import { AuthProvider } from '@/auth/AuthProvider';

export const metadata: Metadata = {
  title: 'Eloquence',
  description: 'AI communication coach',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
