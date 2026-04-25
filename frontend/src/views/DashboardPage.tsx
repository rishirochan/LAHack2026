'use client';

import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Zap, MessageSquare, Mic, ArrowRight, Loader2 } from 'lucide-react';

import { useSessionsContext } from '@/context/SessionsContext';
import { formatSessionDate, formatSessionMeta, scoreBadgeClassName, SESSION_MODE_DISPLAY } from '@/lib/session-display';

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

export default function DashboardPage() {
  const router = useRouter();
  const { recentSessions, loading, error } = useSessionsContext();

  return (
    <div className="max-w-5xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mb-10"
      >
        <h1
          className="mb-1 font-['Playfair_Display'] text-2xl font-semibold text-slate-900"
        >
          Good morning, Jordan
        </h1>
        <p className="text-slate-500">What are we working on today?</p>
      </motion.div>

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

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <h2 className="font-['Playfair_Display'] text-xl font-semibold text-slate-900 mb-4">
          Recent sessions
        </h2>
        <div className="bg-white rounded-2xl border border-cream-300 overflow-hidden shadow-sm">
          {loading && (
            <div className="flex items-center gap-3 px-5 py-4 text-sm text-slate-600">
              <Loader2 size={16} className="animate-spin text-navy-500" />
              Loading recent sessions
            </div>
          )}

          {!loading && error && (
            <div className="px-5 py-4 text-sm text-rose-600">{error}</div>
          )}

          {!loading && !error && recentSessions.length === 0 && (
            <div className="px-5 py-4 text-sm text-slate-500">
              No practice sessions yet. Complete a mode to populate this list.
            </div>
          )}

          {!loading && !error && recentSessions.slice(0, 5).map((session, index, items) => {
            const modeDisplay = SESSION_MODE_DISPLAY[session.mode];
            return (
              <button
                key={session.session_id}
                onClick={() => router.push(`/replays?session=${encodeURIComponent(session.session_id)}`)}
                className={`w-full flex items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-cream-50 ${
                  index < items.length - 1 ? 'border-b border-cream-200' : ''
                }`}
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-cream-100">
                  <modeDisplay.icon size={18} className={modeDisplay.iconClassName} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-900">{session.label}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {formatSessionDate(session.completed_at || session.updated_at || session.created_at)} · {formatSessionMeta(session)}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${scoreBadgeClassName(session.score)}`}>
                  {session.score ?? '--'}
                </span>
              </button>
            );
          })}
        </div>
      </motion.div>
    </div>
  );
}
