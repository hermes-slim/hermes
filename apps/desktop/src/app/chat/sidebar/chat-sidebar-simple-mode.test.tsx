import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'

import { SidebarProvider } from '@/components/ui/sidebar'
import { $interfaceMode, type InterfaceMode } from '@/store/interface-mode'

import { ChatSidebar } from './index'

const noop = () => {}
const noopAsync = async () => {}

const renderSidebar = () =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <SidebarProvider>
        <ChatSidebar
          currentView="chat"
          onArchiveSession={noop}
          onBranchSession={noop}
          onDeleteSession={noop}
          onLoadMoreSessions={noop}
          onManageCronJob={noop}
          onNavigate={noop}
          onNewSessionInWorkspace={noop}
          onNewSessionSplit={noop}
          onResumeSession={noop}
          onRetrySessions={noopAsync}
          onTriggerCronJob={noopAsync}
        />
      </SidebarProvider>
    </MemoryRouter>
  )

describe('ChatSidebar Scheduled jobs row', () => {
  afterEach(() => {
    cleanup()
    $interfaceMode.set('advanced')
  })

  it.each<InterfaceMode>(['simple', 'advanced'])('is in the nav in %s mode', mode => {
    $interfaceMode.set(mode)
    renderSidebar()

    expect(screen.getByRole('button', { name: 'Scheduled jobs' })).toBeTruthy()
  })
})
