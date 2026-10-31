/**
 * The sidebar's Scheduled jobs (cron) nav row is on screen on a fresh launch.
 *
 * Reported missing on Windows. Runs on every OS; the Windows Desktop lane
 * (.github/workflows/windows-desktop-attach-e2e.yml) runs it on a real Windows
 * runner. A full-window screenshot is attached either way so the CI artifact
 * shows what the sidebar actually rendered.
 */

import { expect, test } from '@playwright/test'

import { createCoreSandbox, launchCoreAppForLane, waitForInteractive, writeProviderHome } from './harness'
import { startScriptedProvider } from './provider'

const BUILT_IN_NAV = ['new-session', 'capabilities', 'messaging', 'artifacts', 'cron']

test(`sidebar${process.env.HERMES_E2E_PACKAGED_EXE ? ' (packaged)' : ''}: the Scheduled jobs nav row is visible and opens the cron view`, async () => {
  const testInfo = test.info()
  const provider = await startScriptedProvider()
  const sandbox = createCoreSandbox('schedule-nav')
  writeProviderHome(sandbox.hermesHome, provider.url)
  const { app, page } = await launchCoreAppForLane(sandbox)

  try {
    await waitForInteractive(app, page)

    const rendered = await page.$$eval('[data-tour^="sidebar-nav-"]', els =>
      els.map(el => ({
        id: el.getAttribute('data-tour'),
        rect: (({ x, y, width, height }) => ({ x, y, width, height }))(el.getBoundingClientRect())
      }))
    )

    const window_ = await page.evaluate(() => ({
      w: window.innerWidth,
      h: window.innerHeight,
      platform: navigator.platform,
      mode: localStorage.getItem('hermes.desktop.interfaceMode.v1')
    }))

    await testInfo.attach('sidebar-nav.json', {
      body: JSON.stringify({ window: window_, rendered }, null, 2),
      contentType: 'application/json'
    })
    await testInfo.attach('window.png', { body: await page.screenshot(), contentType: 'image/png' })

    expect(rendered.map(r => r.id)).toEqual(BUILT_IN_NAV.map(id => `sidebar-nav-${id}`))

    const cron = page.locator('[data-tour="sidebar-nav-cron"]')
    await expect(cron).toBeVisible()
    await expect(cron).toBeInViewport()

    await cron.click()
    await expect(page).toHaveURL(/#\/cron|\/cron/, { timeout: 15_000 })

    // Simple mode used to drop the row (it was tier: 'advanced') — the reported "missing" button.
    // Close the cron dialog first: reloading on it never shows the composer waitForInteractive needs.
    await page.keyboard.press('Escape')
    await waitForInteractive(app, page)
    await page.evaluate(() => localStorage.setItem('hermes.desktop.interfaceMode.v1', 'simple'))
    await page.reload()
    await waitForInteractive(app, page)
    await testInfo.attach('window-simple.png', { body: await page.screenshot(), contentType: 'image/png' })
    await expect(page.locator('[data-tour="sidebar-nav-cron"]')).toBeVisible()
    await expect(page.locator('[data-tour="sidebar-nav-cron"]')).toBeInViewport()
  } finally {
    await app.close().catch(() => undefined)
    await provider.close()
    sandbox.cleanup()
  }
})
