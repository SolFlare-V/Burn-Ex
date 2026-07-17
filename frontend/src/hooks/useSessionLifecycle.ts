/**
 * TASK-13.2 — useSessionLifecycle hook
 *
 * Coordinates session start/end REST calls with WebSocket open/close.
 * Exposes status: "idle" | "active" | "ended" | "interrupted"
 *
 * Design ref: §5.2. REQs: REQ-6.1, REQ-6.2, REQ-6.4.
 */

import { useCallback, useState } from 'react'
import { usePoseSession, type UsePoseSessionReturn } from './usePoseSession'
import { API_BASE } from '../lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SessionStatus = 'idle' | 'active' | 'ended' | 'interrupted'

export interface SessionLifecycle {
  status: SessionStatus
  sessionId: string | null
  poseSession: UsePoseSessionReturn
  /** Start a session for the given userId. Opens WS on success. */
  startSession: (userId: number) => Promise<void>
  /** End the active session. Closes WS on success. */
  endSession: () => Promise<void>
  /** Mark session interrupted (e.g. WS dropped). */
  interruptSession: () => void
  /** Reset session back to idle state (e.g. closing summary view) */
  resetSession: () => void
  error: string | null
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSessionLifecycle(): SessionLifecycle {
  const [status, setStatus] = useState<SessionStatus>('idle')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const poseSession = usePoseSession()

  const startSession = useCallback(async (userId: number) => {
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/v1/sessions/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId }),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        const detail = body?.detail ?? {}
        const code = typeof detail === 'object' ? detail.code : detail

        if (res.status === 409 && code === 'SESSION_ALREADY_ACTIVE') {
          // A stale session is blocking start (usually from a server restart).
          // Find it in the session list and end it, then retry once.
          const listRes = await fetch(`${API_BASE}/api/v1/sessions?limit=1`)
          if (listRes.ok) {
            const sessions = await listRes.json().catch(() => [])
            const stale = sessions.find(
              (s: { status: string; session_id: string }) => s.status === 'active'
            )
            if (stale) {
              await fetch(`${API_BASE}/api/v1/sessions/${stale.session_id}/end`, {
                method: 'POST',
              }).catch(() => null)
            }
          }
          // Retry start once after clearing the stale session.
          const retryRes = await fetch(`${API_BASE}/api/v1/sessions/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId }),
          })
          if (!retryRes.ok) {
            const retryBody = await retryRes.json().catch(() => ({}))
            setError(`Failed to start session: ${retryBody?.detail?.code ?? retryRes.status}`)
            return
          }
          const retryData = await retryRes.json()
          const newSessionId: string = retryData.session_id
          setSessionId(newSessionId)
          setStatus('active')
          poseSession.connect(newSessionId)
          return
        }

        if (res.status === 422) {
          setError('WEIGHT_REQUIRED')
        } else {
          setError(`Start failed: ${code}`)
        }
        return
      }

      const data = await res.json()
      const newSessionId: string = data.session_id
      setSessionId(newSessionId)
      setStatus('active')

      // Open WebSocket now that session is active
      poseSession.connect(newSessionId)

      console.log('[useSessionLifecycle] Session started:', newSessionId)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      console.error('[useSessionLifecycle] startSession error:', err)
    }
  }, [poseSession])

  const endSession = useCallback(async () => {
    if (!sessionId) return
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/end`, {
        method: 'POST',
      })

      // Close WS regardless of HTTP outcome
      poseSession.disconnect()

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setError(`End failed: ${body?.detail ?? res.status}`)
        return
      }

      setStatus('ended')
      console.log('[useSessionLifecycle] Session ended:', sessionId)
    } catch (err) {
      poseSession.disconnect()
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      console.error('[useSessionLifecycle] endSession error:', err)
    }
  }, [sessionId, poseSession])

  const interruptSession = useCallback(() => {
    poseSession.disconnect()
    setStatus('interrupted')
    console.log('[useSessionLifecycle] Session interrupted:', sessionId)
  }, [poseSession, sessionId])

  const resetSession = useCallback(() => {
    setStatus('idle')
    setSessionId(null)
    setError(null)
  }, [])

  return {
    status,
    sessionId,
    poseSession,
    startSession,
    endSession,
    interruptSession,
    resetSession,
    error,
  }
}
