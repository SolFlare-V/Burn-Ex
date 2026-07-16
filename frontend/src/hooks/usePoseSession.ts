/**
 * TASK-13.1 — usePoseSession hook
 *
 * Manages the WebSocket connection lifecycle and real-time pose state.
 * Matches the PoseSessionState interface from design.md §5.2.
 *
 * Design ref: §5.2. REQs: REQ-1.1, REQ-3.2, REQ-4.3, REQ-5.5.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_BASE } from '../lib/api'

// ---------------------------------------------------------------------------
// Types (design.md §5.2)
// ---------------------------------------------------------------------------

export interface Landmark {
  id: number
  x: number
  y: number
  z: number
  visibility: number
}

export interface PoseSessionState {
  connected: boolean
  exercise: string | null
  repCount: number
  setNumber: number
  formScore: number
  corrections: string[]
  caloriesRunning: number
  warning: string | null
  landmarks: Landmark[]
}

export interface ServerMessage {
  exercise: string | null
  rep_count: number
  set_number: number
  form_score: number
  corrections: string[]
  calories_running: number
  warning: string
  landmarks: Landmark[]
  latency_ms?: number
  type?: string
}

const DEFAULT_STATE: PoseSessionState = {
  connected: false,
  exercise: null,
  repCount: 0,
  setNumber: 1,
  formScore: 0,
  corrections: [],
  caloriesRunning: 0,
  warning: null,
  landmarks: [],
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UsePoseSessionReturn {
  state: PoseSessionState
  /** Open the WebSocket for the given sessionId. */
  connect: (sessionId: string) => void
  /** Close the WebSocket and reset state. */
  disconnect: () => void
  /** Encode and send a JPEG blob as a base64 frame message. */
  sendFrame: (jpegBlob: Blob) => void
  /** Expose the last raw server message for debugging. */
  lastMessage: ServerMessage | null
}

export function usePoseSession(): UsePoseSessionReturn {
  const [state, setState] = useState<PoseSessionState>(DEFAULT_STATE)
  const [lastMessage, setLastMessage] = useState<ServerMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback((sessionId: string) => {
    // Close any existing connection first
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const url = `${WS_BASE}/ws/pose?session_id=${sessionId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setState(prev => ({ ...prev, connected: true }))
      console.log('[usePoseSession] WebSocket connected:', sessionId)
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: ServerMessage = JSON.parse(event.data as string)

        // Ignore heartbeat pings from server
        if (msg.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }))
          return
        }

        setLastMessage(msg)
        setState(prev => ({
          ...prev,
          exercise: msg.exercise ?? prev.exercise,
          repCount: msg.rep_count ?? prev.repCount,
          setNumber: msg.set_number ?? prev.setNumber,
          formScore: msg.form_score ?? prev.formScore,
          corrections: msg.corrections ?? prev.corrections,
          caloriesRunning: msg.calories_running ?? prev.caloriesRunning,
          warning: msg.warning || null,
          landmarks: msg.landmarks ?? prev.landmarks,
        }))

        // Log every update so the verify script can confirm state updates
        console.log('[usePoseSession] state updated:', {
          exercise: msg.exercise,
          rep_count: msg.rep_count,
          form_score: msg.form_score,
          landmarks: msg.landmarks?.length ?? 0,
          warning: msg.warning,
          latency_ms: msg.latency_ms,
        })
      } catch (err) {
        console.error('[usePoseSession] parse error:', err)
      }
    }

    ws.onerror = (err) => {
      console.error('[usePoseSession] WS error:', err)
    }

    ws.onclose = (event) => {
      setState(prev => ({ ...prev, connected: false }))
      console.log('[usePoseSession] WebSocket closed:', event.code, event.reason)
    }
  }, [])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setState(DEFAULT_STATE)
  }, [])

  const sendFrame = useCallback((jpegBlob: Blob) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    const reader = new FileReader()
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1]
      ws.send(JSON.stringify({ frame: base64, exercise_hint: 'squat' }))
    }
    reader.readAsDataURL(jpegBlob)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  return { state, connect, disconnect, sendFrame, lastMessage }
}
