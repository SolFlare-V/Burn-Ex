/**
 * Phase 13 verification page.
 * Exercises usePoseSession, useSessionLifecycle, and all query hooks
 * against the live backend on localhost:8766.
 *
 * To run: set App.tsx to render <VerifyPhase13 userId={N} /> where N
 * is a valid user_id from the DB.
 */

import { useEffect, useRef, useState } from 'react'
import { useSessionLifecycle } from '../src/hooks/useSessionLifecycle'
import {
  useSessionHistory,
  useUserProfile,
  useProgressCalories,
  useProgressForm,
  useStreaks,
  useGoals,
  useGoalsProgress,
} from '../src/lib/queryClient'

interface Props { userId: number }

export function VerifyPhase13({ userId }: Props) {
  const lifecycle = useSessionLifecycle()
  const { state: poseState, lastMessage } = lifecycle.poseSession

  // Query hooks
  const history = useSessionHistory(5)
  const profile = useUserProfile(userId)
  const calories = useProgressCalories(userId)
  const form = useProgressForm(userId)
  const streaks = useStreaks(userId)
  const goals = useGoals(userId)
  const goalsProgress = useGoalsProgress(userId)

  const [log, setLog] = useState<string[]>([])
  const [framesSent, setFramesSent] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const addLog = (msg: string) => {
    const ts = new Date().toISOString().slice(11, 23)
    setLog(prev => [`[${ts}] ${msg}`, ...prev].slice(0, 30))
    console.log(`[Phase13Verify] ${msg}`)
  }

  // Log state updates when connected
  useEffect(() => {
    if (poseState.connected) {
      addLog(`WS state update: exercise=${poseState.exercise} rep=${poseState.repCount} score=${poseState.formScore} landmarks=${poseState.landmarks.length} warning=${poseState.warning}`)
    }
  }, [lastMessage])

  // Log query results
  useEffect(() => {
    if (history.data) addLog(`useSessionHistory: ${history.data.length} sessions returned`)
  }, [history.data])

  useEffect(() => {
    if (profile.data) addLog(`useUserProfile: weight=${profile.data.weight_kg} name=${profile.data.name}`)
  }, [profile.data])

  useEffect(() => {
    if (calories.data) addLog(`useProgressCalories: ${calories.data.length} entries`)
  }, [calories.data])

  useEffect(() => {
    if (form.data) addLog(`useProgressForm: ${form.data.length} exercises`)
  }, [form.data])

  useEffect(() => {
    if (streaks.data) addLog(`useStreaks: current=${streaks.data.current} best=${streaks.data.best}`)
  }, [streaks.data])

  useEffect(() => {
    if (goals.data) addLog(`useGoals: ${goals.data.length} active goals`)
  }, [goals.data])

  useEffect(() => {
    if (goalsProgress.data) addLog(`useGoalsProgress: ${goalsProgress.data.length} progress items`)
  }, [goalsProgress.data])

  // Send a blank JPEG frame every 500ms when connected to trigger WS updates
  useEffect(() => {
    if (!poseState.connected) {
      if (timerRef.current) clearInterval(timerRef.current)
      return
    }
    timerRef.current = setInterval(async () => {
      // Create a tiny 4x4 canvas JPEG
      const canvas = document.createElement('canvas')
      canvas.width = 64; canvas.height = 48
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#333'
      ctx.fillRect(0, 0, 64, 48)
      canvas.toBlob(blob => {
        if (blob) {
          lifecycle.poseSession.sendFrame(blob)
          setFramesSent(n => n + 1)
        }
      }, 'image/jpeg', 0.7)
    }, 500)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [poseState.connected])

  const handleStart = async () => {
    addLog(`Starting session for user ${userId}...`)
    await lifecycle.startSession(userId)
    addLog(`Status: ${lifecycle.status}`)
  }

  const handleEnd = async () => {
    addLog('Ending session...')
    await lifecycle.endSession()
    addLog(`Status after end: ${lifecycle.status}`)
  }

  return (
    <div style={{ fontFamily: 'monospace', padding: 20, background: '#111', color: '#eee', minHeight: '100vh' }}>
      <h1 style={{ color: '#4af' }}>Phase 13 Verification</h1>

      {/* Session lifecycle */}
      <section style={{ marginBottom: 16 }}>
        <h2 style={{ color: '#fa4' }}>TASK-13.1 + 13.2 — Session + WS</h2>
        <p>userId: {userId} | status: <b style={{ color: lifecycle.status === 'active' ? '#4f4' : '#fa4' }}>{lifecycle.status}</b> | sessionId: {lifecycle.sessionId ?? 'none'}</p>
        <p>WS connected: <b style={{ color: poseState.connected ? '#4f4' : '#f44' }}>{String(poseState.connected)}</b> | frames sent: {framesSent}</p>
        {lifecycle.error && <p style={{ color: '#f44' }}>Error: {lifecycle.error}</p>}
        <button onClick={handleStart} disabled={lifecycle.status === 'active'} style={{ marginRight: 8, padding: '4px 12px' }}>Start</button>
        <button onClick={handleEnd} disabled={lifecycle.status !== 'active'} style={{ padding: '4px 12px' }}>End</button>
      </section>

      {/* Real-time pose state */}
      <section style={{ marginBottom: 16 }}>
        <h3 style={{ color: '#4af' }}>Pose State</h3>
        <pre style={{ fontSize: 11, background: '#222', padding: 8 }}>{JSON.stringify(poseState, null, 2)}</pre>
      </section>

      {/* Query hooks */}
      <section style={{ marginBottom: 16 }}>
        <h2 style={{ color: '#fa4' }}>TASK-13.3 — Query Hooks</h2>
        <p>useSessionHistory: <b>{history.isSuccess ? `${history.data?.length} sessions` : history.isLoading ? 'loading...' : `error: ${history.error?.message}`}</b></p>
        <p>useUserProfile: <b>{profile.isSuccess ? `weight=${profile.data?.weight_kg}` : profile.isLoading ? 'loading...' : `error: ${profile.error?.message}`}</b></p>
        <p>useProgressCalories: <b>{calories.isSuccess ? `${calories.data?.length} entries` : calories.isLoading ? 'loading...' : `error: ${calories.error?.message}`}</b></p>
        <p>useProgressForm: <b>{form.isSuccess ? `${form.data?.length} exercises` : form.isLoading ? 'loading...' : `error: ${form.error?.message}`}</b></p>
        <p>useStreaks: <b>{streaks.isSuccess ? `current=${streaks.data?.current} best=${streaks.data?.best}` : streaks.isLoading ? 'loading...' : `error: ${streaks.error?.message}`}</b></p>
        <p>useGoals: <b>{goals.isSuccess ? `${goals.data?.length} goals` : goals.isLoading ? 'loading...' : `error: ${goals.error?.message}`}</b></p>
        <p>useGoalsProgress: <b>{goalsProgress.isSuccess ? `${goalsProgress.data?.length} items` : goalsProgress.isLoading ? 'loading...' : `error: ${goalsProgress.error?.message}`}</b></p>
      </section>

      {/* Event log */}
      <section>
        <h3 style={{ color: '#4af' }}>Event Log (also in console)</h3>
        <div style={{ fontSize: 11, background: '#1a1a1a', padding: 8, maxHeight: 300, overflowY: 'auto' }}>
          {log.map((l, i) => <div key={i} style={{ color: l.includes('ERROR') ? '#f44' : '#ccc' }}>{l}</div>)}
        </div>
      </section>
    </div>
  )
}
