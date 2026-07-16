import React from 'react'
import {
  useProgressCalories,
  useProgressForm,
  useStreaks,
  useGoalsProgress,
} from '../lib/queryClient'

// ---------------------------------------------------------------------------
// Subcomponent 1: StreakWidget
// ---------------------------------------------------------------------------
interface StreakWidgetProps {
  userId: number
}

export const StreakWidget: React.FC<StreakWidgetProps> = ({ userId }) => {
  const { data: streak, isLoading, error } = useStreaks(userId)

  if (isLoading) return <div className="h-28 bg-slate-900/30 border border-slate-900 rounded-2xl animate-pulse" />
  if (error || !streak) return null

  return (
    <div className="flex items-center justify-between p-5 bg-slate-900/40 border border-slate-900 rounded-2xl relative overflow-hidden group hover:border-orange-500/30 transition-all duration-300">
      {/* Decorative orange background glow */}
      <div className="absolute -top-12 -right-12 w-28 h-28 bg-orange-500/5 rounded-full blur-2xl pointer-events-none" />

      <div className="flex flex-col">
        <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Activity Streak</span>
        <div className="flex items-baseline space-x-1.5 mt-2">
          <span className="text-3xl font-black text-white">{streak.current}</span>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Days</span>
        </div>
        <span className="text-[9px] font-bold text-orange-400 uppercase mt-1">
          Best Streak: {streak.best} Days
        </span>
      </div>

      {/* Flame Icon with neon orange glow */}
      <div className="w-14 h-14 bg-orange-500/10 border border-orange-500/20 rounded-2xl flex items-center justify-center shadow-[0_0_15px_rgba(249,115,22,0.1)]">
        <svg className="w-8 h-8 text-orange-500 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 2: GoalsWidget
// ---------------------------------------------------------------------------
interface GoalsWidgetProps {
  userId: number
}

export const GoalsWidget: React.FC<GoalsWidgetProps> = ({ userId }) => {
  const { data: progressItems, isLoading, error } = useGoalsProgress(userId)

  if (isLoading) return <div className="h-36 bg-slate-900/30 border border-slate-900 rounded-2xl animate-pulse" />
  if (error || !progressItems || progressItems.length === 0) {
    return (
      <div className="p-5 bg-slate-900/40 border border-slate-900 rounded-2xl flex flex-col justify-center text-center">
        <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Goals Tracker</span>
        <span className="text-slate-500 text-xs mt-3 uppercase">No active calorie goals configured.</span>
      </div>
    )
  }

  return (
    <div className="p-5 bg-slate-900/40 border border-slate-900 rounded-2xl relative overflow-hidden flex flex-col justify-between h-full">
      <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-lime-500/5 to-transparent rounded-full blur-2xl pointer-events-none" />
      
      <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase mb-4 block">
        Active Calorie Goals
      </span>

      <div className="space-y-4">
        {progressItems.map((item, idx) => {
          const target = item.target_calories
          const achieved = item.achieved_calories
          const ratio = target > 0 ? achieved / target : 0
          const percent = Math.min(Math.round(ratio * 100), 100)
          
          return (
            <div key={idx} className="flex flex-col space-y-1">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-slate-300 uppercase tracking-wider">{item.type} Goal</span>
                <span className="font-mono font-bold text-slate-400">
                  {achieved.toFixed(0)} / {target.toFixed(0)} <span className="text-[10px] text-slate-600">Kcal</span>
                </span>
              </div>
              
              {/* Progress bar container */}
              <div className="flex items-center space-x-3">
                <div className="flex-1 h-2 bg-slate-950 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      item.achieved 
                        ? 'bg-gradient-to-r from-lime-600 to-lime-400' 
                        : 'bg-gradient-to-r from-blue-600 to-blue-400'
                    }`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
                
                {/* Goal Achieved Indicator (REQ-7.8) */}
                {item.achieved ? (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-black bg-lime-500/10 text-lime-400 border border-lime-500/25 uppercase tracking-widest animate-pulse">
                    Achieved
                  </span>
                ) : (
                  <span className="text-[10px] font-mono font-bold text-slate-600 w-8 text-right">
                    {percent}%
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 3: CalorieTimelineChart
// ---------------------------------------------------------------------------
interface CalorieTimelineChartProps {
  userId: number
}

export const CalorieTimelineChart: React.FC<CalorieTimelineChartProps> = ({ userId }) => {
  const { data: history, isLoading, error } = useProgressCalories(userId)

  if (isLoading) return <div className="h-64 bg-slate-900/30 border border-slate-900 rounded-2xl animate-pulse" />
  if (error) return <div className="h-64 bg-slate-900/40 border border-slate-900 rounded-2xl p-6 text-center text-xs text-rose-500">Failed to load calories timeline.</div>

  // Render safe empty state if timeline has no sessions logged
  if (!history || history.length === 0) {
    return (
      <div className="bg-slate-900/20 border border-slate-900 rounded-2xl p-6 flex flex-col justify-center items-center text-center h-64 select-none">
        <div className="w-10 h-10 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center mb-3">
          <svg className="w-5 h-5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h4 className="text-xs font-extrabold text-white uppercase mb-1">No Activity Data</h4>
        <p className="text-slate-500 text-[10px] max-w-xs uppercase leading-relaxed">
          Calorie timeline will populate once you complete workout sessions.
        </p>
      </div>
    )
  }

  // Find max calorie value for relative bar heights, ensuring we don't divide by 0
  const maxCaloriesRaw = Math.max(...history.map(d => d.calories))
  const maxCalories = maxCaloriesRaw <= 0 ? 1 : maxCaloriesRaw

  // Keep only the last 15 items for standard visual chart density in local viewport
  const displayHistory = history.slice(-15)

  return (
    <div className="bg-slate-900/20 border border-slate-900 rounded-2xl p-6 flex flex-col h-64">
      <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-6">
        Calorie Burn Timeline
      </h3>
      
      {/* Bars Layout */}
      <div className="flex-1 flex items-end justify-between space-x-1.5 h-full relative">
        {/* Horizontal gridlines */}
        <div className="absolute inset-x-0 top-0 h-[1px] bg-slate-950 border-t border-slate-900/60" />
        <div className="absolute inset-x-0 top-1/2 h-[1px] bg-slate-950 border-t border-slate-900/40" />

        {displayHistory.map((entry, idx) => {
          const ratio = entry.calories / maxCalories
          const heightPercent = Math.max(4, ratio * 85) // Cap height percentage to leave room for label
          
          return (
            <div key={idx} className="flex-1 flex flex-col items-center group relative h-full justify-end">
              
              {/* Tooltip on Hover */}
              <div className="absolute bottom-full mb-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300 z-10 pointer-events-none bg-slate-950 border border-slate-800 text-[9px] font-mono text-rose-400 px-1.5 py-0.5 rounded shadow-lg whitespace-nowrap">
                {entry.calories.toFixed(0)} Kcal
              </div>

              {/* Glowing vertical bar */}
              <div
                className="w-full bg-gradient-to-t from-rose-600 to-rose-400 rounded-t-sm group-hover:from-rose-500 group-hover:to-rose-300 transition-all duration-300 shadow-[0_0_10px_rgba(225,29,72,0.1)] group-hover:shadow-[0_0_15px_rgba(225,29,72,0.25)]"
                style={{ height: `${heightPercent}%` }}
              />

              {/* Day index label */}
              <span className="text-[8px] font-mono font-bold text-slate-600 mt-2 select-none uppercase">
                #{idx + 1}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 4: FormTrendChart
// ---------------------------------------------------------------------------
interface FormTrendChartProps {
  userId: number
}

export const FormTrendChart: React.FC<FormTrendChartProps> = ({ userId }) => {
  const { data: formTrends, isLoading, error } = useProgressForm(userId)

  if (isLoading) return <div className="h-64 bg-slate-900/30 border border-slate-900 rounded-2xl animate-pulse" />
  if (error) return <div className="h-64 bg-slate-900/40 border border-slate-900 rounded-2xl p-6 text-center text-xs text-rose-500">Failed to load form trends.</div>

  // Render safe empty state if trends are empty
  if (!formTrends || formTrends.length === 0) {
    return (
      <div className="bg-slate-900/20 border border-slate-900 rounded-2xl p-6 flex flex-col justify-center items-center text-center h-64 select-none">
        <div className="w-10 h-10 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center mb-3">
          <svg className="w-5 h-5 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h4 className="text-xs font-extrabold text-white uppercase mb-1">No Form Trends</h4>
        <p className="text-slate-500 text-[10px] max-w-xs uppercase leading-relaxed">
          Form score trend lines will plot once you perform exercises.
        </p>
      </div>
    )
  }

  // Draw sparkline trend path
  const drawSparkline = (trend: number[]): string => {
    if (trend.length < 2) return ''
    const width = 120
    const height = 30
    return trend.map((score, idx) => {
      const x = (idx / (trend.length - 1)) * width
      const y = height - (score / 100) * height
      return `${x},${y}`
    }).join(' ')
  }

  return (
    <div className="bg-slate-900/20 border border-slate-900 rounded-2xl p-6 flex flex-col h-64 overflow-y-auto">
      <h3 className="text-xs font-bold tracking-wider text-slate-400 uppercase mb-4">
        Biomechanics Form Trends
      </h3>

      <div className="space-y-4 flex-1">
        {formTrends.map((trendData, idx) => {
          const exName = trendData.exercise.replace('_', ' ').replace('-', ' ').toUpperCase()
          const scores = trendData.trend || []
          const latestScore = scores.length > 0 ? scores[scores.length - 1] : null
          
          let scoreColor = 'text-slate-500'
          if (latestScore != null) {
            if (latestScore >= 80) scoreColor = 'text-emerald-400 font-bold'
            else if (latestScore >= 50) scoreColor = 'text-amber-400 font-bold'
            else scoreColor = 'text-rose-400 font-bold'
          }

          return (
            <div key={idx} className="flex items-center justify-between py-2 border-b border-slate-900/40 last:border-0">
              <div className="flex flex-col">
                <span className="text-[11px] font-bold text-slate-200 tracking-wide">{exName}</span>
                <span className={`text-[10px] mt-0.5 ${scoreColor}`}>
                  Latest: {latestScore != null ? `${Math.round(latestScore)}%` : '--'}
                </span>
              </div>

              {/* Sparkline chart */}
              {scores.length >= 2 ? (
                <svg className="w-28 h-8" viewBox="0 0 120 30">
                  <polyline
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2.5"
                    points={drawSparkline(scores)}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <span className="text-[9px] font-mono text-slate-650 uppercase">Not enough data</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component: ProgressDashboard
// ---------------------------------------------------------------------------
export const ProgressDashboard: React.FC = () => {
  // Defaulting to user_id=1 for local single-user system
  const defaultUserId = 1

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col items-center p-4 md:p-8 font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Container Header */}
      <div className="w-full max-w-4xl border-b border-slate-900 pb-4 mb-8">
        <h1 className="text-3xl font-black tracking-tight text-white uppercase">
          Performance Dashboard
        </h1>
        <p className="text-slate-400 text-xs mt-1">
          Review daily calorie milestones, activity consistency, and biomechanics accuracy trends.
        </p>
      </div>

      {/* Dashboard Widgets Layout */}
      <div className="w-full max-w-4xl space-y-6">
        
        {/* Top Widgets Grid (Streak & Goals progress) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <StreakWidget userId={defaultUserId} />
          <GoalsWidget userId={defaultUserId} />
        </div>

        {/* Charts Grid (Calorie timeline & Biomechanics trends) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CalorieTimelineChart userId={defaultUserId} />
          <FormTrendChart userId={defaultUserId} />
        </div>
      </div>
    </div>
  )
}
