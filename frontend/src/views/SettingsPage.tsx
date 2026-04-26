'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import * as SliderPrimitive from '@radix-ui/react-slider';
import { Check, Loader2, Play, Volume2, WandSparkles } from 'lucide-react';
import { useVoiceSettings } from '@/context/VoiceSettingsContext';
import { fetchVoiceOptions, fetchVoicePreviewAudio, type VoiceOption } from '@/lib/tts-api';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export default function SettingsPage() {
  const {
    isHydrated,
    selectedVoiceId,
    selectedVoiceName,
    speechRate,
    setSelectedVoice,
    setSpeechRate,
  } = useVoiceSettings();
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadVoices() {
      try {
        setIsLoadingVoices(true);
        const nextVoices = await fetchVoiceOptions();
        if (!isMounted) {
          return;
        }
        setVoices(nextVoices);
      } catch (error) {
        if (!isMounted) {
          return;
        }
        setErrorMessage(getErrorMessage(error, 'Could not load available voices.'));
      } finally {
        if (isMounted) {
          setIsLoadingVoices(false);
        }
      }
    }

    void loadVoices();

    return () => {
      isMounted = false;
      stopPreview(previewAudioRef);
    };
  }, []);

  useEffect(() => {
    if (!isHydrated || voices.length === 0 || selectedVoiceId) {
      return;
    }

    const fallbackVoice = voices.find((voice) => voice.isDefault) ?? voices[0];
    if (fallbackVoice) {
      setSelectedVoice({ voiceId: fallbackVoice.voiceId, name: fallbackVoice.displayName });
    }
  }, [isHydrated, selectedVoiceId, setSelectedVoice, voices]);

  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.voiceId === selectedVoiceId) ?? null,
    [selectedVoiceId, voices],
  );
  const orderedVoices = useMemo(() => {
    if (!selectedVoiceId) {
      return voices;
    }

    const selected = voices.find((voice) => voice.voiceId === selectedVoiceId);
    if (!selected) {
      return voices;
    }

    return [
      selected,
      ...voices.filter((voice) => voice.voiceId !== selectedVoiceId),
    ];
  }, [selectedVoiceId, voices]);
  const speedTicks = useMemo(() => {
    return Array.from({ length: 11 }, (_, index) => Number((0.5 + index * 0.1).toFixed(1)));
  }, []);

  const previewSentence = `Hi, my name is ${selectedVoice?.displayName || selectedVoiceName || 'your selected voice'}. Here's what I sound like at your selected speed.`;

  async function handlePreview() {
    if (!selectedVoice) {
      setErrorMessage('Choose a voice before previewing it.');
      return;
    }

    stopPreview(previewAudioRef);
    setErrorMessage('');
    setIsPreviewing(true);

    try {
      const blob = await fetchVoicePreviewAudio({
        voiceId: selectedVoice.voiceId,
        voiceName: selectedVoice.displayName,
      });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      previewAudioRef.current = audio;
      audio.playbackRate = speechRate;
      audio.onended = () => cleanupPreview(previewAudioRef, url, setIsPreviewing);
      audio.onerror = () => cleanupPreview(previewAudioRef, url, setIsPreviewing);
      await audio.play();
    } catch (error) {
      setIsPreviewing(false);
      setErrorMessage(getErrorMessage(error, 'Could not generate the voice preview.'));
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="font-['Playfair_Display'] text-2xl font-semibold text-slate-900">Voice Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Pick a voice, tune playback speed, and preview how it will sound before starting a conversation.
        </p>
      </div>

      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-cream-200 bg-white p-8 shadow-sm">
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-navy-500">
            <Volume2 className="h-4 w-4" />
            Voice
          </div>

          <div className="mt-4">
            <label className="text-sm font-medium text-slate-900" htmlFor="voice-select">
              Choose a voice
            </label>
            <Select
              value={selectedVoiceId ?? undefined}
              onValueChange={(nextVoiceId) => {
                const nextVoice = voices.find((voice) => voice.voiceId === nextVoiceId);
                if (nextVoice) {
                  setSelectedVoice({ voiceId: nextVoice.voiceId, name: nextVoice.displayName });
                }
              }}
              disabled={isLoadingVoices}
            >
              <SelectTrigger
                id="voice-select"
                className="mt-3 h-12 w-full rounded-2xl border-cream-300 px-4 text-center [&_[data-slot=select-value]]:w-full [&_[data-slot=select-value]]:justify-center"
              >
                <SelectValue placeholder={isLoadingVoices ? 'Loading voices...' : 'Select a voice'} />
              </SelectTrigger>
              <SelectContent
                position="popper"
                align="center"
                className="z-[80] max-h-80 min-w-[var(--radix-select-trigger-width)] w-[var(--radix-select-trigger-width)] overflow-hidden rounded-[24px] border-cream-300 bg-white shadow-2xl [&_[data-slot=select-scroll-up-button]]:hidden [&_[data-slot=select-scroll-down-button]]:hidden [&_[data-slot=select-viewport]]:overflow-x-hidden [&_[data-slot=select-viewport]]:p-2"
              >
                {orderedVoices.map((voice) => (
                  <SelectItem
                    key={voice.voiceId}
                    value={voice.voiceId}
                    className="justify-center rounded-2xl bg-white px-4 py-3 text-center data-[state=checked]:bg-navy-50 data-[state=checked]:text-slate-900 focus:bg-cream-100 [&>[data-slot=select-item-indicator]]:hidden"
                  >
                    <span
                      className="inline-flex max-w-full items-center justify-center gap-1.5 text-center"
                      title={voice.displayName}
                    >
                      <span className="truncate">{voice.displayName}</span>
                      <span
                        className={`inline-flex items-center text-navy-600 transition-opacity ${
                          voice.voiceId === selectedVoiceId ? 'opacity-100' : 'opacity-0'
                        }`}
                      >
                        <Check className="h-3.5 w-3.5" />
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedVoice && (
            <div className="mt-4 rounded-2xl bg-cream-50 px-4 py-3 text-sm text-slate-600">
              <p className="font-medium text-slate-900">{selectedVoice.displayName}</p>
              <p className="mt-1">
                {selectedVoice.styleHint || selectedVoice.description || 'No extra voice styling details available.'}
              </p>
            </div>
          )}

          <div className="mt-8">
            <div className="flex items-center justify-between gap-4">
              <label className="text-sm font-medium text-slate-900" htmlFor="speech-rate">
                Text speed
              </label>
              <span className="rounded-full bg-cream-100 px-3 py-1 text-xs font-semibold text-slate-700">
                {speechRate.toFixed(1)}x
              </span>
            </div>

            <VoiceSpeedSlider
              id="speech-rate"
              value={speechRate}
              onValueChange={(value) => setSpeechRate(value[0] ?? 1)}
              ticks={speedTicks}
            />

            <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
              <span>0.5x</span>
              <span>Natural</span>
              <span>1.5x</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handlePreview}
            disabled={!selectedVoice || isPreviewing}
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-navy-500 px-5 py-3 text-sm font-medium text-white transition hover:bg-navy-600 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isPreviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
            {isPreviewing ? 'Generating preview' : 'Preview voice'}
          </button>

          {errorMessage && (
            <p className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">{errorMessage}</p>
          )}
        </div>

        <div className="rounded-3xl border border-cream-200 bg-white p-8 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-navy-500">Preview Details</h2>

          <div className="mt-4 rounded-3xl border border-navy-100 bg-navy-50 p-5">
            <p className="text-xs font-semibold uppercase tracking-widest text-navy-500">Preview line</p>
            <p className="mt-3 text-sm leading-7 text-slate-700">{previewSentence}</p>
          </div>

      <div className="mt-5 space-y-3 text-sm text-slate-600">
            <InfoRow
              label="Selected voice"
              value={selectedVoice?.displayName || selectedVoiceName || 'Not selected yet'}
            />
            <InfoRow label="Voice style" value={selectedVoice?.styleHint || 'Standard'} />
            <InfoRow label="Category" value={selectedVoice?.category || 'Standard'} />
            <InfoRow label="Playback speed" value={`${speechRate.toFixed(1)}x`} />
          </div>

          <div className="mt-5 rounded-2xl bg-cream-50 p-4 text-sm leading-6 text-slate-600">
            Changes save automatically and will still be here after a refresh. The chosen voice is used for new
            conversation turns, and playback speed is applied in the browser for both preview and live audio.
          </div>
        </div>
      </section>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-cream-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className="mt-1 text-sm text-slate-700">{value}</p>
    </div>
  );
}

function VoiceSpeedSlider({
  id,
  value,
  onValueChange,
  ticks,
}: {
  id: string;
  value: number;
  onValueChange: (value: number[]) => void;
  ticks: number[];
}) {
  return (
    <SliderPrimitive.Root
      id={id}
      min={0.5}
      max={1.5}
      step={0.1}
      value={[value]}
      onValueChange={onValueChange}
      className="relative mt-5 flex h-12 w-full touch-none items-center select-none"
    >
      <div className="pointer-events-none absolute inset-0 rounded-[1.1rem] border border-cream-300 bg-gradient-to-b from-white to-cream-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_8px_18px_rgba(15,23,42,0.08)]" />

      <SliderPrimitive.Track className="absolute inset-x-2 top-1/2 h-11 -translate-y-1/2 overflow-hidden rounded-full">
        <div className="absolute inset-0 flex items-center justify-between px-3">
          {ticks.map((tick, index) => {
            const isMajor = tick === 0.5 || tick === 1 || tick === 1.5;
            const isMedium = !isMajor && index % 2 === 1;

            return (
              <span
                key={tick}
                className={`block w-px rounded-full ${
                  isMajor
                    ? 'h-5 bg-slate-300'
                    : isMedium
                      ? 'h-3.5 bg-cream-400'
                      : 'h-2.5 bg-cream-300'
                }`}
              />
            );
          })}
        </div>
        <SliderPrimitive.Range className="absolute inset-y-0 left-0 rounded-full bg-transparent" />
      </SliderPrimitive.Track>

      <SliderPrimitive.Thumb className="relative z-10 flex h-11 w-8 items-center justify-center rounded-[0.8rem] border border-navy-700 bg-gradient-to-b from-slate-700 to-navy-500 shadow-[0_10px_20px_rgba(15,23,42,0.22)] outline-none transition hover:scale-[1.02] focus-visible:ring-4 focus-visible:ring-navy-200">
        <Play className="ml-0.5 h-3 w-3 fill-amber-300 text-amber-300" />
      </SliderPrimitive.Thumb>
    </SliderPrimitive.Root>
  );
}

function cleanupPreview(
  previewAudioRef: { current: HTMLAudioElement | null },
  url: string,
  setIsPreviewing: (value: boolean) => void,
) {
  URL.revokeObjectURL(url);
  if (previewAudioRef.current?.src === url) {
    previewAudioRef.current = null;
  }
  setIsPreviewing(false);
}

function stopPreview(previewAudioRef: { current: HTMLAudioElement | null }) {
  const audio = previewAudioRef.current;
  if (!audio) {
    return;
  }

  audio.pause();
  audio.currentTime = 0;
  if (audio.src.startsWith('blob:')) {
    URL.revokeObjectURL(audio.src);
  }
  previewAudioRef.current = null;
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim()) {
    return error;
  }
  return fallback;
}
