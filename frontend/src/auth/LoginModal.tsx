'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Lock, Mail, ArrowRight, Zap } from 'lucide-react';
import { useAuth } from '@/auth/AuthProvider';
import {
  createMockUser,
  isValidMockLogin,
  MOCK_LOGIN_CREDENTIALS,
} from '@/auth/mock-auth';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function LoginModal({
  isOpen,
  onClose,
  onSuccess,
}: LoginModalProps) {
  const { login } = useAuth();
  const [email, setEmail] = useState<string>(MOCK_LOGIN_CREDENTIALS.email);
  const [password, setPassword] = useState<string>(MOCK_LOGIN_CREDENTIALS.password);
  const [error, setError] = useState('');
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);

  useEffect(() => {
    if (!isOpen) setError('');
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen || !portalTarget) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidMockLogin(email, password)) {
      setError('Invalid credentials. Use the demo account shown below.');
      return;
    }
    login(createMockUser(email));
    onSuccess();
  };

  const inputClass =
    'w-full rounded-xl border border-cream-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 transition-colors focus:border-navy-500 focus:ring-2 focus:ring-navy-500/20';

  return createPortal(
    <div
      className="fixed inset-0 flex items-center justify-center bg-cream-100"
      style={{ zIndex: 99999 }}
    >
      {/* Branding top-left */}
      <div className="absolute top-6 left-8 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-navy-500 flex items-center justify-center">
          <Zap size={16} className="text-white" />
        </div>
        <span className="font-['Playfair_Display'] text-xl font-semibold text-slate-900">
          Eloquence
        </span>
      </div>

      {/* Back link top-right */}
      <button
        type="button"
        onClick={onClose}
        className="absolute top-7 right-8 text-sm text-slate-500 hover:text-slate-900 transition-colors"
      >
        &larr; Back to home
      </button>

      {/* Centered card */}
      <div className="w-[400px] rounded-2xl border border-cream-300 bg-cream-50 p-8 shadow-[0_8px_32px_rgba(0,0,0,0.08)]">
        <h2 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Welcome back
        </h2>
        <p className="mt-1 text-sm text-slate-500 mb-8">
          Sign in to open your practice dashboard.
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1.5 flex items-center gap-2 text-xs font-medium text-slate-600">
              <Mail size={14} /> Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label className="mb-1.5 flex items-center gap-2 text-xs font-medium text-slate-600">
              <Lock size={14} /> Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
          </div>

          {error && (
            <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs text-rose-600">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-navy-500 py-3 text-sm font-medium text-white transition-colors hover:bg-navy-600"
          >
            Sign in
            <ArrowRight size={14} />
          </button>
        </form>

        <div className="mt-6 rounded-xl border border-cream-300 bg-white px-4 py-3">
          <p className="text-xs font-medium text-slate-700">Demo account</p>
          <p className="mt-1 text-xs text-slate-500">
            {MOCK_LOGIN_CREDENTIALS.email} &nbsp;/&nbsp; {MOCK_LOGIN_CREDENTIALS.password}
          </p>
        </div>
      </div>
    </div>,
    portalTarget,
  );
}
