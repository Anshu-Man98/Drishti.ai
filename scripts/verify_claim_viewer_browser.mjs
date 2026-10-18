import { chromium } from '../frontend/node_modules/playwright/index.mjs';

async function runVisualCheck() {
  const browser = await chromium.launch({ headless: true });
  const targetBase = process.env.TARGET_URL || 'http://localhost:3000';
  console.log(`Checking Claim Detail page layout at ${targetBase}...`);

  for (const theme of ['light', 'dark']) {
    for (const viewport of [
      { width: 1440, height: 1000, name: '1440px' },
      { width: 390, height: 844, name: '390px' }
    ]) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        colorScheme: theme
      });
      const page = await context.newPage();

      // Route /api calls directly to live Cloud Run backend
      await page.route('**/api/**', async (route) => {
        const req = route.request();
        const liveUrl = req.url().replace(/^http:\/\/localhost:\d+\/api/, 'https://drishti-app-6lmavyq52q-el.a.run.app/api');
        try {
          const response = await fetch(liveUrl, {
            method: req.method(),
            headers: req.headers(),
            body: req.postDataBuffer() || undefined,
          });
          const body = await response.arrayBuffer();
          await route.fulfill({
            status: response.status,
            headers: Object.fromEntries(response.headers.entries()),
            body: Buffer.from(body),
          });
        } catch (e) {
          console.error('API proxy error:', e);
          await route.continue();
        }
      });

      // Set localStorage token and theme
      await page.addInitScript((th) => {
        localStorage.setItem('drishti-theme', th);
        if (th === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
      }, theme);

      try {
        const url = `${targetBase}/claims/CLM-93986054`;
        await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
        await page.waitForTimeout(1000);

        // Ensure theme class is applied
        await page.evaluate((th) => {
          if (th === 'dark') {
            document.documentElement.classList.add('dark');
          } else {
            document.documentElement.classList.remove('dark');
          }
        }, theme);
        await page.waitForTimeout(500);

        const docViewer = await page.$('text=Document AI Viewer');
        const claimantProfile = await page.$('text=Claimant Profile');

        if (docViewer && claimantProfile) {
          const docBox = await docViewer.evaluate((el) => {
            const card = el.closest('.rounded-\\[20px\\]');
            if (!card) return null;
            const rect = card.getBoundingClientRect();
            return {
              top: rect.top,
              bottom: rect.bottom,
              height: rect.height
            };
          });

          const profileBox = await claimantProfile.evaluate((el) => {
            const card = el.closest('.rounded-\\[20px\\]');
            if (!card) return null;
            const rect = card.getBoundingClientRect();
            return {
              top: rect.top,
              bottom: rect.bottom,
              height: rect.height
            };
          });

          if (docBox && profileBox) {
            const distance = profileBox.top - docBox.bottom;
            console.log(`[${theme.toUpperCase()}] [${viewport.name}] DocViewer height: ${Math.round(docBox.height)}px, Profile top: ${Math.round(profileBox.top)}px, Gap between: ${Math.round(distance)}px`);
          }
        }

        const screenshotPath = `/Users/anshu/.gemini/antigravity/brain/941f2246-e4d9-42b6-bbf1-858f20bc13e7/scratch/screenshots/claim_detail_${theme}_${viewport.name}.png`;
        await page.screenshot({ path: screenshotPath, fullPage: false });
        console.log(`Saved screenshot: ${screenshotPath}`);

        // Scrolled screenshot showing the junction between Document AI Viewer and Claimant Profile
        if (viewport.width === 1440) {
          await page.evaluate(() => window.scrollBy(0, 600));
          await page.waitForTimeout(300);
          const scrolledPath = `/Users/anshu/.gemini/antigravity/brain/941f2246-e4d9-42b6-bbf1-858f20bc13e7/scratch/screenshots/claim_detail_${theme}_scrolled_1440px.png`;
          await page.screenshot({ path: scrolledPath, fullPage: false });
          console.log(`Saved scrolled screenshot: ${scrolledPath}`);
        }
      } catch (err) {
        console.error(`Error on ${theme} ${viewport.name}:`, err.message);
      } finally {
        await context.close();
      }
    }
  }

  await browser.close();
}

runVisualCheck().catch(console.error);
