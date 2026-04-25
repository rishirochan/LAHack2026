'use client';

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { VoiceOption } from '@/lib/tts-api';

const STORAGE_KEY = 'eloquence.voice-settings';
const DEFAULT_SPEECH_RATE = 1.0;

type StoredVoiceSettings = {
  selectedVoiceId: string | null;
  selectedVoiceName: string;
  speechRate: number;
};

interface VoiceSettingsContextValue {
  isHydrated: boolean;
  selectedVoiceId: string | null;
  selectedVoiceName: string;
  speechRate: number;
  setSelectedVoice: (voice: Pick<VoiceOption, 'voiceId' | 'name'>) => void;
  setSpeechRate: (value: number) => void;
}

const VoiceSettingsContext = createContext<VoiceSettingsContextValue | undefined>(undefined);

export function VoiceSettingsProvider({ children }: { children: ReactNode }) {
  const [isHydrated, setIsHydrated] = useState(false);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [selectedVoiceName, setSelectedVoiceName] = useState('');
  const [speechRate, setSpeechRateState] = useState(DEFAULT_SPEECH_RATE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as Partial<StoredVoiceSettings>;
        setSelectedVoiceId(typeof parsed.selectedVoiceId === 'string' ? parsed.selectedVoiceId : null);
        setSelectedVoiceName(typeof parsed.selectedVoiceName === 'string' ? parsed.selectedVoiceName : '');
        setSpeechRateState(clampSpeechRate(parsed.speechRate));
      }
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    } finally {
      setIsHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    const payload: StoredVoiceSettings = {
      selectedVoiceId,
      selectedVoiceName,
      speechRate,
    };

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [isHydrated, selectedVoiceId, selectedVoiceName, speechRate]);

  const value = useMemo<VoiceSettingsContextValue>(
    () => ({
      isHydrated,
      selectedVoiceId,
      selectedVoiceName,
      speechRate,
      setSelectedVoice: (voice) => {
        setSelectedVoiceId(voice.voiceId);
        setSelectedVoiceName(voice.name);
      },
      setSpeechRate: (value) => {
        setSpeechRateState(clampSpeechRate(value));
      },
    }),
    [isHydrated, selectedVoiceId, selectedVoiceName, speechRate],
  );

  return <VoiceSettingsContext.Provider value={value}>{children}</VoiceSettingsContext.Provider>;
}

export function useVoiceSettings() {
  const context = useContext(VoiceSettingsContext);

  if (!context) {
    throw new Error('useVoiceSettings must be used within a VoiceSettingsProvider');
  }

  return context;
}

function clampSpeechRate(value: unknown) {
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) {
    return DEFAULT_SPEECH_RATE;
  }
  return Math.max(0.5, Math.min(1.5, Math.round(numeric * 10) / 10));
}
