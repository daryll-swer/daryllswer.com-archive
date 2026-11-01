#!/usr/bin/env node
// Optional browser regression suite. Requires an existing local site and external Playwright.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const base = (process.env.ARCHIVE_BASE_URL || 'http://127.0.0.1:4173/').replace(/\/$/, '');
const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'archive-manifest.json'), 'utf8'));
const posts = manifest.posts;
const ds = posts.find((post) => post.id !== 5324);
const sn = posts.find((post) => post.id === 5324);
if (!ds || !sn) throw new Error('Could not identify representative DS and Swer Networks posts');
const routes = [
  '/',
  `/posts/${ds.slug}/`,
  `/posts/${sn.slug}/`,
  '/sheets/as141253-ipv6-architecture-example/',
  '/sheets/as141253-ipv6-architecture-example/visual.html',
];
const widths = [320, 360, 390, 768, 1024, 1440, 1920, 2560];
const reservedSummaryWidths = [320, 390, 480, 481, 540, 640, 760, 761];
const screenshots = path.join(require('node:os').tmpdir(), 'daryllswer-reader-safety-shots');

async function settleImages(page) {
  await page.evaluate(async () => {
    const images = [...document.images].filter((image) => image.hasAttribute('src') || image.hasAttribute('srcset'));
    for (const image of images) image.loading = 'eager';
    await Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise((resolve) => {
      image.addEventListener('load', resolve, { once: true });
      image.addEventListener('error', resolve, { once: true });
    })));
    await Promise.all(images.map((image) => image.decode().catch(() => {})));
    await document.fonts.ready;
    const [bodyFaces, headingFaces] = await Promise.all([
      document.fonts.load('400 16px "Poppins"', 'Archive reader'),
      document.fonts.load('700 16px "Raleway"', 'Archive reader'),
    ]);
    if (!bodyFaces.some((face) => face.status === 'loaded') || !headingFaces.some((face) => face.status === 'loaded')) {
      throw new Error(`Expected local Poppins/Raleway faces unavailable (Poppins=${bodyFaces.map((face) => face.status)}, Raleway=${headingFaces.map((face) => face.status)})`);
    }
  });
}

async function checkLayout(page, route, width, failures) {
  const state = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const clipped = [...document.body.querySelectorAll('*')].filter((element) => {
      const style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      let parent = element.parentElement;
      while (parent && parent !== document.body) {
        if (['auto', 'scroll'].includes(getComputedStyle(parent).overflowX)) return false;
        parent = parent.parentElement;
      }
      return element.getBoundingClientRect().right > viewport + 1;
    }).slice(0, 5).map((element) => `${element.tagName}.${element.className}`);
    const broken = [...document.images].filter((image) => !image.complete || image.naturalWidth === 0).map((image) => image.currentSrc || image.src || '(no image source)');
    const cardMediaEscapes = [...document.querySelectorAll('.post-card .post-card-image, .post-card .post-card-image img')].flatMap((element) => {
      const card = element.closest('.post-card');
      if (!card) return [];
      const media = element.getBoundingClientRect();
      const bounds = card.getBoundingClientRect();
      return media.left < bounds.left - 1 || media.right > bounds.right + 1
        ? [`${element.tagName}.${element.className}: ${Math.round(media.left)}..${Math.round(media.right)} outside ${Math.round(bounds.left)}..${Math.round(bounds.right)}`]
        : [];
    });
    return { viewport, scroll: document.documentElement.scrollWidth, clipped, broken, cardMediaEscapes };
  });
  if (state.scroll > state.viewport + 1 || state.clipped.length || state.cardMediaEscapes.length) failures.push(`${route} @ ${width}: clipping/overflow ${JSON.stringify(state)}`);
  if (state.broken.length) failures.push(`${route} @ ${width}: broken images ${state.broken.join(', ')}`);
}

