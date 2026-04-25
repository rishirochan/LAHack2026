'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Mail, ArrowRight, User2, X } from 'lucide-react';
import { useAuth } from '@/auth/AuthProvider';
import {
  createMockUser,
  isValidMockLogin,
  MOCK_LOGIN_CREDENTIALS,
} from '@/auth/mock-auth';

export type AuthMode = 'signin' | 'signup';

interface LoginModalProps {
  isOpen: boolean;
  initialMode?: AuthMode;
  onClose: () => void;
  onSuccess: () => void;
}

export default function LoginModal({
  isOpen,
  initialMode = 'signin',
  onClose,
  onSuccess,
}: LoginModalProps) {
  const { login } = useAuth();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState<string>(MOCK_LOGIN_CREDENTIALS.email);
  const [password, setPassword] = useState<string>(MOCK_LOGIN_CREDENTIALS.password);
  const [error, setError] = useState('');
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  useEffect(() => setPortalTarget(document.body), []);

  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setError('');
    }
  }, [isOpen, initialMode]);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  if (!portalTarget) return null;

  const handleClose = () => {
    setError('');
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidMockLogin(email, password)) {
      setError('Invalid credentials. Try the demo account below.');
      return;
    }
    login(createMockUser(mode === 'signup' ? fullName : 'Demo User', email));
    setError('');
    onSuccess();
  };

  const switchMode = () => {
    setError('');
    setMode(mode === 'signin' ? 'signup' : 'signin');
  };

  const isSignUp = mode === 'signup';

  const inputClass =
    'w-full rounded-2xl border border-cream-300 bg-cream-50 px-5 py-4 text-[15px] text-slate-900 outline-none placeholder:text-slate-400 transition-all focus:border-navy-500 focus:bg-white focus:shadow-[0_0_0_3px_rgba(45,91,227,0.10)]';

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 flex items-center justify-center"
          style={{ zIndex: 99999 }}
        >
          {/* Backdrop: fades in, light blur */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="absolute inset-0 bg-black/20 backdrop-blur-sm"
            onClick={handleClose}
          />

          {/* Card: scales up + fades in */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-[440px] mx-4 rounded-3xl bg-white shadow-[0_24px_80px_rgba(0,0,0,0.15)] overflow-hidden"
          >
            {/* Close button */}
            <button
              type="button"
              onClick={onClose}
              className="absolute top-5 right-5 w-8 h-8 flex items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-cream-100 hover:text-slate-600"
            >
              <X size={18} />
            </button>

            <div className="px-8 pt-10 pb-8">
              {/* Header */}
              <div className="text-center mb-8">
                <h2 className="font-['Playfair_Display'] text-[28px] font-semibold text-slate-900 leading-tight">
                  {isSignUp ? 'Create your account' : 'Sign in'}
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  {isSignUp
                    ? 'Set up your profile to start practicing.'
                    : 'Continue to your practice dashboard.'}
                </p>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {isSignUp && (
                  <div>
                    <label className="mb-1.5 block text-[13px] font-medium text-slate-600">
                      Full name
                    </label>
                    <div className="relative">
                      <User2 size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Jordan Davis"
                        className={`${inputClass} pl-11`}
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="mb-1.5 block text-[13px] font-medium text-slate-600">
                    Email address
                  </label>
                  <div className="relative">
                    <Mail size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className={`${inputClass} pl-11`}
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-[13px] font-medium text-slate-600">
                    Password
                  </label>
                  <div className="relative">
                    <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className={`${inputClass} pl-11`}
                    />
                  </div>
                </div>

                {error && (
                  <p className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-navy-500 py-4 text-[15px] font-semibold text-white shadow-md transition-all hover:bg-navy-600 hover:shadow-lg active:scale-[0.98]"
                >
                  {isSignUp ? 'Get started' : 'Continue'}
                  <ArrowRight size={15} />
                </button>
              </form>

              {/* Divider */}
              <div className="mt-6 mb-5 flex items-center gap-4">
                <div className="h-px flex-1 bg-cream-200" />
                <span className="text-xs text-slate-400 uppercase tracking-wide">or</span>
                <div className="h-px flex-1 bg-cream-200" />
              </div>

              <button
                type="button"
                onClick={switchMode}
                className="w-full rounded-2xl border border-cream-300 bg-cream-50 py-3.5 text-sm font-medium text-slate-700 transition-all hover:bg-cream-100"
              >
                {isSignUp ? 'Sign in to existing account' : 'Create a new account'}
              </button>

              {/* Demo hint */}
              <p className="mt-5 text-center text-xs text-slate-400">
                Demo: <span className="font-medium text-slate-500">{MOCK_LOGIN_CREDENTIALS.email}</span> / <span className="font-medium text-slate-500">{MOCK_LOGIN_CREDENTIALS.password}</span>
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    portalTarget,
  );
}
