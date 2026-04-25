'use client';

import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Zap, MessageSquare, Mic, ArrowRight } from 'lucide-react';

const modes = [
  {
    icon: Zap,
    name: 'Emotion Sprint',
    description: 'Practice delivering lines in a specific emotional tone',
    color: 'bg-navy-500',
    path: '/sprint',
  },
  {
    icon: MessageSquare,
    name: 'Conversation',
    description: 'Simulate interviews, negotiations, or casual chats',
    color: 'bg-teal-500',
    path: '/conversation',
  },
  {
    icon: Mic,
    name: 'Free Speaking',
    description: 'Give a speech or freestyle talk for full analysis',
    color: 'bg-amber-500',
    path: '/free',
  },
];

const recentSessions = [
  {
    icon: Zap,
    name: 'Confidence Sprint',
    date: 'Apr 22, 2025',
    score: 84,
    color: 'text-navy-500',
  },
  {
    icon: MessageSquare,
    name: 'Interview Practice',
    date: 'Apr 20, 2025',
    score: 78,
    color: 'text-teal-500',
  },
  {
    icon: Mic,
    name: 'Free Speech: Project Update',
    date: 'Apr 18, 2025',
    score: 91,
    color: 'text-amber-500',
  },
];

export default function DashboardPage() {
  const router = useRouter();

  return (
    <div className="max-w-5xl mx-auto">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mb-10"
      >
        <h1
          className="font-['Playfair_Display'] text-[28px] font-semibold text-slate-900 mb-1"
        >
          Good morning, Jordan
        </h1>
        <p className="text-slate-500">What are we working on today?</p>
      </motion.div>

      {/* Mode Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
        {modes.map((mode, i) => (
          <motion.div
            key={mode.name}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            whileHover={{ y: -2, boxShadow: '0 10px 40px rgba(0,0,0,0.08)' }}
            onClick={() => router.push(mode.path)}
            className="bg-white rounded-2xl border border-cream-300 overflow-hidden cursor-pointer transition-all duration-200 shadow-sm"
          >
            {/* Accent bar */}
            <div className={`h-1.5 rounded-t-2xl ${mode.color}`} />
            <div className="p-6">
              <mode.icon size={22} className={`${mode.color.replace('bg-', 'text-')} mb-4`} />
              <h3 className="font-semibold text-slate-900 mb-1">{mode.name}</h3>
              <p className="text-sm text-slate-500 mb-4">{mode.description}</p>
              <span className="inline-flex items-center gap-1 text-sm text-navy-500 font-medium">
                Start session <ArrowRight size={14} />
              </span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Recent Sessions */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <h2 className="font-['Playfair_Display'] text-xl font-semibold text-slate-900 mb-4">
          Recent sessions
        </h2>
        <div className="bg-white rounded-2xl border border-cream-300 overflow-hidden shadow-sm">
          {recentSessions.map((session, i) => (
            <button
              key={i}
              onClick={() => router.push('/replays')}
              className={`w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-cream-50 transition-colors ${
                i < recentSessions.length - 1 ? 'border-b border-cream-200' : ''
              }`}
            >
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center shrink-0">
                <session.icon size={18} className={session.color} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">
                  {session.name}
                </p>
                <p className="text-xs text-slate-500">{session.date}</p>
              </div>
              <span className="px-3 py-1 rounded-full bg-cream-100 text-xs font-medium text-slate-700 shrink-0">
                {session.score}
              </span>
            </button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
