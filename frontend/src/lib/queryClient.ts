/**
 * TASK-13.3 — React Query setup and typed query hooks
 *
 * QueryClient with stale time 30s, no background refetch during active session.
 * Typed hooks for all REST endpoints from design.md §3.1.
 *
 * Design ref: §5.2. REQs: REQ-7.1–REQ-7.8, REQ-9.1.
 */

import { QueryClient, useQuery } from '@tanstack/react-query'
import { API_BASE } from './api'

// ---------------------------------------------------------------------------
// QueryClient
// ---------------------------------------------------------------------------

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,          // 30 seconds
      refetchOnWindowFocus: false, // no background refetch during active session
      retry: 1,
    },
  },
})

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
  }
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Type definitions matching backend Pydantic schemas
// ---------------------------------------------------------------------------

export interface SessionSummary {
  session_id: string
  started_at: string
  ended_at: string | null
  status: string
  total_reps: number
  total_calories: number
  avg_form_score: number | null
  duration_seconds: number | null
}

export interface SetSummary {
  id: number
  set_number: number
  exercise: string
  reps: number
  hold_seconds: number | null
  avg_form_score: number | null
  closed_at: string | null
}

export interface CalorieSegmentSummary {
  exercise: string
  calories: number | null
  duration_seconds: number | null
  started_at: string
  ended_at: string | null
}

export interface SessionDetail extends SessionSummary {
  sets: SetSummary[]
  form_score_trend: number[]
  calorie_segments: CalorieSegmentSummary[]
}

export interface CaloriesEntry {
  date: string
  calories: number
}

export interface FormTrend {
  exercise: string
  trend: number[]
}

export interface StreakResponse {
  current: number
  best: number
}

export interface GoalResponse {
  id: number
  user_id: number
  type: string
  target_calories: number
  active: boolean
  created_at: string
}

export interface GoalProgressItem {
  type: string
  target_calories: number
  achieved_calories: number
  achieved: boolean
}

export interface UserProfile {
  id: number
  name: string | null
  weight_kg: number
  created_at: string
}

// ---------------------------------------------------------------------------
// Query hooks — one per REST endpoint
// ---------------------------------------------------------------------------

/** REQ-7.1 — Session history list */
export function useSessionHistory(limit = 20, offset = 0) {
  return useQuery<SessionSummary[]>({
    queryKey: ['sessions', limit, offset],
    queryFn: () => apiFetch<SessionSummary[]>('/api/v1/sessions', { limit, offset }),
  })
}

/** REQ-7.2 — Single session detail */
export function useSessionDetail(sessionId: string | null) {
  return useQuery<SessionDetail>({
    queryKey: ['session', sessionId],
    queryFn: () => apiFetch<SessionDetail>(`/api/v1/sessions/${sessionId}`),
    enabled: sessionId != null,
  })
}

/** REQ-7.3 — Calorie progress (last 30 sessions) */
export function useProgressCalories(userId?: number) {
  return useQuery<CaloriesEntry[]>({
    queryKey: ['progress', 'calories', userId],
    queryFn: () => apiFetch<CaloriesEntry[]>('/api/v1/progress/calories',
      userId !== undefined ? { user_id: userId } : undefined),
  })
}

/** REQ-7.4 — Form score trends */
export function useProgressForm(userId?: number) {
  return useQuery<FormTrend[]>({
    queryKey: ['progress', 'form', userId],
    queryFn: () => apiFetch<FormTrend[]>('/api/v1/progress/form',
      userId !== undefined ? { user_id: userId } : undefined),
  })
}

/** REQ-7.5, REQ-7.6 — Streak */
export function useStreaks(userId: number) {
  return useQuery<StreakResponse>({
    queryKey: ['streaks', userId],
    queryFn: () => apiFetch<StreakResponse>('/api/v1/streaks', { user_id: userId }),
    enabled: userId > 0,
  })
}

/** REQ-7.7 — Goals list */
export function useGoals(userId: number) {
  return useQuery<GoalResponse[]>({
    queryKey: ['goals', userId],
    queryFn: () => apiFetch<GoalResponse[]>('/api/v1/goals', { user_id: userId }),
    enabled: userId > 0,
  })
}

/** REQ-7.8 — Goals progress */
export function useGoalsProgress(userId: number) {
  return useQuery<GoalProgressItem[]>({
    queryKey: ['goals', 'progress', userId],
    queryFn: () => apiFetch<GoalProgressItem[]>('/api/v1/goals/progress', { user_id: userId }),
    enabled: userId > 0,
  })
}

/** REQ-9.1 — User profile */
export function useUserProfile(userId: number) {
  return useQuery<UserProfile>({
    queryKey: ['user', userId],
    queryFn: () => apiFetch<UserProfile>('/api/v1/user', { user_id: userId }),
    enabled: userId > 0,
  })
}
