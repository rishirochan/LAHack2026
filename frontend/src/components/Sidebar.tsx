'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/auth/AuthProvider';
import { useSessionsContext } from '@/context/SessionsContext';
import { useSidebar } from '@/context/SidebarContext';
import { formatSessionDate, SESSION_MODE_DISPLAY } from '@/lib/session-display';
import {
  Home,
  PlayCircle,
  Zap,
  MessageSquare,
  Mic,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Loader2,
  SlidersHorizontal,
} from 'lucide-react';

const navItems = [
  { icon: Home, label: 'Home', path: '/home' },
  { icon: PlayCircle, label: 'Replays', path: '/replays' },
  { icon: SlidersHorizontal, label: 'Settings', path: '/settings' },
];

const practiceItems = [
  { icon: Zap, label: 'Emotion Sprint', path: '/sprint' },
  { icon: MessageSquare, label: 'Conversation', path: '/conversation' },
  { icon: Mic, label: 'Free Speaking', path: '/free' },
];

const SIDEBAR_EXPAND_DURATION_MS = 300;

function SidebarSectionDivider({
  label,
  showLabel,
  motionClassName,
}: {
  label: string;
  showLabel: boolean;
  motionClassName: string;
}) {
  if (!showLabel) {
    return (
      <div className="mx-3 my-3 flex min-h-[20px] items-center">
        <div className="h-px w-full bg-cream-300" />
      </div>
    );
  }

  return (
    <div className="mx-3 my-3 flex min-h-[20px] items-center gap-3">
      <div className="h-px flex-1 bg-cream-300" />
      <p className={`shrink-0 px-1 text-[10px] uppercase tracking-widest text-slate-400 ${motionClassName}`}>
        {label}
      </p>
      <div className="h-px flex-1 bg-cream-300" />
    </div>
  );
}

export default function Sidebar() {
  const { expanded, toggleSidebar } = useSidebar();
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const { recentSessions, loading, error } = useSessionsContext();
  const [showExpandedContent, setShowExpandedContent] = useState(expanded);
  const expandTimeoutRef = useRef<number | null>(null);

  const isActive = (path: string) => pathname === path;

  const navItemBase =
    'flex items-center rounded-xl mx-2 cursor-pointer transition-all duration-150 text-slate-600 hover:bg-cream-200 hover:text-slate-900';
  const navItemActive = 'bg-navy-500 text-white hover:bg-navy-600 hover:text-white';
  const navItemCollapsed = 'justify-center px-0 py-2.5';
  const navItemExpanded = 'gap-3 px-3 py-2.5';
  const expandedContentMotion = 'animate-in fade-in-0 slide-in-from-left-1 duration-200 ease-out';

  useEffect(() => () => {
    if (expandTimeoutRef.current !== null) {
      window.clearTimeout(expandTimeoutRef.current);
    }
  }, []);

  const handleToggleSidebar = () => {
    if (expandTimeoutRef.current !== null) {
      window.clearTimeout(expandTimeoutRef.current);
      expandTimeoutRef.current = null;
    }

    if (expanded) {
      setShowExpandedContent(false);
      toggleSidebar();
      return;
    }

    toggleSidebar();
    expandTimeoutRef.current = window.setTimeout(() => {
      setShowExpandedContent(true);
      expandTimeoutRef.current = null;
    }, SIDEBAR_EXPAND_DURATION_MS);
  };

  return (
    <aside
      className={`fixed left-4 top-4 bottom-4 z-50 bg-cream-50 border border-cream-300 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.10)] flex flex-col transition-all duration-300 ease-in-out ${
        expanded ? 'w-56' : 'w-[72px]'
      }`}
    >
      {/* Profile */}
      <Link
        href="/profile"
        className={`flex items-center gap-3 p-4 rounded-xl mx-2 mt-1 transition-colors hover:bg-cream-200 ${expanded ? '' : 'justify-center'} ${pathname === '/profile' ? 'bg-navy-500 hover:bg-navy-600' : ''}`}
      >
        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 ${pathname === '/profile' ? 'bg-white text-navy-500' : 'bg-navy-500 text-white'}`}>
          JD
        </div>
        {showExpandedContent && (
          <div className={expandedContentMotion}>
            <p className={`text-sm font-medium ${pathname === '/profile' ? 'text-white' : 'text-slate-900'}`}>Jordan D.</p>
            <p className={`text-xs ${pathname === '/profile' ? 'text-navy-200' : 'text-slate-500'}`}>View profile</p>
          </div>
        )}
      </Link>

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
            {showExpandedContent && <span className={`text-sm ${expandedContentMotion}`}>{item.label}</span>}
          </Link>
        ))}
      </nav>

      <SidebarSectionDivider
        label="Practice"
        showLabel={showExpandedContent}
        motionClassName={expandedContentMotion}
      />

      {/* Practice Section */}
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
            {showExpandedContent && <span className={`text-sm ${expandedContentMotion}`}>{item.label}</span>}
          </Link>
        ))}
      </nav>

      <SidebarSectionDivider
        label="Recents"
        showLabel={showExpandedContent}
        motionClassName={expandedContentMotion}
      />

      {/* Recents */}
      {showExpandedContent && (
        <div className={`flex flex-col gap-1 ${expandedContentMotion}`}>
          {loading && (
            <div className="flex items-center gap-3 px-5 py-2 text-xs text-slate-500">
              <Loader2 size={14} className="animate-spin" />
              <span>Loading sessions</span>
            </div>
          )}
          {!loading && error && (
            <div className="px-5 py-2 text-xs text-rose-600">
              {error}
            </div>
          )}
          {!loading && !error && recentSessions.length === 0 && (
            <div className="px-5 py-2 text-xs text-slate-500">
              No sessions yet
            </div>
          )}
          {!loading && !error && recentSessions.slice(0, 4).map((session) => {
            const modeDisplay = SESSION_MODE_DISPLAY[session.mode];
            return (
              <Link
                key={session.session_id}
                href={`/replays?session=${encodeURIComponent(session.session_id)}`}
                className="flex items-start gap-3 rounded-xl px-3 py-2 mx-2 text-xs text-slate-500 transition-colors hover:bg-cream-200 hover:text-slate-900"
              >
                <modeDisplay.icon size={14} className={`${modeDisplay.iconClassName} mt-0.5 shrink-0`} />
                <div className="min-w-0">
                  <p className="truncate text-sm text-slate-700">{session.label}</p>
                  <p className="mt-0.5 truncate text-[11px] text-slate-400">
                    {formatSessionDate(session.completed_at || session.updated_at || session.created_at)}
                  </p>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Logout */}
      <button
        onClick={() => {
          logout();
          router.push('/');
        }}
        className={`${navItemBase} ${expanded ? navItemExpanded : navItemCollapsed} mb-2`}
      >
        <LogOut size={18} />
        {showExpandedContent && <span className={`text-sm ${expandedContentMotion}`}>Log out</span>}
      </button>

      {/* Collapse Toggle */}
      <button
        onClick={handleToggleSidebar}
        className="flex items-center justify-center gap-2 w-full py-3 border-t border-cream-300 text-slate-500 hover:text-slate-900 transition-colors"
      >
        {expanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
      </button>
    </aside>
  );
}
