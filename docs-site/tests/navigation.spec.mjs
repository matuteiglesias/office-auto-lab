import { expect, test } from '@playwright/test'

function observeRuntime(page) {
  const problems = []
  page.addInitScript(() => {
    window.__cspViolations = []
    document.addEventListener('securitypolicyviolation', event => window.__cspViolations.push(`${event.violatedDirective}: ${event.blockedURI}`))
  })
  page.on('pageerror', error => problems.push(`pageerror: ${error.message}`))
  page.on('console', message => { if (message.type() === 'error') problems.push(`console: ${message.text()}`) })
  page.on('requestfailed', request => problems.push(`request: ${request.url()} (${request.failure()?.errorText})`))
  return problems
}

async function expectHealthy(page, problems) {
  expect(problems).toEqual([])
  expect(await page.evaluate(() => window.__cspViolations)).toEqual([])
}

async function expectPage(page, pathname, heading) {
  await expect(page).toHaveURL(url => url.pathname === pathname)
  await expect(page.getByRole('heading', { level: 1 })).toContainText(heading)
}

test('desktop navigation, history, deep links, Mermaid, and 404 stay healthy', async ({ page }) => {
  const problems = observeRuntime(page)
  await page.goto('/')
  await expectPage(page, '/', 'Operational signals')
  await page.locator('.VPNavBarMenuLink', { hasText: 'Architecture' }).click()
  await expectPage(page, '/architecture/system-overview', 'System overview')
  await expect(page.locator('.mermaid svg')).toHaveCount(1)
  await expect(page.locator('.mermaid')).not.toContainText(/syntax error|parse error/i)
  await page.locator('.VPSidebarItem a', { hasText: 'Local routines' }).click()
  await expectPage(page, '/operations/local-routines', 'Routine local operation')
  await page.goBack(); await expectPage(page, '/architecture/system-overview', 'System overview')
  await page.goForward(); await expectPage(page, '/operations/local-routines', 'Routine local operation')
  await page.goto('/')
  await page.locator('.route-card', { hasText: 'Review the GCP engineering case' }).click()
  await expectPage(page, '/case-studies/gcp-project-health-retrofit', 'GCP Repo Health retrofit')
  await expect(page.locator('.mermaid svg')).toHaveCount(1)
  await page.goto('/architecture/system-overview'); await page.reload()
  await expectPage(page, '/architecture/system-overview', 'System overview')
  await page.locator('.vp-doc').getByRole('link', { name: 'trust boundaries', exact: true }).click()
  await expectPage(page, '/architecture/trust-boundaries', 'Trust boundaries')
  await expectHealthy(page, problems)
  const response = await page.goto('/route-that-does-not-exist')
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('PAGE NOT FOUND')
  expect(problems).toEqual(['console: Failed to load resource: the server responded with a status of 404 (Not Found)'])
  expect(await page.evaluate(() => window.__cspViolations)).toEqual([])
})

test('Mermaid labels remain visible in light and dark modes', async ({ page }) => {
  const problems = observeRuntime(page)
  await page.goto('/architecture/system-overview')
  const diagram = page.locator('.mermaid svg')
  await expect(diagram).toBeVisible(); await expect(diagram).toContainText('Human or timer')
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme }); await expect(diagram).toBeVisible()
    expect(await diagram.locator('text, foreignObject').count()).toBeGreaterThan(0)
  }
  await expectHealthy(page, problems)
})

test('mobile navigation works at approximately 390px', async ({ page }) => {
  const problems = observeRuntime(page)
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/')
  await page.getByRole('button', { name: 'mobile navigation' }).click()
  await page.locator('#VPNavScreen').getByRole('link', { name: 'Architecture' }).click()
  await expectPage(page, '/architecture/system-overview', 'System overview')
  await expectHealthy(page, problems)
})

test('every public Mermaid block renders without a parser error', async ({ page }) => {
  const problems = observeRuntime(page)
  const pages = {
    '/architecture/system-overview': 1,
    '/architecture/runtime-and-artifact-flow': 2,
    '/architecture/ownership-and-state': 1,
    '/architecture/trust-boundaries': 1,
    '/architecture/repo-health-gcp': 1,
    '/case-studies/gcp-project-health-retrofit': 1
  }
  for (const [route, count] of Object.entries(pages)) {
    await page.goto(route)
    await expect(page.locator('.mermaid svg')).toHaveCount(count)
    await expect(page.locator('.mermaid').filter({ hasText: /syntax error|parse error/i })).toHaveCount(0)
  }
  await expectHealthy(page, problems)
})
