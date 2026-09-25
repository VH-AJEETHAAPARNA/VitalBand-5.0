// src/lib/voiceAlerts.ts
// Priority-ordered spoken alert queue (EN / TA / HI / KN).
//
// Why a queue rather than speak-on-arrival: the previous code called
// speechSynthesis.cancel() before every utterance, so during a burst of
// alerts each one silenced the last and the nurse heard only the final
// fragment. Here, alerts queue; a CRITICAL jumps the line ahead of pending
// warnings, and nothing is discarded unless the backlog exceeds MAX_QUEUE.
//
// Two speech engines, in this order:
//   1. Pre-rendered gTTS audio from /api/voice/<EVENT>/<lang>. This is the
//      DEFAULT for ta/hi/kn because it always sounds correct and needs no OS
//      voice pack — the clips ship cached with the project.
//   2. The browser's speechSynthesis, used when a real voice pack exists for
//      the language (typically English) since it can name the specific bed
//      and vitals rather than reading a fixed phrase.

import { playEmergencyChime, getAudioMuted, getAudioVolume } from "./audioAlert";
import type { Lang } from "./i18n";

export type AlertPriority = "CRITICAL" | "WARNING" | "INFO";

export interface VoiceAlert {
  priority: AlertPriority;
  eventType: string;      // SOS | FALL | ABNORMAL_VITALS | DISTRESS | ...
  patientId: string;
  bed?: string;
  spo2?: number;
  heartRate?: number;
}

const PRIORITY_RANK: Record<AlertPriority, number> = {
  CRITICAL: 3,
  WARNING: 2,
  INFO: 1,
};

// BCP-47 tags used to pick a matching installed voice.
const LOCALE: Record<Lang, string> = {
  en: "en-IN",
  ta: "ta-IN",
  hi: "hi-IN",
  kn: "kn-IN",
};

type Phrase = {
  emergency: string;
  sos: string;
  fall: string;
  vitals: string;
  distress: string;
  bed: (b: string) => string;
  spo2: (v: number) => string;
  hr: (v: number) => string;
  patient: (id: string) => string;
};

const PHRASES: Record<Lang, Phrase> = {
  en: {
    emergency: "Emergency.",
    sos: "Panic button pressed.",
    fall: "Fall detected.",
    vitals: "Abnormal vital signs.",
    distress: "Patient distress detected.",
    bed: (b) => `Bed ${b}.`,
    spo2: (v) => `Oxygen saturation ${v} percent.`,
    hr: (v) => `Heart rate ${v}.`,
    patient: (id) => `Patient ${id}.`,
  },
  ta: {
    emergency: "அவசரநிலை.",
    sos: "அவசர பொத்தான் அழுத்தப்பட்டது.",
    fall: "விழுந்தது கண்டறியப்பட்டது.",
    vitals: "உயிர்நாடி அளவுகள் சீரற்றவை.",
    distress: "நோயாளி துன்பத்தில் உள்ளார்.",
    bed: (b) => `படுக்கை ${b}.`,
    spo2: (v) => `ஆக்ஸிஜன் அளவு ${v} சதவீதம்.`,
    hr: (v) => `இதய துடிப்பு ${v}.`,
    patient: (id) => `நோயாளி ${id}.`,
  },
  hi: {
    emergency: "आपातकाल।",
    sos: "आपातकालीन बटन दबाया गया।",
    fall: "गिरने का पता चला।",
    vitals: "असामान्य महत्वपूर्ण संकेत।",
    distress: "रोगी संकट में है।",
    bed: (b) => `बिस्तर ${b}।`,
    spo2: (v) => `ऑक्सीजन स्तर ${v} प्रतिशत।`,
    hr: (v) => `हृदय गति ${v}।`,
    patient: (id) => `रोगी ${id}।`,
  },
  kn: {
    emergency: "ತುರ್ತು ಪರಿಸ್ಥಿತಿ.",
    sos: "ತುರ್ತು ಗುಂಡಿ ಒತ್ತಲಾಗಿದೆ.",
    fall: "ಬಿದ್ದಿರುವುದು ಪತ್ತೆಯಾಗಿದೆ.",
    vitals: "ಅಸಾಮಾನ್ಯ ಜೀವಸೂಚಕಗಳು.",
    distress: "ರೋಗಿ ಸಂಕಟದಲ್ಲಿದ್ದಾರೆ.",
    bed: (b) => `ಹಾಸಿಗೆ ${b}.`,
    spo2: (v) => `ಆಮ್ಲಜನಕ ಮಟ್ಟ ${v} ಶೇಕಡಾ.`,
    hr: (v) => `ಹೃದಯ ಬಡಿತ ${v}.`,
    patient: (id) => `ರೋಗಿ ${id}.`,
  },
};

export function buildAnnouncement(alert: VoiceAlert, lang: Lang): string {
  const p = PHRASES[lang] ?? PHRASES.en;
  const parts: string[] = [];

  if (alert.priority === "CRITICAL") parts.push(p.emergency);

  const evt = alert.eventType.toUpperCase();
  if (evt.includes("SOS")) parts.push(p.sos);
  else if (evt.includes("FALL")) parts.push(p.fall);
  else if (evt.includes("DISTRESS")) parts.push(p.distress);
  else parts.push(p.vitals);

  parts.push(alert.bed ? p.bed(alert.bed) : p.patient(alert.patientId));

  if (alert.spo2 != null) parts.push(p.spo2(alert.spo2));
  if (alert.heartRate != null) parts.push(p.hr(alert.heartRate));

  return parts.join(" ");
}

