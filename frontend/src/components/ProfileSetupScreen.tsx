import React, { useState } from 'react'

interface ProfileSetupScreenProps {
  onProfileSaved: () => void
}

const API_BASE = `http://${window.location.hostname}:8766`

export const ProfileSetupScreen: React.FC<ProfileSetupScreenProps> = ({ onProfileSaved }) => {
  const [name, setName] = useState('')
  const [weight, setWeight] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)

    // Local validation
    const parsedWeight = parseFloat(weight)
    if (isNaN(parsedWeight) || parsedWeight < 20 || parsedWeight > 300) {
      setErrorMsg('Weight must be a positive number between 20 kg and 300 kg.')
      return
    }

    setIsSubmitting(true)

    try {
      const response = await fetch(`${API_BASE}/api/v1/user`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name.trim() || null,
          weight_kg: parsedWeight,
        }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        const errorDetail = errData?.detail
        
        if (errorDetail && typeof errorDetail === 'object') {
          // Handle backend custom exception format: {"detail": {"code": "INVALID_WEIGHT", "message": "..."}}
          if (errorDetail.code === 'INVALID_WEIGHT') {
            setErrorMsg(errorDetail.message || 'Invalid weight value.')
          } else if (errorDetail.code === 'WEIGHT_LOCKED_DURING_SESSION') {
            setErrorMsg(errorDetail.message || 'Weight cannot be updated while a workout session is active.')
          } else {
            setErrorMsg(errorDetail.message || `Error: ${response.statusText}`)
          }
        } else if (typeof errorDetail === 'string') {
          setErrorMsg(errorDetail)
        } else {
          setErrorMsg(`Failed to save profile (HTTP ${response.status})`)
        }
        setIsSubmitting(false)
        return
      }

      setIsSubmitting(false)
      onProfileSaved()
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Network error. Please make sure the backend is running.')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-tr from-gray-950 via-slate-900 to-black flex items-center justify-center p-4 selection:bg-lime-500 selection:text-black">
      {/* Glow effects in background */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-lime-500/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-[120px] pointer-events-none" />

      {/* Profile Card Container */}
      <div className="relative w-full max-w-md bg-gray-900/60 backdrop-blur-xl border border-gray-800/80 rounded-2xl p-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
        <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent rounded-2xl pointer-events-none" />
        
        {/* Logo/Icon Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-16 h-16 bg-lime-500/10 border border-lime-500/30 rounded-full flex items-center justify-center shadow-[0_0_15px_rgba(132,204,22,0.15)] mb-4">
            {/* Inline SVG scale/weight icon */}
            <svg className="w-8 h-8 text-lime-400 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
            </svg>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white mb-2 font-sans">
            Welcome to <span className="text-lime-400 font-extrabold">Burn-Ex</span>
          </h2>
          <p className="text-gray-400 text-sm">
            AI-powered fitness analytics. Set up your profile to enable MET-based calorie calculations.
          </p>
        </div>

        {/* Validation Alert */}
        {errorMsg && (
          <div className="flex items-start space-x-3 bg-red-950/40 border border-red-900/60 text-red-200 rounded-xl p-4 mb-6 text-sm">
            <svg className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="leading-snug">{errorMsg}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Display Name Input */}
          <div className="space-y-2">
            <label htmlFor="name-input" className="block text-xs font-semibold uppercase tracking-wider text-gray-400">
              Display Name <span className="text-gray-600 font-normal">(Optional)</span>
            </label>
            <div className="relative rounded-lg shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <input
                id="name-input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                className="block w-full pl-10 pr-3 py-3 border border-gray-800 rounded-lg bg-gray-950 text-white placeholder-gray-600 text-sm transition-all focus:border-lime-500 focus:ring-1 focus:ring-lime-500 focus:outline-none"
                disabled={isSubmitting}
                maxLength={40}
              />
            </div>
          </div>

          {/* Weight Input */}
          <div className="space-y-2">
            <label htmlFor="weight-input" className="block text-xs font-semibold uppercase tracking-wider text-gray-400">
              Weight <span className="text-lime-400">*</span>
            </label>
            <div className="relative rounded-lg shadow-sm">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20 12H4" />
                </svg>
              </div>
              <input
                id="weight-input"
                type="number"
                step="0.1"
                min="20"
                max="300"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="Enter weight in kg (e.g. 72.5)"
                className="block w-full pl-10 pr-12 py-3 border border-gray-800 rounded-lg bg-gray-950 text-white placeholder-gray-600 text-sm transition-all focus:border-lime-500 focus:ring-1 focus:ring-lime-500 focus:outline-none"
                disabled={isSubmitting}
                required
              />
              <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none">
                <span className="text-gray-500 text-sm font-semibold">kg</span>
              </div>
            </div>
            <p className="text-[10px] text-gray-500 leading-normal">
              Acceptable range is 20 kg to 300 kg. This weight is saved locally on your machine.
            </p>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isSubmitting || !weight}
            className="w-full flex items-center justify-center bg-lime-500 hover:bg-lime-400 text-black font-bold py-3.5 px-4 rounded-lg text-sm uppercase tracking-wider shadow-[0_4px_20px_rgba(132,204,22,0.15)] hover:shadow-[0_4px_25px_rgba(132,204,22,0.3)] transition-all duration-300 transform active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none cursor-pointer"
          >
            {isSubmitting ? (
              <span className="flex items-center space-x-2">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-black" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving Profile...
              </span>
            ) : (
              'Save & Continue'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
