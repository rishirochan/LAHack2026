'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { RotateCcw, Save } from 'lucide-react';

const focusOptions = [
  'Filler words',
  'Emotion shifts',
  'Pace changes',
  'Eye contact',
  'Word repetition',
];

const fillerWordData = [
  { word: 'um', count: 12 },
  { word: 'like', count: 8 },
  { word: 'uh', count: 6 },
  { word: 'you know', count: 5 },
  { word: 'so', count: 4 },
  { word: 'actually', count: 3 },
];

const emotionTimeline = [
  { emotion: 'Calm', color: '#2D5BE3', duration: 45 },
  { emotion: 'Confident', color: '#10B981', duration: 30 },
  { emotion: 'Nervous', color: '#F59E0B', duration: 15 },
  { emotion: 'Enthusiastic', color: '#EF4444', duration: 25 },
  { emotion: 'Calm', color: '#2D5BE3', duration: 35 },
];

const momentTimeline = [
  { time: '0:15', color: '#F59E0B', label: 'Filler words spike', detail: '3 "ums" in 10 seconds' },
  { time: '0:34', color: '#2D5BE3', label: 'Strong eye contact', detail: 'Sustained 8+ seconds' },
  { time: '1:02', color: '#10B981', label: 'Emotion shift', detail: 'Moved from calm to confident' },
  { time: '1:28', color: '#EF4444', label: 'Pace increased', detail: 'WPM jumped from 120 to 165' },
  { time: '1:55', color: '#2D5BE3', label: 'Good pause', detail: 'Strategic 3-second silence' },
  { time: '2:30', color: '#F59E0B', label: 'Word repetition', detail: '"Really" used 4 times' },
  { time: '2:45', color: '#10B981', label: 'Strong closing', detail: 'Confident final statement' },
];

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function FreePage() {
  const [activeFocus, setActiveFocus] = useState<string[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [recordTime, setRecordTime] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [waveformBars, setWaveformBars] = useState<number[]>(Array(32).fill(4));
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const waveRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const toggleFocus = (option: string) => {
    setActiveFocus((prev) =>
      prev.includes(option) ? prev.filter((o) => o !== option) : [...prev, option]
    );
  };

  const startRecording = () => {
    setIsRecording(true);
    setRecordTime(0);
    setShowResults(false);
    intervalRef.current = setInterval(() => {
      setRecordTime((t) => t + 1);
    }, 1000);
    waveRef.current = setInterval(() => {
      setWaveformBars(
        Array(32)
          .fill(0)
          .map(() => Math.floor(4 + Math.random() * 40))
      );
    }, 150);
  };

  const stopRecording = () => {
    setIsRecording(false);
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (waveRef.current) clearInterval(waveRef.current);
    setWaveformBars(Array(32).fill(4));
    setShowResults(true);
  };

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (waveRef.current) clearInterval(waveRef.current);
    };
  }, []);

  const maxCount = Math.max(...fillerWordData.map((d) => d.count));

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Free Speaking
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Give a speech or talk freely — full analysis at the end
        </p>
      </div>

      {/* Focus Chips */}
      <div className="mb-6">
        <p className="text-xs text-slate-500 mb-3 uppercase tracking-wider font-medium">
          Focus areas (optional)
        </p>
        <div className="flex flex-wrap gap-2">
          {focusOptions.map((option) => (
            <button
              key={option}
              onClick={() => toggleFocus(option)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                activeFocus.includes(option)
                  ? 'bg-navy-500 text-white shadow-md'
                  : 'bg-cream-200 text-slate-600 hover:bg-cream-300'
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      {/* Waveform */}
      <div className="bg-white rounded-2xl border border-cream-300 p-8 mb-6 shadow-sm">
        <div className="flex items-end justify-center gap-[3px] h-24 mb-6">
          {waveformBars.map((height, i) => (
            <motion.div
              key={i}
              animate={{ height: `${height * 3}px` }}
              transition={{ duration: 0.1 }}
              className={`w-1.5 rounded-full ${
                isRecording ? 'bg-navy-500' : 'bg-cream-300'
              }`}
            />
          ))}
        </div>

        {/* Timer */}
        <div className="text-center mb-6">
          <p className="text-3xl font-mono font-semibold text-slate-900">
            {formatTime(recordTime)}
          </p>
        </div>

        {/* Controls */}
        <div className="flex justify-center gap-4">
          {!showResults && (
            <button
              onClick={isRecording ? stopRecording : startRecording}
              className={`px-8 py-3 rounded-full font-medium text-sm transition-all shadow-md ${
                isRecording
                  ? 'bg-red-500 text-white hover:bg-red-600'
                  : 'bg-navy-500 text-white hover:bg-navy-600'
              }`}
            >
              {isRecording ? 'Stop' : 'Start Recording'}
            </button>
          )}
          {showResults && (
            <button
              onClick={() => {
                setShowResults(false);
                setRecordTime(0);
              }}
              className="px-6 py-3 rounded-full bg-navy-500 text-white text-sm font-medium hover:bg-navy-600 transition-colors shadow-md"
            >
              Record again
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {showResults && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* 2-col grid: Filler words + Emotion timeline */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {/* Filler Word Cloud */}
            <div className="bg-white rounded-2xl border border-cream-300 p-6 shadow-sm">
              <h3 className="text-sm font-medium text-slate-700 mb-4">
                Filler Word Frequency
              </h3>
              <div className="flex flex-wrap items-end gap-3">
                {fillerWordData.map((d) => (
                  <div key={d.word} className="flex flex-col items-center gap-1">
                    <span
                      className="font-medium"
                      style={{
                        fontSize: `${0.75 + (d.count / maxCount) * 1.25}rem`,
                        color:
                          d.count > 8
                            ? '#EF4444'
                            : d.count > 5
                            ? '#F59E0B'
                            : '#64748B',
                      }}
                    >
                      {d.word}
                    </span>
                    <span className="text-xs text-slate-400">{d.count}x</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Emotion Timeline */}
            <div className="bg-white rounded-2xl border border-cream-300 p-6 shadow-sm">
              <h3 className="text-sm font-medium text-slate-700 mb-4">
                Emotion Timeline
              </h3>
              <div className="flex items-center gap-1 h-12">
                {emotionTimeline.map((seg, i) => (
                  <motion.div
                    key={i}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ delay: i * 0.1, duration: 0.4 }}
                    style={{
                      backgroundColor: seg.color,
                      width: `${seg.duration}%`,
                    }}
                    className="h-full rounded-sm origin-left relative group"
                  >
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-white text-xs px-2 py-1 rounded pointer-events-none whitespace-nowrap z-10">
                      {seg.emotion} ({seg.duration}s)
                    </div>
                  </motion.div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-slate-400 mt-2">
                <span>0:00</span>
                <span>{formatTime(recordTime || 150)}</span>
              </div>
            </div>
          </div>

          {/* Moment-by-moment timeline */}
          <div className="bg-white rounded-2xl border border-cream-300 p-6 shadow-sm mb-6">
            <h3 className="text-sm font-medium text-slate-700 mb-4">
              Moment-by-Moment
            </h3>
            <div className="space-y-0">
              {momentTimeline.map((moment, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08 }}
                  className={`flex items-start gap-4 py-3 ${
                    i < momentTimeline.length - 1 ? 'border-b border-cream-100' : ''
                  }`}
                >
                  <span className="text-xs font-mono text-slate-400 w-10 shrink-0 mt-0.5">
                    {moment.time}
                  </span>
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0 mt-1"
                    style={{ backgroundColor: moment.color }}
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-slate-800">
                      {moment.label}
                    </p>
                    <p className="text-xs text-slate-500">{moment.detail}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                setShowResults(false);
                setRecordTime(0);
              }}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-cream-300 text-slate-600 text-sm font-medium hover:bg-cream-200 transition-colors"
            >
              <RotateCcw size={14} /> Record again
            </button>
            <button className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-navy-500 text-white text-sm font-medium hover:bg-navy-600 transition-colors shadow-md">
              <Save size={14} /> Save to replays
            </button>
          </div>
        </motion.div>
      )}
    </div>
  );
}
