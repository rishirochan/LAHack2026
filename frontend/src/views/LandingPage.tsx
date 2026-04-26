'use client';

import { useState } from 'react';
import LoginModal, { type AuthMode } from '@/auth/LoginModal';
import { useAuth } from '@/auth/AuthProvider';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.7, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

const problemAtHand = [
  {
    label: 'Friends',
    quote: '“You sound fine.”',
    description:
      'Subjective feedback builds false confidence and teaches nothing.',
  },
  {
    label: 'Advice',
    quote: '“Just be yourself.”',
    description:
      'Vague advice with no path forward. You leave the conversation the same way you arrived.',
  },
  {
    label: 'Recording',
    quote: '“Record yourself.”',
    description:
      'You watch it once, cringe, and close the tab. No structure. No diagnosis. No next step.',
  },
] as const;

export default function LandingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>('signin');

  const openAuth = (mode: AuthMode) => {
    if (user) {
      router.push('/home');
      return;
    }
    setAuthMode(mode);
    setIsLoginOpen(true);
  };

  return (
    <div className="min-h-screen bg-cream-100">
      <LoginModal
        isOpen={isLoginOpen}
        initialMode={authMode}
        onClose={() => setIsLoginOpen(false)}
        onSuccess={() => {
          setIsLoginOpen(false);
          router.push('/home');
        }}
      />

      {/* Grain overlay */}
      <div
        className="fixed inset-0 pointer-events-none z-[100] opacity-[0.03]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
          backgroundSize: '256px 256px',
        }}
      />

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-8 pt-8 pb-4 max-w-[1200px] mx-auto">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center gap-2.5"
        >
          <div className="w-9 h-9 rounded-xl bg-navy-500 flex items-center justify-center">
            <Sparkles size={18} className="text-white" />
          </div>
          <span className="font-serif text-2xl font-semibold text-slate-900">
            Clarity
          </span>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center gap-3"
        >
          <button
            onClick={() => openAuth('signin')}
            className="px-5 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors rounded-full hover:bg-cream-200"
          >
            Log in
          </button>
          <button
            onClick={() => openAuth('signup')}
            className="px-5 py-2 text-sm bg-navy-500 text-white rounded-full hover:bg-navy-600 transition-all shadow-md"
          >
            Get started
          </button>
        </motion.div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-20 pb-12 md:pb-16 px-6 flex flex-col items-center text-center overflow-hidden">
        {/* 3D Decorative Elements */}
        <motion.img
          src="/hero-3d-elements.png"
          alt=""
          initial={{ opacity: 0, z: -500, filter: 'blur(20px)' }}
          animate={{ opacity: 0.15, z: 0, filter: 'blur(0px)' }}
          transition={{ duration: 1.5, ease: [0.16, 1, 0.3, 1] }}
          className="absolute top-20 right-[10%] w-64 h-64 pointer-events-none"
        />
        <motion.img
          src="/hero-3d-elements.png"
          alt=""
          initial={{ opacity: 0, z: -500, filter: 'blur(20px)' }}
          animate={{ opacity: 0.1, z: 0, filter: 'blur(0px)' }}
          transition={{ duration: 1.5, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="absolute bottom-20 left-[5%] w-48 h-48 pointer-events-none rotate-180"
        />

        {/* Eyebrow */}
        <motion.div
          custom={0}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-navy-500/10 text-navy-500 text-sm font-medium mb-8"
        >
          AI Communication Coach
        </motion.div>

        {/* Heading */}
        <motion.h1
          custom={1}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="font-serif text-5xl md:text-6xl lg:text-7xl font-semibold text-slate-900 max-w-4xl leading-tight mb-6"
        >
          Speak with intention,
          <br />
          <span className="italic">land with impact</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          custom={2}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="text-lg text-slate-500 max-w-xl mb-10"
        >
          AI-powered feedback on facial expression, body language, vocal tone,
          and word choice — in real time.
        </motion.p>

        {/* CTAs */}
        <motion.div
          custom={3}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="flex items-center gap-4 mb-12"
        >
          <button
            onClick={() => openAuth('signup')}
            className="px-7 py-3 bg-navy-500 text-white rounded-full font-medium hover:bg-navy-600 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
          >
            Start practicing free
          </button>
          <button className="px-7 py-3 border border-cream-300 text-slate-700 rounded-full font-medium hover:bg-cream-200 transition-all">
            Watch demo
          </button>
        </motion.div>

        {/* Stats */}
        <motion.div
          custom={4}
          variants={fadeUp}
          initial="hidden"
          animate="visible"
          className="flex items-center gap-4 mb-16"
        >
          {['10k+ sessions', '3 analysis modes', 'Real-time feedback'].map(
            (stat) => (
              <span
                key={stat}
                className="px-4 py-2 rounded-full bg-cream-50 border border-cream-300 text-sm text-slate-600"
              >
                {stat}
              </span>
            )
          )}
        </motion.div>

      </section>

      {/* Problem at hand */}
      <section className="pt-6 pb-16 sm:pt-8 sm:pb-20 bg-cream-100">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="text-center mb-9 sm:mb-10 max-w-3xl mx-auto"
          >
            <h2 className="font-serif text-3xl md:text-4xl font-semibold text-slate-900 mb-3 leading-tight">
              Most people never get real feedback on how they communicate.
            </h2>
            <p className="text-slate-500 text-base md:text-lg leading-relaxed">
              The gap between how you think you sound and how you actually land
              — that gap costs opportunities. Friends are kind, not calibrated.
              Vague advice teaches nothing. Recording yourself leads to cringe,
              not growth.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {problemAtHand.map((item, i) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0, y: 32 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{
                  duration: 0.65,
                  delay: i * 0.12,
                  ease: [0.16, 1, 0.3, 1],
                }}
                className="bg-white rounded-2xl border border-cream-300 p-6 md:p-8 shadow-sm"
              >
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-slate-400 mb-4">
                  {item.label}
                </p>
                <p className="font-serif text-xl font-semibold text-slate-900 mb-4 leading-snug">
                  {item.quote}
                </p>
                <p className="text-sm text-slate-500 leading-relaxed">
                  {item.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-cream-200 py-8 px-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-navy-500 flex items-center justify-center">
              <Sparkles size={14} className="text-white" />
            </div>
            <span className="font-serif text-lg font-semibold text-slate-900">
              Clarity
            </span>
          </div>
        </div>
      </footer>

    </div>
  );
}
