'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Mic, MicOff, Power } from 'lucide-react';

type Mode = 'interview' | 'negotiation' | 'coffee';

const modeData: Record<
  Mode,
  { label: string; description: string; color: string }
> = {
  interview: {
    label: 'Interview',
    description: 'Practice answering tough questions under pressure',
    color: 'border-navy-500',
  },
  negotiation: {
    label: 'Negotiation / Sales',
    description: 'Hone your persuasion and deal-making skills',
    color: 'border-teal-500',
  },
  coffee: {
    label: 'Coffee Chat',
    description: 'Build rapport and practice casual networking',
    color: 'border-amber-500',
  },
};

const aiResponses: Record<Mode, string[]> = {
  interview: [
    "Tell me about a time you had to convince someone to see things your way.",
    "What's your biggest professional weakness, and how are you working on it?",
    "Describe a project that failed. What did you learn?",
    "Why should we hire you over other qualified candidates?",
    "Where do you see yourself in five years?",
  ],
  negotiation: [
    "The budget for this project is firm at $50K. Can you deliver within that?",
    "I'm not sure your solution is worth the premium you're asking for.",
    "We need a 30-day delivery, but your timeline says 60. What can you do?",
    "The competitor quoted us 20% less. Can you match that?",
    "I love the proposal, but I need approval from three other stakeholders.",
  ],
  coffee: [
    "So, what got you interested in this field in the first place?",
    "I'm curious — what's the most exciting project you're working on right now?",
    "How do you usually stay productive during busy weeks?",
    "If you could give your younger self one piece of career advice, what would it be?",
    "What's something you're learning outside of work these days?",
  ],
};

const tips = [
  'Maintain steady eye contact with the camera',
  'Use pauses strategically — silence builds authority',
  'Mirror the other person\'s energy level',
  'Avoid filler words like "um" and "like"',
  'Lean slightly forward to show engagement',
];

interface Message {
  id: number;
  role: 'ai' | 'user';
  text: string;
}

