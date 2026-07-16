import React from 'react'

export const CompatibilityWarningScreen: React.FC = () => {
  const hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  const hasWebSocket = 'WebSocket' in window

  return (
    <div className="min-h-screen w-full bg-gradient-to-tr from-gray-950 via-slate-950 to-black flex items-center justify-center p-4 selection:bg-amber-500 selection:text-black">
      {/* Amber/Orange background ambient glow */}
      <div className="absolute top-1/3 left-1/3 w-96 h-96 bg-amber-500/5 rounded-full blur-[120px] pointer-events-none" />
      
      {/* Warning Card Container */}
      <div className="relative w-full max-w-lg bg-gray-900/60 backdrop-blur-xl border border-gray-800/80 rounded-2xl p-8 shadow-[0_20px_50px_rgba(0,0,0,0.6)] text-center">
        <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent rounded-2xl pointer-events-none" />
        
        {/* Warning Icon */}
        <div className="flex flex-col items-center mb-6">
          <div className="w-16 h-16 bg-amber-500/10 border border-amber-500/30 rounded-full flex items-center justify-center shadow-[0_0_15px_rgba(245,158,11,0.15)] mb-4">
            <svg className="w-8 h-8 text-amber-400 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white mb-2 font-sans">
            Browser Compatibility Warning
          </h2>
          <p className="text-gray-400 text-sm max-w-md">
            Burn-Ex runs entirely in your browser using local machine vision and real-time sockets. Your current browser lacks support for critical features.
          </p>
        </div>

        {/* Feature Check Grid */}
        <div className="bg-gray-950/80 border border-gray-800 rounded-xl p-5 mb-6 text-left space-y-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Feature Checklist
          </h3>
          
          {/* Camera Stream check */}
          <div className="flex items-center justify-between py-1 border-b border-gray-900 last:border-0">
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-gray-200">Webcam Access (getUserMedia)</span>
              <span className="text-[11px] text-gray-500">Required to capture video frames for pose detection.</span>
            </div>
            <div className="flex items-center space-x-2">
              {hasGetUserMedia ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Supported
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  Missing
                </span>
              )}
            </div>
          </div>

          {/* WebSockets check */}
          <div className="flex items-center justify-between py-1 border-b border-gray-900 last:border-0">
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-gray-200">WebSocket Connections</span>
              <span className="text-[11px] text-gray-500">Required to stream video landmarks with sub-200ms latency.</span>
            </div>
            <div className="flex items-center space-x-2">
              {hasWebSocket ? (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Supported
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  Missing
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Recommendations */}
        <div className="space-y-4">
          <div className="text-xs text-gray-400 leading-relaxed bg-amber-500/5 border border-amber-500/10 rounded-xl p-4 text-left">
            <span className="font-semibold text-amber-400 block mb-1">Recommended Action:</span>
            Please open this application in a modern browser that supports these features, such as:
            <ul className="list-disc pl-4 mt-2 space-y-1 text-gray-300">
              <li>Google Chrome (90+)</li>
              <li>Mozilla Firefox (88+)</li>
              <li>Apple Safari (15+)</li>
              <li>Microsoft Edge (90+)</li>
            </ul>
          </div>

          <div className="text-[11px] text-gray-500">
            Note: If you are accessing this application on a mobile device, make sure your mobile browser has permissions to access the camera and that you are loading the site from a local network IP address.
          </div>
        </div>
      </div>
    </div>
  )
}