// ── Queue ────────────────────────────────────────────────────────────────────

interface QueueItem extends VoiceAlert {
  id: number;
  text: string;
  lang: Lang;
}

// Beyond this depth a spoken backlog is stale before it plays.
const MAX_QUEUE = 6;

let queue: QueueItem[] = [];
let speaking = false;
let nextId = 1;

function supported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

function pickVoice(lang: Lang): SpeechSynthesisVoice | null {
  if (!supported()) return null;
  const target = LOCALE[lang];
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  // Exact locale, then any voice for the base language.
  const base = target.split("-")[0];
  return (
    voices.find((v) => v.lang === target) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(base)) ??
    null
  );
}

/**
 * Indian-language voices are frequently not installed on demo laptops.
 * Report that honestly so the UI can say "text shown, no voice pack" rather
 * than silently saying nothing.
 */
export function hasVoiceFor(lang: Lang): boolean {
  return pickVoice(lang) !== null;
}

/** Map a dashboard event name onto one of the five pre-rendered clips. */
function clipNameFor(eventType: string): string {
  const e = eventType.toUpperCase();
  if (e.includes("SOS")) return "SOS";
  if (e.includes("FALL")) return "FALL";
  if (e.includes("DISTRESS")) return "DISTRESS";
  return "ABNORMAL_VITALS";
}

let currentAudio: HTMLAudioElement | null = null;

/**
 * Play the server-rendered clip. Resolves false if it could not play, so the
 * caller can fall back to speechSynthesis rather than going silent.
 */
function playClip(item: QueueItem, onDone: () => void): boolean {
  try {
    const url = `/api/voice/${clipNameFor(item.eventType)}/${item.lang}`;
    const audio = new Audio(url);
    audio.volume = getAudioVolume();
    currentAudio = audio;

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      currentAudio = null;
      onDone();
    };

    audio.onended = finish;
    audio.onerror = finish;

    void audio.play().catch(finish);
    // Clips are a few seconds; never let a stalled element wedge the queue.
    setTimeout(finish, 12000);
    return true;
  } catch {
    return false;
  }
}

function drain() {
  if (speaking || queue.length === 0 || getAudioMuted()) return;


  // Highest priority first; ties resolved oldest-first so nothing starves.
  queue.sort((a, b) =>
    PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority] || a.id - b.id
  );

  const item = queue.shift()!;
  speaking = true;

  const finish = () => {
    speaking = false;
    // Small gap so consecutive announcements don't run together.
    setTimeout(drain, 220);
  };

  // Prefer the pre-rendered clip whenever the OS lacks a voice for this
  // language. That is what makes Tamil/Hindi/Kannada actually audible on a
  // stock Windows laptop.
  const voice = pickVoice(item.lang);
  if (!voice) {
    if (playClip(item, finish)) return;
  }

  try {
    const u = new SpeechSynthesisUtterance(item.text);
    if (voice) u.voice = voice;
    u.lang = LOCALE[item.lang];
    u.volume = getAudioVolume();
    u.rate = item.priority === "CRITICAL" ? 1.05 : 1.0;
    u.pitch = 1.0;
    u.onend = finish;
    u.onerror = finish;
    window.speechSynthesis.speak(u);

    // Safety net: some browsers never fire onend for long utterances.
    setTimeout(() => {
      if (speaking) finish();
    }, Math.max(4000, item.text.length * 110));
  } catch {
    finish();
  }
}

/** Queue an alert: chime immediately, speech in priority order. */
export function enqueueVoiceAlert(alert: VoiceAlert, lang: Lang) {
  if (getAudioMuted()) return;

  playEmergencyChime(alert.priority);

  queue.push({
    ...alert,
    id: nextId++,
    text: buildAnnouncement(alert, lang),
    lang,
  });

  // Bound the backlog rather than discarding by priority. An earlier version
  // purged every pending WARNING whenever a CRITICAL arrived, which meant a
  // real alert could be silently never announced — hard to defend clinically.
  // Now nothing is dropped until the queue is genuinely too long to be useful
  // (a 6-deep spoken backlog is already stale by the time it plays), and when
  // it is, the LOWEST-priority OLDEST item goes first. Criticals still jump
  // the line via the priority sort in drain(), and every alert remains on the
  // dashboard and in the permanent event history regardless.
  if (queue.length > MAX_QUEUE) {
    let worstIdx = 0;
    for (let i = 1; i < queue.length; i++) {
      const a = queue[i];
      const w = queue[worstIdx];
      if (
        PRIORITY_RANK[a.priority] < PRIORITY_RANK[w.priority] ||
        (PRIORITY_RANK[a.priority] === PRIORITY_RANK[w.priority] && a.id < w.id)
      ) {
        worstIdx = i;
      }
    }
    queue.splice(worstIdx, 1);
  }

  drain();
}

export function clearVoiceQueue() {
  queue = [];
  if (supported()) window.speechSynthesis.cancel();
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  speaking = false;
}

export function getVoiceQueueLength(): number {
  return queue.length;
}
