'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Zap,
  MessageSquare,
  Mic,
  X,
  FileText,
} from 'lucide-react';

interface Session {
  id: number;
  icon: typeof Zap;
  name: string;
  date: string;
  duration: string;
  score: number;
  emotions: string[];
  color: string;
  breakdown: { label: string; value: number }[];
  feedback: string;
}

const sessions: Session[] = [
  {
    id: 1,
    icon: Zap,
    name: 'Confidence Sprint',
    date: 'Apr 22, 2025',
    duration: '1:24',
    score: 84,
    emotions: ['Confident', 'Assertive'],
    color: 'text-navy-500',
    breakdown: [
      { label: 'Clarity', value: 88 },
      { label: 'Tone Match', value: 91 },
      { label: 'Pacing', value: 76 },
      { label: 'Body Language', value: 82 },
    ],
    feedback:
      'Strong confident delivery with excellent tone alignment. Your pacing slowed slightly in the second half — try maintaining consistent energy throughout.',
  },
  {
    id: 2,
    icon: MessageSquare,
    name: 'Interview Practice',
    date: 'Apr 20, 2025',
    duration: '3:42',
    score: 78,
    emotions: ['Calm', 'Neutral'],
    color: 'text-teal-500',
    breakdown: [
      { label: 'Clarity', value: 82 },
      { label: 'Tone Match', value: 74 },
      { label: 'Pacing', value: 80 },
      { label: 'Body Language', value: 75 },
    ],
    feedback:
      'Good calm demeanor appropriate for the context. Work on adding more variation in vocal tone to avoid sounding monotone. Eye contact was steady.',
  },
  {
    id: 3,
    icon: Mic,
    name: 'Free Speech: Project Update',
    date: 'Apr 18, 2025',
    duration: '2:55',
    score: 91,
    emotions: ['Enthusiastic', 'Confident'],
    color: 'text-amber-500',
    breakdown: [
      { label: 'Clarity', value: 94 },
      { label: 'Tone Match', value: 89 },
      { label: 'Pacing', value: 92 },
      { label: 'Body Language', value: 88 },
    ],
    feedback:
      'Outstanding delivery! Your enthusiasm was contagious and well-measured. Pacing was excellent with natural pauses. Minimal filler words detected.',
  },
  {
    id: 4,
    icon: Zap,
    name: 'Empathy Sprint',
    date: 'Apr 15, 2025',
    duration: '0:58',
    score: 72,
    emotions: ['Empathetic', 'Vulnerable'],
    color: 'text-navy-500',
    breakdown: [
      { label: 'Clarity', value: 78 },
      { label: 'Tone Match', value: 68 },
      { label: 'Pacing', value: 74 },
      { label: 'Body Language', value: 70 },
    ],
    feedback:
      'Good attempt at empathetic delivery. Your tone softened appropriately but could go further. Try speaking more slowly and using warmer vocal inflection.',
  },
  {
    id: 5,
    icon: MessageSquare,
    name: 'Negotiation: Budget Discussion',
    date: 'Apr 12, 2025',
    duration: '4:18',
    score: 80,
    emotions: ['Assertive', 'Calm'],
    color: 'text-teal-500',
    breakdown: [
      { label: 'Clarity', value: 85 },
      { label: 'Tone Match', value: 82 },
      { label: 'Pacing', value: 78 },
      { label: 'Body Language', value: 76 },
    ],
    feedback:
      'Solid negotiation presence. You maintained composure while being assertive. Watch for slight tension in shoulders — relaxation signals confidence.',
  },
];

export default function ReplaysPage() {
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Replays
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Review your past practice sessions
        </p>
      </div>

      {/* Session Cards */}
      <div className="space-y-4">
        {sessions.map((session, i) => (
          <motion.div
            key={session.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.08 }}
            className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-center gap-4">
              {/* Icon */}
              <div className="w-12 h-12 rounded-xl bg-cream-100 flex items-center justify-center shrink-0">
                <session.icon size={22} className={session.color} />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <h3 className="font-medium text-slate-900 truncate">
                  {session.name}
                </h3>
                <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                  <span>{session.date}</span>
                  <span>{session.duration}</span>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  {session.emotions.map((emotion) => (
                    <span
                      key={emotion}
                      className="px-2 py-0.5 rounded-full bg-cream-100 text-xs text-slate-600"
                    >
                      {emotion}
                    </span>
                  ))}
                </div>
              </div>

              {/* Score + Action */}
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-center">
                  <p className="text-2xl font-semibold text-navy-500">
                    {session.score}
                  </p>
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">
                    Score
                  </p>
                </div>
                <button
                  onClick={() => setSelectedSession(session)}
                  className="px-4 py-2 rounded-full bg-navy-500 text-white text-sm font-medium hover:bg-navy-600 transition-colors shadow-sm"
                >
                  View replay
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Modal */}
      <AnimatePresence>
        {selectedSession && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
            onClick={() => setSelectedSession(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ duration: 0.25 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-cream-50 rounded-2xl border border-cream-300 shadow-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto"
            >
              {/* Modal Header */}
              <div className="flex items-center justify-between p-6 border-b border-cream-200">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                    <selectedSession.icon
                      size={20}
                      className={selectedSession.color}
                    />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      {selectedSession.name}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {selectedSession.date} · {selectedSession.duration}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSession(null)}
                  className="w-8 h-8 rounded-full bg-cream-200 flex items-center justify-center hover:bg-cream-300 transition-colors"
                >
                  <X size={16} className="text-slate-600" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6">
                {/* Big Score */}
                <div className="text-center mb-6">
                  <p className="font-['Playfair_Display'] text-6xl font-bold text-navy-500">
                    {selectedSession.score}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">Overall Score</p>
                </div>

                {/* Breakdown */}
                <div className="bg-white rounded-xl border border-cream-300 p-5 mb-5">
                  {selectedSession.breakdown.map((item, i) => (
                    <div
                      key={item.label}
                      className={`flex items-center gap-4 py-3 ${
                        i < selectedSession.breakdown.length - 1
                          ? 'border-b border-cream-100'
                          : ''
                      }`}
                    >
                      <span className="text-sm text-slate-600 w-28">
                        {item.label}
                      </span>
                      <div className="flex-1 h-2 bg-cream-200 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${item.value}%` }}
                          transition={{ duration: 0.6, delay: i * 0.1 }}
                          className="h-full rounded-full bg-navy-500"
                        />
                      </div>
                      <span className="text-sm font-medium text-slate-900 w-8 text-right">
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Feedback */}
                <div className="bg-white rounded-xl border-l-4 border-navy-500 border border-cream-300 p-5">
                  <div className="flex items-center gap-2 mb-2">
                    <FileText size={14} className="text-navy-500" />
                    <span className="text-xs font-medium text-navy-500 uppercase tracking-wider">
                      AI Feedback
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {selectedSession.feedback}
                  </p>
                </div>

                {/* Emotion Tags */}
                <div className="flex items-center gap-2 mt-5">
                  <span className="text-xs text-slate-500">Emotions:</span>
                  {selectedSession.emotions.map((emotion) => (
                    <span
                      key={emotion}
                      className="px-3 py-1 rounded-full bg-cream-200 text-xs text-slate-600"
                    >
                      {emotion}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
