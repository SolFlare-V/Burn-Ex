import React, { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUserProfile } from '../lib/queryClient'
import { useSessionLifecycle } from '../hooks/useSessionLifecycle'

// Defaulting to user_id=1 for local single-user system
const DEFAULT_USER_ID = 1

export const ProfileView: React.FC = () => {
  const queryClient = useQueryClient()
  
  // Hooks
  const { data: user, isLoading, error } = useUserProfile(DEFAULT_USER_ID)
  const { status: sessionStatus } = useSessionLifecycle()

  // Local component state
  const [name, setName] = useState<string>('')
  const [weightText, setWeightText] = useState<string>('')
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Sync server data to local form state on load
  useEffect(() => {
    if (user) {
      setName(user.name || '')
      setWeightText(user.weight_kg.toString())
    }
  }, [user])

  // Save handler for PUT /api/v1/user
  const handleSave = async () => {
    setSaveStatus('saving')
    setErrorMessage(null)

    // Validate weight
    const parsedWeight = parseFloat(weightText)
    if (isNaN(parsedWeight) || parsedWeight < 20 || parsedWeight > 300) {
      setErrorMessage('Weight must be a valid number between 20 and 300 kg.')
      setSaveStatus('error')
      return
    }

    try {
      const res = await fetch('/api/v1/user', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: DEFAULT_USER_ID,
          name: name.trim() || null,
          weight_kg: parsedWeight,
        }),
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail?.message || 'Failed to update profile')
      }

      // Invalidate the query to fetch fresh data globally
      await queryClient.invalidateQueries({ queryKey: ['user', DEFAULT_USER_ID] })
      
      setSaveStatus('saved')
      
      // Reset save status to idle after 2 seconds
      setTimeout(() => {
        setSaveStatus((current) => (current === 'saved' ? 'idle' : current))
      }, 2000)

    } catch (err: any) {
      setErrorMessage(err.message)
      setSaveStatus('error')
    }
  }

  // Format date helper
  const formatJoinDate = (isoString: string): string => {
    try {
      return new Date(isoString).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    } catch {
      return '--'
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center p-8 bg-slate-950">
        <div className="w-8 h-8 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Loading Profile...</span>
      </div>
    )
  }

  if (error || !user) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center p-8 bg-slate-950">
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs px-6 py-4 rounded-xl text-center max-w-sm">
          <span className="font-bold block mb-2">Error loading profile</span>
          {error instanceof Error ? error.message : 'Unknown error occurred.'}
        </div>
      </div>
    )
  }

  const isSessionActive = sessionStatus === 'active'

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col items-center p-4 md:p-8 font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Container Header */}
      <div className="w-full max-w-2xl border-b border-slate-900 pb-4 mb-8">
        <h1 className="text-3xl font-black tracking-tight text-white uppercase">
          User Settings
        </h1>
        <p className="text-slate-400 text-xs mt-1">
          Manage your personal profile and biomechanical tracking parameters.
        </p>
      </div>

      {/* Main Settings Card */}
      <div className="w-full max-w-2xl bg-slate-900/30 border border-slate-900 rounded-3xl p-6 md:p-10 relative overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.5)]">
        
        {/* Decorative backdrop glow */}
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-lime-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center space-x-6 mb-10 pb-10 border-b border-slate-900/50">
          {/* Avatar Placeholder */}
          <div className="w-24 h-24 bg-slate-900 border-2 border-slate-800 rounded-full flex items-center justify-center shadow-inner relative overflow-hidden">
            <svg className="w-10 h-10 text-slate-700" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
            </svg>
            <div className="absolute inset-0 bg-gradient-to-tr from-lime-500/10 to-transparent pointer-events-none" />
          </div>
          
          <div className="flex flex-col">
            <h2 className="text-2xl font-black text-white">{user.name || 'Anonymous User'}</h2>
            <span className="text-xs text-slate-500 font-mono mt-1">ID: {user.id.toString().padStart(4, '0')}</span>
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest mt-2">
              Joined {formatJoinDate(user.created_at)}
            </span>
          </div>
        </div>

        {/* Edit Form */}
        <div className="space-y-8 relative z-10">
          
          {/* Display Name Input */}
          <div className="flex flex-col space-y-2">
            <label htmlFor="displayName" className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">
              Display Name
            </label>
            <input
              id="displayName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-5 py-4 text-sm font-semibold text-white placeholder-slate-700 focus:outline-none focus:border-lime-500/50 focus:ring-1 focus:ring-lime-500/50 transition-all"
            />
          </div>

          {/* Weight Input (Disabled during active sessions) */}
          <div className="flex flex-col space-y-2 relative group">
            <label htmlFor="userWeight" className="text-[10px] font-bold tracking-widest text-slate-500 uppercase flex items-center justify-between">
              <span>Body Weight (KG)</span>
              {isSessionActive && (
                <span className="text-rose-500 flex items-center">
                  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                  Locked
                </span>
              )}
            </label>
            <input
              id="userWeight"
              type="number"
              step="0.1"
              value={weightText}
              onChange={(e) => setWeightText(e.target.value)}
              disabled={isSessionActive}
              className={`w-full bg-slate-950 border rounded-xl px-5 py-4 text-sm font-semibold text-white placeholder-slate-700 focus:outline-none transition-all ${
                isSessionActive 
                  ? 'border-slate-800/50 opacity-50 cursor-not-allowed' 
                  : 'border-slate-800 focus:border-lime-500/50 focus:ring-1 focus:ring-lime-500/50'
              }`}
            />
            {/* Tooltip for disabled state */}
            {isSessionActive && (
              <div className="absolute bottom-full left-0 mb-2 w-full text-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
                <div className="inline-block bg-rose-500 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded shadow-lg">
                  Cannot change weight during an active session
                </div>
              </div>
            )}
            <p className="text-[10px] text-slate-600 mt-1">
              Required for accurate MET calorie expenditure estimations (Range: 20-300 kg).
            </p>
          </div>

          {/* Error Banner */}
          {errorMessage && (
            <div className="bg-rose-500/10 border border-rose-500/20 px-4 py-3 rounded-xl flex items-start space-x-3">
              <svg className="w-4 h-4 text-rose-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs text-rose-400 font-medium leading-relaxed">{errorMessage}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="pt-4 border-t border-slate-900/50 flex items-center justify-end">
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving' || isSessionActive}
              className={`px-8 py-4 rounded-xl text-xs font-black uppercase tracking-widest transition-all duration-300 flex items-center space-x-2 ${
                saveStatus === 'saved'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-lime-500 hover:bg-lime-400 text-slate-950 shadow-[0_10px_30px_rgba(132,204,22,0.2)] hover:shadow-[0_12px_35px_rgba(132,204,22,0.3)] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none'
              }`}
            >
              {saveStatus === 'saving' ? (
                <>
                  <div className="w-4 h-4 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                  <span>Saving...</span>
                </>
              ) : saveStatus === 'saved' ? (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>Saved</span>
                </>
              ) : (
                <span>Save Changes</span>
              )}
            </button>
          </div>
          
        </div>
      </div>
    </div>
  )
}
