export const phases = ["INTRO", "BACKGROUND", "PROJECTS", "ROLE_CORE", "DEEP_DIVE", "BEHAVIOURAL", "CLOSING", "COMPLETE"] as const;
export type Phase = (typeof phases)[number];

export const turnTypes = ["planned", "depth_probe", "contradiction_probe", "ladder_up", "ladder_down", "recovery", "transition", "closing"] as const;
export type TurnType = (typeof turnTypes)[number];

export type TurnResponse = {
  question_text: string;
  audio_url: string | null;
  turn_index: number;
  phase: Phase;
  turn_type: TurnType;
};

export type ScoreStatus = "scored" | "not_enough_signal";


