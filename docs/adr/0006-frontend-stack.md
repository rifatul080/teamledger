# ADR-0006 — React + Vite + TypeScript (strict) + TanStack Query + Tailwind

- **Status:** accepted
- **Context:** Spec says React, TypeScript strict, Vite, TanStack Query, Tailwind. Accessibility matters (phone + keyboard + screen reader).
- **Decision:** Vite + React 18 + TS 5 with `strict: true`. TanStack Query for server state. Tailwind for styling. Headless primitives (Radix) for menus/dialogs to keep a11y costs low.
- **Consequences:**
  - Strict TS catches bugs at edit time; ESLint catches unused/lint issues.
  - TanStack Query removes a whole class of "fetch in useEffect" bugs and gives us cache invalidation per requirement.
  - Tailwind keeps CSS predictable and tree-shakes unused styles.
  - Radix handles focus traps, ARIA roving, and ESC-to-close.
- **Alternatives considered:**
  - Next.js — overkill (no SSR requirement, single-tenant web app).
  - Redux Toolkit — TanStack Query is enough for server state; local UI state stays in components/Zustand.
