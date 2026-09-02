"use client";

import { useEffect, useRef, useState } from "react";

type MirrorOrbProps = { activeStep: number };

export function MirrorOrb({ activeStep }: MirrorOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;

    const draw = (timestamp: number) => {
      const size = canvas.getBoundingClientRect().width;
      const ratio = Math.min(window.devicePixelRatio || 1, 3);
      const pixels = Math.max(1, Math.round(size * ratio));
      if (canvas.width !== pixels || canvas.height !== pixels) {
        canvas.width = pixels;
        canvas.height = pixels;
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, size, size);

      const time = timestamp / 1000;
      const speed = hovered ? 1.18 : 1;
      const phase = time * speed;
      const center = size / 2;
      const base = size * 0.285;
      const breathing = 1 + Math.sin(phase * 1.55 + activeStep * 0.3) * 0.045;
      const radius = base * breathing;

      const aura = context.createRadialGradient(center, center, radius * 0.25, center, center, radius * 2.3);
      aura.addColorStop(0, "rgba(79, 209, 165, 0.22)");
      aura.addColorStop(0.35, "rgba(79, 209, 165, 0.11)");
      aura.addColorStop(1, "rgba(79, 209, 165, 0)");
      context.fillStyle = aura;
      context.beginPath();
      context.arc(center, center, radius * 2.3, 0, Math.PI * 2);
      context.fill();

      const drawLobe = (x: number, y: number, lobeRadius: number, color: string) => {
        const lobe = context.createRadialGradient(x - lobeRadius * 0.34, y - lobeRadius * 0.38, 0, x, y, lobeRadius);
        lobe.addColorStop(0, color);
        lobe.addColorStop(0.72, "rgba(79, 209, 165, 0.12)");
        lobe.addColorStop(1, "rgba(79, 209, 165, 0)");
        context.fillStyle = lobe;
        context.beginPath();
        context.arc(x, y, lobeRadius, 0, Math.PI * 2);
        context.fill();
      };

      context.save();
      context.globalCompositeOperation = "screen";
      drawLobe(center - radius * 0.44 + Math.sin(phase * 0.9) * radius * 0.08, center - radius * 0.2, radius * 0.96, "rgba(196, 255, 232, 0.48)");
      drawLobe(center + radius * 0.4 + Math.cos(phase * 0.7) * radius * 0.1, center + radius * 0.2, radius * 0.9, "rgba(79, 209, 165, 0.48)");
      drawLobe(center + Math.sin(phase * 0.8) * radius * 0.15, center + radius * 0.48, radius * 0.72, "rgba(35, 159, 125, 0.42)");
      context.restore();

      const sphere = context.createRadialGradient(center - radius * 0.34, center - radius * 0.42, radius * 0.04, center, center, radius * 1.08);
      sphere.addColorStop(0, "rgba(242, 255, 250, 0.92)");
      sphere.addColorStop(0.18, "rgba(154, 244, 210, 0.86)");
      sphere.addColorStop(0.58, "rgba(52, 193, 148, 0.72)");
      sphere.addColorStop(0.86, "rgba(23, 107, 86, 0.48)");
      sphere.addColorStop(1, "rgba(7, 45, 37, 0.06)");
      context.fillStyle = sphere;
      context.beginPath();
      context.arc(center, center, radius, 0, Math.PI * 2);
      context.fill();

      context.save();
      context.globalCompositeOperation = "screen";
      for (let index = 0; index < 240; index += 1) {
        const angle = index * 2.39996 + phase * 0.18;
        const latitude = ((index * 37) % 100) / 100;
        const wobble = Math.sin(angle * 2.7 + phase * 0.9) * radius * 0.035;
        const distance = radius * (0.18 + latitude * 0.74) + wobble;
        const x = center + Math.cos(angle) * distance;
        const y = center + Math.sin(angle) * distance * 0.72;
        const dot = 0.45 + ((index * 13) % 10) / 12;
        context.fillStyle = `rgba(237, 255, 247, ${0.05 + dot * 0.16})`;
        context.beginPath();
        context.arc(x, y, dot * Math.max(0.7, size / 260), 0, Math.PI * 2);
        context.fill();
      }
      context.restore();

      if (!reduced) frame = requestAnimationFrame(draw);
    };

    if (reduced) draw(0);
    else frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [activeStep, hovered]);

  return (
    <div className="relative mx-auto flex min-h-[26rem] w-full max-w-[31rem] items-center justify-center" onPointerEnter={() => setHovered(true)} onPointerLeave={() => setHovered(false)}>
      <canvas ref={canvasRef} className="orb-voice" role="img" aria-label="Mirror voice orb" />
    </div>
  );
}


