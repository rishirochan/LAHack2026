'use client';

export type VoiceOption = {
  voiceId: string;
  name: string;
  displayName: string;
  styleHint: string | null;
  category: string | null;
  description: string | null;
  previewUrl: string | null;
  isDefault: boolean;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function fetchVoiceOptions(): Promise<VoiceOption[]> {
  const response = await fetch(`${API_URL}/api/tts/voices`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(body || 'Could not load voice options.');
  }

  const data = (await response.json()) as {
    voices?: Array<{
      voice_id?: string;
      name?: string;
      category?: string | null;
      description?: string | null;
      preview_url?: string | null;
      is_default?: boolean;
    }>;
  };

  return (data.voices ?? []).map((voice) => {
    const fullName = String(voice.name ?? 'Unnamed voice');
    const [displayName, ...styleParts] = fullName.split(' - ');

    return {
      voiceId: String(voice.voice_id ?? ''),
      name: fullName,
      displayName: displayName.trim() || fullName,
      styleHint: styleParts.join(' - ').trim() || null,
      category: voice.category ?? null,
      description: voice.description ?? null,
      previewUrl: voice.preview_url ?? null,
      isDefault: Boolean(voice.is_default),
    };
  });
}

export async function fetchVoicePreviewAudio(input: {
  voiceId?: string | null;
  voiceName: string;
  text?: string;
}): Promise<Blob> {
  const response = await fetch(`${API_URL}/api/tts/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      voice_id: input.voiceId,
      voice_name: input.voiceName,
      text: input.text,
    }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(detail || 'Could not generate the voice preview.');
  }

  return response.blob();
}
