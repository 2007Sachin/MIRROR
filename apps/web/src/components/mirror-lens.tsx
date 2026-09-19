export function MirrorLens({ className = "" }: { className?: string }) {
  return (
    <div className={`ld-lens${className ? ` ${className}` : ""}`} aria-hidden="true">
      <svg viewBox="0 0 240 240" fill="none" focusable="false">
        <circle className="ld-lens-ring ld-lens-ring-one" cx="120" cy="120" r="92" />
        <circle className="ld-lens-ring ld-lens-ring-two" cx="120" cy="120" r="66" />
        <circle className="ld-lens-ring ld-lens-ring-three" cx="120" cy="120" r="39" />
        <path className="ld-lens-trace" d="M28 120h42m100 0h42M120 28v42m0 100v42" />
        <circle className="ld-lens-node ld-lens-node-a" cx="178" cy="87" r="4" />
        <circle className="ld-lens-node ld-lens-node-b" cx="80" cy="158" r="4" />
        <circle className="ld-lens-core" cx="120" cy="120" r="9" />
      </svg>
    </div>
  );
}
