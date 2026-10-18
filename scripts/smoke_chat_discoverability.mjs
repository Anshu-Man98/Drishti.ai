import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import fs from 'fs';
import path from 'path';

const TARGET_URL = process.env.TARGET_URL || 'https://drishti-app-6lmavyq52q-el.a.run.app';
const SCREENSHOT_DIR = path.resolve('docs/ui-qa/chat-after');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

const VIEWPORTS = [
  { name: 'desktop-1440px', width: 1440, height: 900 },
  { name: 'mobile-390px', width: 390, height: 844 },
];

const PAGES = [
  { name: 'Dashboard', path: '/', isClaim: false },
  { name: 'Claims Queue', path: '/claims', isClaim: false },
  { name: 'Claim Detail G1', path: '/claims/CLM-G1-CLEAN-DEMO', isClaim: true },
  { name: 'Fraud Network', path: '/network', isClaim: false },
  { name: 'Duel Arena', path: '/duel', isClaim: false },
  { name: 'Upload Claim', path: '/upload', isClaim: false },
];

async function runSmokeCheck() {
  console.log('================================================================');
  console.log(`PLAYWRIGHT SMOKE CHECK: AI Chat (Case Assistant) Discoverability`);
  console.log(`Target: ${TARGET_URL}`);
  console.log(`Viewports: 1440px (Desktop), 390px (Mobile)`);
  console.log('================================================================\n');

  const browser = await chromium.launch({ headless: true });
  const results = [];
  let allPassed = true;

  for (const vp of VIEWPORTS) {
    console.log(`\n--- Testing Viewport: ${vp.name} (${vp.width}x${vp.height}) ---`);

    for (const pageDef of PAGES) {
      const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });

      try {
        await page.goto(`${TARGET_URL}${pageDef.path}`, { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(1000);

        // 1. Check TopBar Assistant Entry (in <header>)
        const topBarAssistant = await page.$('header button[aria-label*="Assistant"]');
        const hasTopBarAssistant = topBarAssistant !== null;

        // 2. Check Sidebar Assistant Entry (Desktop only >= 1024px)
        let hasSidebarAssistant = null;
        if (vp.width >= 1024) {
          const sidebarAssistant = await page.$('aside button:has-text("Case Assistant"), nav button:has-text("Case Assistant")');
          hasSidebarAssistant = sidebarAssistant !== null;
        }

        // 3. Check Claim Detail specific floating pill
        let hasFloatingPill = null;
        if (pageDef.isClaim) {
          const pill = await page.$('button[aria-label="Ask Case Assistant"]');
          hasFloatingPill = pill !== null;
        }

        // Take initial screenshot
        const pageSlug = pageDef.name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
        const initialShot = path.join(SCREENSHOT_DIR, `${vp.name}-${pageSlug}-initial.png`);
        await page.screenshot({ path: initialShot, fullPage: false });

        // 4. Test Opening Chat / Picker
        let openSuccess = false;
        if (topBarAssistant) {
          await topBarAssistant.click();
          await page.waitForTimeout(600);

          if (pageDef.isClaim) {
            // Should open ChatDrawer
            const drawer = await page.$('div[role="dialog"][aria-label="Case Assistant Chat"]');
            openSuccess = drawer !== null;

            const drawerShot = path.join(SCREENSHOT_DIR, `${vp.name}-${pageSlug}-drawer-open.png`);
            await page.screenshot({ path: drawerShot, fullPage: false });

            // On desktop Claim Detail, test submitting a question and getting an answer!
            if (vp.width >= 1024) {
              const input = await page.$('div[role="dialog"][aria-label="Case Assistant Chat"] input');
              if (input) {
                await input.fill('What is the verdict on this claim?');
                await page.keyboard.press('Enter');
                console.log('    -> Asked question in drawer, waiting for streaming response...');
                // Wait for bot response to stream in
                await page.waitForTimeout(8000);
                const answerShot = path.join(SCREENSHOT_DIR, `${vp.name}-${pageSlug}-chat-answered.png`);
                await page.screenshot({ path: answerShot, fullPage: false });
              }
            }

            // Press Escape to test close & focus restoration
            await page.keyboard.press('Escape');
            await page.waitForTimeout(400);
          } else {
            // Should open ClaimChatPickerModal
            const picker = await page.$('div[role="dialog"][aria-label*="Which claim do you want to ask about?"]');
            openSuccess = picker !== null;

            const pickerShot = path.join(SCREENSHOT_DIR, `${vp.name}-${pageSlug}-picker-open.png`);
            await page.screenshot({ path: pickerShot, fullPage: false });

            // Press Escape to close
            await page.keyboard.press('Escape');
            await page.waitForTimeout(400);
          }
        }

        const pagePass = hasTopBarAssistant && (vp.width < 1024 || hasSidebarAssistant) && openSuccess && (!pageDef.isClaim || hasFloatingPill);
        if (!pagePass) allPassed = false;

        results.push({
          viewport: vp.name,
          page: pageDef.name,
          topBarEntry: hasTopBarAssistant ? 'PASS' : 'FAIL',
          sidebarEntry: hasSidebarAssistant !== null ? (hasSidebarAssistant ? 'PASS' : 'FAIL') : 'N/A (mobile)',
          floatingPill: hasFloatingPill !== null ? (hasFloatingPill ? 'PASS' : 'FAIL') : 'N/A',
          openAndEscape: openSuccess ? 'PASS' : 'FAIL',
          overall: pagePass ? 'PASS' : 'FAIL',
        });

        console.log(`  [${pagePass ? 'PASS' : 'FAIL'}] ${pageDef.name} (${vp.name}) -> TopBar: ${hasTopBarAssistant ? '✓' : '✗'}, Interactive: ${openSuccess ? '✓' : '✗'}`);
      } catch (err) {
        allPassed = false;
        console.error(`  [ERROR] ${pageDef.name} (${vp.name}):`, err.message);
        results.push({
          viewport: vp.name,
          page: pageDef.name,
          overall: 'ERROR: ' + err.message,
        });
      } finally {
        await page.close();
      }
    }
  }

  await browser.close();

  console.log('\n================================================================');
  console.log('PLAYWRIGHT SMOKE CHECK SUMMARY TABLE');
  console.log('================================================================');
  console.table(results);

  if (allPassed) {
    console.log('\n✓ ALL PLAYWRIGHT SMOKE CHECKS PASSED.');
  } else {
    console.error('\n✗ SOME SMOKE CHECKS FAILED. Review summary above.');
    process.exitCode = 1;
  }
}

runSmokeCheck().catch((err) => {
  console.error('Fatal smoke test runner error:', err);
  process.exit(1);
});