async function checkReservedLabelReadability(page, route, width, failures) {
  const result = await page.locator('.reserved-group > summary .reserved-label').evaluateAll((labels) => labels.map((label) => {
    const rect = label.getBoundingClientRect();
    const style = getComputedStyle(label);
    const lineHeight = Number.parseFloat(style.lineHeight) || Number.parseFloat(style.fontSize) * 1.2;
    return {
      text: label.textContent.trim(),
      width: rect.width,
      lines: rect.height / lineHeight,
    };
  }));
  const unreadable = result.filter((label) => label.width < 64 || label.lines > 4.25);
  if (result.length !== 13 || unreadable.length) {
    failures.push(`${route} @ ${width}: reserved labels are missing or compressed ${JSON.stringify({ count: result.length, unreadable })}`);
  }
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  });
  const failures = [];
  const browserErrors = [];
  fs.mkdirSync(screenshots, { recursive: true });
  try {
    const page = await browser.newPage();
    page.on('pageerror', (error) => browserErrors.push(error.message));
    page.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
    await page.route('**/*', (request) => {
      if (['localhost', '127.0.0.1', '::1'].includes(new URL(request.request().url()).hostname)) return request.continue();
      return request.abort();
    });
    for (const route of routes) {
      for (const colorScheme of ['light', 'dark']) {
        for (const width of widths) {
          await page.setViewportSize({ width, height: 900 });
          await page.emulateMedia({ colorScheme });
          const response = await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
          if (!response || response.status() !== 200) failures.push(`${route} @ ${width} ${colorScheme}: HTTP ${response && response.status()}`);
          await settleImages(page);
          if (route.includes('/visual.html')) {
            await page.evaluate(() => document.querySelectorAll('details').forEach((item) => { item.open = true; }));
            await checkReservedLabelReadability(page, route, width, failures);
          }
          await checkLayout(page, `${route} ${colorScheme}`, width, failures);
          if (route === '/' && width === 320) await page.screenshot({ path: path.join(screenshots, `home-320-${colorScheme}.png`) });
          if (route.includes('/visual.html') && width <= 390 && colorScheme === 'light') {
            await page.locator('#full-hierarchy').scrollIntoViewIfNeeded();
            await page.screenshot({ path: path.join(screenshots, `visual-expanded-${width}.png`) });
          }
        }
      }
      if (route.includes('/visual.html')) {
        await page.emulateMedia({ colorScheme: 'light' });
        for (const width of reservedSummaryWidths) {
          await page.setViewportSize({ width, height: 900 });
          await page.evaluate(() => document.querySelectorAll('details').forEach((item) => { item.open = true; }));
          await checkReservedLabelReadability(page, `${route} breakpoint`, width, failures);
          await checkLayout(page, `${route} breakpoint`, width, failures);
        }
      }
      await page.setViewportSize({ width: 320, height: 800 });
      await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
      await settleImages(page);
      if (route.includes('/visual.html')) {
        const openOnFreshLoad = await page.locator('details[open]').count();
        if (openOnFreshLoad) failures.push(`${route}: ${openOnFreshLoad} disclosures are open on fresh load`);
      }
      if (route.includes('/sheets/') && !route.includes('visual.html')) {
        const toggles = page.locator('.sheet-toggle');
        const count = await toggles.count();
        if (count > 1) {
          const initialIndex = await toggles.evaluateAll((nodes) => nodes.findIndex((node) => node.checked));
          await toggles.nth(initialIndex).focus();
          await page.keyboard.press('ArrowRight');
          const nextIndex = await toggles.evaluateAll((nodes) => nodes.findIndex((node) => node.checked));
          const focusState = await toggles.nth(nextIndex).evaluate((node) => {
            const label = document.querySelector(`label[for="${node.id}"]`);
            return {
              active: document.activeElement === node,
              selected: node.checked,
              labelOutlineStyle: label ? getComputedStyle(label).outlineStyle : 'none',
              panelVisible: getComputedStyle(document.querySelector(`#sheet-panel-${node.id.slice('sheet-tab-'.length)}`)).display !== 'none',
            };
          });
          if (nextIndex !== (initialIndex + 1) % count || !focusState.active || !focusState.selected || focusState.labelOutlineStyle === 'none' || !focusState.panelVisible) {
            failures.push(`${route}: workbook radio arrow navigation/focus failed ${JSON.stringify({ initialIndex, nextIndex, focusState })}`);
          }
        }
        const regions = page.locator('.sheet-viewport');
        const regionCount = await regions.count();
        if (!regionCount) failures.push(`${route}: workbook table scroller region is missing`);
        else {
          const semantics = await regions.first().evaluate((node) => ({
            role: node.getAttribute('role'),
            tabIndex: node.tabIndex,
            label: node.getAttribute('aria-label'),
          }));
          if (semantics.role !== 'region' || semantics.tabIndex !== 0 || !semantics.label) failures.push(`${route}: workbook scroller lacks accessible keyboard semantics ${JSON.stringify(semantics)}`);
        }
      }
      // Keyboard probes above may move focus; test the skip target from a clean navigation state.
      await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
      await settleImages(page);
      await page.keyboard.press('Tab');
      const firstFocus = await page.evaluate(() => document.activeElement && document.activeElement.outerHTML);
      if (!firstFocus || !firstFocus.includes('skip-link')) failures.push(`${route}: first Tab does not reach skip link`);
      await page.keyboard.press('Enter');
      const skipResult = await page.evaluate(() => ({
        hash: location.hash,
        focusedMain: document.activeElement && document.activeElement.id === 'main-content',
      }));
      if (skipResult.hash !== '#main-content' || !skipResult.focusedMain) failures.push(`${route}: activating skip link did not focus #main-content (${JSON.stringify(skipResult)})`);
      await page.keyboard.press('Tab');
      const nextFocusInMain = await page.evaluate(() => {
        const main = document.querySelector('#main-content');
        return Boolean(main && main.contains(document.activeElement));
      });
      if (!nextFocusInMain) failures.push(`${route}: Tab after skip link did not enter main content`);
      const mainTarget = await page.locator('#main-content').count();
      if (mainTarget !== 1) failures.push(`${route}: expected one #main-content target`);
      await page.emulateMedia({ media: 'print' });
      const printState = await page.evaluate(() => {
        const main = document.querySelector('#main-content');
        const viewport = document.querySelector('.sheet-viewport');
        return {
          main: main ? getComputedStyle(main).display : null,
          bodyText: document.body.innerText.trim().length,
          viewportOverflow: viewport ? getComputedStyle(viewport).overflow : null,
          viewportMaxHeight: viewport ? getComputedStyle(viewport).maxHeight : null,
          hiddenPanels: [...document.querySelectorAll('.sheet-panel')].filter((panel) => getComputedStyle(panel).display === 'none').length,
          hiddenMediaLinks: [...document.querySelectorAll('.media-fallback')].filter((link) => getComputedStyle(link).display === 'none').length,
        };
      });
      if (!printState.main || printState.main === 'none' || printState.bodyText === 0) failures.push(`${route}: reader main/content missing in print media ${JSON.stringify(printState)}`);
      if (route.includes('/sheets/') && !route.includes('visual.html') && (printState.viewportOverflow !== 'visible' || printState.viewportMaxHeight !== 'none' || printState.hiddenPanels)) failures.push(`${route}: workbook table/panels clipped in print ${JSON.stringify(printState)}`);
      if (route.startsWith('/posts/') && printState.hiddenMediaLinks) failures.push(`${route}: media fallback links hidden in print`);
      await page.emulateMedia({ media: 'screen' });
      await page.evaluate(() => {
        const sizes = [...document.body.querySelectorAll('*')].map((element) => [element, parseFloat(getComputedStyle(element).fontSize)]);
        for (const [element, size] of sizes) if (Number.isFinite(size)) element.style.fontSize = `${size * 2}px`;
      });
      await checkLayout(page, `${route} (200% text enlargement)`, 320, failures);
      if (route.includes('/visual.html')) {
        const singletonCards = page.locator('[data-reserved-singleton-grid] [data-reserved-leaf]');
        const singletonBefore = await singletonCards.evaluateAll((nodes) => nodes.map((node) => ({
          html: node.outerHTML,
          prefix: node.querySelector('.prefix-chip code')?.textContent?.trim() || '',
        })));
        if (!singletonBefore.length) failures.push(`${route}: expected reserved singleton cards but found none`);
        const summary = page.locator('details > summary').first();
        const initial = await summary.evaluate((node) => node.parentElement.open);
        await summary.focus();
        await page.keyboard.press('Enter');
        const afterEnter = await summary.evaluate((node) => node.parentElement.open);
        await page.keyboard.press('Space');
        const afterSpace = await summary.evaluate((node) => node.parentElement.open);
        if (afterEnter === initial || afterSpace !== initial) failures.push(`${route}: native summary Enter/Space toggling failed`);
        const expand = page.locator('[data-final-tree-expand]');
        const collapse = page.locator('[data-final-tree-collapse]');
        if (await expand.count()) {
          await expand.click();
          await collapse.click();
          const singletonAfter = await singletonCards.evaluateAll((nodes) => nodes.map((node) => ({
            html: node.outerHTML,
            prefix: node.querySelector('.prefix-chip code')?.textContent?.trim() || '',
          })));
          if (JSON.stringify(singletonAfter) !== JSON.stringify(singletonBefore) || !(await expand.isVisible()) || !(await collapse.isVisible())) failures.push(`${route}: bulk controls changed/removed reserved singleton cards or disappeared`);
        }
      }
    }

    const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 800 } });
    const noJsPage = await noJs.newPage();
    noJsPage.on('pageerror', (error) => browserErrors.push(error.message));
    noJsPage.on('console', (message) => { if (message.type() === 'error') browserErrors.push(message.text()); });
    await noJsPage.route('**/*', (request) => {
      if (['localhost', '127.0.0.1', '::1'].includes(new URL(request.request().url()).hostname)) return request.continue();
      return request.abort();
    });
    for (const route of routes) {
      await noJsPage.setViewportSize({ width: 1280, height: 900 });
      const response = await noJsPage.goto(`${base}${route}`, { waitUntil: 'networkidle' });
      await settleImages(noJsPage);
      const content = await noJsPage.locator('#main-content').count();
      if (!response || response.status() !== 200 || content !== 1) failures.push(`${route}: no-JavaScript content unavailable`);
      await checkLayout(noJsPage, `${route} (1280px reference)`, 1280, failures);
      if (route.includes('/visual.html')) {
        const summary = noJsPage.locator('details > summary').first();
        const initial = await summary.evaluate((node) => node.parentElement.open);
        await summary.focus();
        await noJsPage.keyboard.press('Space');
        if (await summary.evaluate((node) => node.parentElement.open) === initial) failures.push(`${route}: no-JavaScript disclosure keyboard support failed`);
      }
    }
    for (const route of routes) {
      await noJsPage.setViewportSize({ width: 320, height: 800 });
      if (noJsPage.url() !== `${base}${route}`) {
        await noJsPage.goto(`${base}${route}`, { waitUntil: 'networkidle' });
        await settleImages(noJsPage);
      }
      await checkLayout(noJsPage, `${route} (400% viewport reflow approximation)`, 320, failures);
    }
    await noJs.close();
  } finally {
    await browser.close();
  }
  if (browserErrors.length) failures.push(`browser console/page errors: ${browserErrors.join(' | ')}`);
  if (failures.length) {
    for (const failure of failures) console.error(`FAIL ${failure}`);
    process.exitCode = 1;
  } else {
    console.log(`PASS ${routes.length} routes; ${widths.length} widths; keyboard, print, 200% text enlargement, 400% viewport reflow approximation, no-JavaScript, images, screenshots=${screenshots}`);
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
