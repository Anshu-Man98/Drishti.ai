import { chromium } from '../frontend/node_modules/playwright/index.mjs';

async function verifyPages() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(`[Console Error] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    consoleErrors.push(`[Page Error] ${err.message}`);
  });

  const routes = [
    { name: 'Dashboard', path: '/', selector: 'h1, h2, table, [data-testid="stats"]' },
    { name: 'Claims Queue', path: '/claims', selector: 'table, [data-testid="claim-row"]' },
    { name: 'Claim Detail', path: '/claims/CLM-G1-CLEAN-DEMO', selector: 'h1, h2, [data-testid="claim-summary"]' },
    { name: 'Network Graph', path: '/network', selector: 'svg, canvas, h1, h2' },
    { name: 'Adversarial Duel', path: '/duel', selector: 'h1, h2, button' },
  ];

  console.log('=== Drishti.ai Browser Verification (Playwright) ===');
  console.log('Target Host: http://localhost:3000\n');

  let allPassed = true;

  for (const route of routes) {
    const url = `http://localhost:3000${route.path}`;
    const beforeErrorCount = consoleErrors.length;

    try {
      const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
      const status = response ? response.status() : 'no-response';

      // Wait a short beat for any asynchronous state updates
      await page.waitForTimeout(1000);

      const content = await page.content();
      const hasFailedToFetch = content.includes('Failed to fetch') || content.includes('Not Found');

      const routeErrors = consoleErrors.slice(beforeErrorCount);

      if (status === 200 && !hasFailedToFetch && routeErrors.length === 0) {
        console.log(`  [PASS] ${route.name} (${route.path}) -> HTTP ${status}, rendered data cleanly, 0 console errors`);
      } else {
        allPassed = false;
        console.error(`  [FAIL] ${route.name} (${route.path}) -> HTTP ${status}`);
        if (hasFailedToFetch) console.error(`    Found "Failed to fetch" or "Not Found" in DOM`);
        if (routeErrors.length > 0) {
          routeErrors.forEach(err => console.error(`    ${err}`));
        }
      }
    } catch (e) {
      allPassed = false;
      console.error(`  [ERROR] ${route.name} (${route.path}): ${e.message}`);
    }
  }

  await browser.close();

  console.log('\n================================================');
  if (allPassed) {
    console.log('ALL BROWSER ROUTE CHECKS PASSED WITH NO CONSOLE ERRORS.');
    process.exit(0);
  } else {
    console.error('ONE OR MORE BROWSER CHECKS FAILED.');
    process.exit(1);
  }
}

verifyPages().catch((err) => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
