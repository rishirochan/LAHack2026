"use client";

import Link from "next/link";
import {
  Home,
  PlayCircle,
  Mic,
  MessageSquare,
  AudioLines,
  Clock,
  ChevronLeft,
  ChevronRight,
  User,
} from "lucide-react";

const navItems = [
  { icon: Home, label: "Home", href: "/dashboard" },
  { icon: PlayCircle, label: "Replays", href: "/dashboard/replays" },
];

const practiceItems = [
  { icon: Mic, label: "Emotion Drills", href: "/dashboard/emotion-drills" },
  { icon: MessageSquare, label: "Conversations", href: "/dashboard/conversations" },
  { icon: AudioLines, label: "Free Speaking", href: "/dashboard/free-speaking" },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={`fixed top-4 left-4 bottom-4 z-40 flex flex-col bg-cream-50 rounded-2xl shadow-xl shadow-black/5 border border-cream-200/60 transition-all duration-300 ${
        collapsed ? "w-[72px]" : "w-[220px]"
      }`}
    >
      {/* Profile */}
      <div className="flex items-center gap-3 px-4 pt-5 pb-4">
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center shrink-0">
          <User className="w-5 h-5 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-foreground truncate">User</p>
            <p className="text-xs text-foreground/40 truncate">user@email.com</p>
          </div>
        )}
      </div>

      <div className="h-px bg-cream-200 mx-4" />

      {/* Nav */}
      <nav className="flex-1 flex flex-col px-3 pt-3 gap-0.5 overflow-y-auto">
        {navItems.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-foreground/60 hover:text-foreground hover:bg-cream-200/60 transition-colors group"
          >
            <item.icon className="w-5 h-5 shrink-0 group-hover:text-blue-600 transition-colors" />
            {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
          </Link>
        ))}

        {/* Practice section */}
        <div className="mt-4 mb-1">
          {!collapsed ? (
            <span className="px-3 text-[11px] font-semibold uppercase tracking-wider text-foreground/30">
              Practice
            </span>
          ) : (
            <div className="h-px bg-cream-200 mx-2" />
          )}
        </div>

        {practiceItems.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-foreground/60 hover:text-foreground hover:bg-cream-200/60 transition-colors group"
          >
            <item.icon className="w-5 h-5 shrink-0 group-hover:text-blue-600 transition-colors" />
            {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
          </Link>
        ))}

        {/* Recents */}
        <div className="mt-4 mb-1">
          {!collapsed ? (
            <span className="px-3 text-[11px] font-semibold uppercase tracking-wider text-foreground/30">
              Recents
            </span>
          ) : (
            <div className="h-px bg-cream-200 mx-2" />
          )}
        </div>

        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-foreground/40">
          <Clock className="w-5 h-5 shrink-0" />
          {!collapsed && <span className="text-sm italic">No recent sessions</span>}
        </div>
      </nav>

      {/* Collapse toggle */}
      <div className="px-3 pb-4 pt-2">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-foreground/40 hover:text-foreground hover:bg-cream-200/60 transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <>
              <ChevronLeft className="w-5 h-5" />
              <span className="text-sm font-medium">Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}
