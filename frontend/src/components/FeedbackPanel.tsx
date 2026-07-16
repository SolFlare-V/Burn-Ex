import React from 'react'

// ---------------------------------------------------------------------------
// Subcomponent 1: ExerciseLabel
// ---------------------------------------------------------------------------
interface ExerciseLabelProps {
  exercise: string | null
  confidence: number // Normalized float 0.0 - 1.0 (or percentage)
}

export const ExerciseLabel: React.FC<ExerciseLabelProps> = ({ exercise, confidence }) => {
  const displayExercise = exercise
    ? exercise.replace('_', ' ').replace('-', ' ').toUpperCase()
    : 'DETECTING...'

  // Ensure confidence is represented as a percentage (e.g. 0.98 -> 98%)
  const percentage = confidence <= 1.0 ? Math.round(confidence * 100) : Math.round(confidence)
  const displayConfidence = exercise ? `${percentage}%` : '--'

  return (
    <div className="flex flex-col p-4 bg-slate-900/40 border border-slate-800/60 rounded-xl backdrop-blur-md relative overflow-hidden group hover:border-blue-500/30 transition-all duration-300">
      {/* Decorative top-right accent */}
      <div className="absolute top-0 right-0 w-8 h-[2px] bg-gradient-to-l from-blue-500 to-transparent" />
      <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Current Exercise</span>
      <div className="flex items-baseline justify-between mt-2">
        <span className="text-lg font-bold tracking-tight text-white group-hover:text-blue-400 transition-colors duration-300">
          {displayExercise}
        </span>
        <span className={`text-xs font-mono font-bold ${exercise ? 'text-blue-400' : 'text-slate-600'}`}>
          Conf: {displayConfidence}
        </span>
      </div>
      {/* Visual confidence indicator bar */}
      <div className="w-full h-1 bg-slate-950 rounded-full mt-3 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-500"
          style={{ width: exercise ? `${Math.min(percentage, 100)}%` : '0%' }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 2: RepCounter
// ---------------------------------------------------------------------------
interface RepCounterProps {
  repCount: number
  setNumber: number
}

export const RepCounter: React.FC<RepCounterProps> = ({ repCount, setNumber }) => {
  return (
    <div className="flex flex-col p-4 bg-slate-900/40 border border-slate-800/60 rounded-xl backdrop-blur-md relative overflow-hidden group hover:border-lime-500/30 transition-all duration-300">
      {/* Decorative top-right accent */}
      <div className="absolute top-0 right-0 w-8 h-[2px] bg-gradient-to-l from-lime-500 to-transparent" />
      
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Set Progress</span>
        <span className="text-xs font-mono font-bold text-lime-400 bg-lime-500/10 px-2 py-0.5 border border-lime-500/20 rounded-md">
          SET {setNumber}
        </span>
      </div>

      <div className="flex items-baseline justify-center my-2 select-none">
        <span className="text-5xl font-black font-sans tracking-tighter text-lime-400 drop-shadow-[0_0_15px_rgba(132,204,22,0.3)] animate-pulse">
          {repCount}
        </span>
        <span className="text-xs font-bold text-slate-400 ml-2 tracking-widest uppercase">Reps</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 3: CalorieDisplay
// ---------------------------------------------------------------------------
interface CalorieDisplayProps {
  caloriesRunning: number
}

export const CalorieDisplay: React.FC<CalorieDisplayProps> = ({ caloriesRunning }) => {
  return (
    <div className="flex flex-col p-4 bg-slate-900/40 border border-slate-800/60 rounded-xl backdrop-blur-md relative overflow-hidden group hover:border-rose-500/30 transition-all duration-300">
      {/* Decorative top-right accent */}
      <div className="absolute top-0 right-0 w-8 h-[2px] bg-gradient-to-l from-rose-500 to-transparent" />
      
      <div className="flex items-center space-x-1.5">
        {/* Flame SVG Icon */}
        <svg className="w-3.5 h-3.5 text-rose-500 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Burn Estimate</span>
      </div>

      <div className="flex items-baseline justify-center my-2 select-none">
        <span className="text-4xl font-extrabold tracking-tight text-white">
          {caloriesRunning.toFixed(1)}
        </span>
        <span className="text-xs font-bold text-rose-400 ml-1.5 tracking-wider uppercase">Kcal</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 4: FormScoreGauge
// ---------------------------------------------------------------------------
interface FormScoreGaugeProps {
  formScore: number // Integer 0 - 100
}

export const FormScoreGauge: React.FC<FormScoreGaugeProps> = ({ formScore }) => {
  // Determine color theme based on score quality
  let colorClass = 'text-rose-500 stroke-rose-500'
  let bgGlow = 'rgba(239,68,68,0.2)'
  let labelText = 'Poor'
  let labelColor = 'text-rose-400'

  if (formScore >= 80) {
    colorClass = 'text-emerald-400 stroke-emerald-400'
    bgGlow = 'rgba(52,211,153,0.2)'
    labelText = 'Excellent'
    labelColor = 'text-emerald-400'
  } else if (formScore >= 50) {
    colorClass = 'text-amber-400 stroke-amber-400'
    bgGlow = 'rgba(251,191,36,0.2)'
    labelText = 'Average'
    labelColor = 'text-amber-400'
  }

  // Circular progress dimensions
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (formScore / 100) * circumference

  return (
    <div className="flex items-center justify-between p-4 bg-slate-900/40 border border-slate-800/60 rounded-xl backdrop-blur-md relative overflow-hidden group hover:border-emerald-500/30 transition-all duration-300">
      {/* Decorative top-right accent */}
      <div className="absolute top-0 right-0 w-8 h-[2px] bg-gradient-to-l from-emerald-500 to-transparent" />

      <div className="flex flex-col">
        <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Form Quality</span>
        <span className="text-2xl font-black text-white mt-1">{formScore}</span>
        <span className={`text-[10px] font-bold uppercase tracking-wider mt-1.5 ${labelColor}`}>
          {labelText}
        </span>
      </div>

      {/* Circular Progress Meter */}
      <div className="relative w-16 h-16 flex items-center justify-center">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 64 64">
          {/* Background circle */}
          <circle cx="32" cy="32" r={radius} className="stroke-slate-800" strokeWidth="4.5" fill="transparent" />
          {/* Progress circle */}
          <circle
            cx="32"
            cy="32"
            r={radius}
            className={`transition-all duration-500 ease-out ${colorClass}`}
            strokeWidth="4.5"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            style={{ filter: `drop-shadow(0 0 6px ${bgGlow})` }}
          />
        </svg>
        <span className="absolute text-[11px] font-mono font-bold text-slate-300">%</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Subcomponent 5: CorrectionCues
// ---------------------------------------------------------------------------
interface CorrectionCuesProps {
  corrections: string[] // List of active correction alerts (max 2 items)
  warning: string | null // Active system warning ("Move into frame", "Exercise not recognized...", etc.)
}

export const CorrectionCues: React.FC<CorrectionCuesProps> = ({ corrections, warning }) => {
  const visibleCues = corrections.slice(0, 2)

  // Only show the positive "form looks solid" message when:
  //   - corrections is empty (no form violations), AND
  //   - warning is null/empty (not occluded / not unrecognised)
  // When a warning is active the sensor data is unreliable — showing
  // "Form looks solid" would be a false positive.
  const showPositive = visibleCues.length === 0 && !warning

  return (
    <div className="flex flex-col p-4 bg-slate-900/30 border border-slate-800/40 rounded-xl backdrop-blur-md col-span-1 sm:col-span-2">
      <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase mb-3">
        Active Correction Alerts
      </span>

      {showPositive ? (
        <div className="flex items-center space-x-2 py-3 px-4 bg-emerald-500/5 border border-emerald-500/10 rounded-lg text-emerald-400 text-xs font-semibold">
          {/* Clean Checkmark SVG */}
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Form looks solid. Keep it up!</span>
        </div>
      ) : visibleCues.length > 0 ? (
        <div className="space-y-2">
          {visibleCues.map((cue, idx) => (
            <div
              key={idx}
              className="flex items-center space-x-3 py-3 px-4 bg-rose-950/20 border border-rose-500/20 rounded-lg text-rose-300 text-xs font-semibold animate-headShake"
            >
              {/* Alert Warning SVG */}
              <svg className="w-4 h-4 text-rose-500 shrink-0 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{cue}</span>
            </div>
          ))}
        </div>
      ) : (
        // warning is active, corrections is empty — show a neutral "waiting" state
        <div className="flex items-center space-x-2 py-3 px-4 bg-slate-800/30 border border-slate-700/30 rounded-lg text-slate-500 text-xs font-semibold">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Waiting for clear frame...</span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component: FeedbackPanel
// ---------------------------------------------------------------------------
interface FeedbackPanelProps {
  exercise: string | null
  confidence: number
  repCount: number
  setNumber: number
  caloriesRunning: number
  formScore: number
  corrections: string[]
  warning: string | null  // passed through to CorrectionCues to suppress false positives
}

export const FeedbackPanel: React.FC<FeedbackPanelProps> = ({
  exercise,
  confidence,
  repCount,
  setNumber,
  caloriesRunning,
  formScore,
  corrections,
  warning,
}) => {
  return (
    <div className="w-full bg-slate-950/80 backdrop-blur-2xl border border-slate-900 rounded-2xl p-6 shadow-[0_30px_60px_rgba(0,0,0,0.8)] relative">
      {/* Decorative corner glows */}
      <div className="absolute top-0 left-0 w-32 h-32 bg-blue-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-32 h-32 bg-lime-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Panel header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-900 mb-6">
        <h3 className="text-sm font-extrabold tracking-wider text-slate-400 uppercase font-sans">
          Real-time Workout HUD
        </h3>
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-900 text-slate-400 border border-slate-800">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-ping" />
          Live Stream
        </span>
      </div>

      {/* Grid Layout of Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ExerciseLabel exercise={exercise} confidence={confidence} />
        <RepCounter repCount={repCount} setNumber={setNumber} />
        <CalorieDisplay caloriesRunning={caloriesRunning} />
        <FormScoreGauge formScore={formScore} />
        <CorrectionCues corrections={corrections} warning={warning} />
      </div>
    </div>
  )
}
