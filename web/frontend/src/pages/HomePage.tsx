import { useState, useCallback } from 'react'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import SessionList from '../components/SessionList'
import ChatArea from '../components/ChatArea'
import InfoPanel from '../components/InfoPanel'
import SettingsDrawer from '../components/SettingsDrawer'

export default function HomePage() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [defaultTab, setDefaultTab] = useState<string | undefined>()
  const [refreshKey, setRefreshKey] = useState(0)
  const [sessionId, setSessionId] = useState('')
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0)

  const handleOpenSettings = useCallback((tab?: string) => {
    setDefaultTab(tab)
    setDrawerOpen(true)
  }, [])

  const handleSettingsChange = useCallback(() => {
    setRefreshKey((k) => k + 1)
  }, [])

  const handleSessionCreated = useCallback((id: string) => {
    setSessionId(id)
  }, [])

  const handleSelectSession = useCallback((id: string) => {
    setSessionId(id)
  }, [])

  const handleNewSession = useCallback(() => {
    setSessionId('')
    setSessionRefreshKey((k) => k + 1)
  }, [])

  const handleRefreshSessions = useCallback(() => {
    setSessionRefreshKey((k) => k + 1)
  }, [])

  return (
    <div className="app-layout">
      <Header onOpenSettings={handleOpenSettings} refreshKey={refreshKey} />
      <div className="app-body">
        <Sidebar>
          <SessionList
            activeSessionId={sessionId}
            onSelect={handleSelectSession}
            onNew={handleNewSession}
            refreshKey={sessionRefreshKey}
          />
        </Sidebar>
        <ChatArea
          sessionId={sessionId}
          onSessionCreated={handleSessionCreated}
          refreshSessions={handleRefreshSessions}
        />
        <InfoPanel />
      </div>
      <SettingsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSettingsChange={handleSettingsChange}
        defaultTab={defaultTab}
      />
    </div>
  )
}
