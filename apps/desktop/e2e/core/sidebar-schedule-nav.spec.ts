/**
 * The sidebar's Scheduled jobs (cron) nav row is on screen on a fresh launch.
 *
 * Reported missing on Windows. Runs on every OS; the Windows Desktop lane
 * (.github/workflows/windows-desktop-attach-e2e.yml) runs it on a real Windows
 * runner. A full-window screenshot is attached either way so the CI artifact
 * shows what the sidebar actually rendered.
 */

import { expect, test } from '@playwright/test'

import { coreAppEnv, createCoreSandbox, launchCoreApp, waitForInteractive, writeProviderHome } from './harness'
import { startScriptedProvider } from './provider'

const BUILT_IN_NAV = ['new-session', 'capabilities', 'messaging', 'artifacts', 'cron']

test('sidebar: the Scheduled jobs nav row is visible and opens the cron view', async () => {
  const testInfo = test.info()
  const provider = await startScriptedProvider()
  const sandbox = createCoreSandbox('schedule-nav')
  writeProviderHome(sandbox.hermesHome, provider.url)
  const { app, page } = await launchCoreApp(coreAppEnv(sandbox))

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
  } finally {
    await app.close().catch(() => undefined)
    await provider.close()
    sandbox.cleanup()
  }
})
