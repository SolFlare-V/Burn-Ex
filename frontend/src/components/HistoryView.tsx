import React, { useState } from 'react'
import { useSessionHistory, useSessionDetail } from '../lib/queryClient'

// ---------------------------------------------------------------------------
// Subcomponent: SessionDetailDrawer
// ---------------------------------------------------------------------------
interface SessionDetailDrawerProps {
  sessionId: string | null
  onClose: () => void
}

export const SessionDetailDrawer: React.FC<SessionDetailDrawerProps> = ({
  sessionId,
  onClose,
}) => {
  const { data: session, isLoading, error } = useSessionDetail(sessionId)

  const formatDuration = (totalSeconds: number | null): string => {
    if (totalSeconds == null) return '--:--'
    const h = Math.floor(totalSeconds / 3600)
    const m = Math.floor((totalSeconds % 3600) / 60)
    const s = totalSeconds % 60
    if (h > 0) {
      return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const formatDateTime = (isoString: string): string => {
    try {
      const date = new Date(isoString)
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return '--'
    }
  }

  const getScoreColorClass = (score: number | null): string => {
    if (score == null) return 'text-slate-500'
    if (score >= 80) return 'text-emerald-400 font-bold'
    if (score >= 50) return 'text-amber-400 font-bold'
    return 'text-rose-400 font-bold'
  }

  // Draw trend sparkline path
  const drawTrendLine = (trend: number[]): string => {
    if (trend.length < 2) return ''
    const width = 400
    const height = 80
    const padding = 10
    const graphWidth = width - padding * 2
    const graphHeight = height - padding * 2

    return trend.map((score, idx) => {
      const x = padding + (idx / (trend.length - 1)) * graphWidth
      const y = padding + graphHeight - (score / 100) * graphHeight
      return `${x},${y}`
    }).join(' ')
  }

  const maxCaloriesRaw = session?.calorie_segments && session.calorie_segments.length > 0
    ? Math.max(...session.calorie_segments.map(seg => seg.calories ?? 0))
    : 1
  const maxCalories = maxCaloriesRaw <= 0 ? 1 : maxCaloriesRaw

  return (
    <>
      {/* Backdrop overlay */}
      {sessionId && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 transition-opacity duration-300 animate-fadeIn"
        />
      )}

      {/* Slide-out Drawer Panel */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-lg bg-slate-950 border-l border-slate-900 shadow-[0_0_60px_rgba(0,0,0,0.8)] z-50 transform transition-transform duration-300 ease-out overflow-y-auto flex flex-col ${
          sessionId ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-900 flex justify-between items-center sticky top-0 bg-slate-950/90 backdrop-blur-md z-10">
          <div>
            <span className="text-[9px] font-mono font-bold tracking-widest text-slate-500 uppercase">Workout Logs</span>
            <h3 className="text-lg font-black text-white uppercase mt-0.5 tracking-tight">Session Log Details</h3>
          </div>
          <button
            onClick={onClose}
            className="w-9 h-9 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white rounded-xl flex items-center justify-center transition-colors duration-300"
          >
            {/* Close SVG */}
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content Body */}
        {isLoading ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <div className="w-8 h-8 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Loading...</span>
          </div>
        ) : error || !session ? (
          <div className="flex-1 p-8 text-center">
            <div className="text-rose-500 text-xs font-bold bg-rose-500/10 px-4 py-3 border border-rose-500/20 rounded-xl mb-4">
              Failed to load session details.
            </div>
          </div>
        ) : (
          <div className="p-6 space-y-6 flex-1">
            
            {/* Status indicator banner */}
            <div className="flex justify-between items-center bg-slate-900/40 border border-slate-900 rounded-xl p-4">
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-slate-500 uppercase">Timestamp</span>
                <span className="text-xs font-bold text-slate-300 mt-1">{formatDateTime(session.started_at)}</span>
              </div>
              <div>
                {session.status === 'interrupted' ? (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-1.5" />
                    Interrupted
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5" />
                    Completed
                  </span>
                )}
              </div>
            </div>

            {/* Metrics cards grid */}
            <div className="grid grid-cols-2 gap-4">
              
              {/* Reps */}
              <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-xl">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Total Reps</span>
                <div className="text-2xl font-black text-white mt-1">{session.total_reps}</div>
              </div>

              {/* Calories */}
              <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-xl">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Burn Estimate</span>
                <div className="text-2xl font-black text-white mt-1">
                  {session.total_calories.toFixed(1)} <span className="text-xs font-bold text-rose-500">Kcal</span>
                </div>
              </div>

              {/* Duration */}
              <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-xl">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Duration</span>
                <div className="text-2xl font-black text-white mt-1 font-mono">{formatDuration(session.duration_seconds)}</div>
              </div>

              {/* Form Score */}
              <div className="bg-slate-900/20 border border-slate-900 p-4 rounded-xl">
                <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Avg Form Quality</span>
                <div className={`text-2xl font-black mt-1 ${getScoreColorClass(session.avg_form_score)}`}>
                  {session.avg_form_score != null ? `${Math.round(session.avg_form_score)}%` : '--'}
                </div>
              </div>
            </div>

            {/* Sparkline trend path */}
            {session.form_score_trend && session.form_score_trend.length >= 2 && (
              <div className="bg-slate-900/10 border border-slate-900 p-4 rounded-xl">
                <h4 className="text-[10px] font-bold tracking-widest text-slate-500 uppercase mb-3">Form Score Consistency</h4>
                <div className="w-full flex justify-center">
                  <svg className="w-full h-20 max-w-sm" viewBox="0 0 400 80">
                    <line x1="0" y1="10" x2="400" y2="10" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                    <line x1="0" y1="40" x2="400" y2="40" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                    <line x1="0" y1="70" x2="400" y2="70" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                    
                    <polyline
                      fill="none"
                      stroke="#84cc16"
                      strokeWidth="3"
                      points={drawTrendLine(session.form_score_trend)}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </div>
            )}

            {/* Sets Table */}
            <div className="bg-slate-900/20 border border-slate-900 rounded-xl overflow-hidden">
              <div className="px-4 py-3 bg-slate-950/40 border-b border-slate-900">
                <h4 className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Set Log</h4>
              </div>
              {session.sets && session.sets.length > 0 ? (
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-slate-900 text-[9px] font-bold text-slate-500 uppercase tracking-widest bg-slate-950/20">
                        <th className="py-2.5 px-4">Set</th>
                        <th className="py-2.5 px-4">Exercise</th>
                        <th className="py-2.5 px-4 text-center">Reps</th>
                        <th className="py-2.5 px-4 text-right">Avg Form</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/30">
                      {session.sets.map(set => (
                        <tr key={set.id}>
                          <td className="py-2.5 px-4 font-mono text-slate-400">#{set.set_number}</td>
                          <td className="py-2.5 px-4 font-semibold text-slate-200 uppercase tracking-wider">
                            {set.exercise.replace('_', ' ').replace('-', ' ')}
                          </td>
                          <td className="py-2.5 px-4 font-bold text-center text-white">{set.reps}</td>
                          <td className={`py-2.5 px-4 text-right ${getScoreColorClass(set.avg_form_score)}`}>
                            {set.avg_form_score != null ? `${Math.round(set.avg_form_score)}%` : '--'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4 text-center text-[10px] text-slate-500 uppercase">No completed sets.</div>
              )}
            </div>

            {/* Calories graph segments */}
            {session.calorie_segments && session.calorie_segments.length > 0 && (
              <div className="bg-slate-900/20 border border-slate-900 rounded-xl p-4 space-y-3">
                <h4 className="text-[10px] font-bold tracking-widest text-slate-500 uppercase mb-2">Exercise Calories</h4>
                {session.calorie_segments.map((seg, idx) => {
                  const val = seg.calories ?? 0
                  const widthPercent = Math.max(5, (val / maxCalories) * 100)
                  return (
                    <div key={idx} className="flex flex-col space-y-1">
                      <div className="flex justify-between items-baseline text-[10px]">
                        <span className="font-semibold text-slate-200 uppercase tracking-wider">
                          {seg.exercise.replace('_', ' ').replace('-', ' ')}
                        </span>
                        <span className="font-bold font-mono text-rose-400">{val.toFixed(1)} Kcal</span>
                      </div>
                      <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-rose-600 to-rose-400 rounded-full"
                          style={{ width: `${widthPercent}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Main Component: HistoryView
// ---------------------------------------------------------------------------
export const HistoryView: React.FC = () => {
  const { data: historyList, isLoading, error } = useSessionHistory(20, 0)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  const formatDuration = (totalSeconds: number | null): string => {
    if (totalSeconds == null) return '--:--'
    const h = Math.floor(totalSeconds / 3600)
    const m = Math.floor((totalSeconds % 3600) / 60)
    const s = totalSeconds % 60
    if (h > 0) {
      return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    }
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const formatDate = (isoString: string): string => {
    try {
      const date = new Date(isoString)
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return '--'
    }
  }

  const getScoreColorClass = (score: number | null): string => {
    if (score == null) return 'text-slate-500'
    if (score >= 80) return 'text-emerald-400 font-bold'
    if (score >= 50) return 'text-amber-400 font-bold'
    return 'text-rose-400 font-bold'
  }

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col items-center p-4 md:p-8 font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Container Header */}
      <div className="w-full max-w-4xl border-b border-slate-900 pb-4 mb-8">
        <h1 className="text-3xl font-black tracking-tight text-white uppercase">
          Workout History Log
        </h1>
        <p className="text-slate-400 text-xs mt-1">
          Review details of your completed and interrupted workout sessions.
        </p>
      </div>

      {/* Main List Layout */}
      <div className="w-full max-w-4xl">
        
        {isLoading ? (
          <div className="flex flex-col items-center justify-center p-12">
            <div className="w-8 h-8 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
            <span className="text-slate-500 text-xs font-bold uppercase tracking-wider">Loading history log...</span>
          </div>
        ) : error ? (
          <div className="bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs px-4 py-3 rounded-xl">
            <span className="font-bold">Error loading history:</span> {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        ) : !historyList || historyList.length === 0 ? (
          <div className="bg-slate-900/20 border border-slate-900 rounded-2xl p-12 text-center select-none">
            <div className="w-12 h-12 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-sm font-extrabold text-white uppercase mb-2">No Sessions Recorded</h2>
            <p className="text-slate-400 text-xs max-w-xs mx-auto leading-relaxed">
              You haven't completed any workout sessions yet. Start a session from the workspace to begin logging your training data.
            </p>
          </div>
        ) : (
          /* Responsive Table list */
          <div className="bg-slate-900/20 border border-slate-900 rounded-2xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.4)]">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-900 text-[10px] font-bold text-slate-500 uppercase tracking-widest bg-slate-950/40">
                    <th className="py-4 px-6">Date & Time</th>
                    <th className="py-4 px-6 text-center">Reps</th>
                    <th className="py-4 px-6 text-center">Calories</th>
                    <th className="py-4 px-6 text-center">Duration</th>
                    <th className="py-4 px-6 text-center">Avg Form</th>
                    <th className="py-4 px-6 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40 select-none">
                  {historyList.map((summary) => (
                    <tr
                      key={summary.session_id}
                      onClick={() => setSelectedSessionId(summary.session_id)}
                      className="hover:bg-slate-900/25 active:bg-slate-900/40 cursor-pointer transition-colors duration-200 group"
                    >
                      <td className="py-4 px-6 font-bold text-slate-200 group-hover:text-lime-400 transition-colors duration-200">
                        {formatDate(summary.started_at)}
                      </td>
                      <td className="py-4 px-6 text-center text-white font-semibold">{summary.total_reps}</td>
                      <td className="py-4 px-6 text-center text-rose-300 font-semibold font-mono">
                        {summary.total_calories.toFixed(0)} <span className="text-[10px] font-bold">Kcal</span>
                      </td>
                      <td className="py-4 px-6 text-center text-slate-300 font-mono">
                        {formatDuration(summary.duration_seconds)}
                      </td>
                      <td className={`py-4 px-6 text-center ${getScoreColorClass(summary.avg_form_score)}`}>
                        {summary.avg_form_score != null ? `${Math.round(summary.avg_form_score)}%` : '--'}
                      </td>
                      <td className="py-4 px-6 text-right">
                        {summary.status === 'interrupted' ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                            Interrupted
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            Completed
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Side Detail Slide-Out Drawer */}
      <SessionDetailDrawer
        sessionId={selectedSessionId}
        onClose={() => setSelectedSessionId(null)}
      />
    </div>
  )
}
