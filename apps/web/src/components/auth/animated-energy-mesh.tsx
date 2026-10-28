"use client";

import { useEffect, useState } from "react";

type AnimatedEnergyMeshProps = {
  energized?: boolean;
  variant?: "default" | "compact";
};

/**
 * Quiet three-node mark for the sign-in desk: resume, role, answers.
 * The mark is still until `energized` is true. That state only fills the
 * answers node. auth.css transitions the fill and drops the transition
 * under prefers-reduced-motion, so nothing loops.
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
      <svg viewBox="0 0 240 40" className="mirror-mesh-svg" role="presentation" focusable="false">
        <line x1="40" y1="20" x2="200" y2="20" className="mirror-mesh-line" />
        <circle cx="40" cy="20" r="5.5" className="mirror-mesh-node" />
        <circle cx="120" cy="20" r="5.5" className="mirror-mesh-node" />
        <circle cx="200" cy="20" r="5.5" className={`mirror-mesh-node${energized ? " is-active" : ""}`} />
      </svg>
      <ul className="mirror-mesh-legend">
        <li>Your resume</li>
        <li>Target role</li>
        <li>Your answers</li>
      </ul>
    </div>
  );
}
