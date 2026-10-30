import { describe, expect, it } from 'vitest'

import {
  decideLinuxGpuLaunch,
  LINUX_GPU_REPROBE_BASE_LAUNCHES,
  LINUX_GPU_REPROBE_BASE_MS,
  type LinuxGpuMarker,
  linuxGpuMarkerAfterSuccessfulBoot
} from './linux-gpu-fallback'

const base = { platform: 'linux', argv: [], env: {}, appVersion: '0.0.0' }
const T0 = 1_000_000

describe('same-version sticky fallback re-probes the GPU (#6)', () => {
  it('re-probes after the base number of software launches without a version change', () => {
    let marker: LinuxGpuMarker = { state: 'fallback', reason: 'boot-loop', version: '0.0.0', since: T0 }

    for (let i = 0; i < LINUX_GPU_REPROBE_BASE_LAUNCHES; i++) {
      const d = decideLinuxGpuLaunch({ ...base, marker, now: T0 })
      expect(d.enable).toBe(true)
      marker = linuxGpuMarkerAfterSuccessfulBoot({ fallbackActive: true, marker: d.nextMarker })
    }

    const probe = decideLinuxGpuLaunch({ ...base, marker, now: T0 })
    expect(probe.enable).toBe(false)
    expect(probe.nextMarker).toMatchObject({ state: 'booting', reprobe: true })
  })

  it('re-probes after the base wall time', () => {
    const marker: LinuxGpuMarker = { state: 'fallback', reason: 'gpu-crash', version: '0.0.0', since: T0 }
    expect(decideLinuxGpuLaunch({ ...base, marker, now: T0 + LINUX_GPU_REPROBE_BASE_MS }).enable).toBe(false)
  })

  it('a failed re-probe returns to fallback and doubles the next interval', () => {
    const probe = decideLinuxGpuLaunch({
      ...base,
      marker: { state: 'fallback', reason: 'boot-loop', since: T0 },
      now: T0 + LINUX_GPU_REPROBE_BASE_MS
    })
    const failed = decideLinuxGpuLaunch({ ...base, marker: probe.nextMarker, now: T0 + LINUX_GPU_REPROBE_BASE_MS })
    expect(failed.enable).toBe(true)
    expect(failed.nextMarker).toMatchObject({ state: 'fallback', failedReprobes: 1 })

    const later = T0 + 2 * LINUX_GPU_REPROBE_BASE_MS + 1
    expect(decideLinuxGpuLaunch({ ...base, marker: failed.nextMarker, now: later }).enable).toBe(true)
    expect(decideLinuxGpuLaunch({ ...base, marker: failed.nextMarker, now: later + 2 * LINUX_GPU_REPROBE_BASE_MS }).enable).toBe(false)
  })
})
