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
  capture_ts_echo?: number
  _confidence?: number
  _angle_count?: number
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
  /** Send a pre-encoded base64 JPEG string directly — no FileReader round-trip.
   *  captureTs is performance.now() at frame capture time for lag measurement. */
  sendFrameBase64: (base64: string, captureTs?: number) => void
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
          // Use explicit null check: if server sends null, clear the field.
          // Do NOT fall back to prev.exercise on null — that keeps stale state
          // from a previous workout visible after the person stops moving.
          exercise: msg.exercise !== undefined ? msg.exercise : prev.exercise,
          repCount: msg.rep_count ?? prev.repCount,
          setNumber: msg.set_number ?? prev.setNumber,
          formScore: msg.form_score ?? prev.formScore,
          corrections: msg.corrections ?? prev.corrections,
          caloriesRunning: msg.calories_running ?? prev.caloriesRunning,
          warning: msg.warning || null,
          landmarks: msg.landmarks ?? prev.landmarks,
        }))

        // Frame timing instrumentation — logs every frame to browser console.
        // capture_ts is performance.now() at the moment the frame was drawn from
        // the video element. receiveTs is now. Gap = total pipeline lag.
        const receiveTs = performance.now()
        const captureTs = (msg as any).capture_ts_echo
        const pipelineGap = captureTs ? (receiveTs - captureTs).toFixed(0) : '?'
        console.log('[TIMING] capture→receive gap:', pipelineGap, 'ms | backend_latency:', msg.latency_ms, 'ms | exercise:', msg.exercise, '| angles:', (msg as any)._angle_count, '| conf:', (msg as any)._confidence)
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
    // Kept for API compatibility — prefer sendFrameBase64 to avoid
    // the async FileReader round-trip.
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return

    const reader = new FileReader()
    reader.onloadend = () => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
      const base64 = (reader.result as string).split(',')[1]
      wsRef.current.send(JSON.stringify({ frame: base64 }))
    }
    reader.readAsDataURL(jpegBlob)
  }, [])

  // Synchronous path — caller has already encoded to base64 via
  // canvas.toDataURL(). No FileReader, no async delay, no frame queue buildup.
  // captureTs is performance.now() at the moment the frame was drawn from the
  // video element — embedded in the message so the backend echoes it back and
  // we can measure total capture→receive gap in the browser console.
  const sendFrameBase64 = useCallback((base64: string, captureTs?: number) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(JSON.stringify({ frame: base64, capture_ts: captureTs ?? performance.now() }))
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  return { state, connect, disconnect, sendFrame, sendFrameBase64, lastMessage }
}
