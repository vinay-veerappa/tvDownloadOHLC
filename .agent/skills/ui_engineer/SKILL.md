---
name: UI Engineer
description: Specialized skill for building modern, high-performance web UIs using Next.js, Tailwind, and Shadcn/UI.
applyTo: "**/*.{ts,tsx,js,jsx}"
---

# UI Engineer

## When to use

Use when building modern, high-performance web UIs — Next.js, TypeScript, Tailwind CSS patterns and conventions.

## Purpose
This skill embodies the role of a Frontend Specialist. Use it when implementing new features or refactoring the web interface (`tvDownloadOHLC/web/`).

## Tech Stack
- **Framework**: Next.js 16 (App Router)
- **Styling**: Tailwind CSS v4
- **Components**: Shadcn/UI (Radix Primitives)
- **Icons**: Lucide React
- **Charts**: Lightweight Charts v5
- **State**: React Context + SWR

## Best Practices

### 1. Component Design
- **Atomicity**: Break down complex views into small, reusable components.
- **Props**: Use TypeScript interfaces for all props.
- **Composition**: Prefer composition over large prop-drilling configurations.

### 2. Styling (Tailwind)
- **Utility-First**: Use utility classes directly.
- **Theme Tokens**: Use `bg-background`, `text-foreground`, `border-border` (shadcn-defined variables) instead of hardcoded hex values to support Dark Mode.
- **Layout**: Use Flexbox and Grid. Avoid floats.

### 3. State Management
- **Server State**: Use `useSWR` or Server Components where possible.
- **Local State**: Use `useState` / `useReducer` for UI toggles.
- **Global State**: Use Context specific to the domain (e.g., `TradingContext`).

### 4. Code Quality
- **Linting**: Ensure no `eslint` warnings introduced.
- **Types**: No `any`. Explicitly type event handlers.

## Workflow
1.  **Analyze**: Understand the UI requirement.
2.  **Scaffold**: Create file structure in `app/` or `components/`.
3.  **Implement**: Write code using the stack above.
4.  **Verify**: Run `npm run lint` and verify build.
