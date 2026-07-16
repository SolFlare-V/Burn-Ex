import React, { useEffect, useRef } from 'react'
import { Landmark } from '../hooks/usePoseSession'

interface CameraCanvasProps {
  landmarks: Landmark[]
  videoRef: React.RefObject<HTMLVideoElement | null>
  width: number
  height: number
}

// MediaPipe Pose connection map (skeleton lines)
// Format: [start_index, end_index]
const POSE_CONNECTIONS: [number, number][] = [
  // Shoulders and Torso
  [11, 12], // Left shoulder to right shoulder
  [11, 23], // Left shoulder to left hip
  [12, 24], // Right shoulder to right hip
  [23, 24], // Left hip to right hip

  // Left Arm
  [11, 13], // Left shoulder to left elbow
  [13, 15], // Left elbow to left wrist
  [15, 17], // Left wrist to left pinky
  [15, 19], // Left wrist to left index
  [15, 21], // Left wrist to left thumb
  [17, 19], // Hand boundary

  // Right Arm
  [12, 14], // Right shoulder to right elbow
  [14, 16], // Right elbow to right wrist
  [16, 18], // Right wrist to right pinky
  [16, 20], // Right wrist to right index
  [16, 22], // Right wrist to right thumb
  [18, 20], // Hand boundary

  // Left Leg & Foot
  [23, 25], // Left hip to left knee
  [25, 27], // Left knee to left ankle
  [27, 29], // Left ankle to left heel
  [29, 31], // Left heel to left toe
  [27, 31], // Left ankle to left toe

  // Right Leg & Foot
  [24, 26], // Right hip to right knee
  [26, 28], // Right knee to right ankle
  [28, 30], // Right ankle to right heel
  [30, 32], // Right heel to right toe
  [28, 32], // Right ankle to right toe
]

export const CameraCanvas: React.FC<CameraCanvasProps> = ({
  landmarks,
  videoRef,
  width,
  height,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (videoRef.current) {}
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear previous drawing
    ctx.clearRect(0, 0, width, height)

    // If there are no landmarks, stop drawing
    if (!landmarks || landmarks.length === 0) return

    // Draw Skeleton Connections
    ctx.lineWidth = 3
    ctx.strokeStyle = 'rgba(132, 204, 22, 0.7)' // Neon lime green connection line
    ctx.shadowBlur = 4
    ctx.shadowColor = 'rgba(132, 204, 22, 0.5)'

    POSE_CONNECTIONS.forEach(([startIdx, endIdx]) => {
      // Find landmarks by their ID
      const startLm = landmarks.find(lm => lm.id === startIdx)
      const endLm = landmarks.find(lm => lm.id === endIdx)

      // Only draw if both points exist and have visibility >= 0.5 (REQ-1.3)
      if (startLm && endLm && startLm.visibility >= 0.5 && endLm.visibility >= 0.5) {
        const x1 = startLm.x * width
        const y1 = startLm.y * height
        const x2 = endLm.x * width
        const y2 = endLm.y * height

        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }
    })

    // Draw Landmark Joints (dots)
    landmarks.forEach((lm) => {
      // Ignore low confidence landmarks (REQ-1.3)
      if (lm.visibility < 0.5) return

      const cx = lm.x * width
      const cy = lm.y * height

      // Distinguish key joints (shoulders, elbows, wrists, hips, knees, ankles) from details (face, fingers)
      const isCoreJoint = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28].includes(lm.id)

      ctx.beginPath()
      if (isCoreJoint) {
        // Draw large glowing dot for core joints
        ctx.arc(cx, cy, 6, 0, 2 * Math.PI)
        ctx.fillStyle = '#84cc16' // Neon Lime Green
        ctx.shadowBlur = 10
        ctx.shadowColor = '#84cc16'
      } else {
        // Draw smaller, subtle dot for peripheral keypoints (face, fingers)
        ctx.arc(cx, cy, 3, 0, 2 * Math.PI)
        ctx.fillStyle = '#60a5fa' // Bright Blue
        ctx.shadowBlur = 5
        ctx.shadowColor = '#60a5fa'
      }
      ctx.fill()
    })
  }, [landmarks, width, height])

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="absolute top-0 left-0 w-full h-full pointer-events-none z-10 scale-x-[-1]"
      style={{ mixBlendMode: 'screen' }}
    />
  )
}