export default function ConversationPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [mode, setMode] = useState<Mode | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [micOn, setMicOn] = useState(false);
  const [meters, setMeters] = useState({
    confidence: 65,
    arousal: 40,
    positivity: 70,
    eyeContact: 80,
  });
  const [currentTip, setCurrentTip] = useState(0);
  const [fillerWords, setFillerWords] = useState<string[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const meterRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tipRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startConversation = () => {
    if (!mode) return;
    setStep(2);
    const firstMessage: Message = {
      id: 1,
      role: 'ai',
      text: aiResponses[mode][0],
    };
    setMessages([firstMessage]);
  };

  const sendMessage = () => {
    if (!input.trim() || !mode) return;
    const userMsg: Message = {
      id: Date.now(),
      role: 'user',
      text: input.trim(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Simulate filler words
    const words = input.toLowerCase().split(/\s+/);
    const fillers = words.filter((w) =>
      ['um', 'uh', 'like', 'you know', 'so', 'actually'].includes(w)
    );
    if (fillers.length > 0) {
      setFillerWords((prev) => [...prev, ...fillers]);
    }

    // AI responds after delay
    setTimeout(() => {
      const responses = aiResponses[mode];
      const nextResponse = responses[Math.floor(Math.random() * responses.length)];
      const aiMsg: Message = {
        id: Date.now() + 1,
        role: 'ai',
        text: nextResponse,
      };
      setMessages((prev) => [...prev, aiMsg]);
      setIsTyping(false);
    }, 1800);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Live meters
  useEffect(() => {
    if (step === 2) {
      meterRef.current = setInterval(() => {
        setMeters({
          confidence: Math.floor(50 + Math.random() * 40),
          arousal: Math.floor(30 + Math.random() * 50),
          positivity: Math.floor(45 + Math.random() * 45),
          eyeContact: Math.floor(60 + Math.random() * 35),
        });
      }, 4000);

      tipRef.current = setInterval(() => {
        setCurrentTip((prev) => (prev + 1) % tips.length);
      }, 5000);
    }
    return () => {
      if (meterRef.current) clearInterval(meterRef.current);
      if (tipRef.current) clearInterval(tipRef.current);
    };
  }, [step]);

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col">
      {/* Header */}
      <div className="mb-4 shrink-0">
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">
          Conversation Practice
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          Simulate real conversations and get live feedback
        </p>
      </div>

      <AnimatePresence mode="wait">
        {step === 1 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex-1"
          >
            <h2 className="text-sm font-medium text-slate-700 mb-4">
              Select a conversation mode
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
              {(Object.keys(modeData) as Mode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`bg-white rounded-2xl border-2 p-6 text-left transition-all duration-200 hover:shadow-md ${
                    mode === m
                      ? `${modeData[m].color} shadow-md`
                      : 'border-cream-300'
                  }`}
                >
                  <h3 className="font-semibold text-slate-900 mb-1">
                    {modeData[m].label}
                  </h3>
                  <p className="text-sm text-slate-500">
                    {modeData[m].description}
                  </p>
                </button>
              ))}
            </div>
            <button
              disabled={!mode}
              onClick={startConversation}
              className={`px-6 py-3 rounded-full font-medium text-sm transition-all ${
                mode
                  ? 'bg-navy-500 text-white hover:bg-navy-600 shadow-md'
                  : 'bg-cream-200 text-slate-400 cursor-not-allowed'
              }`}
            >
              Begin conversation →
            </button>
          </motion.div>
        )}

        {step === 2 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex-1 flex gap-4 overflow-hidden"
          >
            {/* Chat Thread — 65% */}
            <div className="flex-[65] flex flex-col bg-white rounded-2xl border border-cream-300 overflow-hidden shadow-sm">
              {/* Chat mode header */}
              <div className="px-5 py-3 border-b border-cream-200 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">
                  {mode && modeData[mode].label}
                </span>
                <button
                  onClick={() => router.push('/replays')}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-red-50 text-red-500 text-xs font-medium hover:bg-red-100 transition-colors"
                >
                  <Power size={12} /> End session
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-navy-500 text-white rounded-br-md'
                          : 'bg-cream-50 border border-cream-300 text-slate-800 rounded-bl-md'
                      }`}
                    >
                      {msg.text}
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="flex justify-start">
                    <div className="bg-cream-50 border border-cream-300 rounded-2xl rounded-bl-md px-4 py-3">
                      <div className="flex gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" />
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0.15s' }} />
                        <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0.3s' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div className="px-5 py-3 border-t border-cream-200">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setMicOn(!micOn)}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                      micOn
                        ? 'bg-navy-500 text-white'
                        : 'bg-cream-100 text-slate-500 hover:bg-cream-200'
                    }`}
                  >
                    {micOn ? <Mic size={18} /> : <MicOff size={18} />}
                  </button>
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your response..."
                    className="flex-1 px-4 py-2.5 rounded-full bg-cream-50 border border-cream-300 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500/20 focus:border-navy-500"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim()}
                    className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors ${
                      input.trim()
                        ? 'bg-navy-500 text-white hover:bg-navy-600'
                        : 'bg-cream-100 text-slate-400 cursor-not-allowed'
                    }`}
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </div>

            {/* Live Analysis Sidebar — 35% */}
            <div className="flex-[35] flex flex-col gap-4">
              {/* Meters */}
              <div className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm">
                <h3 className="text-sm font-medium text-slate-700 mb-4">
                  Live Analysis
                </h3>
                <div className="space-y-4">
                  {(
                    [
                      ['Confidence', meters.confidence],
                      ['Arousal', meters.arousal],
                      ['Positivity', meters.positivity],
                      ['Eye contact', meters.eyeContact],
                    ] as [string, number][]
                  ).map(([label, value]) => (
                    <div key={label}>
                      <div className="flex justify-between text-xs mb-1.5">
                        <span className="text-slate-600">{label}</span>
                        <span className="text-slate-900 font-medium">{value}%</span>
                      </div>
                      <div className="h-1.5 bg-cream-200 rounded-full overflow-hidden">
                        <motion.div
                          animate={{ width: `${value}%` }}
                          transition={{ duration: 0.8 }}
                          className="h-full rounded-full bg-navy-500"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Rotating Tip */}
              <div className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-navy-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-navy-500" />
                  </span>
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">
                    Tip
                  </span>
                </div>
                <AnimatePresence mode="wait">
                  <motion.p
                    key={currentTip}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    transition={{ duration: 0.3 }}
                    className="text-sm text-slate-700"
                  >
                    {tips[currentTip]}
                  </motion.p>
                </AnimatePresence>
              </div>

              {/* Filler Words */}
              <div className="bg-white rounded-2xl border border-cream-300 p-5 shadow-sm">
                <h3 className="text-sm font-medium text-slate-700 mb-3">
                  Filler words detected
                </h3>
                {fillerWords.length === 0 ? (
                  <p className="text-xs text-slate-400">No filler words yet</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {fillerWords.slice(-8).map((word, i) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-xs text-amber-700"
                      >
                        {word}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
