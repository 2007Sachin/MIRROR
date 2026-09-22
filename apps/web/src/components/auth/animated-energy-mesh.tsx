"use client";

import { useEffect, useState } from "react";

type AnimatedEnergyMeshProps = {
  energized?: boolean;
  variant?: "default" | "compact";
};

/**
 * A static evidence-pipeline diagram: claim source -> target role ->
 * interview evidence. This replaced an earlier continuous WebGL animation
 * (rotating noise-displaced mesh, drifting particles, cyan/violet/magenta
 * glow) that ran on a loop regardless of page state -- exactly the kind of
 * ambient decorative motion and AI-gradient/glow treatment mirror-visual-design
 * rules out, and it sat behind a credential form where calm trumps spectacle.
 *
 * Per mirror-visual-design, motion should explain a state change rather than
 * loop decoratively. So this diagram renders inert by default and fades in
 * once on mount; the terminal ("evidence") node only pulses while `energized`
 * is true, meaning the caller has real work in flight -- an auth request
 * submitting, or (in its other call site, the workspace dashboard's compact
 * reuse) a diagnostic actually processing. Idle, nothing moves.
 */
export function AnimatedEnergyMesh({ energized = false, variant = "default" }: AnimatedEnergyMeshProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div
      className={`mirror-mesh${variant === "compact" ? " mirror-mesh--compact" : ""}${mounted ? " mirror-mesh--in" : ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 220 130" className="mirror-mesh-svg" role="presentation" focusable="false">
        <line x1="28" y1="66" x2="108" y2="26" className="mirror-mesh-line" />
        <line x1="108" y1="26" x2="188" y2="66" className="mirror-mesh-line" />
        <line x1="108" y1="26" x2="108" y2="104" className="mirror-mesh-line" />
        <circle cx="28" cy="66" r="6" className="mirror-mesh-node" />
        <circle cx="188" cy="66" r="6" className="mirror-mesh-node" />
        <circle cx="108" cy="26" r="6" className="mirror-mesh-node" />
        <circle cx="108" cy="104" r="6" className={`mirror-mesh-node${energized ? " is-active" : ""}`} />
      </svg>
      <ul className="mirror-mesh-legend">
        <li>Your resume</li>
        <li>Target role</li>
        <li>Your answers</li>
      </ul>
    </div>
  );
}
