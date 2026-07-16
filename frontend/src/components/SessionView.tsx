import React, { useEffect, useRef, useState } from 'react'
import { useSessionLifecycle } from '../hooks/useSessionLifecycle'
import { CameraCanvas } from './CameraCanvas'
import { FeedbackPanel } from './FeedbackPanel'
import { WarningBanner } from './WarningBanner'

export const SessionView: React.FC = () => {
  const {
    status,
    sessionId,
    poseSession,
    startSession,
    endSession,
    error: lifecycleError,
  } = useSessionLifecycle()

  const { state: poseState } = poseSession

  const [isCameraLoading, setIsCameraLoading] = useState<boolean>(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0)

  // Refs for video, stream, and frame loops
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const offscreenCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const animationFrameIdRef = useRef<number | null>(null)
  const lastFrameTimeRef = useRef<number>(0)
  const timerIntervalRef = useRef<any>(null)

  // Timer counter for active workouts
  useEffect(() => {
    if (status === 'active') {
      setElapsedSeconds(0)
      timerIntervalRef.current = setInterval(() => {
        setElapsedSeconds(prev => prev + 1)
      }, 1000)
    } else {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
        timerIntervalRef.current = null
      }
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
    }
  }, [status])

  // Format seconds to MM:SS
  const formatTime = (secs: number): string => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0')
    const s = (secs % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  // Manage camera access and cleanup
  const startCamera = async () => {
    setCameraError(null)
    setIsCameraLoading(true)
    try {
      if (streamRef.current) {
        // Stop any old stream first
        streamRef.current.getTracks().forEach(track => track.stop())
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 15 },
        },
        audio: false,
      })

      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        // Wait for video metadata to load before playing
        videoRef.current.onloadedmetadata = () => {
          videoRef.current?.play().catch(err => {
            console.error('[SessionView] Video play error:', err)
          })
        }
      }
    } catch (err) {
      console.error('[SessionView] Webcam access failed:', err)
      setCameraError('Failed to access webcam. Please check permissions and try again.')
    } finally {
      setIsCameraLoading(false)
    }
  }

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }

  // Effect to boot/kill camera stream based on workout session active state
  useEffect(() => {
    if (status === 'active') {
      startCamera()
    } else {
      stopCamera()
    }

    return () => {
      stopCamera()
    }
  }, [status])

  // Frame processing loop using requestAnimationFrame (~15 FPS)
  useEffect(() => {
    if (status !== 'active' || !poseState.connected) {
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current)
        animationFrameIdRef.current = null
      }
      return
    }

    // Initialize offscreen canvas for frame capture
    if (!offscreenCanvasRef.current) {
      offscreenCanvasRef.current = document.createElement('canvas')
    }
    const canvas = offscreenCanvasRef.current
    const ctx = canvas.getContext('2d')

    const captureLoop = (timestamp: number) => {
      const video = videoRef.current
      if (video && video.readyState >= 2 && ctx) {
        // Control frame rate to ~15 FPS (66.7ms interval)
        const delta = timestamp - lastFrameTimeRef.current
        if (delta >= 1000 / 15) {
          lastFrameTimeRef.current = timestamp

          // Match canvas dimensions to the actual streaming video size
          canvas.width = video.videoWidth || 640
          canvas.height = video.videoHeight || 480

          // Render the video frame to canvas
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

          canvas.toBlob(
            blob => {
              if (blob) {
                poseSession.sendFrame(blob)
              }
            },
            'image/jpeg',
            0.8 // quality parameter matching latency retest standard
          )
        }
      }

      animationFrameIdRef.current = requestAnimationFrame(captureLoop)
    }

    // Start requestAnimationFrame loop
    lastFrameTimeRef.current = performance.now()
    animationFrameIdRef.current = requestAnimationFrame(captureLoop)

    return () => {
      if (animationFrameIdRef.current) {
        cancelAnimationFrame(animationFrameIdRef.current)
        animationFrameIdRef.current = null
      }
    }
  }, [status, poseState.connected])

  const handleStartWorkout = async () => {
    // Defaulting to user_id=1 for local single-user system
    await startSession(1)
  }

  const handleEndWorkout = async () => {
    await endSession()
  }

  // Dimensions for CameraCanvas (dynamically matches aspect-video standard)
  const canvasWidth = 640
  const canvasHeight = 480

  return (
    <div className="min-h-screen w-full bg-slate-950 text-slate-100 flex flex-col items-center p-4 md:p-8 font-sans selection:bg-lime-500 selection:text-black">
      
      {/* Session Title Header */}
      <div className="w-full max-w-6xl flex flex-col md:flex-row items-start md:items-center justify-between border-b border-slate-900 pb-4 mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-white uppercase font-sans">
            Workout Session Workspace
          </h1>
          <p className="text-slate-400 text-xs mt-1">
            Secure offline posture tracking and biomechanics calibration.
          </p>
        </div>

        {status === 'active' && (
          <div className="flex items-center space-x-4 bg-slate-900 border border-slate-800 px-4 py-2 rounded-xl">
            <div className="flex flex-col">
              <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Workout Time</span>
              <span className="text-lg font-mono font-black text-lime-400">
                {formatTime(elapsedSeconds)}
              </span>
            </div>
            <div className="h-6 w-[1px] bg-slate-800" />
            <div className="flex flex-col">
              <span className="text-[10px] font-bold tracking-widest text-slate-500 uppercase">Latency Status</span>
              <span className="text-xs font-mono font-bold text-blue-400 mt-1">
                {poseState.connected ? `${poseSession.lastMessage?.latency_ms ?? '--'} ms` : 'Disconnected'}
              </span>
            </div>
          </div>
        )}
      </div>

      {lifecycleError && (
        <div className="w-full max-w-6xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs px-4 py-3 rounded-xl mb-6">
          <span className="font-bold">Error:</span> {lifecycleError === 'WEIGHT_REQUIRED' 
            ? 'A profile setup is required. Please set your weight first.' 
            : `Failed to coordinate session lifecycle: ${lifecycleError}`}
        </div>
      )}

      {/* Main Grid View */}
      <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-5 gap-6">
        
        {/* Left Column: Video Feed (Spans 3 cols) */}
        <div className="lg:col-span-3 flex flex-col gap-4">
          <div className="relative aspect-video w-full bg-slate-900/60 border border-slate-900 rounded-2xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)]">
            
            {/* Mirror styled Video Element */}
            {status === 'active' && (
              <video
                ref={videoRef}
                className="w-full h-full object-cover scale-x-[-1]"
                playsInline
                muted
              />
            )}

            {/* Warning Banner overlay */}
            <WarningBanner warning={poseState.warning} />

            {/* Camera Landmark Overlay */}
            {status === 'active' && poseState.connected && (
              <CameraCanvas
                landmarks={poseState.landmarks}
                videoRef={videoRef}
                width={canvasWidth}
                height={canvasHeight}
              />
            )}

            {/* Idle and Error Overlay */}
            {status !== 'active' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-8 bg-slate-950/80 backdrop-blur-sm text-center">
                <div className="w-16 h-16 bg-slate-900 border border-slate-800 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </div>
                <h2 className="text-lg font-bold text-white mb-2 uppercase">Camera Feed Inactive</h2>
                <p className="text-slate-400 text-xs max-w-sm">
                  Start a workout session to initialize the local computer vision model and real-time biomechanics tracking.
                </p>
              </div>
            )}

            {isCameraLoading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/90 text-center">
                <div className="w-8 h-8 border-2 border-lime-500 border-t-transparent rounded-full animate-spin mb-4" />
                <span className="text-xs text-lime-400 font-bold uppercase tracking-wider">Accessing webcam...</span>
              </div>
            )}

            {cameraError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-6 bg-slate-950 text-center">
                <div className="text-rose-500 text-xs font-bold bg-rose-500/10 px-4 py-3 border border-rose-500/20 rounded-xl max-w-sm mb-4">
                  {cameraError}
                </div>
                <button
                  onClick={startCamera}
                  className="px-4 py-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-white rounded-xl text-xs font-bold uppercase tracking-wider"
                >
                  Retry Connection
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: HUD Feedback and Session Controls (Spans 2 cols) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          
          {/* Workout Config Panel (Only when idle) */}
          {status !== 'active' ? (
            <div className="w-full bg-slate-900/40 border border-slate-900 rounded-2xl p-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-lime-500/5 to-transparent rounded-full blur-2xl pointer-events-none" />
              
              <h2 className="text-sm font-extrabold text-slate-400 uppercase tracking-widest border-b border-slate-800 pb-3 mb-4 font-sans">
                Ready to Begin
              </h2>
              
              <p className="text-slate-400 text-xs leading-relaxed mb-6">
                Burn-Ex runs fully automated exercise classification. As you perform movements, the local neural network will classify your exercises (Squats, Push-Ups, Lunges, Bicep Curls, Shoulder Presses, or Planks) and display custom corrective cues and counts in real-time.
              </p>

              <button
                onClick={handleStartWorkout}
                className="w-full py-4 bg-lime-500 hover:bg-lime-400 text-slate-950 font-black text-sm uppercase tracking-widest rounded-xl transition-all duration-300 shadow-[0_10px_35px_rgba(132,204,22,0.25)] flex items-center justify-center space-x-2"
              >
                <span>Start Workout Session</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          ) : (
            // Feedback Panel active during workout
            <div className="flex flex-col gap-4">
              <FeedbackPanel
                exercise={poseState.exercise}
                confidence={poseSession.lastMessage?.latency_ms ? 0.95 : 0.0} // Fallback or mock confidence
                repCount={poseState.repCount}
                setNumber={poseState.setNumber}
                caloriesRunning={poseState.caloriesRunning}
                formScore={poseState.formScore}
                corrections={poseState.corrections}
                warning={poseState.warning}
              />

              <button
                onClick={handleEndWorkout}
                className="w-full py-4 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500 hover:text-white text-rose-400 font-extrabold text-sm uppercase tracking-widest rounded-xl transition-all duration-300 flex items-center justify-center space-x-2 shadow-[0_10px_30px_rgba(239,68,68,0.1)]"
              >
                {/* Stop Square SVG */}
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="1.5" />
                </svg>
                <span>End Workout Session</span>
              </button>
            </div>
          )}

          {/* Connection Stats (Active only) */}
          {status === 'active' && (
            <div className="bg-slate-950 border border-slate-900 rounded-2xl p-4 flex justify-between items-center text-[10px] font-mono text-slate-500 uppercase">
              <div className="flex items-center space-x-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${poseState.connected ? 'bg-emerald-500 animate-ping' : 'bg-rose-500'}`} />
                <span>Socket: {poseState.connected ? 'Connected' : 'Disconnected'}</span>
              </div>
              <span>Session ID: {sessionId?.slice(0, 8)}...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
