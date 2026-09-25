// src/lib/audioAlert.ts
// Web Audio chime synthesiser + shared output settings (mute / volume).
//
// Separate from speech: the chime is what actually gets a nurse's head up
// across a noisy ward, and it must fire even when speech synthesis has no
// voice installed for the selected language.

let audioCtx: AudioContext | null = null;
let isMuted = false;
let volume = 0.7; // 0..1, applied to both chime and speech

type SettingsListener = (s: { muted: boolean; volume: number }) => void;
const listeners = new Set<SettingsListener>();

function emit() {
  const snapshot = { muted: isMuted, volume };
  listeners.forEach((fn) => fn(snapshot));
}

export function subscribeAudioSettings(fn: SettingsListener): () => void {
  listeners.add(fn);
  fn({ muted: isMuted, volume });
  return () => listeners.delete(fn);
}

export function setAudioMuted(muted: boolean) {
  isMuted = muted;
  emit();
}

export function getAudioMuted(): boolean {
  return isMuted;
}

export function setAudioVolume(v: number) {
  volume = Math.max(0, Math.min(1, v));
  emit();
}

export function getAudioVolume(): number {
  return volume;
}

function getOrCreateAudioContext(): AudioContext | null {
  try {
    const Ctor = window.AudioContext || (window as any).webkitAudioContext;
    if (!Ctor) return null;
    if (!audioCtx) audioCtx = new Ctor();
    if (audioCtx.state === "suspended") void audioCtx.resume();
    return audioCtx;
  } catch (e) {
    console.warn("AudioContext init error:", e);
    return null;
  }
}

// Browsers block audio until the page has been interacted with. Unlock on the
// first gesture so the first real alert is never the one that gets swallowed.
if (typeof window !== "undefined") {
  const unlock = () => {
    const ctx = getOrCreateAudioContext();
    if (ctx && ctx.state === "running") {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    }
  };
  window.addEventListener("pointerdown", unlock, { passive: true });
  window.addEventListener("keydown", unlock, { passive: true });
}

export type ChimeSeverity = "CRITICAL" | "WARNING" | "INFO";

/**
 * Two-tone medical attention chime.
 * CRITICAL uses the 880 Hz → 440 Hz falling interval (a minor-sounding drop
 * reads as "bad news" far faster than a rising tone); WARNING is a softer
 * single pair; INFO is a short blip.
 */
export function playEmergencyChime(severity: ChimeSeverity = "CRITICAL") {
  if (isMuted || volume <= 0) return;

  const ctx = getOrCreateAudioContext();
  if (!ctx) return;

  try {
    const now = ctx.currentTime;
    const master = ctx.createGain();
    master.gain.setValueAtTime(volume, now);
    master.connect(ctx.destination);

    const tone = (freq: number, start: number, dur: number, peak: number) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + start);
      // Exponential ramps can't touch zero, so floor the tail.
      g.gain.setValueAtTime(0.0001, now + start);
      g.gain.exponentialRampToValueAtTime(peak, now + start + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
      osc.connect(g);
      g.connect(master);
      osc.start(now + start);
      osc.stop(now + start + dur + 0.02);
    };

    if (severity === "CRITICAL") {
      tone(880, 0, 0.26, 0.8);
      tone(440, 0.24, 0.34, 0.8);
      tone(880, 0.60, 0.26, 0.6);
      tone(440, 0.84, 0.34, 0.6);
    } else if (severity === "WARNING") {
      tone(660, 0, 0.2, 0.45);
      tone(440, 0.2, 0.28, 0.45);
    } else {
      tone(523, 0, 0.14, 0.25);
    }
  } catch (err) {
    console.warn("Audio chime play error:", err);
  }
}
