"use client";

/**
 * Entrance-only scroll reveal, shared across every redesigned page so motion
 * stays consistent and centrally respects prefers-reduced-motion.
 *
 * Per mirror-visual-design: motion must explain state change, never loop
 * decoratively. This fires once when a section enters the viewport and stops.
 *
 * Usage:
 *   <Reveal><section>...</section></Reveal>
 *   <Reveal as="ul" stagger><li>...</li><li>...</li></Reveal>
 */
import { createElement, ElementType, ReactNode, useEffect, useRef, useState } from "react";

export function useInView<T extends HTMLElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px", ...options },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [options]);

  return { ref, inView };
}

export function Reveal({
  children,
  as: Tag = "div",
  stagger = false,
  className = "",
  delay,
}: {
  children: ReactNode;
  as?: ElementType;
  stagger?: boolean;
  className?: string;
  delay?: number;
}) {
  const { ref, inView } = useInView<HTMLElement>();
  const base = stagger ? "reveal-stagger" : "reveal";
  return createElement(
    Tag,
    {
      ref,
      className: `${base}${inView ? " is-visible" : ""}${className ? ` ${className}` : ""}`,
      style: delay ? { animationDelay: `${delay}ms` } : undefined,
    },
    children,
  );
}
