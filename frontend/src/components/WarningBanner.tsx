import React from 'react'

interface WarningBannerProps {
  warning: string | null
}

export const WarningBanner: React.FC<WarningBannerProps> = ({ warning }) => {
  if (!warning || warning.trim() === '') return null

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 w-11/12 max-w-md animate-bounce">
      {/* Container with bright amber border, translucent warning background, and blur */}
      <div className="flex items-center space-x-3 bg-amber-500/90 text-slate-950 px-4 py-3.5 rounded-xl shadow-[0_10px_30px_rgba(245,158,11,0.3)] backdrop-blur-md border border-amber-400 select-none">
        
        {/* Animated Caution Sign Icon */}
        <div className="flex-shrink-0 w-6 h-6 bg-slate-950/10 rounded-full flex items-center justify-center">
          <svg className="w-4 h-4 text-slate-950 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>

        {/* Warning Text */}
        <div className="flex-1 text-xs font-black tracking-wide uppercase font-sans">
          {warning}
        </div>

        {/* Decorative corner notch */}
        <div className="w-1.5 h-1.5 bg-slate-950 rotate-45 transform translate-x-1" />
      </div>
    </div>
  )
}
