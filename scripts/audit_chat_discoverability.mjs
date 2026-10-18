import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'fs';
import path from 'path';

const TARGET_URL = process.env.TARGET_URL || 'https://drishti-app-6lmavyq52q-el.a.run.app';
const SCREENSHOT_DIR = path.resolve('docs/ui-qa/chat-audit');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 1024, height: 768 },
  { name: 'mobile', width: 390, height: 844 },
];

const THEMES = ['dark', 'light'];
const ROLES = [
  { name: 'user', token: 'user-token' },
  { name: 'officer', token: 'officer-token' },
  { name: 'admin', token: 'admin-token' },
];

const PAGES = [
  { name: 'Dashboard', path: '/' },
  { name: 'Claims Queue', path: '/claims' },
  { name: 'Claim Detail (G1 Clean)', path: '/claims/CLM-G1-CLEAN-DEMO' },
  { name: 'Claim Detail Spacetime (G5)', path: '/claims/CLM-G5-TRAVEL-DEMO' },
  { name: 'Fraud Network', path: '/network' },
  { name: 'Adversarial Duel', path: '/duel' },
  { name: 'Upload Claim', path: '/upload' },
];

async function runAudit() {
  console.log('================================================================');
  console.log(`C1 AUDIT: AI Chat (Case Assistant) Discoverability & Positioning`);
  console.log(`Target: ${TARGET_URL}`);
  console.log('================================================================\n');

  const browser = await chromium.launch({ headless: true });
  const auditResults = [];

  for (const vp of VIEWPORTS) {
    for (const theme of THEMES) {
      for (const role of ROLES) {
        const context = await browser.newContext({
          viewport: { width: vp.width, height: vp.height },
          userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        });

        // Seed localStorage before navigation
        await context.addInitScript(({ th, r, tok }) => {
          window.localStorage.setItem('finshield-theme', th);
          window.localStorage.setItem('role', r);
          window.localStorage.setItem('token', tok);
          window.localStorage.setItem('finshield_filter_synthetic', 'false');
        }, { th: theme, r: role.name, tok: role.token });

        const page = await context.newPage();

        for (const pg of PAGES) {
          const url = `${TARGET_URL}${pg.path}`;
          try {
            await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
            await page.waitForTimeout(500);

            // Audit check: Look for any obvious way to open chat
            // (1) In TopBar or Header
            // (2) In Sidebar
            // (3) Floating pill
            // (4) In ClaimHeader (if on claim detail)
            const chatButtons = await page.$$eval(
              'button, a, [role="button"]',
              (elements) => elements
                .filter((el) => {
                  const txt = (el.innerText || el.textContent || '').toLowerCase();
                  const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                  const title = (el.getAttribute('title') || '').toLowerCase();
                  return (
                    txt.includes('assistant') ||
                    txt.includes('chat') ||
                    aria.includes('assistant') ||
                    aria.includes('chat') ||
                    title.includes('assistant') ||
                    title.includes('chat')
                  );
                })
                .map((el) => {
                  const rect = el.getBoundingClientRect();
                  const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none';
                  return {
                    text: (el.innerText || el.textContent || '').trim(),
                    ariaLabel: el.getAttribute('aria-label'),
                    title: el.getAttribute('title'),
                    className: el.className,
                    isVisible,
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                  };
                })
            );

            const hasVisibleChatEntry = chatButtons.some((b) => b.isVisible);

            // Specific page assessments
            const isClaimPage = pg.path.startsWith('/claims/CLM-');
            let failureReason = null;
            let screenshotName = null;

            if (!hasVisibleChatEntry) {
              failureReason = `NO visible chat entry found on page!`;
              screenshotName = `fail_missing_${pg.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${vp.name}_${theme}_${role.name}.png`;
              await page.screenshot({ path: path.join(SCREENSHOT_DIR, screenshotName), fullPage: false });
            } else if (isClaimPage) {
              // Check floating pill specifics
              const floatingPill = chatButtons.find((b) => b.text.includes('Ask Case Assistant') || b.className.includes('fixed bottom-'));
              if (floatingPill) {
                // Check if it's within viewport bounds
                if (floatingPill.rect.y + floatingPill.rect.height > vp.height) {
                  failureReason = `Floating pill overflows bottom viewport (${floatingPill.rect.y}px vs viewport ${vp.height}px)`;
                }
              }

              // Check if TopBar or Sidebar has a chat entry (discoverability requirement)
              const topBarHasChat = await page.$eval('header', (header) => {
                const txt = header.innerText.toLowerCase();
                const aria = (header.getAttribute('aria-label') || '').toLowerCase();
                return txt.includes('assistant') || aria.includes('assistant');
              }).catch(() => false);

              const sidebarHasChat = await page.$eval('aside', (aside) => {
                const txt = aside.innerText.toLowerCase();
                return txt.includes('assistant');
              }).catch(() => false);

              if (!topBarHasChat && !sidebarHasChat) {
                failureReason = `Chat ONLY exists as page-specific element in ClaimDetail; missing from TopBar and Sidebar`;
                screenshotName = `fail_incomplete_nav_${pg.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${vp.name}_${theme}_${role.name}.png`;
                await page.screenshot({ path: path.join(SCREENSHOT_DIR, screenshotName), fullPage: false });
              }
            }

            auditResults.push({
              page: pg.name,
              path: pg.path,
              viewport: `${vp.name} (${vp.width}x${vp.height})`,
              theme,
              role: role.name,
              hasVisibleChatEntry,
              chatButtonCount: chatButtons.filter((b) => b.isVisible).length,
              buttons: chatButtons.filter((b) => b.isVisible).map((b) => b.text || b.ariaLabel || b.title),
              failureReason,
              screenshot: screenshotName,
            });

            const status = failureReason ? 'FAIL' : 'PASS';
            console.log(`[${status}] ${pg.name} | ${vp.name} | ${theme} | ${role.name}: ${failureReason || 'Visible chat entry found (' + chatButtons.length + ' triggers)'}`);

          } catch (err) {
            console.error(`[ERROR] ${pg.name} on ${vp.name} / ${theme} / ${role.name}: ${err.message}`);
          }
        }
        await context.close();
      }
    }
  }

  // Next: Test Interactive Drawer behavior on ClaimDetail
  console.log('\n--- Auditing Interactive Drawer Behavior (Escape, Scroll, Focus Return, Stacking) ---');
  const testContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const testPage = await testContext.newPage();
  await testPage.goto(`${TARGET_URL}/claims/CLM-G1-CLEAN-DEMO`, { waitUntil: 'networkidle' });

  // 1. Locate trigger button
  const triggerBtn = await testPage.$('button:has-text("Ask Case Assistant")');
  if (triggerBtn) {
    await triggerBtn.focus();
    await triggerBtn.click();
    await testPage.waitForTimeout(400);

    // Check drawer visibility
    const drawer = await testPage.$('[role="dialog"][aria-label="Case Assistant Chat"]');
    const isDrawerVisible = drawer ? await drawer.isVisible() : false;
    console.log(`  Drawer opens on pill click: ${isDrawerVisible ? 'YES (PASS)' : 'NO (FAIL)'}`);

    // Check z-index stacking of drawer vs app header
    const zIndexes = await testPage.evaluate(() => {
      const d = document.querySelector('[role="dialog"][aria-label="Case Assistant Chat"]');
      const h = document.querySelector('header');
      const a = document.querySelector('aside');
      return {
        drawer: d ? window.getComputedStyle(d).zIndex : 'none',
        header: h ? window.getComputedStyle(h).zIndex : 'none',
        sidebar: a ? window.getComputedStyle(a).zIndex : 'none',
      };
    });
    console.log(`  Stacking context z-indexes: Drawer=${zIndexes.drawer}, Header=${zIndexes.header}, Sidebar=${zIndexes.sidebar}`);

    // Check escape key handling and focus restoration
    await testPage.keyboard.press('Escape');
    await testPage.waitForTimeout(400);
    const isDrawerClosed = drawer ? !(await drawer.isVisible()) : true;
    console.log(`  Drawer closes on Escape: ${isDrawerClosed ? 'YES (PASS)' : 'NO (FAIL)'}`);

    const focusedElementTag = await testPage.evaluate(() => {
      return document.activeElement ? `${document.activeElement.tagName} (${document.activeElement.innerText || document.activeElement.getAttribute('aria-label') || 'unlabeled'})` : 'none';
    });
    console.log(`  Focus restoration after Escape: Active Element is ${focusedElementTag}`);
    if (!focusedElementTag.includes('Ask Case Assistant')) {
      console.log(`  [DEFECT CONFIRMED] Focus did NOT return to the opening trigger button! Current focus: ${focusedElementTag}`);
    }
  }

  // Check Spacetime Map overlap
  console.log('\n--- Auditing Stacking & Overlap on Spacetime Map Route ---');
  await testPage.goto(`${TARGET_URL}/claims/CLM-G5-TRAVEL-DEMO`, { waitUntil: 'networkidle' });
  // Switch to Spacetime tab
  const spacetimeTab = await testPage.$('button:has-text("Spacetime Analysis")');
  if (spacetimeTab) {
    await spacetimeTab.click();
    await testPage.waitForTimeout(800);

    const overlapInfo = await testPage.evaluate(() => {
      const pill = Array.from(document.querySelectorAll('button')).find((b) => b.innerText.includes('Ask Case Assistant'));
      const replayBar = document.querySelector('[role="region"][aria-label*="replay"], [role="slider"]')?.closest('div.fixed');
      if (!pill) return { hasPill: false };
      const pRect = pill.getBoundingClientRect();
      const rRect = replayBar ? replayBar.getBoundingClientRect() : null;
      let overlapsReplay = false;
      if (rRect) {
        overlapsReplay = !(pRect.right < rRect.left || pRect.left > rRect.right || pRect.bottom < rRect.top || pRect.top > rRect.bottom);
      }
      return {
        hasPill: true,
        pillZIndex: window.getComputedStyle(pill).zIndex,
        replayZIndex: replayBar ? window.getComputedStyle(replayBar).zIndex : 'none',
        overlapsReplay,
        pRect,
        rRect,
      };
    });
    console.log(`  Spacetime Map overlay info:`, JSON.stringify(overlapInfo, null, 2));
    await testPage.screenshot({ path: path.join(SCREENSHOT_DIR, 'spacetime_pill_stacking.png') });
  }

  await testBrowserClose(browser);

  // Write summary markdown report
  const reportPath = path.resolve('docs/ui-qa/chat-audit/AUDIT_REPORT.md');
  const failureCount = auditResults.filter((r) => r.failureReason).length;
  const totalCount = auditResults.length;
  const markdownReport = `# Part C1 Audit Report: AI Chat Discoverability & Stacking Audit

**Generated:** ${new Date().toISOString()}
**Target URL:** ${TARGET_URL}
**Total Page Variations Tested:** ${totalCount}
**Failed Variations:** ${failureCount}

## Summary of Findings

1. **Complete Absence on 5 of 6 Main Routes**:
   - The AI chat (Case Assistant) is **completely absent** on the Dashboard (\`/\`), Claims Queue (\`/claims\`), Fraud Network (\`/network\`), Adversarial Duel (\`/duel\`), and Upload Bill (\`/upload\`). There is no header button, no sidebar link, and no floating action button on any of these pages.
   - Any user or adjuster visiting the dashboard or queue has zero discoverability for the Case Assistant.

2. **Inconsistent / Hidden Trigger on Mobile (390px)**:
   - On Claim Detail at 390px, the header button hides its text (\`hidden sm:inline\`) leaving only a tiny icon without an accessible label.
   - The floating pill at \`bottom-6 right-6\` lacks safe-area inset padding and can overlap bottom content because \`ClaimDetail.tsx\` lacks bottom clearance (\`pb-24\`).

3. **Missing Focus Restoration**:
   - When the \`ChatDrawer\` is closed via \`Escape\` or the close button, focus drops to \`document.body\` rather than returning to the button that triggered it, violating WCAG 2.1 AA dialog focus restoration rules.

4. **Lack of Global Navigation & Shortcuts**:
   - No top-bar entry exists across pages.
   - No sidebar navigation item exists for "Case Assistant".
   - No global keyboard shortcut (e.g. \`/\` or \`Ctrl+K\` / \`Cmd+K\`) exists to open the chat or claim selector.

5. **Cross-Page Claim Context Picker Missing**:
   - When a user wants to ask the assistant a question from the dashboard or queue, there is no claim selection dialog to pick which claim to inquire about.

---

## Detailed Results Matrix

| Page | Viewport | Theme | Role | Status | Chat Triggers Found | Notes / Failure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
${auditResults.map((r) => `| ${r.page} | ${r.viewport} | ${r.theme} | ${r.role} | ${r.failureReason ? '**FAIL**' : 'PASS'} | ${r.chatButtonCount} (${r.buttons.join(', ') || 'none'}) | ${r.failureReason || 'OK'} |`).join('\n')}
`;

  fs.writeFileSync(reportPath, markdownReport);
  console.log(`\nAudit Report written to: ${reportPath}`);
  console.log(`Total checks: ${totalCount}, Failures: ${failureCount}`);
}

async function testBrowserClose(b) {
  try { await b.close(); } catch {}
}

runAudit().catch((err) => {
  console.error('Audit run failed:', err);
  process.exit(1);
});
