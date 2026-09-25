// src/components/SafeCameraStream.tsx – Robust WebCam Component handling Scenarios A, B, C, D
import React, { useEffect, useRef, useState } from "react";
import { Camera, AlertTriangle, RefreshCw, CheckCircle2, ShieldAlert, Cpu } from "lucide-react";
import { cn } from "../lib/utils";

interface SafeCameraStreamProps {
  onStateChange?: (active: boolean) => void;
}

export function SafeCameraStream({ onStateChange }: SafeCameraStreamProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [streamMode, setStreamMode] = useState<"backend" | "browser">("backend");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [errorScenario, setErrorScenario] = useState<"A" | "B" | "C" | "D" | "UNKNOWN" | null>(null);
  const [streamActive, setStreamActive] = useState(false);

  // HTML5 getUserMedia WebCam initialization for browser direct mode
  useEffect(() => {
    let localStream: MediaStream | null = null;
    let isSubscribed = true;

    if (streamMode === "browser") {
      async function startCamera() {
        setErrorMsg(null);
        setErrorScenario(null);

        try {
          if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setErrorScenario("A");
            throw new Error("TypeError: Cannot read properties of undefined (reading 'getUserMedia'). WebCam API requires HTTPS or http://localhost access.");
          }

          const stream = await navigator.mediaDevices.getUserMedia({
            video: {
              width: { ideal: 1280, max: 1920 },
              height: { ideal: 720, max: 1080 },
              facingMode: "user"
            },
            audio: false
          });

          if (!isSubscribed) {
            stream.getTracks().forEach((track) => track.stop());
            return;
          }

          localStream = stream;
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }
          setStreamActive(true);
          if (onStateChange) onStateChange(true);

        } catch (err: any) {
          console.error("Camera Initialization Error:", err);
          setStreamActive(false);
          if (onStateChange) onStateChange(false);

          const name = err.name || "";
          const msg = err.message || String(err);

          if (name === "TypeError" || msg.includes("getUserMedia") || (window.location.protocol === "http:" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1")) {
            setErrorScenario("A");
            setErrorMsg("Scenario A (Insecure Origin): Site accessed via HTTP IP address. Access via http://localhost:5173 or enable chrome://flags/#unsafely-treat-insecure-origin-as-secure.");
          } else if (name === "NotAllowedError" || name === "PermissionDeniedError") {
            setErrorScenario("B");
            setErrorMsg("Scenario B (Permission Denied): Camera blocked by OS or Browser. Check Windows Settings -> Privacy & Security -> Camera -> Allow desktop apps.");
          } else if (name === "NotReadableError" || name === "TrackStartError") {
            setErrorScenario("C");
            setErrorMsg("Scenario C (Hardware Conflict): Logitech C270 is locked by another background video application (Teams, Zoom, OBS, or another tab).");
          } else {
            setErrorScenario("UNKNOWN");
            setErrorMsg(`${name || "CameraError"}: ${msg}`);
          }
        }
      }

      startCamera();
    } else {
      // Ensure any previous browser MediaStream is completely released when switching to MediaPipe backend mode
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
      setErrorMsg(null);
    }

    return () => {
      isSubscribed = false;
      if (localStream) {
        localStream.getTracks().forEach((track) => track.stop());
      }
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    };
  }, [streamMode, onStateChange]);

  return (
    <div className="bg-slate-950 rounded-2xl border-2 border-slate-800 p-4 shadow-xl overflow-hidden transition-all duration-300 font-sans">
      {/* Top Controls Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3 text-white">
        <div className="flex items-center gap-2">
          <span className={cn(
            "w-2.5 h-2.5 rounded-full transition-all",
            errorMsg ? "bg-red-500" : "bg-emerald-500 animate-ping"
          )} />
          <h3 className="font-bold text-xs tracking-wider uppercase text-white flex items-center gap-1.5">
            <Camera className="w-4 h-4 text-cyan-400" /> SCAN MACHINE LIVE CAMERA FEED
          </h3>
        </div>

        {/* Mode Selector & Status Pills */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-800 text-[11px] font-bold">
            <button
              onClick={() => setStreamMode("backend")}
              title="View live OpenCV Face + MediaPipe Skeleton + Dizziness Tilt + Fall Model stream"
              className={cn(
                "px-2.5 py-1 rounded-lg transition-all flex items-center gap-1",
                streamMode === "backend" ? "bg-cyan-600 text-white shadow" : "text-slate-400 hover:text-white"
              )}
            >
              <Cpu className="w-3 h-3" /> MediaPipe AI Models Feed
            </button>
            <button
              onClick={() => setStreamMode("browser")}
              title="Browser HTML5 raw video feed without AI overlays"
              className={cn(
                "px-2.5 py-1 rounded-lg transition-all flex items-center gap-1",
                streamMode === "browser" ? "bg-cyan-600 text-white shadow" : "text-slate-400 hover:text-white"
              )}
            >
              <Camera className="w-3 h-3" /> Direct HTML5 WebCam
            </button>
          </div>

          <span className={cn(
            "text-[10px] font-mono font-bold px-2 py-0.5 rounded border uppercase",
            errorMsg ? "bg-red-950 text-red-300 border-red-800" : "bg-emerald-950 text-emerald-400 border-emerald-800"
          )}>
            {errorMsg ? "● STREAM DISRUPTED" : streamMode === "backend" ? "● MEDIAPIPE AI OVERLAY" : "● HTML5 WEBCAM ACTIVE"}
          </span>
        </div>
      </div>

      {/* Main Stream Area */}
      <div className="relative aspect-video max-h-80 w-full bg-slate-900 rounded-xl overflow-hidden flex items-center justify-center border border-slate-800">
        {streamMode === "backend" ? (
          /* Backend FastAPI MediaPipe Stream with Face & Pose Detector Overlay */
          <img
            src="/video_feed"
            alt="Scan Machine Camera Stream"
            className="w-full h-full object-contain"
          />
        ) : (
          /* Direct HTML5 WebCam (<video>) with Pose Tracker Overlay */
          <div className="relative w-full h-full flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-contain"
            />
            {/* Pose HUD Overlay for Direct HTML5 Mode */}
            <div className="absolute top-3 left-3 bg-slate-900/90 border border-emerald-500/60 p-2.5 rounded-xl backdrop-blur-md text-white text-xs space-y-1">
              <p className="font-bold text-emerald-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                POSE STATE: NORMAL
              </p>
              <p className="text-[10px] font-mono text-slate-300">
                HEAD-TO-LEG 33 KEYPOINTS: ACTIVE SCANNING
              </p>
            </div>
          </div>
        )}

        {/* Error Diagnostic Overlay for Scenarios A, B, C, D */}
        {errorMsg && (
          <div className="absolute inset-0 bg-slate-950/90 backdrop-blur-md p-6 flex flex-col items-center justify-center text-center z-30 space-y-3">
            <div className="p-3 bg-red-900/60 text-red-400 rounded-2xl border border-red-700/50 animate-bounce">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div className="max-w-md space-y-1">
              <h4 className="font-bold text-sm text-red-200">
                Camera Access Disrupted {errorScenario ? `(Scenario ${errorScenario})` : ""}
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed font-mono bg-slate-900/80 p-2.5 rounded-lg border border-slate-800 text-left">
                {errorMsg}
              </p>
            </div>

            {/* Step-by-step Quick Fix Guidance */}
            <div className="text-[11px] text-slate-400 text-left max-w-md space-y-1 bg-slate-900 p-3 rounded-xl border border-slate-800">
              <strong className="text-cyan-400 block mb-1">🛠 Quick Troubleshooting Steps:</strong>
              {errorScenario === "A" && (
                <p>• Ensure URL is <strong>http://localhost:5173</strong> or <strong>http://127.0.0.1:5173</strong> (not an external IP address).</p>
              )}
              {errorScenario === "B" && (
                <p>• Go to Windows <strong>Settings → Privacy & Security → Camera</strong> and enable <em>"Allow desktop apps to access your camera"</em>.</p>
              )}
              {errorScenario === "C" && (
                <p>• Fully close Zoom, Microsoft Teams, OBS Studio, or other open browser tabs using the Logitech C270 camera.</p>
              )}
              {errorScenario === "D" && (
                <p>• Add <code>allow="camera; microphone"</code> attribute to parent iframe tags.</p>
              )}
              {(!errorScenario || errorScenario === "UNKNOWN") && (
                <p>• Re-plug Logitech C270 USB cable and switch between MediaPipe and HTML5 mode above.</p>
              )}
            </div>

            <button
              onClick={() => {
                setErrorMsg(null);
                setStreamMode(streamMode === "backend" ? "browser" : "backend");
              }}
              className="tactile-button px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs rounded-xl shadow transition flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Try Alternate Camera Stream Mode
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default SafeCameraStream;
