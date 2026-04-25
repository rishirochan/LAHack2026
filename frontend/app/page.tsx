"use client";

import Link from "next/link";
import {
  Mic,
  Brain,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Eye,
  AudioLines,
  ChevronDown,
} from "lucide-react";
import { useState } from "react";

function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-cream-50/80 backdrop-blur-md border-b border-cream-300/50">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Mic className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-semibold text-foreground tracking-tight">
            VoxCoach
          </span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-foreground/60">
          <a href="#features" className="hover:text-foreground transition-colors">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-foreground transition-colors">
            How It Works
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="text-sm font-medium text-foreground/70 hover:text-foreground transition-colors px-4 py-2"
          >
            Log in
          </Link>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 transition-colors px-5 py-2 rounded-lg shadow-sm"
          >
            Sign up
          </Link>
        </div>
      </div>
    </nav>
  );
}

function FeatureCard({
  icon,
  title,
  description,
  details,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  details: string[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="group bg-white rounded-2xl p-8 shadow-sm border border-cream-200 hover:shadow-md hover:border-cream-300 transition-all duration-300">
      <div className="w-12 h-12 rounded-xl bg-blue-600/10 flex items-center justify-center mb-5">
        {icon}
      </div>
      <h3 className="text-xl font-semibold text-foreground mb-3">{title}</h3>
      <p className="text-foreground/60 leading-relaxed mb-4">{description}</p>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
      >
        Learn more
        <ChevronDown
          className={`w-4 h-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <ul className="mt-4 space-y-2">
          {details.map((d, i) => (
            <li
              key={i}
              className="flex items-start gap-2 text-sm text-foreground/60"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
              {d}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-cream-100">
      <Navbar />

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-blue-600/10 text-blue-700 text-sm font-medium px-4 py-1.5 rounded-full mb-6">
            <Sparkles className="w-4 h-4" />
            AI-Powered Communication Coach
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-foreground leading-tight tracking-tight mb-6">
            Master How You
            <br />
            <span className="text-blue-600">Communicate</span>
          </h1>
          <p className="text-lg md:text-xl text-foreground/60 max-w-2xl mx-auto mb-10 leading-relaxed">
            Practice speaking with real-time AI analysis of your body language,
            facial expressions, tone, and word choice. Get instant, actionable
            feedback to become a more confident communicator.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 py-3.5 rounded-xl shadow-lg shadow-blue-600/20 transition-all duration-200 hover:shadow-xl hover:shadow-blue-600/30"
            >
              Get Started Free
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Analysis pipeline badges */}
      <section className="pb-20 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="flex flex-wrap items-center justify-center gap-3">
            {[
              { icon: <Eye className="w-4 h-4" />, label: "Computer Vision" },
              {
                icon: <AudioLines className="w-4 h-4" />,
                label: "Audio Analysis",
              },
              {
                icon: <MessageSquare className="w-4 h-4" />,
                label: "Sentiment Analysis",
              },
              { icon: <Brain className="w-4 h-4" />, label: "AI Coaching" },
            ].map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-2 bg-white/80 border border-cream-200 text-foreground/70 text-sm px-4 py-2 rounded-full"
              >
                {item.icon}
                {item.label}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="pb-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
              Three Ways to Practice
            </h2>
            <p className="text-foreground/60 text-lg max-w-xl mx-auto">
              Whether you want quick drills or full conversations, we have a
              mode for you.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Mic className="w-6 h-6 text-blue-600" />}
              title="Emotion Drills"
              description="Practice delivering sentences with the right emotional tone. Get instant feedback on how well your expression matches your intent."
              details={[
                "Choose an emotion to practice (confident, empathetic, assertive, etc.)",
                "Receive curated sentences to deliver with that emotion",
                "Computer vision analyzes facial expressions and body language",
                "Audio analysis evaluates tone, pace, and emphasis",
                "AI agent Gemma provides personalized coaching and critiques",
              ]}
            />
            <FeatureCard
              icon={<MessageSquare className="w-6 h-6 text-blue-600" />}
              title="Conversation Practice"
              description="Simulate real-world conversations like interviews, negotiations, and coffee chats with a dynamic AI partner."
              details={[
                "Choose a scenario: interviews, sales, negotiations, or coffee chats",
                "AI generates dynamic, realistic conversation flows (~1 minute)",
                "Full analysis pipeline: vision, audio, and transcript sentiment",
                "See if your words align with your emotional delivery",
                "Build confidence for high-stakes real-world interactions",
              ]}
            />
            <FeatureCard
              icon={<AudioLines className="w-6 h-6 text-blue-600" />}
              title="Free Speaking"
              description="Practice a speech, pitch, or just speak freely. The full analysis pipeline runs in the background."
              details={[
                "Speak naturally without prompts or constraints",
                "Perfect for rehearsing presentations, pitches, or speeches",
                "Complete analysis: body language, tone, and transcript review",
                "Track your progress over time with saved recordings",
                "Get holistic feedback on your overall communication style",
              ]}
            />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="pb-24 px-6">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
              How It Works
            </h2>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "01",
                title: "Record",
                desc: "Choose a practice mode and start speaking. Your camera and microphone capture your session.",
              },
              {
                step: "02",
                title: "Analyze",
                desc: "Our pipeline processes facial expressions, body language, audio tone, and transcript sentiment in real time.",
              },
              {
                step: "03",
                title: "Improve",
                desc: "Gemma, your AI coach, delivers a detailed breakdown with actionable tips to sharpen your communication.",
              },
            ].map((item) => (
              <div key={item.step} className="text-center">
                <div className="text-4xl font-bold text-blue-600/20 mb-3">
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {item.title}
                </h3>
                <p className="text-foreground/60 text-sm leading-relaxed">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="pb-24 px-6">
        <div className="max-w-3xl mx-auto bg-blue-600 rounded-2xl p-12 text-center shadow-xl shadow-blue-600/10">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to level up your communication?
          </h2>
          <p className="text-white/80 mb-8 text-lg">
            Start practicing for free. No credit card required.
          </p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-white text-blue-700 font-semibold px-8 py-3.5 rounded-xl hover:bg-cream-50 transition-colors shadow-lg"
          >
            Get Started
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-cream-300/50 py-8 px-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-sm text-foreground/40">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center">
              <Mic className="w-3 h-3 text-white" />
            </div>
            VoxCoach
          </div>
          <span>&copy; 2026 VoxCoach. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
}
