import { MessageSquare, Mic, Zap, type LucideIcon } from 'lucide-react';

import type { SessionMode, SessionPreview } from '@/hooks/useSessions';

type SessionModeDisplay = {
  icon: LucideIcon;
  iconClassName: string;
  badgeClassName: string;
};

export const SESSION_MODE_DISPLAY: Record<SessionMode, SessionModeDisplay> = {
  phase_a: {
    icon: Zap,
    iconClassName: 'text-navy-500',
    badgeClassName: 'bg-navy-50 text-navy-700 border-navy-200',
  },
  phase_b: {
    icon: MessageSquare,
    iconClassName: 'text-teal-500',
    badgeClassName: 'bg-teal-50 text-teal-700 border-teal-200',
  },
  phase_c: {
    icon: Mic,
    iconClassName: 'text-amber-500',
    badgeClassName: 'bg-amber-50 text-amber-700 border-amber-200',
  },
};

export function formatSessionDate(value: string | null | undefined) {
  if (!value) {
    return 'Unknown date';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unknown date';
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function formatSessionMeta(session: SessionPreview) {
  if (typeof session.duration_seconds === 'number') {
    return `${session.duration_seconds.toFixed(1)}s`;
  }
  if (typeof session.total_turns === 'number') {
    return `${session.total_turns} turns`;
  }
  if (typeof session.round_count === 'number') {
    return `${session.round_count} rounds`;
  }
  return session.status.replace('_', ' ');
}

export function scoreBadgeClassName(score: number | null | undefined) {
  if (typeof score !== 'number') {
    return 'bg-cream-100 text-slate-700';
  }
  if (score >= 80) {
    return 'bg-emerald-50 text-emerald-700';
  }
  if (score >= 60) {
    return 'bg-amber-50 text-amber-700';
  }
  return 'bg-rose-50 text-rose-700';
}
