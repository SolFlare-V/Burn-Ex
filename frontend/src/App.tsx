import { useState } from 'react'
import { CompatibilityWarningScreen } from './components/CompatibilityWarningScreen'
import { ProfileSetupScreen } from './components/ProfileSetupScreen'
import { SessionView } from './components/SessionView'
import { SessionSummaryView } from './components/SessionSummaryView'
import { ProgressDashboard } from './components/ProgressDashboard'
import { HistoryView } from './components/HistoryView'
import { ProfileView } from './components/ProfileView'
import { useUserProfile } from './lib/queryClient'
import { useSessionLifecycle } from './hooks/useSessionLifecycle'

// Defaulting to user_id=1 for local single-user system
const DEFAULT_USER_ID = 1

export default function App() {
  // 1. Browser Compatibility Check
  const hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  const hasWebSocket = 'WebSocket' in window
  const isBrowserSupported = hasGetUserMedia && hasWebSocket

  if (!isBrowserSupported) {
    return <CompatibilityWarningScreen />
  }

  // 2. User Profile Setup Check
  const { data: userProfile, isLoading: isProfileLoading, error: profileError } = useUserProfile(DEFAULT_USER_ID)
  
  // 3. Session Lifecycle State
  const { status: sessionStatus, sessionId, resetSession } = useSessionLifecycle()

  // Tabbed Navigation State
  const [activeTab, setActiveTab] = useState<'session' | 'progress' | 'history' | 'profile'>('session')

  // Render logic for loading and profile setup
  if (isProfileLoading) {
    return (
      <div className="min-h-screen w-full bg-slate-950 flex flex-col items-center justify-center p-8">
        <div className="w-10 h-10 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Initializing Burn-Ex...</span>
      </div>
    )
  }

  // If the profile fetch returned a 404, we need to show the setup screen.
  // We assume that any error where the profile isn't returned means they need to set it up.
  if (profileError || !userProfile) {
    return <ProfileSetupScreen onProfileSaved={() => window.location.reload()} />
  }

  // 4. Session State Routing
  // If the user is actively working out, show the session camera view.
  if (sessionStatus === 'active') {
    return <SessionView />
  }

  // If the user just finished or interrupted a session, show the summary report.
  if (sessionStatus === 'ended' || sessionStatus === 'interrupted') {
    // We pass the sessionId to the summary view, and a close handler to reset back to idle
    return (
      <SessionSummaryView 
        sessionId={sessionId!} 
        onClose={() => {
          // Resetting session via hook so status goes back to 'idle'
          resetSession()
        }} 
      />
    )
  }

  // 5. Main Application Tabbed Viewport (Idle State)
  return (
    <div className="min-h-screen w-full bg-slate-950 flex flex-col md:flex-row font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Sidebar Navigation */}
      <nav className="w-full md:w-64 bg-slate-900/50 border-b md:border-b-0 md:border-r border-slate-900 flex flex-col justify-between p-4 md:p-6 shrink-0 relative z-20">
        
        {/* Logo Area */}
        <div className="flex items-center space-x-3 mb-8">
          <div className="w-10 h-10 bg-lime-500/10 border border-lime-500/20 rounded-xl flex items-center justify-center shadow-[0_0_15px_rgba(132,204,22,0.15)]">
            <svg className="w-6 h-6 text-lime-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div className="flex flex-col">
            <h1 className="text-xl font-black text-white tracking-tight uppercase">Burn-Ex</h1>
            <span className="text-[9px] font-bold text-slate-500 tracking-widest uppercase">Analytics</span>
          </div>
        </div>

        {/* Tab Links */}
        <div className="flex flex-row md:flex-col space-x-2 md:space-x-0 md:space-y-2 mb-4 md:mb-auto overflow-x-auto">
          
          <button
            onClick={() => setActiveTab('session')}
            className={`flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${
              activeTab === 'session'
                ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20 font-bold'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 font-semibold'
            }`}
          >
            <svg className="w-5 h-5 mr-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs uppercase tracking-wider">New Session</span>
          </button>

          <button
            onClick={() => setActiveTab('progress')}
            className={`flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${
              activeTab === 'progress'
                ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20 font-bold'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 font-semibold'
            }`}
          >
            <svg className="w-5 h-5 mr-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            <span className="text-xs uppercase tracking-wider">Analytics</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${
              activeTab === 'history'
                ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20 font-bold'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 font-semibold'
            }`}
          >
            <svg className="w-5 h-5 mr-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-xs uppercase tracking-wider">Log History</span>
          </button>

          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${
              activeTab === 'profile'
                ? 'bg-lime-500/10 text-lime-400 border border-lime-500/20 font-bold'
                : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200 font-semibold'
            }`}
          >
            <svg className="w-5 h-5 mr-3 opacity-80" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span className="text-xs uppercase tracking-wider">Profile Config</span>
          </button>
        </div>
      </nav>

      {/* Main Tabbed Viewport Content */}
      <main className="flex-1 relative overflow-y-auto">
        <div className="absolute inset-0 pb-16">
          {activeTab === 'session' && (
            <div className="animate-fadeIn p-4 md:p-8 pb-0">
              <SessionView />
            </div>
          )}
          {activeTab === 'progress' && (
            <div className="animate-fadeIn">
              <ProgressDashboard />
            </div>
          )}
          {activeTab === 'history' && (
            <div className="animate-fadeIn">
              <HistoryView />
            </div>
          )}
          {activeTab === 'profile' && (
            <div className="animate-fadeIn">
              <ProfileView />
            </div>
          )}
        </div>
      </main>

    </div>
  )
}
