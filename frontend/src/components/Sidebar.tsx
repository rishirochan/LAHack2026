 'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useSidebar } from '@/context/SidebarContext';
import {
  Home,
  PlayCircle,
  Zap,
  MessageSquare,
  Mic,
  FileText,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const navItems = [
  { icon: Home, label: 'Home', path: '/home' },
  { icon: PlayCircle, label: 'Replays', path: '/replays' },
];

const practiceItems = [
  { icon: Zap, label: 'Emotion Sprint', path: '/sprint' },
  { icon: MessageSquare, label: 'Conversation', path: '/conversation' },
  { icon: Mic, label: 'Free Speaking', path: '/free' },
];

const recentSessions = [
  { name: 'Confidence Sprint — Apr 22' },
  { name: 'Interview Practice — Apr 20' },
  { name: 'Free Speech — Apr 18' },
];

export default function Sidebar() {
  const { expanded, toggleSidebar } = useSidebar();
  const pathname = usePathname();

  const isActive = (path: string) => pathname === path;

  const navItemBase =
    'flex items-center rounded-xl mx-2 cursor-pointer transition-all duration-150 text-slate-600 hover:bg-cream-200 hover:text-slate-900';
  const navItemActive = 'bg-navy-500 text-white hover:bg-navy-600 hover:text-white';
  const navItemCollapsed = 'justify-center px-0 py-2.5';
  const navItemExpanded = 'gap-3 px-3 py-2.5';

  return (
    <aside
      className={`fixed left-4 top-4 bottom-4 z-50 bg-cream-50 border border-cream-300 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.10)] flex flex-col transition-all duration-300 ease-in-out ${
        expanded ? 'w-56' : 'w-[72px]'
      }`}
    >
      {/* Profile */}
      <div className={`flex items-center gap-3 p-4 ${expanded ? '' : 'justify-center'}`}>
        <div className="w-10 h-10 rounded-full bg-navy-500 text-white flex items-center justify-center text-sm font-semibold shrink-0">
          JD
        </div>
        {expanded && (
          <div className="transition-opacity duration-300">
            <p className="text-sm font-medium text-slate-900">Jordan D.</p>
            <p className="text-xs text-slate-500">Practicing daily</p>
          </div>
        )}
      </div>

      {/* Main Nav */}
      <nav className="flex flex-col gap-1 mt-2">
        {navItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            className={`${navItemBase} ${isActive(item.path) ? navItemActive : ''} ${
              expanded ? navItemExpanded : navItemCollapsed
            }`}
          >
            <item.icon size={18} />
            {expanded && <span className="text-sm">{item.label}</span>}
          </Link>
        ))}
      </nav>

      {/* Divider */}
      <div className="border-t border-cream-300 mx-3 my-3" />

      {/* Practice Section */}
      {expanded && (
        <p className="text-[10px] uppercase tracking-widest text-slate-400 px-5 mb-2">
          Practice
        </p>
      )}
      <nav className="flex flex-col gap-1">
        {practiceItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            className={`${navItemBase} ${isActive(item.path) ? navItemActive : ''} ${
              expanded ? navItemExpanded : navItemCollapsed
            }`}
          >
            <item.icon size={18} />
            {expanded && <span className="text-sm">{item.label}</span>}
          </Link>
        ))}
      </nav>

      {/* Divider */}
      <div className="border-t border-cream-300 mx-3 my-3" />

      {/* Recents */}
      {expanded && (
        <p className="text-[10px] uppercase tracking-widest text-slate-400 px-5 mb-2">
          Recents
        </p>
      )}
      {expanded && (
        <div className="flex flex-col gap-1">
          {recentSessions.map((session, i) => (
            <div
              key={i}
              className="flex items-center gap-3 px-5 py-2 text-xs text-slate-500"
            >
              <FileText size={14} />
              <span className="truncate">{session.name}</span>
            </div>
          ))}
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Collapse Toggle */}
      <button
        onClick={toggleSidebar}
        className="flex items-center justify-center gap-2 w-full py-3 border-t border-cream-300 text-slate-500 hover:text-slate-900 transition-colors"
      >
        {expanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
      </button>
    </aside>
  );
}
