import { chromium } from '../frontend/node_modules/playwright/index.mjs';

async function verifySpacetimeMap() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  const mapErrors = [];

  page.on('console', (msg) => {
    const text = msg.text();
    if (msg.type() === 'error' || text.includes('Google Maps JavaScript API error') || text.includes('RefererNotAllowedMapError')) {
      consoleErrors.push(`[Console Error] ${text}`);
      if (text.includes('RefererNotAllowedMapError') || text.includes('Google Maps')) {
        mapErrors.push(text);
      }
    }
  });

  page.on('pageerror', (err) => {
    consoleErrors.push(`[Page Error] ${err.message}`);
  });

  console.log('=== Spacetime Map Browser Verification ===');
  const targetUrl = 'https://drishti-app-6lmavyq52q-el.a.run.app/claims/CLM-G5-TRAVEL-DEMO';
  console.log(`Navigating to ${targetUrl}...`);

  await page.goto(targetUrl, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Click on the Spacetime tab in PillTabs
  console.log('Clicking Spacetime tab...');
  const spacetimeTab = page.locator('button:has-text("Spacetime")').first();
  await spacetimeTab.waitFor({ state: 'visible', timeout: 10000 });
  await spacetimeTab.click();
  console.log('Clicked Spacetime tab.');

  // Wait 4 seconds for Google Maps SDK and tile render
  await page.waitForTimeout(4000);

  const content = await page.content();
  const mapContainerVisible = content.includes('Spacetime Physics & Velocity Gauge') || content.includes('Impossible Travel');
  console.log(`Spacetime UI rendered: ${mapContainerVisible}`);

  console.log(`Detected Google Maps errors: ${mapErrors.length}`);
  if (mapErrors.length > 0) {
    mapErrors.forEach(err => console.error(`  ${err}`));
  }

  await browser.close();

  if (mapErrors.length === 0) {
    console.log('[PASS] Google Maps loaded on Cloud Run without RefererNotAllowedMapError.');
    process.exit(0);
  } else {
    console.error('[FAIL] Google Maps encountered referrer or configuration error.');
    process.exit(1);
  }
}

verifySpacetimeMap().catch((err) => {
  console.error('Execution error:', err);
  process.exit(1);
});
