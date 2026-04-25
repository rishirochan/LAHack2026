"use client";

import { Mic, MessageSquare, AudioLines, ArrowRight, Calendar } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RecentSession = {
  session_id: string;
  label: string;
  mode_label: "Emotion Drills" | "Conversations" | "Free Speaking";
  status: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
  score?: number | null;
  total_turns?: number | null;
  round_count?: number | null;
};

const modeIcon = {
  "Emotion Drills": Mic,
  Conversations: MessageSquare,
  "Free Speaking": AudioLines,
};

export default function DashboardHome() {
  const [recentSessions, setRecentSessions] = useState<RecentSession[]>([]);
  const [isLoadingRecent, setIsLoadingRecent] = useState(true);

  useEffect(() => {
    let isMounted = true;

    async function loadRecentSessions() {
      try {
        const response = await fetch(`${API_URL}/api/sessions/recent?limit=10`);
        if (!response.ok) {
          throw new Error("Could not load recent sessions.");
        }
        const data = (await response.json()) as { sessions: RecentSession[] };
        if (isMounted) {
          setRecentSessions(data.sessions);
        }
      } catch {
        if (isMounted) {
          setRecentSessions([]);
        }
      } finally {
        if (isMounted) {
          setIsLoadingRecent(false);
        }
      }
    }

    void loadRecentSessions();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div>
      {/* Hero greeting */}
      <div className="flex flex-col items-center text-center pt-16 pb-14">
        <h1 className="text-6xl font-bold text-foreground mb-4 tracking-tight">
          Welcome, <span className="text-blue-600">User</span>
        </h1>
        <p className="text-2xl text-foreground/60 font-medium">
          Your voice is ready when you are.
        </p>
      </div>

      {/* Practice cards */}
      <div className="grid md:grid-cols-3 gap-6">
        <Link
          href="/dashboard/emotion-drills"
          className="group bg-white rounded-2xl p-6 border border-cream-200 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/5 transition-all duration-200"
        >
          <div className="w-11 h-11 rounded-xl bg-blue-600/10 flex items-center justify-center mb-4">
            <Mic className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">Emotion Drills</h3>
          <p className="text-sm text-foreground/50 mb-4 leading-relaxed">
            Practice delivering sentences with the right emotional tone and get instant AI feedback.
          </p>
          <span className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 group-hover:gap-2 transition-all">
            Start practice <ArrowRight className="w-4 h-4" />
          </span>
        </Link>

        <Link
          href="/dashboard/conversations"
          className="group bg-white rounded-2xl p-6 border border-cream-200 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/5 transition-all duration-200"
        >
          <div className="w-11 h-11 rounded-xl bg-blue-600/10 flex items-center justify-center mb-4">
            <MessageSquare className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">Conversations</h3>
          <p className="text-sm text-foreground/50 mb-4 leading-relaxed">
            Simulate interviews, negotiations, and coffee chats with a dynamic AI conversation partner.
          </p>
          <span className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 group-hover:gap-2 transition-all">
            Start practice <ArrowRight className="w-4 h-4" />
          </span>
        </Link>

        <Link
          href="/dashboard/free-speaking"
          className="group bg-white rounded-2xl p-6 border border-cream-200 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/5 transition-all duration-200"
        >
          <div className="w-11 h-11 rounded-xl bg-blue-600/10 flex items-center justify-center mb-4">
            <AudioLines className="w-5 h-5 text-blue-600" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">Free Speaking</h3>
          <p className="text-sm text-foreground/50 mb-4 leading-relaxed">
            Speak freely or rehearse a speech with full AI analysis of your delivery and expression.
          </p>
          <span className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 group-hover:gap-2 transition-all">
            Start practice <ArrowRight className="w-4 h-4" />
          </span>
        </Link>
      </div>

      {/* Divider */}
      <div className="flex items-center gap-4 mt-12 mb-6">
        <div className="flex-1 h-px bg-cream-300/70" />
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground/30">
          Recent Sessions
        </span>
        <div className="flex-1 h-px bg-cream-300/70" />
      </div>

      {/* Recent sessions */}
      <div className="bg-white rounded-2xl border border-cream-200 overflow-hidden">
        {/* Header row */}
        <div className="grid grid-cols-4 px-6 py-3 bg-cream-50 border-b border-cream-200 text-xs font-semibold uppercase tracking-wider text-foreground/30">
          <span>Mode</span>
          <span>Session</span>
          <span className="flex items-center gap-1">
            <Calendar className="w-3 h-3" /> Date
          </span>
          <span>Result</span>
        </div>

        {isLoadingRecent ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-xl bg-cream-100 flex items-center justify-center mb-3">
              <Mic className="w-5 h-5 text-foreground/20" />
            </div>
            <p className="text-sm font-medium text-foreground/40">Loading sessions...</p>
          </div>
        ) : recentSessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-xl bg-cream-100 flex items-center justify-center mb-3">
              <Mic className="w-5 h-5 text-foreground/20" />
            </div>
            <p className="text-sm font-medium text-foreground/40">No sessions yet</p>
            <p className="text-xs text-foreground/30 mt-1">
              Start a practice above and your sessions will appear here.
            </p>
          </div>
        ) : (
          recentSessions.map((session, i) => {
            const Icon = modeIcon[session.mode_label] ?? Mic;
            return (
              <div
                key={session.session_id}
                className={`grid grid-cols-4 px-6 py-4 items-center hover:bg-cream-50 transition-colors ${
                  i !== recentSessions.length - 1 ? "border-b border-cream-100" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-blue-600/10 flex items-center justify-center">
                    <Icon className="w-3.5 h-3.5 text-blue-600" />
                  </div>
                  <span className="text-sm font-medium text-foreground">{session.mode_label}</span>
                </div>
                <span className="text-sm text-foreground/60">{session.label}</span>
                <span className="text-sm text-foreground/50">{formatSessionDate(session.completed_at ?? session.updated_at ?? session.created_at)}</span>
                <span className="text-sm text-foreground/50">{formatSessionStatus(session)}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function formatSessionDate(value?: string) {
  if (!value) {
    return "Just now";
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatSessionStatus(session: RecentSession) {
  if (session.score !== null && session.score !== undefined) {
    return `${session.score}% avg`;
  }
  if (session.total_turns) {
    return `${session.total_turns} turns`;
  }
  if (session.round_count) {
    return `${session.round_count} rounds`;
  }
  return session.status === "complete" ? "Complete" : "In progress";
}
