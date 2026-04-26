'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, RotateCcw } from 'lucide-react';
import type { FinalReport, PeerProfile } from '@/hooks/usePhaseBConversation';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

type SessionStateResponse = {
  session_id: string;
  practice_prompt: string | null;
  scenario: string | null;
  peer_profile: PeerProfile | null;
  starter_topic: string | null;
  turns: Array<{ turn_index: number }>;
  final_report: FinalReport | null;
  status: 'active' | 'complete' | 'error';
};

type EndSessionResponse = {
  status: string;
  turns: Array<{ turn_index: number }>;
  final_report?: FinalReport | null;
};

type ReportSurfaceState =
  | { status: 'loading'; context: SessionStateResponse | null }
  | { status: 'ready'; context: SessionStateResponse | null; report: FinalReport; turnCount: number }
  | { status: 'error'; context: SessionStateResponse | null; message: string };

export default function ConversationReportPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get('sessionId')?.trim() ?? '';
  const [reloadToken, setReloadToken] = useState(0);
  const [surface, setSurface] = useState<ReportSurfaceState>({ status: 'loading', context: null });

  useEffect(() => {
    if (!sessionId) {
      router.replace('/conversation');
      return;
    }

    let isCancelled = false;

    async function loadReport() {
      const existingSession = await fetchSessionState(sessionId);
      if (isCancelled) {
        return;
      }

      if (existingSession?.final_report) {
        setSurface({
          status: 'ready',
          context: existingSession,
          report: existingSession.final_report,
          turnCount: existingSession.turns.length,
        });
        return;
      }

      setSurface({ status: 'loading', context: existingSession });

      try {
        const response = await fetch(`${API_URL}/api/phase-b/sessions/${sessionId}/end`, {
          method: 'POST',
        });

        if (!response.ok) {
          const detail = await safeDetail(response);
          throw new Error(detail || 'Could not finish building the final report.');
        }

        const data = (await response.json()) as EndSessionResponse;
        if (isCancelled) {
          return;
        }

        const refreshedSession = (await fetchSessionState(sessionId)) ?? existingSession;
        const report = data.final_report ?? refreshedSession?.final_report;
        if (!report) {
          throw new Error('The final report was not available yet. Please try again.');
        }

        setSurface({
          status: 'ready',
          context: refreshedSession,
          report,
          turnCount: data.turns.length,
        });
      } catch (error) {
        if (isCancelled) {
          return;
        }
        setSurface({
          status: 'error',
          context: existingSession,
          message: getErrorMessage(error, 'Could not finish building the final report.'),
        });
      }
    }

    void loadReport();

    return () => {
      isCancelled = true;
    };
  }, [router, sessionId, reloadToken]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="rounded-[32px] border border-cream-200 bg-white p-8 shadow-sm sm:p-10">
        <p className="text-sm font-semibold uppercase tracking-widest text-navy-500">Conversation Debrief</p>
        <h1 className="mt-4 font-['Playfair_Display'] text-4xl font-semibold leading-tight text-slate-900 sm:text-5xl">
          {surface.status === 'ready' ? 'Your final report is ready' : 'Compiling your final report'}
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">
          {surface.status === 'ready'
            ? 'Review the conversation outcome, where your delivery landed, and what to tighten before the next run.'
            : 'Hold here while we close the session, gather the last analysis, and compile the full report.'}
        </p>

        {surface.context ? (
          <div className="mt-6 rounded-[28px] border border-cream-200 bg-[linear-gradient(140deg,#fffdf7_0%,#f8f2e2_58%,#eef4ff_100%)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Session Context</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">
                  {surface.context.peer_profile
                    ? `${surface.context.peer_profile.name} • ${surface.context.peer_profile.role}`
                    : 'Conversation session'}
                </p>
                <p className="mt-1 text-sm text-slate-500">
                  {surface.context.scenario ?? surface.context.peer_profile?.scenario ?? 'Conversation'} • topic:{' '}
                  {surface.context.starter_topic ?? 'Loading'}
                </p>
              </div>
              {surface.status === 'ready' && (
                <div className="rounded-2xl bg-white/90 px-4 py-3 text-right shadow-sm ring-1 ring-cream-200">
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Completed turns</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">{surface.turnCount}</p>
                </div>
              )}
            </div>
            {surface.context.practice_prompt ? (
              <p className="mt-4 rounded-2xl bg-white/80 px-4 py-3 text-sm leading-6 text-slate-600 shadow-sm ring-1 ring-cream-200">
                Simulating: {surface.context.practice_prompt}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      {surface.status === 'loading' && (
        <section className="rounded-[32px] border border-cream-200 bg-white p-10 shadow-sm">
          <div className="flex flex-col items-center justify-center text-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-navy-50 text-navy-500">
              <Loader2 className="h-10 w-10 animate-spin" />
            </div>
            <p className="mt-6 text-xl font-semibold text-slate-900">Finalizing conversation analysis</p>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
              We are waiting for the backend to finish the last report pass. This can take a few seconds depending on
              model latency.
            </p>
          </div>
        </section>
      )}

      {surface.status === 'error' && (
        <section className="rounded-[32px] border border-red-200 bg-white p-8 shadow-sm">
          <p className="text-sm font-semibold uppercase tracking-widest text-red-500">Report Error</p>
          <h2 className="mt-3 text-2xl font-semibold text-slate-900">The final report did not finish cleanly</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">{surface.message}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setReloadToken((current) => current + 1)}
              className="inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-navy-600"
            >
              <RotateCcw className="h-4 w-4" />
              Try again
            </button>
            <button
              type="button"
              onClick={() => router.push('/conversation')}
              className="rounded-full border border-cream-300 px-5 py-3 text-sm font-medium text-slate-700 transition hover:bg-cream-100"
            >
              Back to conversation setup
            </button>
          </div>
        </section>
      )}

      {surface.status === 'ready' && (
        <section className="rounded-[32px] border border-cream-200 bg-white p-8 shadow-sm sm:p-10">
          <p className="text-sm font-semibold uppercase tracking-widest text-navy-500">Final Report</p>
          <p className="mt-5 text-lg leading-8 text-slate-700">{surface.report.summary}</p>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <ScoreTile label="Momentum" value={surface.report.conversation_momentum_score} />
            <ScoreTile label="Content" value={surface.report.content_quality_score} />
            <ScoreTile label="Delivery" value={surface.report.emotional_delivery_score} />
            <ScoreTile label="Energy" value={surface.report.energy_match_score} />
            <ScoreTile label="Authenticity" value={surface.report.authenticity_score} />
            <ScoreTile label="Follow-up" value={surface.report.follow_up_invitation_score} />
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[28px] bg-cream-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Why it ended</p>
              <p className="mt-3 text-sm leading-6 text-slate-700">{surface.report.natural_ending_reason}</p>
            </div>
            <div className="rounded-[28px] border border-navy-100 bg-navy-50 p-5">
              <p className="text-xs font-semibold uppercase tracking-widest text-navy-500">Next focus</p>
              <p className="mt-3 text-sm leading-6 text-navy-900">{surface.report.next_focus}</p>
            </div>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-2">
            <BulletList title="Strengths" items={surface.report.strengths} />
            <BulletList title="Growth edges" items={surface.report.growth_edges} />
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => router.push('/conversation')}
              className="inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-navy-600"
            >
              <RotateCcw className="h-4 w-4" />
              Start another session
            </button>
            <button
              type="button"
              onClick={() => router.push('/home')}
              className="rounded-full border border-cream-300 px-5 py-3 text-sm font-medium text-slate-700 transition hover:bg-cream-100"
            >
              Back to home
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

async function fetchSessionState(sessionId: string) {
  const response = await fetch(`${API_URL}/api/phase-b/sessions/${sessionId}`);
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as SessionStateResponse;
}

async function safeDetail(response: Response) {
  try {
    const data = (await response.json()) as { detail?: unknown };
    return typeof data.detail === 'string' ? data.detail : '';
  } catch {
    return '';
  }
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[24px] bg-cream-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-900">{Math.round(value)}</p>
    </div>
  );
}

function BulletList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[28px] border border-cream-200 bg-white p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{title}</p>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <div key={item} className="rounded-2xl bg-cream-50 px-4 py-3 text-sm leading-6 text-slate-700">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
}
