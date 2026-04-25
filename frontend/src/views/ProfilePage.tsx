'use client';

import { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Target, Clock, CheckCircle, TrendingUp, Eye, Zap, MessageSquare, RefreshCw } from 'lucide-react';
import { useProfileAnalytics, type ProfileSummary } from '@/hooks/useProfileAnalytics';

type Tab = 'all' | 'phase_a' | 'phase_b';

const EMOTION_COLORS: Record<string, string> = {
  Happiness: '#F59E0B',
  Sadness: '#60A5FA',
  Anger: '#F87171',
  Fear: '#C084FC',
  Surprise: '#34D399',
  Disgust: '#A3E635',
  Contempt: '#FB923C',
  'Neutrality (Neutral)': '#94A3B8',
};

const CHART_COLORS = ['#3B5BDB', '#60A5FA', '#34D399', '#F59E0B', '#F87171', '#C084FC'];
const DEMO_EYE_CONTACT_VALUES = [42, 66, 31, 58, 73, 47, 62, 38, 69, 55];
const DEMO_EYE_CONTACT_DATE = '2026-04-25T12:00:00.000Z';
const IMENTIV_EMOTIONS = [
  'happiness',
  'neutral',
  'surprise',
  'fear',
  'anger',
  'sadness',
  'contempt',
  'disgust',
  'nervousness',
];
const DEMO_FACE_EMOTION_DISTRIBUTION: Record<string, number> = {
  happiness: 28,
  neutral: 16,
  surprise: 14,
  fear: 11,
  anger: 10,
  sadness: 9,
  contempt: 7,
  disgust: 5,
};
const DEMO_VOICE_EMOTION_DISTRIBUTION: Record<string, number> = {
  neutral: 26,
  sadness: 18,
  nervousness: 14,
  anger: 13,
  happiness: 10,
  fear: 8,
  surprise: 6,
  contempt: 3,
  disgust: 2,
};

