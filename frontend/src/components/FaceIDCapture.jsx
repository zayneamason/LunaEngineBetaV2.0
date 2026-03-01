import React, { useRef, useEffect, useState } from 'react';

/**
 * FaceIDCapture — Camera capture with live preview + bounding box overlay.
 *
 * Shows a small camera preview when scanning/enrolling.
 * Includes a Reset button that wipes embeddings and re-enrolls from browser camera.
 */

const PREVIEW_W = 160;
const PREVIEW_H = 120;

const FaceIDCapture = ({
  captureState, onStart, onStop, onReset, onEnroll, onBypass,
  videoRef, bboxes = [], enrollCount = 0,
}) => {
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);
  const [showReset, setShowReset] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [resetError, setResetError] = useState('');

  // Safety timeout: if stuck in 'resetting' for >10s, auto-recover to idle
  useEffect(() => {
    if (captureState !== 'resetting') return;
    const timer = setTimeout(() => {
      if (onStop) onStop();
    }, 10000);
    return () => clearTimeout(timer);
  }, [captureState, onStop]);

  // Draw video + bounding boxes onto canvas
  const isLive = captureState === 'scanning' || captureState === 'enrolling';

  useEffect(() => {
    if (!isLive || !videoRef?.current || !canvasRef.current) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const video = videoRef.current;

    const draw = () => {
      if (!video || video.readyState < 2) {
        animFrameRef.current = requestAnimationFrame(draw);
        return;
      }

      ctx.save();
      ctx.translate(PREVIEW_W, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, PREVIEW_W, PREVIEW_H);
      ctx.restore();

      const scaleX = PREVIEW_W / (video.videoWidth || 320);
      const scaleY = PREVIEW_H / (video.videoHeight || 240);

      for (const box of bboxes) {
        const bx = PREVIEW_W - (box.x * scaleX) - (box.w * scaleX);
        const by = box.y * scaleY;
        const bw = box.w * scaleX;
        const bh = box.h * scaleY;

        const color = captureState === 'enrolling' ? '#4ade80' : (box.confidence > 0.7 ? '#22d3ee' : '#fbbf24');
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(bx, by, bw, bh);

        ctx.fillStyle = color;
        ctx.font = '9px monospace';
        ctx.fillText(`${(box.confidence * 100).toFixed(0)}%`, bx + 2, by - 3);
      }

      animFrameRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isLive, captureState, videoRef, bboxes]);

  if (captureState === 'recognized') return null;

  const handleResetAndEnroll = async () => {
    setResetError('');
    if (onEnroll) {
      const result = await onEnroll(pinInput);
      if (result && !result.success) {
        setResetError(result.error || 'Reset failed');
        setShowReset(true);
        return;
      }
    }
    setShowReset(false);
    setPinInput('');
  };

  return (
    <div className="flex items-center gap-2">
      {/* Idle: Identify + Bypass + Reset buttons */}
      {captureState === 'idle' && (
        <>
          <button
            onClick={onStart}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border transition-all
              bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-white/20 hover:text-white/60"
            title="Identify yourself"
          >
            <CameraIcon />
            <span>Identify</span>
          </button>

          <button
            onClick={onBypass}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border transition-all
              bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-emerald-500/30 hover:text-emerald-400/80"
            title="Bypass FaceID — grant admin access without camera"
          >
            <BypassIcon />
            <span>Pass</span>
          </button>

          <div className="relative">
            <button
              onClick={() => setShowReset(!showReset)}
              className="flex items-center gap-1 px-2 py-1.5 text-xs rounded border transition-all
                bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-red-500/30 hover:text-red-400/80"
              title="Reset FaceID and re-enroll"
            >
              <ResetIcon />
            </button>

            {/* Reset dropdown */}
            {showReset && (
              <div className="absolute right-0 top-full mt-1 w-56 p-3 rounded border border-kozmo-border bg-kozmo-surface shadow-xl z-50"
                style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.6)' }}>
                <p className="text-[10px] text-white/50 mb-2">Reset face data & re-enroll</p>
                <input
                  type="password"
                  maxLength={4}
                  placeholder="PIN (if set)"
                  value={pinInput}
                  onChange={(e) => setPinInput(e.target.value.replace(/\D/g, ''))}
                  className="w-full px-2 py-1.5 mb-2 text-xs rounded border border-kozmo-border bg-kozmo-bg text-white/80 placeholder-white/30 focus:outline-none focus:border-red-500/50"
                />
                {resetError && <p className="text-[10px] text-red-400 mb-2">{resetError}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={handleResetAndEnroll}
                    className="flex-1 px-2 py-1.5 text-xs rounded border border-red-500/40 text-red-400 hover:bg-red-500/10 transition-all"
                  >
                    Reset & Enroll
                  </button>
                  <button
                    onClick={() => { setShowReset(false); setPinInput(''); setResetError(''); }}
                    className="px-2 py-1.5 text-xs rounded border border-kozmo-border text-kozmo-muted hover:text-white/60 transition-all"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {captureState === 'requesting' && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-white/40">
          <CameraIcon />
          <span>Allow camera...</span>
        </div>
      )}

      {captureState === 'resetting' && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-amber-400/80">
          <ResetIcon />
          <span>Resetting...</span>
          <button
            onClick={onStop}
            className="ml-1 px-1.5 py-0.5 text-[10px] rounded border border-white/10 text-white/30 hover:text-white/60 hover:border-white/20 transition-all"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Live preview for scanning or enrolling */}
      {isLive && (
        <div className="relative flex items-center gap-2">
          <div
            className={`relative rounded overflow-hidden border ${
              captureState === 'enrolling' ? 'border-green-500/40' : 'border-cyan-500/30'
            }`}
            style={{
              width: PREVIEW_W,
              height: PREVIEW_H,
              boxShadow: captureState === 'enrolling'
                ? '0 0 12px rgba(74,222,128,0.15)'
                : '0 0 12px rgba(34,211,238,0.15)',
            }}
          >
            <canvas
              ref={canvasRef}
              width={PREVIEW_W}
              height={PREVIEW_H}
              className="block"
            />
            {/* Status indicator */}
            <div className="absolute top-1 left-1 flex items-center gap-1 px-1.5 py-0.5 rounded-sm"
              style={{ background: 'rgba(0,0,0,0.6)' }}>
              {captureState === 'enrolling' ? (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-[9px] text-green-400">ENROLLING {enrollCount}/10</span>
                </>
              ) : (
                <>
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="text-[9px] text-cyan-400">SCANNING</span>
                </>
              )}
            </div>

            {/* Enrollment progress bar */}
            {captureState === 'enrolling' && (
              <div className="absolute bottom-0 left-0 right-0 h-1 bg-black/40">
                <div
                  className="h-full bg-green-400 transition-all duration-300"
                  style={{ width: `${(enrollCount / 10) * 100}%` }}
                />
              </div>
            )}
          </div>

          <button
            onClick={onStop}
            className="px-2 py-1 text-[10px] rounded border border-white/10 text-white/40 hover:text-white/60 hover:border-white/20 transition-all"
          >
            ✕
          </button>
        </div>
      )}

      {/* Enrollment complete — brief success state */}
      {captureState === 'enrolled' && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-green-400">
          <span>Enrolled! Verifying...</span>
        </div>
      )}

      {captureState === 'denied' && (
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400/80">
          <CameraIcon />
          <span>Camera denied</span>
        </div>
      )}

      {captureState === 'failed' && (
        <button
          onClick={onStart}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded border transition-all
            border-amber-500/30 text-amber-400/80 hover:border-amber-500/50"
        >
          <CameraIcon />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};

const CameraIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </svg>
);

const ResetIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 4v6h6" />
    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
  </svg>
);

const BypassIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 9.9-1" />
  </svg>
);

export default FaceIDCapture;
