export type Theme =
  | "Job Interview"
  | "Salary Negotiation"
  | "Casual Conversation"
  | "Public Speaking";

export type TargetEmotion =
  | "Confident"
  | "Enthusiastic"
  | "Calm"
  | "Assertive"
  | "Passionate";

export type SessionStatus =
  | "setup"
  | "scenario"
  | "recording"
  | "processing"
  | "critique"
  | "summary"
  | "error";

export type SessionSetup = {
  theme: Theme;
  targetEmotion: TargetEmotion;
  difficulty: number;
};

export type RoundSummary = {
  scenario_prompt: string;
  critique: string;
  match_score: number;
  filler_words_found: string[];
  filler_word_count: number;
};

export type SessionSummary = {
  session_id: string;
  critiques: string[];
  match_scores: number[];
  filler_words: Record<string, number>;
  rounds: RoundSummary[];
};

export type RoundResult = {
  critique: string;
  match_score: number;
  filler_words_found: string[];
  filler_word_count: number;
};