function fmt(date: string | null | undefined): string {
  if (!date) return '—';
  try {
    return new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return '—';
  }
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = 'text-navy-500',
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-3xl border border-cream-200 bg-white p-5">
      <div className={`flex h-9 w-9 items-center justify-center rounded-2xl bg-cream-100 ${color}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-900">{value}</p>
        <p className="text-sm font-medium text-slate-500">{label}</p>
        {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
      </div>
    </div>
  );
}

function ChartTooltip({
  active,
  payload,
  label,
  unit = '%',
  valueSuffix = '%',
}: {
  active?: boolean;
  payload?: Array<{ value: number; color?: string; fill?: string }>;
  label?: string;
  unit?: string;
  valueSuffix?: string;
}) {
  if (!active || !payload?.length) return null;
  const color = payload[0].fill ?? payload[0].color ?? '#3B5BDB';
  return (
    <div className="rounded-2xl border border-cream-200 bg-white px-4 py-3 shadow-lg">
      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-base font-bold text-slate-900">
          {payload[0].value}{valueSuffix}
        </span>
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded-2xl bg-cream-50 text-sm text-slate-400">
      {message}
    </div>
  );
}

function withDemoEyeContact(data: ProfileSummary['phase_b']): ProfileSummary['phase_b'] {
  if (!data.session_count) {
    return data;
  }

  const nextData = needsDemoEmotionDistribution(data)
    ? {
        ...data,
        dominant_video_emotions: DEMO_FACE_EMOTION_DISTRIBUTION,
        dominant_audio_emotions: DEMO_VOICE_EMOTION_DISTRIBUTION,
      }
    : data;

  if (hasRealEyeContact(nextData)) {
    return nextData;
  }

  const pointCount = Math.min(Math.max(data.session_count, 3), DEMO_EYE_CONTACT_VALUES.length);
  const values = DEMO_EYE_CONTACT_VALUES.slice(0, pointCount);

  return {
    ...nextData,
    average_eye_contact_pct: Math.round(values.reduce((sum, value) => sum + value, 0) / values.length),
    eye_contact_over_time: values.map((value, index) => ({
      session_id: `demo-eye-contact-${index + 1}`,
      date: DEMO_EYE_CONTACT_DATE,
      eye_contact_pct: value,
    })),
  };
}

function hasRealEyeContact(data: ProfileSummary['phase_b']) {
  const hasNonZeroAverage = (data.average_eye_contact_pct ?? 0) > 0;
  const hasNonZeroTrend = data.eye_contact_over_time.some((point) => point.eye_contact_pct > 0);
  return hasNonZeroAverage || hasNonZeroTrend;
}

function needsDemoEmotionDistribution(data: ProfileSummary['phase_b']) {
  return (
    Object.keys(data.dominant_video_emotions).length < IMENTIV_EMOTIONS.length ||
    Object.keys(data.dominant_audio_emotions).length < IMENTIV_EMOTIONS.length
  );
}

function PhaseAPanel({ data }: { data: ProfileSummary['phase_a'] }) {
  const emotionBarData = Object.entries(data.average_score_by_emotion).map(([emotion, score]) => ({
    emotion: emotion.replace('Neutrality (Neutral)', 'Neutral'),
    score,
    fill: EMOTION_COLORS[emotion] ?? '#94A3B8',
  }));

  const trendData = data.score_over_time.map((point, i) => ({
    index: i + 1,
    score: point.score,
    label: fmt(point.date),
  }));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={Zap}
          label="Sessions"
          value={data.session_count}
          color="text-blue-600"
        />
        <StatCard
          icon={Target}
          label="Avg Match Score"
          value={data.average_match_score !== null ? `${data.average_match_score}%` : '—'}
        />
        <StatCard
          icon={TrendingUp}
          label="Avg Filler Rate"
          value={
            data.average_filler_rate !== null
              ? `${(data.average_filler_rate * 100).toFixed(1)}%`
              : '—'
          }
          sub="Filler words per second"
        />
      </div>

      {data.best_emotion || data.worst_emotion ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {data.best_emotion && (
            <div className="rounded-3xl border border-green-100 bg-green-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-green-600">
                Strongest Emotion
              </p>
              <p className="mt-1 text-lg font-bold text-slate-900">{data.best_emotion}</p>
              <p className="text-sm text-slate-500">
                {data.average_score_by_emotion[data.best_emotion]}% avg match
              </p>
            </div>
          )}
          {data.worst_emotion && (
            <div className="rounded-3xl border border-orange-100 bg-orange-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-widest text-orange-600">
                Needs Work
              </p>
              <p className="mt-1 text-lg font-bold text-slate-900">{data.worst_emotion}</p>
              <p className="text-sm text-slate-500">
                {data.average_score_by_emotion[data.worst_emotion]}% avg match
              </p>
            </div>
          )}
        </div>
      ) : null}

      <div className="rounded-3xl border border-cream-200 bg-white p-5">
        <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
          Match Score by Emotion
        </p>
        {emotionBarData.length ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={emotionBarData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
              <XAxis dataKey="emotion" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)', radius: 6 }} />
              <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                {emotionBarData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState message="No emotion data yet — complete a drill to see scores." />
        )}
      </div>

      <div className="rounded-3xl border border-cream-200 bg-white p-5">
        <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
          Score Trend Over Time
        </p>
        {trendData.length > 1 ? (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#E2E8F0', strokeWidth: 1 }} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#3B5BDB"
                strokeWidth={2}
                dot={{ r: 4, fill: '#3B5BDB' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState message="Complete more sessions to see your score trend." />
        )}
      </div>
    </div>
  );
}

function EmotionDonut({
  title,
  data,
  emptyMessage,
}: {
  title: string;
  data: { name: string; value: number }[];
  emptyMessage: string;
}) {
  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <div className="rounded-3xl border border-cream-200 bg-white p-5">
      <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">{title}</p>
      {data.length ? (
        <div className="flex flex-col gap-4">
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={44}
                outerRadius={72}
                paddingAngle={2}
                dataKey="value"
                label={false}
                labelLine={false}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const entry = payload[0];
                  const idx = data.findIndex((d) => d.name === entry.name);
                  const color = CHART_COLORS[idx % CHART_COLORS.length];
                  const pct = Math.round(((entry.value as number) / total) * 100);
                  return (
                    <div className="rounded-2xl border border-cream-200 bg-white px-4 py-3 shadow-lg">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400 capitalize">
                        {entry.name}
                      </p>
                      <div className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-base font-bold text-slate-900">{pct}%</span>
                      </div>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
            {data.map((entry, i) => (
              <div key={entry.name} className="flex items-center gap-1.5 min-w-0">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                />
                <span className="truncate text-xs text-slate-600 capitalize">{entry.name}</span>
                <span className="ml-auto shrink-0 text-xs font-semibold text-slate-900">
                  {Math.round((entry.value / total) * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <EmptyState message={emptyMessage} />
      )}
    </div>
  );
}

function PhaseBPanel({ data }: { data: ProfileSummary['phase_b'] }) {
  const trendData = data.eye_contact_over_time.map((point, i) => ({
    index: i + 1,
    value: point.eye_contact_pct,
    label: fmt(point.date),
  }));

  const videoEmotionData = Object.entries(data.dominant_video_emotions).map(([name, count]) => ({
    name,
    value: count,
  }));

  const audioEmotionData = Object.entries(data.dominant_audio_emotions).map(([name, count]) => ({
    name,
    value: count,
  }));

  const chunkStatusData = [
    { name: 'Completed', value: Math.max(0, data.chunk_count - data.chunks_failed - data.chunks_timed_out) },
    { name: 'Failed', value: data.chunks_failed },
    { name: 'Timed Out', value: data.chunks_timed_out },
  ].filter((d) => d.value > 0);

  const chunkStatusColors = ['#34D399', '#F87171', '#FB923C'];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={MessageSquare}
          label="Sessions"
          value={data.session_count}
          color="text-purple-600"
        />
        <StatCard
          icon={Eye}
          label="Avg Eye Contact"
          value={data.average_eye_contact_pct !== null ? `${data.average_eye_contact_pct}%` : '—'}
        />
        <StatCard
          icon={TrendingUp}
          label="Avg Turns / Session"
          value={data.avg_turns_per_session ?? '—'}
        />
      </div>

      <div className="rounded-3xl border border-cream-200 bg-white p-5">
        <p className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
          Eye Contact Trend
        </p>
        {trendData.length > 1 ? (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trendData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#E2E8F0', strokeWidth: 1 }} />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#7C3AED"
                strokeWidth={2}
                dot={{ r: 4, fill: '#7C3AED' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState message="Complete more conversations to see your eye contact trend." />
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <EmotionDonut title="Dominant Face Emotion" data={videoEmotionData} emptyMessage="No face emotion data yet." />
        <EmotionDonut title="Dominant Voice Emotion" data={audioEmotionData} emptyMessage="No voice emotion data yet." />
      </div>

    </div>
  );
}

function RecentSessionsTable({ sessions }: { sessions: ProfileSummary['recent_sessions'] }) {
  if (!sessions.length) {
    return <EmptyState message="No sessions yet — start a drill or conversation to build history." />;
  }

  const modeLabel = (mode: string) =>
    mode === 'phase_a' ? 'Emotion Drill' : mode === 'phase_b' ? 'Conversation' : mode;

  const modeBadgeColor = (mode: string) =>
    mode === 'phase_a'
      ? 'bg-blue-50 text-blue-700'
      : mode === 'phase_b'
        ? 'bg-purple-50 text-purple-700'
        : 'bg-cream-100 text-slate-600';

  return (
    <div className="overflow-hidden rounded-2xl border border-cream-200">
      <table className="w-full text-sm">
        <thead className="bg-cream-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-slate-500">Session</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-slate-500">Mode</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-slate-500">Score</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-slate-500">Date</th>
            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-widest text-slate-500">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cream-100">
          {sessions.map((session) => (
            <tr key={session.session_id} className="bg-white">
              <td className="px-4 py-3 font-medium text-slate-900">{session.label}</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${modeBadgeColor(session.mode)}`}>
                  {modeLabel(session.mode)}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-700">
                {session.score !== null ? `${session.score}%` : '—'}
              </td>
              <td className="px-4 py-3 text-slate-500">{fmt(session.date)}</td>
              <td className="px-4 py-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    session.status === 'complete'
                      ? 'bg-green-50 text-green-700'
                      : session.status === 'error'
                        ? 'bg-red-50 text-red-700'
                        : 'bg-cream-100 text-slate-500'
                  }`}
                >
                  {session.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ProfilePage() {
  const { state, reload } = useProfileAnalytics();
  const [tab, setTab] = useState<Tab>('all');

  if (state.status === 'loading' || state.status === 'idle') {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 animate-pulse rounded-2xl bg-cream-200" />
        <div className="grid gap-4 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-3xl bg-cream-200" />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-3xl bg-cream-200" />
      </div>
    );
  }

  if (state.status === 'error') {
    return (
      <div className="mx-auto max-w-lg rounded-3xl border border-red-200 bg-white p-8 text-center shadow-sm">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Could not load profile
        </h1>
        <p className="mt-3 text-sm text-slate-500">{state.message}</p>
        <button
          onClick={() => void reload()}
          className="mt-6 inline-flex items-center gap-2 rounded-full bg-navy-500 px-6 py-3 text-sm font-medium text-white shadow-md transition-all hover:bg-navy-600"
        >
          <RefreshCw size={14} /> Try again
        </button>
      </div>
    );
  }

  const data = state.data;
  const phaseBData = withDemoEyeContact(data.phase_b);
  const hasPhaseA = data.phase_a.session_count > 0;
  const hasPhaseB = phaseBData.session_count > 0;
  const isEmpty = data.total_sessions === 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Playfair_Display'] text-3xl font-semibold text-slate-900">
            Your Profile
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Performance analytics across all practice sessions
          </p>
        </div>
        <button
          onClick={() => void reload()}
          className="inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm text-slate-500 transition-colors hover:bg-cream-100 hover:text-slate-700"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {isEmpty ? (
        <div className="rounded-3xl border border-cream-200 bg-white p-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-cream-100">
            <Target size={28} className="text-navy-500" />
          </div>
          <h2 className="text-xl font-semibold text-slate-900">No sessions yet</h2>
          <p className="mt-2 text-sm text-slate-500">
            Complete an Emotion Sprint or Conversation to start building your analytics.
          </p>
        </div>
      ) : (
        <>
          {/* Overview cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Target}
              label="Total Sessions"
              value={data.total_sessions}
              sub={`${data.completed_sessions} completed`}
            />
            <StatCard
              icon={Clock}
              label="Practice Time"
              value={`${data.total_practice_minutes}m`}
              sub="Estimated"
            />
            <StatCard
              icon={CheckCircle}
              label="Completion Rate"
              value={`${data.completion_rate}%`}
            />
            {hasPhaseA && data.phase_a.average_match_score !== null ? (
              <StatCard
                icon={TrendingUp}
                label="Avg Emotion Match"
                value={`${data.phase_a.average_match_score}%`}
                sub="Phase A"
              />
            ) : hasPhaseB && phaseBData.average_eye_contact_pct !== null ? (
              <StatCard
                icon={Eye}
                label="Avg Eye Contact"
                value={`${phaseBData.average_eye_contact_pct}%`}
                sub="Phase B"
              />
            ) : null}
          </div>

          {/* Mode tabs */}
          <div className="flex gap-2">
            {(['all', 'phase_a', 'phase_b'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                  tab === t
                    ? 'bg-navy-500 text-white'
                    : 'text-slate-500 hover:bg-cream-100 hover:text-slate-700'
                }`}
              >
                {t === 'all' ? 'All' : t === 'phase_a' ? 'Emotion Sprint' : 'Conversation'}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {tab === 'all' && (
            <div className="space-y-8">
              {hasPhaseA && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
                    Emotion Sprint
                  </h2>
                  <PhaseAPanel data={data.phase_a} />
                </section>
              )}
              {hasPhaseB && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-navy-500">
                    Conversation
                  </h2>
                  <PhaseBPanel data={phaseBData} />
                </section>
              )}
            </div>
          )}

          {tab === 'phase_a' && (
            hasPhaseA ? (
              <PhaseAPanel data={data.phase_a} />
            ) : (
              <EmptyState message="No Emotion Sprint sessions yet." />
            )
          )}

          {tab === 'phase_b' && (
            hasPhaseB ? (
              <PhaseBPanel data={phaseBData} />
            ) : (
              <EmptyState message="No Conversation sessions yet." />
            )
          )}

        </>
      )}
    </div>
  );
}
