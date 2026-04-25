import type { Metadata } from 'next';
import '@/index.css';
import { AuthProvider } from '@/auth/AuthProvider';
import { VoiceSettingsProvider } from '@/context/VoiceSettingsContext';

export const metadata: Metadata = {
  title: 'Eloquence',
  description: 'AI communication coach',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <VoiceSettingsProvider>{children}</VoiceSettingsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
