import React from 'react'
import { useSessionDetail } from '../lib/queryClient'

interface SessionSummaryViewProps {
  sessionId: string
  onClose: () => void
}

export const SessionSummaryView: React.FC<SessionSummaryViewProps> = ({
  sessionId,
  onClose,
}) => {
  const { data: session, isLoading, error } = useSessionDetail(sessionId)

  // Format seconds to MM:SS or HH:MM:SS
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

  // Format ISO timestamp to readable date/time
  const formatDateTime = (isoString: string): string => {
    try {
      const date = new Date(isoString)
      return date.toLocaleDateString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return '--'
    }
  }

  // Score styling utility
  const getScoreColorClass = (score: number | null): string => {
    if (score == null) return 'text-slate-500'
    if (score >= 80) return 'text-emerald-400 font-bold'
    if (score >= 50) return 'text-amber-400 font-bold'
    return 'text-rose-400 font-bold'
  }

  if (isLoading) {
    return (
      <div className="min-h-screen w-full bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="w-10 h-10 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-slate-400 text-xs font-bold uppercase tracking-wider">Loading Session Summary...</span>
      </div>
    )
  }

  if (error || !session) {
    return (
      <div className="min-h-screen w-full bg-slate-950 flex flex-col items-center justify-center p-4 text-center">
        <div className="text-rose-500 text-xs font-bold bg-rose-500/10 px-4 py-3 border border-rose-500/20 rounded-xl max-w-sm mb-4">
          Failed to load session details: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
        <button
          onClick={onClose}
          className="px-6 py-2.5 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider transition-colors duration-300"
        >
          Return to Dashboard
        </button>
      </div>
    )
  }

  // Find max calorie value among segments for relative bar width calculation, ensuring we don't divide by 0
  const maxCaloriesRaw = session.calorie_segments?.length > 0
    ? Math.max(...session.calorie_segments.map(seg => seg.calories ?? 0))
    : 1
  const maxCalories = maxCaloriesRaw <= 0 ? 1 : maxCaloriesRaw

  // Construct SVG trend path points
  const drawTrendLine = (trend: number[]): string => {
    if (trend.length < 2) return ''
    const width = 500
    const height = 80
    const padding = 10
    const graphWidth = width - padding * 2
    const graphHeight = height - padding * 2

    return trend.map((score, idx) => {
      const x = padding + (idx / (trend.length - 1)) * graphWidth
      const y = padding + graphHeight - (score / 100) * graphHeight
      return `${x},${y}`
    }).join(' ')
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-tr from-gray-950 via-slate-950 to-black text-slate-100 flex flex-col items-center p-4 md:p-8 font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Container Header */}
      <div className="w-full max-w-4xl flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-900 pb-4 mb-8 gap-4">
        <div>
          <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Workout Summary</span>
          <h1 className="text-3xl font-black tracking-tight text-white uppercase mt-0.5">
            Session Report
          </h1>
          <p className="text-slate-400 text-xs mt-1 font-mono">
            {formatDateTime(session.started_at)}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {session.status === 'interrupted' ? (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-400 border border-rose-500/25 shadow-[0_0_10px_rgba(239,68,68,0.1)]">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mr-2 animate-pulse" />
              Interrupted
            </span>
          ) : (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 shadow-[0_0_10px_rgba(52,211,153,0.1)]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-2" />
              Completed
            </span>
          )}
        </div>
      </div>

      {/* Main Container */}
      <div className="w-full max-w-4xl space-y-6">

        {/* 1. Core Summary Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          
          {/* Total Reps */}
          <div className="flex flex-col p-5 bg-slate-900/30 border border-slate-900/80 rounded-2xl relative overflow-hidden group hover:border-lime-500/20 transition-all duration-300">
            <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Total Reps</span>
            <span className="text-3xl font-black text-white mt-2 drop-shadow-[0_0_10px_rgba(255,255,255,0.05)]">
              {session.total_reps}
            </span>
          </div>

          {/* Total Calories */}
          <div className="flex flex-col p-5 bg-slate-900/30 border border-slate-900/80 rounded-2xl relative overflow-hidden group hover:border-rose-500/20 transition-all duration-300">
            <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Energy Burned</span>
            <span className="text-3xl font-black text-white mt-2">
              {session.total_calories.toFixed(1)} <span className="text-xs font-bold text-rose-400">Kcal</span>
            </span>
          </div>

          {/* Workout Duration */}
          <div className="flex flex-col p-5 bg-slate-900/30 border border-slate-900/80 rounded-2xl relative overflow-hidden group hover:border-blue-500/20 transition-all duration-300">
            <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Duration</span>
            <span className="text-3xl font-black text-white mt-2 font-mono">
              {formatDuration(session.duration_seconds)}
            </span>
          </div>

          {/* Average Form Score */}
          <div className="flex flex-col p-5 bg-slate-900/30 border border-slate-900/80 rounded-2xl relative overflow-hidden group hover:border-emerald-500/20 transition-all duration-300">
            <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Avg Form Score</span>
            <span className={`text-3xl font-black mt-2 ${getScoreColorClass(session.avg_form_score)}`}>
              {session.avg_form_score != null ? `${Math.round(session.avg_form_score)}%` : '--'}
            </span>
          </div>
        </div>

        {/* 2. Sparkline Form Score Trend Panel */}
        {session.form_score_trend && session.form_score_trend.length >= 2 && (
          <div className="bg-slate-900/20 border border-slate-900/80 rounded-2xl p-6 relative overflow-hidden">
            <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-4">
              Form Consistency Trend
            </h3>
            
            <div className="w-full flex justify-center py-2">
              <svg className="w-full h-24 max-w-lg" viewBox="0 0 500 80">
                {/* Baseline grid overlays */}
                <line x1="0" y1="10" x2="500" y2="10" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                <line x1="0" y1="40" x2="500" y2="40" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                <line x1="0" y1="70" x2="500" y2="70" className="stroke-slate-900" strokeWidth="1" strokeDasharray="3" />
                
                {/* SVG glowing trend path */}
                <polyline
                  fill="none"
                  stroke="#84cc16"
                  strokeWidth="3.5"
                  points={drawTrendLine(session.form_score_trend)}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ filter: 'drop-shadow(0 0 4px rgba(132, 204, 22, 0.4))' }}
                />
              </svg>
            </div>
            <div className="flex justify-between text-[10px] font-bold text-slate-500 uppercase px-2 mt-2">
              <span>Start</span>
              <span>Form Score (%)</span>
              <span>Finish</span>
            </div>
          </div>
        )}

        {/* 3. Detailed Set Breakdown Table */}
        <div className="bg-slate-900/20 border border-slate-900/80 rounded-2xl overflow-hidden">
          <div className="p-6 border-b border-slate-900">
            <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase">
              Set Breakdown Logs
            </h3>
          </div>
          
          {session.sets && session.sets.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-900 text-[10px] font-bold text-slate-500 uppercase tracking-widest bg-slate-950/40">
                    <th className="py-4 px-6">Set</th>
                    <th className="py-4 px-6">Exercise</th>
                    <th className="py-4 px-6 text-center">Reps</th>
                    <th className="py-4 px-6 text-right">Avg Form Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/40 text-xs">
                  {session.sets.map((set) => (
                    <tr key={set.id} className="hover:bg-slate-900/10 transition-colors duration-200">
                      <td className="py-4 px-6 font-mono font-bold text-slate-400">#{set.set_number}</td>
                      <td className="py-4 px-6 font-semibold text-slate-100 uppercase tracking-wide">
                        {set.exercise.replace('_', ' ').replace('-', ' ')}
                      </td>
                      <td className="py-4 px-6 font-bold text-center text-white">{set.reps}</td>
                      <td className={`py-4 px-6 text-right ${getScoreColorClass(set.avg_form_score)}`}>
                        {set.avg_form_score != null ? `${Math.round(set.avg_form_score)}%` : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500 uppercase">
              No complete set logs recorded for this session.
            </div>
          )}
        </div>

        {/* 4. Exercise Calorie Breakdown Chart */}
        {session.calorie_segments && session.calorie_segments.length > 0 && (
          <div className="bg-slate-900/20 border border-slate-900/80 rounded-2xl p-6">
            <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-5">
              Calorie Breakdown per Exercise
            </h3>

            <div className="space-y-4">
              {session.calorie_segments.map((seg, idx) => {
                const cVal = seg.calories ?? 0
                const percent = Math.max(5, (cVal / maxCalories) * 100)

                return (
                  <div key={idx} className="flex flex-col space-y-1.5">
                    <div className="flex justify-between items-baseline text-xs">
                      <span className="font-semibold text-slate-200 uppercase tracking-wide">
                        {seg.exercise.replace('_', ' ').replace('-', ' ')}
                      </span>
                      <div className="space-x-2 font-mono text-[11px]">
                        <span className="text-slate-400">{formatDuration(seg.duration_seconds)}</span>
                        <span className="font-bold text-rose-400">{cVal.toFixed(1)} Kcal</span>
                      </div>
                    </div>
                    
                    {/* Custom glass bar */}
                    <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-rose-600 to-rose-400 rounded-full transition-all duration-700"
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Footer Control Buttons */}
        <div className="flex justify-center pt-4">
          <button
            onClick={onClose}
            className="px-8 py-4 bg-lime-500 hover:bg-lime-400 text-slate-950 font-black text-sm uppercase tracking-widest rounded-xl transition-all duration-300 shadow-[0_10px_30px_rgba(132,204,22,0.2)] hover:shadow-[0_12px_35px_rgba(132,204,22,0.3)]"
          >
            Acknowledge & Close
          </button>
        </div>
      </div>
    </div>
  )
}
