---
name: mirror-visual-design
description: Guides distinctive, production-grade visual design for Mirror landing pages and candidate-facing UI. Use for art direction, color, typography, composition, product proof, motion, responsive polish, and visual QA.
---

# Mirror Visual Design

Use this skill when redesigning or polishing Mirror UI. Read `mirror-product`, `mirror-frontend`, and the current route/components first. Preserve product truth and candidate safety.

## Core standard

Design from the product mechanism, not from generic AI aesthetics. Mirror should feel precise, credible, intelligent, calm, and memorable. The visual system must communicate evidence, interrogation of claims, uncertainty, and readiness without resembling a chatbot, crypto dashboard, neon AI demo, or card-template SaaS page.

## Workflow

1. Identify the screen's single primary job and the first thing the user must understand.
2. Inspect existing tokens, typography, assets, states, and responsive behavior before proposing change.
3. Choose one explicit art direction and state why it fits Mirror.
4. Use product proof as the hero visual whenever possible: claim, role requirement, follow-up, evidence, and diagnostic output.
5. Build hierarchy through scale, spacing, contrast, typography, and composition before adding decoration.
6. Use a restrained palette with one primary accent and one optional diagnostic accent. Do not spread accents evenly across the page.
7. Prefer structured surfaces, hairlines, editorial grids, and real UI fragments over rounded card grids, glassmorphism, gradient blobs, or generic AI illustrations.
8. Motion must explain state change. Avoid continuous decorative loops, floating particles, scroll-jacking, or animation that competes with comprehension.
9. Verify desktop and mobile renders. Check 1440, 1280, 1024, 768, 430, and 375px where tooling allows.
10. Respect `prefers-reduced-motion`, semantic HTML, focus visibility, touch sizes, contrast, and text labels for status.

## Mirror-specific visual rules

- The orb is a brand/acoustic motif, not evidence of product value. Never let a decorative orb dominate the marketing hero. If retained, use it as subtle secondary atmosphere or redesign it so it clearly represents interview/audio state rather than candidate quality.
- Never use color to imply hidden performance during an interview.
- Show uncertainty explicitly; do not use gamified gauges or false precision.
- Prefer ranges, evidence rows, trace lines, source snippets, claim states, and diagnostic panels.
- Synthetic examples must be visibly labeled as demo/illustrative.
- Never expose chain-of-thought, internal agent labels, hidden prompts, or evaluator weights.

## Anti-patterns

Avoid purple/indigo AI gradients by default, excessive glow, oversized rounded cards, identical three-column feature grids, random icon tiles, stock photography, robot/brain/sparkle imagery, shadow-heavy surfaces, giant empty hero whitespace, and decorative visuals that explain nothing.

## Completion gate

Before accepting a redesign, ask: Can a first-time visitor understand what Mirror does in five seconds? Is the product mechanism visible before generic benefits? Does the page look intentional rather than generated? Is the main visual product proof rather than decoration? Does mobile preserve the same hierarchy?