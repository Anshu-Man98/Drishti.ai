# Part C1 Audit Report: AI Chat Discoverability & Stacking Audit

**Generated:** 2026-10-18T03:28:12.128Z
**Target URL:** https://drishti-app-6lmavyq52q-el.a.run.app
**Total Page Variations Tested:** 126
**Failed Variations:** 126

## Summary of Findings

1. **Complete Absence on 5 of 6 Main Routes**:
   - The AI chat (Case Assistant) is **completely absent** on the Dashboard (`/`), Claims Queue (`/claims`), Fraud Network (`/network`), Adversarial Duel (`/duel`), and Upload Bill (`/upload`). There is no header button, no sidebar link, and no floating action button on any of these pages.
   - Any user or adjuster visiting the dashboard or queue has zero discoverability for the Case Assistant.

2. **Inconsistent / Hidden Trigger on Mobile (390px)**:
   - On Claim Detail at 390px, the header button hides its text (`hidden sm:inline`) leaving only a tiny icon without an accessible label.
   - The floating pill at `bottom-6 right-6` lacks safe-area inset padding and can overlap bottom content because `ClaimDetail.tsx` lacks bottom clearance (`pb-24`).

3. **Missing Focus Restoration**:
   - When the `ChatDrawer` is closed via `Escape` or the close button, focus drops to `document.body` rather than returning to the button that triggered it, violating WCAG 2.1 AA dialog focus restoration rules.

4. **Lack of Global Navigation & Shortcuts**:
   - No top-bar entry exists across pages.
   - No sidebar navigation item exists for "Case Assistant".
   - No global keyboard shortcut (e.g. `/` or `Ctrl+K` / `Cmd+K`) exists to open the chat or claim selector.

5. **Cross-Page Claim Context Picker Missing**:
   - When a user wants to ask the assistant a question from the dashboard or queue, there is no claim selection dialog to pick which claim to inquire about.

---

## Detailed Results Matrix

| Page | Viewport | Theme | Role | Status | Chat Triggers Found | Notes / Failure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Dashboard | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | desktop (1440x900) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | tablet (1024x768) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | dark | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | dark | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | dark | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | light | user | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | light | officer | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Dashboard | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claims Queue | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail (G1 Clean) | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Claim Detail Spacetime (G5) | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Fraud Network | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Adversarial Duel | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
| Upload Claim | mobile (390x844) | light | admin | **FAIL** | 0 (none) | NO visible chat entry found on page! |
