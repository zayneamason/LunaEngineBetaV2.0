import { useState, useEffect, useRef, useCallback } from 'react';

const CAPTURE_INTERVAL = 2000; // ms between frames
const MAX_ATTEMPTS = 15;       // ~30s of scanning before giving up
const ENROLL_CAPTURES = 10;    // frames to capture during enrollment
const API_URL = 'http://127.0.0.1:8000/identity/recognize';
const ENROLL_URL = 'http://127.0.0.1:8000/identity/enroll';
const RESET_URL = 'http://127.0.0.1:8000/identity/reset';
const BYPASS_URL = 'http://127.0.0.1:8000/identity/bypass';
const BYPASS_OFF_URL = 'http://127.0.0.1:8000/identity/bypass-off';

/**
 * useIdentity — WebSocket hook for FaceID identity state + browser camera capture.
 *
 * States: idle → requesting → scanning → recognized
 *         idle → requesting → enrolling → enrolled → scanning → recognized
 *         (reset) → enrolling
 */
export function useIdentity() {
  const [identity, setIdentity] = useState(null);
  const [connected, setConnected] = useState(false);
  const [captureState, setCaptureState] = useState('idle');
  // 'idle' | 'requesting' | 'scanning' | 'recognized' | 'denied' | 'failed'
  // + 'enrolling' | 'enrolled' | 'resetting'
  const [bboxes, setBboxes] = useState([]);
  const [enrollCount, setEnrollCount] = useState(0);

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const streamRef = useRef(null);
  const videoRef = useRef(null);
  const captureTimerRef = useRef(null);
  const attemptCountRef = useRef(0);

  // ---- WebSocket connection ----

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//127.0.0.1:8000/ws/identity`);

    ws.onopen = () => {
      setConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'identity_update' && msg.data) {
          setIdentity(msg.data);
          if (msg.data.is_present && captureState === 'scanning') {
            stopCapture();
            setCaptureState('recognized');
          }
        }
      } catch (e) {
        console.warn('Identity WS parse error:', e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
      stopCapture();
    };
  }, [connect]);

  // ---- Camera helpers ----

  const cameraAvailable = typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia;

  const stopCapture = useCallback(() => {
    if (captureTimerRef.current) {
      clearInterval(captureTimerRef.current);
      captureTimerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current = null;
    }
    attemptCountRef.current = 0;
  }, []);

  const startCamera = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
    });
    streamRef.current = stream;

    const video = document.createElement('video');
    video.srcObject = stream;
    video.setAttribute('playsinline', '');
    video.muted = true;
    await video.play();
    videoRef.current = video;
  }, []);

  const extractFrame = useCallback(() => {
    if (!videoRef.current) return null;
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, 320, 240);
    return canvas.toDataURL('image/jpeg', 0.7);
  }, []);

  // ---- Recognition (existing) ----

  const startRecognition = useCallback(async () => {
    if (!cameraAvailable) {
      setCaptureState('denied');
      return;
    }

    setCaptureState('requesting');
    attemptCountRef.current = 0;

    try {
      await startCamera();
      setCaptureState('scanning');

      captureTimerRef.current = setInterval(async () => {
        if (!videoRef.current || !streamRef.current) return;

        attemptCountRef.current += 1;
        if (attemptCountRef.current > MAX_ATTEMPTS) {
          stopCapture();
          setCaptureState('failed');
          return;
        }

        const frameData = extractFrame();
        if (!frameData) return;

        try {
          const res = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ frame: frameData, source: 'browser' }),
          });
          const data = await res.json();

          setBboxes(data.bboxes || []);

          if (data.is_present) {
            stopCapture();
            setCaptureState('recognized');
            setBboxes([]);
            setIdentity({
              is_present: true,
              entity_id: data.entity_id,
              entity_name: data.entity_name,
              confidence: data.confidence,
              luna_tier: data.luna_tier,
              dataroom_tier: data.dataroom_tier,
            });
          }
        } catch (e) {
          console.warn('FaceID capture error:', e);
        }
      }, CAPTURE_INTERVAL);

    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCaptureState('denied');
      } else {
        console.error('Camera error:', err);
        setCaptureState('failed');
      }
    }
  }, [cameraAvailable, stopCapture, startCamera, extractFrame]);

  const stopRecognition = useCallback(() => {
    stopCapture();
    setCaptureState('idle');
    setBboxes([]);
  }, [stopCapture]);

  // ---- Reset ----

  const resetIdentity = useCallback(async (pin = '') => {
    setCaptureState('resetting');
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      const res = await fetch(RESET_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const data = await res.json();
      if (!data.reset) {
        setCaptureState('idle');
        return { success: false, error: data.error || 'Reset failed' };
      }
      setIdentity(null);
      setCaptureState('idle');
      return { success: true, deleted: data.deleted };
    } catch (e) {
      setCaptureState('idle');
      const msg = e.name === 'AbortError' ? 'Reset timed out' : e.message;
      return { success: false, error: msg };
    }
  }, []);

  // ---- Bypass (skip FaceID) ----

  const [isBypassed, setIsBypassed] = useState(false);

  const bypassIdentity = useCallback(async () => {
    try {
      const res = await fetch(BYPASS_URL, { method: 'POST' });
      const data = await res.json();
      if (data.bypassed) {
        setIsBypassed(true);
        setCaptureState('recognized');
        setIdentity({
          is_present: true,
          entity_id: data.entity_id,
          entity_name: data.entity_name,
          luna_tier: data.luna_tier,
          dataroom_tier: data.dataroom_tier,
          bypass: true,
        });
        return { success: true };
      }
      return { success: false, error: data.detail || 'Bypass failed' };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }, []);

  const revokeBypass = useCallback(async () => {
    try {
      const res = await fetch(BYPASS_OFF_URL, { method: 'POST' });
      const data = await res.json();
      if (data.bypassed === false) {
        setIsBypassed(false);
        setIdentity(null);
        setCaptureState('idle');
        return { success: true };
      }
      return { success: false, error: data.detail || 'Revoke failed' };
    } catch (e) {
      return { success: false, error: e.message };
    }
  }, []);

  // ---- Enrollment ----

  const startEnrollment = useCallback(async (entityName, pin = '') => {
    if (!cameraAvailable) {
      setCaptureState('denied');
      return { success: false, error: 'Camera not available' };
    }

    // First, reset existing data
    setCaptureState('resetting');
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      const resetRes = await fetch(RESET_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      const resetData = await resetRes.json();
      if (!resetData.reset) {
        setCaptureState('idle');
        return { success: false, error: resetData.error || 'Reset failed' };
      }
    } catch (e) {
      setCaptureState('idle');
      const msg = e.name === 'AbortError' ? 'Reset timed out' : e.message;
      return { success: false, error: msg };
    }

    // Start camera and enrollment
    setCaptureState('requesting');
    setEnrollCount(0);

    try {
      await startCamera();
      setCaptureState('enrolling');

      let captured = 0;
      captureTimerRef.current = setInterval(async () => {
        if (!videoRef.current || !streamRef.current) return;

        const frameData = extractFrame();
        if (!frameData) return;

        try {
          const res = await fetch(ENROLL_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ frame: frameData, entity_name: entityName }),
          });
          const data = await res.json();

          setBboxes(data.bboxes || []);

          if (data.enrolled) {
            captured++;
            setEnrollCount(captured);

            if (captured >= ENROLL_CAPTURES) {
              stopCapture();
              setCaptureState('enrolled');
              setBboxes([]);
              // Brief pause then switch to scanning to verify
              setTimeout(() => {
                startRecognition();
              }, 1500);
            }
          }
        } catch (e) {
          console.warn('Enrollment capture error:', e);
        }
      }, CAPTURE_INTERVAL);

    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setCaptureState('denied');
      } else {
        console.error('Camera error:', err);
        setCaptureState('failed');
      }
    }
  }, [cameraAvailable, stopCapture, startCamera, extractFrame, startRecognition]);

  return {
    // Identity state
    identity,
    isPresent: identity?.is_present ?? false,
    entityName: identity?.entity_name ?? null,
    lunaTier: identity?.luna_tier ?? 'unknown',
    confidence: identity?.confidence ?? 0,
    connected,

    // Camera capture
    captureState,
    startRecognition,
    stopRecognition,
    cameraAvailable,

    // Reset + enrollment
    resetIdentity,
    startEnrollment,
    enrollCount,

    // Bypass
    bypassIdentity,
    revokeBypass,
    isBypassed,

    // Preview data
    videoRef,
    streamRef,
    bboxes,
  };
}
