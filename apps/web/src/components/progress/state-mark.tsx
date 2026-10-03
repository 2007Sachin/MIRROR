import type { DevState, ProgressAnswerState, ProgressSeen } from "@/lib/api";

export type MarkKind = DevState | ProgressAnswerState | ProgressSeen;

const SHAPE: Record<MarkKind, { shape: "full" | "half" | "alert" | "dashed" | "dot"; tone: string }> = {
  COMING_THROUGH: { shape: "full", tone: "is-clear" },
  STRONG: { shape: "full", tone: "is-clear" },
  DEVELOPING: { shape: "half", tone: "is-partial" },
  NEEDS_PRACTICE: { shape: "alert", tone: "is-attention" },
  NOT_EXPLORED: { shape: "dashed", tone: "is-quiet" },
  PRESENT: { shape: "dot", tone: "is-partial" },
  REPEATEDLY: { shape: "full", tone: "is-seen" },
  SOMETIMES: { shape: "half", tone: "is-seen" },
};

/**
 * One restrained marker per meaning. The shape differs as well as the colour, and the
 * meaning is always written out next to it, so colour is never the only signal.
 */
export function StateMark({ kind, size = 18 }: { kind: MarkKind; size?: number }) {
  const { shape, tone } = SHAPE[kind];
  return (
    <svg className={`pg-mark ${tone}`} width={size} height={size} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      {shape === "full" ? <circle cx="10" cy="10" r="7" fill="currentColor" /> : null}
      {shape === "half" ? (
        <>
          <circle cx="10" cy="10" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10 3.75a6.25 6.25 0 0 0 0 12.5Z" fill="currentColor" />
        </>
      ) : null}
      {shape === "alert" ? (
        <>
          <circle cx="10" cy="10" r="7" fill="currentColor" />
          <rect x="9.1" y="5.6" width="1.8" height="5.4" rx=".9" fill="#fff" />
          <circle cx="10" cy="13.7" r="1" fill="#fff" />
        </>
      ) : null}
      {shape === "dashed" ? (
        <circle cx="10" cy="10" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2.2 2.4" />
      ) : null}
      {shape === "dot" ? (
        <>
          <circle cx="10" cy="10" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="10" cy="10" r="2.2" fill="currentColor" />
        </>
      ) : null}
    </svg>
  );
}
