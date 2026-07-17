import React, { useState, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useUserProfile } from '../lib/queryClient'
import { useSessionLifecycle } from '../hooks/useSessionLifecycle'
import { API_BASE } from '../lib/api'

const DEFAULT_USER_ID = 1

// ---------------------------------------------------------------------------
// Fitness goal options with SVG body silhouettes
// ---------------------------------------------------------------------------
const FITNESS_GOALS = [
  {
    value: 'lose_weight',
    label: 'Lose Weight',
    desc: 'Burn fat, reduce body weight',
    // Wider silhouette
    svg: (
      <svg viewBox="0 0 60 100" className="w-full h-full" fill="currentColor">
        <ellipse cx="30" cy="12" rx="10" ry="11" />
        <ellipse cx="30" cy="42" rx="18" ry="22" />
        <ellipse cx="30" cy="72" rx="14" ry="18" />
        <rect x="14" y="60" width="8" height="28" rx="4" />
        <rect x="38" y="60" width="8" height="28" rx="4" />
        <rect x="12" y="30" width="7" height="22" rx="3.5" />
        <rect x="41" y="30" width="7" height="22" rx="3.5" />
      </svg>
    ),
  },
  {
    value: 'get_toned',
    label: 'Get Toned',
    desc: 'Lean, defined physique',
    // Medium athletic build
    svg: (
      <svg viewBox="0 0 60 100" className="w-full h-full" fill="currentColor">
        <ellipse cx="30" cy="11" rx="9" ry="10" />
        <ellipse cx="30" cy="38" rx="14" ry="18" />
        <ellipse cx="30" cy="68" rx="11" ry="16" />
        <rect x="17" y="58" width="7" height="30" rx="3.5" />
        <rect x="36" y="58" width="7" height="30" rx="3.5" />
        <rect x="13" y="28" width="6" height="20" rx="3" />
        <rect x="41" y="28" width="6" height="20" rx="3" />
      </svg>
    ),
  },
  {
    value: 'build_muscle',
    label: 'Build Muscle',
    desc: 'Increase muscle mass and size',
    // Wide shoulders, muscular
    svg: (
      <svg viewBox="0 0 60 100" className="w-full h-full" fill="currentColor">
        <ellipse cx="30" cy="11" rx="9" ry="10" />
        <ellipse cx="30" cy="38" rx="20" ry="19" />
        <ellipse cx="30" cy="68" rx="13" ry="16" />
        <rect x="16" y="58" width="8" height="30" rx="4" />
        <rect x="36" y="58" width="8" height="30" rx="4" />
        <rect x="8" y="26" width="9" height="22" rx="4.5" />
        <rect x="43" y="26" width="9" height="22" rx="4.5" />
      </svg>
    ),
  },
  {
    value: 'stay_fit',
    label: 'Stay Fit',
    desc: 'Maintain current fitness level',
    // Balanced build
    svg: (
      <svg viewBox="0 0 60 100" className="w-full h-full" fill="currentColor">
        <ellipse cx="30" cy="11" rx="9" ry="10" />
        <ellipse cx="30" cy="38" rx="15" ry="18" />
        <ellipse cx="30" cy="68" rx="11" ry="16" />
        <rect x="18" y="58" width="7" height="30" rx="3.5" />
        <rect x="35" y="58" width="7" height="30" rx="3.5" />
        <rect x="13" y="27" width="7" height="20" rx="3.5" />
        <rect x="40" y="27" width="7" height="20" rx="3.5" />
      </svg>
    ),
  },
  {
    value: 'improve_endurance',
    label: 'Endurance',
    desc: 'Cardio, stamina, performance',
    // Slim runner build
    svg: (
      <svg viewBox="0 0 60 100" className="w-full h-full" fill="currentColor">
        <ellipse cx="30" cy="11" rx="8" ry="9" />
        <ellipse cx="30" cy="37" rx="12" ry="16" />
        <ellipse cx="30" cy="66" rx="9" ry="15" />
        <rect x="19" y="57" width="6" height="32" rx="3" />
        <rect x="35" y="57" width="6" height="32" rx="3" />
        <rect x="14" y="27" width="6" height="19" rx="3" />
        <rect x="40" y="27" width="6" height="19" rx="3" />
      </svg>
    ),
  },
]

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export const ProfileView: React.FC = () => {
  const queryClient = useQueryClient()
  const { data: user, isLoading, error } = useUserProfile(DEFAULT_USER_ID)
  const { status: sessionStatus } = useSessionLifecycle()

  const [name, setName] = useState('')
  const [weightText, setWeightText] = useState('')
  const [heightText, setHeightText] = useState('')
  const [fitnessGoal, setFitnessGoal] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (user) {
      setName(user.name || '')
      setWeightText(user.weight_kg.toString())
      setHeightText(user.height_cm ? user.height_cm.toString() : '')
      setFitnessGoal(user.fitness_goal || null)
    }
  }, [user])

  const handleSave = async () => {
    setSaveStatus('saving')
    setErrorMessage(null)

    const parsedWeight = parseFloat(weightText)
    if (isNaN(parsedWeight) || parsedWeight < 20 || parsedWeight > 300) {
      setErrorMessage('Weight must be between 20 and 300 kg.')
      setSaveStatus('error')
      return
    }

    const parsedHeight = heightText.trim() ? parseFloat(heightText) : null
    if (parsedHeight !== null && (isNaN(parsedHeight) || parsedHeight < 50 || parsedHeight > 300)) {
      setErrorMessage('Height must be between 50 and 300 cm.')
      setSaveStatus('error')
      return
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/user`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: DEFAULT_USER_ID,
          name: name.trim() || null,
          weight_kg: parsedWeight,
          height_cm: parsedHeight,
          fitness_goal: fitnessGoal,
        }),
      })

      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.detail?.message || 'Failed to update profile')
      }

      await queryClient.invalidateQueries({ queryKey: ['user', DEFAULT_USER_ID] })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus(s => s === 'saved' ? 'idle' : s), 2500)
    } catch (err: any) {
      setErrorMessage(err.message)
      setSaveStatus('error')
    }
  }

  const formatJoinDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
    } catch { return '--' }
  }

  // BMI display
  const bmi = (() => {
    const w = parseFloat(weightText)
    const h = parseFloat(heightText)
    if (!isNaN(w) && !isNaN(h) && h > 0) {
      const val = w / ((h / 100) ** 2)
      return val.toFixed(1)
    }
    return null
  })()

  const bmiLabel = bmi
    ? parseFloat(bmi) < 18.5 ? 'Underweight'
    : parseFloat(bmi) < 25 ? 'Normal'
    : parseFloat(bmi) < 30 ? 'Overweight'
    : 'Obese'
    : null

  const bmiColor = bmi
    ? parseFloat(bmi) < 18.5 ? 'text-blue-400'
    : parseFloat(bmi) < 25 ? 'text-lime-400'
    : parseFloat(bmi) < 30 ? 'text-amber-400'
    : 'text-rose-400'
    : ''

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-slate-950">
        <div className="w-8 h-8 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Loading Profile...</span>
      </div>
    )
  }

  if (error || !user) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-slate-950">
        <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs px-6 py-4 rounded-xl text-center max-w-sm">
          <span className="font-bold block mb-2">Error loading profile</span>
          {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    )
  }

  const isSessionActive = sessionStatus === 'active'
  const selectedGoal = FITNESS_GOALS.find(g => g.value === fitnessGoal)

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 font-sans overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-8 md:px-8 md:py-10 space-y-6">

        {/* ── Page Header ─────────────────────────────────── */}
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white uppercase">Profile</h1>
          <p className="text-slate-500 text-xs mt-1">Your identity and fitness configuration</p>
        </div>

        {/* ── Profile Card ────────────────────────────────── */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden">
          {/* Banner */}
          <div className="h-20 bg-gradient-to-r from-lime-500/20 via-emerald-500/10 to-transparent relative">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(132,204,22,0.15),transparent_60%)]" />
          </div>

          <div className="px-6 pb-6">
            {/* Avatar row */}
            <div className="flex items-end justify-between -mt-10 mb-5">
              <div className="w-20 h-20 rounded-2xl bg-slate-800 border-4 border-slate-950 flex items-center justify-center shadow-xl overflow-hidden">
                {fitnessGoal && selectedGoal ? (
                  <div className="w-10 h-16 text-lime-400 opacity-80">
                    {selectedGoal.svg}
                  </div>
                ) : (
                  <svg className="w-10 h-10 text-slate-600" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                )}
              </div>

              {/* BMI Badge */}
              {bmi && (
                <div className="flex flex-col items-end">
                  <span className={`text-2xl font-black ${bmiColor}`}>{bmi}</span>
                  <span className={`text-[10px] font-bold uppercase tracking-widest ${bmiColor}`}>BMI · {bmiLabel}</span>
                </div>
              )}
            </div>

            {/* Name + meta */}
            <div className="mb-1">
              <h2 className="text-xl font-black text-white">{user.name || 'Anonymous User'}</h2>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-[10px] text-slate-600 font-mono">ID: {user.id.toString().padStart(4, '0')}</span>
                <span className="text-slate-700">·</span>
                <span className="text-[10px] text-slate-600 uppercase tracking-wider">Joined {formatJoinDate(user.created_at)}</span>
              </div>
            </div>

            {/* Stats row */}
            <div className="flex gap-4 mt-4 pt-4 border-t border-slate-800">
              {user.weight_kg && (
                <div>
                  <span className="text-xs font-black text-white">{user.weight_kg} <span className="text-slate-500 font-normal">kg</span></span>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Weight</p>
                </div>
              )}
              {user.height_cm && (
                <div>
                  <span className="text-xs font-black text-white">{user.height_cm} <span className="text-slate-500 font-normal">cm</span></span>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Height</p>
                </div>
              )}
              {user.fitness_goal && (
                <div>
                  <span className="text-xs font-black text-white capitalize">{user.fitness_goal.replace('_', ' ')}</span>
                  <p className="text-[10px] text-slate-600 uppercase tracking-wider">Goal</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Edit Form ────────────────────────────────────── */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 space-y-6">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit Profile</h3>

          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Display Name</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Alex"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3.5 text-sm font-medium text-white placeholder-slate-700 focus:outline-none focus:border-lime-500/60 focus:ring-1 focus:ring-lime-500/40 transition-all"
            />
          </div>

          {/* Weight + Height side by side */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center justify-between">
                <span>Weight (kg)</span>
                {isSessionActive && <span className="text-rose-500 text-[9px]">Locked</span>}
              </label>
              <input
                type="number"
                step="0.1"
                value={weightText}
                onChange={e => setWeightText(e.target.value)}
                disabled={isSessionActive}
                placeholder="e.g. 70"
                className={`w-full bg-slate-950 border rounded-xl px-4 py-3.5 text-sm font-medium text-white placeholder-slate-700 focus:outline-none transition-all ${
                  isSessionActive
                    ? 'border-slate-800/50 opacity-40 cursor-not-allowed'
                    : 'border-slate-800 focus:border-lime-500/60 focus:ring-1 focus:ring-lime-500/40'
                }`}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Height (cm)</label>
              <input
                type="number"
                step="0.5"
                value={heightText}
                onChange={e => setHeightText(e.target.value)}
                placeholder="e.g. 175"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3.5 text-sm font-medium text-white placeholder-slate-700 focus:outline-none focus:border-lime-500/60 focus:ring-1 focus:ring-lime-500/40 transition-all"
              />
            </div>
          </div>

          {/* Fitness Goal Selector */}
          <div className="space-y-3">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Fitness Goal</label>
            <div className="grid grid-cols-5 gap-2">
              {FITNESS_GOALS.map(goal => {
                const active = fitnessGoal === goal.value
                return (
                  <button
                    key={goal.value}
                    type="button"
                    onClick={() => setFitnessGoal(active ? null : goal.value)}
                    className={`flex flex-col items-center gap-1.5 rounded-xl p-2 border transition-all duration-200 group ${
                      active
                        ? 'border-lime-500/60 bg-lime-500/10 shadow-[0_0_16px_rgba(132,204,22,0.12)]'
                        : 'border-slate-800 bg-slate-900/50 hover:border-slate-700 hover:bg-slate-800/50'
                    }`}
                  >
                    {/* Silhouette */}
                    <div className={`w-8 h-14 transition-colors duration-200 ${active ? 'text-lime-400' : 'text-slate-600 group-hover:text-slate-500'}`}>
                      {goal.svg}
                    </div>
                    <span className={`text-[9px] font-bold uppercase tracking-wide leading-tight text-center transition-colors ${
                      active ? 'text-lime-400' : 'text-slate-600 group-hover:text-slate-400'
                    }`}>
                      {goal.label}
                    </span>
                  </button>
                )
              })}
            </div>
            {fitnessGoal && selectedGoal && (
              <p className="text-[10px] text-slate-500">{selectedGoal.desc}</p>
            )}
          </div>

          {/* Error */}
          {errorMessage && (
            <div className="bg-rose-500/10 border border-rose-500/20 px-4 py-3 rounded-xl flex items-start gap-2.5">
              <svg className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs text-rose-400 font-medium">{errorMessage}</span>
            </div>
          )}

          {/* Save Button */}
          <div className="flex justify-end pt-2">
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving' || isSessionActive}
              className={`px-7 py-3.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all duration-300 flex items-center gap-2 ${
                saveStatus === 'saved'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-lime-500 hover:bg-lime-400 text-slate-950 shadow-[0_8px_24px_rgba(132,204,22,0.2)] hover:shadow-[0_10px_28px_rgba(132,204,22,0.3)] disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none'
              }`}
            >
              {saveStatus === 'saving' ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                  <span>Saving…</span>
                </>
              ) : saveStatus === 'saved' ? (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
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
