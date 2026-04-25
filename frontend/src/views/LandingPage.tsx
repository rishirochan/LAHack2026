'use client';

import { useState } from 'react';
import LoginModal from '@/auth/LoginModal';
import { useAuth } from '@/auth/AuthProvider';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Zap, MessageSquare, Mic } from 'lucide-react';

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.7, ease: [0.16, 1, 0.3, 1] as const },
  }),
};

const features = [
  {
    icon: Zap,
    title: 'Emotion Sprint',
    description:
      'Pick an emotion, get 2-3 sentences to say in that style. Recording gets analyzed for facial expressions, body language, and vocal tone via computer vision and audio ML. Gemma synthesizes a detailed critique.',
    image: '/feature-sprint.jpg',
  },
  {
    icon: MessageSquare,
    title: 'Conversation Modes',
    description:
      'Choose interview, negotiation/sales, or coffee chat. AI generates a dynamic ~60 second back-and-forth. Same CV and audio pipeline plus sentiment analysis on transcript to check if words align with emotional delivery.',
    image: '/feature-conversation.jpg',
  },
  {
    icon: Mic,
    title: 'Speak Freely',
    description:
      'Give a speech or just talk. Full analysis pipeline runs at the end — emotion timeline, filler word counts, pacing, AI-generated pattern summary.',
    image: '/feature-free.jpg',
  },
];

export default function LandingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  const openLogin = () => {
    if (user) {
      router.push('/home');
      return;
    }
    setIsLoginOpen(true);
  };

  return (
    <div className="min-h-screen bg-cream-100">
      <LoginModal
        isOpen={isLoginOpen}
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

      {/* Navbar */}
      <motion.nav
        initial={{ y: -100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-cream-50/80 backdrop-blur-xl border border-cream-300 rounded-full px-6 py-3 flex items-center justify-between gap-8 shadow-[0_8px_32px_rgba(0,0,0,0.08)] max-w-[1200px] w-[90%]"
      >
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-navy-500 flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-['Playfair_Display'] text-xl font-semibold text-slate-900">
            Eloquence
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={openLogin}
            className="px-5 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors rounded-full hover:bg-cream-200"
          >
            Log in
          </button>
          <button
            onClick={openLogin}
            className="px-5 py-2 text-sm bg-navy-500 text-white rounded-full hover:bg-navy-600 transition-all shadow-md"
          >
            Get started
          </button>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="relative pt-40 pb-24 px-6 flex flex-col items-center text-center overflow-hidden">
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
          className="font-['Playfair_Display'] text-5xl md:text-6xl lg:text-7xl font-semibold text-slate-900 max-w-4xl leading-tight mb-6"
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
            onClick={openLogin}
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

        {/* Hero Image */}
        <motion.div
          initial={{ opacity: 0, rotateX: -45, y: 60 }}
          animate={{ opacity: 1, rotateX: 0, y: 0 }}
          transition={{ duration: 1.4, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          style={{ perspective: 1000 }}
          className="w-full max-w-2xl"
        >
          <motion.div
            whileHover={{ rotateY: 5, rotateX: -5 }}
            transition={{ type: 'spring', stiffness: 100 }}
            style={{ transformStyle: 'preserve-3d' }}
          >
            <img
              src="/hero-card.jpg"
              alt="Eloquence Score Card"
              className="w-full rounded-2xl shadow-2xl"
            />
          </motion.div>
        </motion.div>
      </section>

      {/* Features Section */}
      <section className="py-24 bg-cream-50">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="text-center mb-16"
          >
            <h2 className="font-['Playfair_Display'] text-4xl font-semibold text-slate-900 mb-4">
              Three ways to practice
            </h2>
            <p className="text-slate-500 text-lg">
              Choose the mode that fits your goals
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 40 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{
                  duration: 0.7,
                  delay: i * 0.15,
                  ease: [0.16, 1, 0.3, 1],
                }}
                whileHover={{ y: -6, scale: 1.02 }}
                className="group relative bg-white rounded-2xl border border-cream-300 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300"
              >
                {/* Gloss sweep */}
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none z-10">
                  <div
                    className="absolute inset-0"
                    style={{
                      background:
                        'linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.5) 50%, transparent 70%)',
                      backgroundSize: '200% 100%',
                      animation: 'glossSweep 1s ease forwards',
                    }}
                  />
                </div>

                <div className="h-48 overflow-hidden bg-cream-100">
                  <img
                    src={feature.image}
                    alt={feature.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                </div>
                <div className="p-6">
                  <div className="w-10 h-10 rounded-xl bg-navy-500/10 flex items-center justify-center mb-4">
                    <feature.icon size={22} className="text-navy-500" />
                  </div>
                  <h3 className="font-['Playfair_Display'] text-xl font-semibold text-slate-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-slate-500 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
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
              <Zap size={14} className="text-white" />
            </div>
            <span className="font-['Playfair_Display'] text-lg font-semibold text-slate-900">
              Eloquence
            </span>
          </div>
          <p className="text-sm text-slate-500">
            Built at LA Hacks 2025
          </p>
        </div>
      </footer>

      <style>{`
        @keyframes glossSweep {
          from { background-position: 200% 0; }
          to { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
