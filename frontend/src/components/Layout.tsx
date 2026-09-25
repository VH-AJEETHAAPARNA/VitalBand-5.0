// Shared Layout: header + nav + Security Audit trigger
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { t, type Lang } from "../lib/i18n";
import { Activity, Shield, LogOut, LayoutDashboard, BarChart2, Volume2, VolumeX, ShieldCheck } from "lucide-react";
import { cn } from "../lib/utils";
import {
  getAudioMuted, setAudioMuted, getAudioVolume, setAudioVolume, playEmergencyChime,
} from "../lib/audioAlert";
import { clearVoiceQueue, hasVoiceFor } from "../lib/voiceAlerts";
import { useState } from "react";

interface LayoutProps {
  children: React.ReactNode;
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  privacyMode?: boolean;
  onTogglePrivacy?: () => void;
  isEmergencyActive?: boolean;
  /** Opens the DPDP audit modal, which App owns so a Layout
   *  re-mount can never close it mid-demo. */
  onOpenSecurityAudit?: () => void;
}

const NAV_LINKS = [
  { path: "/", labelKey: "nurseDashboard", icon: <LayoutDashboard className="w-4 h-4" />, roles: ["nurse", "admin", "super_admin"] },
  { path: "/history", labelKey: "alertHistory", icon: <BarChart2 className="w-4 h-4" />, roles: ["nurse", "admin", "super_admin"] },
  { path: "/admin", labelKey: "adminPanel", icon: <Shield className="w-4 h-4" />, roles: ["admin", "super_admin"] },
];

const LANG_OPTIONS: { code: Lang; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "ta", label: "தமிழ்" },
  { code: "hi", label: "हिं" },
  { code: "kn", label: "ಕನ್ನ" },
];

export function Layout({
  children,
  lang,
  onLangChange,
  privacyMode = false,
  onTogglePrivacy = () => {},
  isEmergencyActive = false,
  onOpenSecurityAudit = () => {},
}: LayoutProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [muted, setMuted] = useState(getAudioMuted());
  const [volume, setVolume] = useState(getAudioVolume());

  const toggleMute = () => {
    const next = !muted;
    setAudioMuted(next);
    setMuted(next);
    // Muting mid-emergency must silence what is already queued, not just
    // suppress future alerts.
    if (next) clearVoiceQueue();
  };

  const changeVolume = (v: number) => {
    setAudioVolume(v);
    setVolume(v);
    if (v > 0 && muted) {
      setAudioMuted(false);
      setMuted(false);
    }
  };

  // Which speech engine will actually be used for the selected language.
  // "live" = an OS voice pack exists, so announcements can name the specific
  // bed and vitals. "clip" = no OS voice, so we play the pre-rendered gTTS
  // audio served from /api/voice — correct pronunciation, fixed phrasing.
  const speechEngine: "live" | "clip" = hasVoiceFor(lang) ? "live" : "clip";

  return (
    <div
      className={cn(
        "min-h-screen flex flex-col transition-all duration-300",
        isEmergencyActive
          ? "ring-4 ring-red-500/80 ring-inset shadow-[inset_0_0_30px_rgba(239,68,68,0.25)] bg-slate-50"
          : "bg-slate-50/80"
      )}
    >
      {/* Header */}
      <header className="bg-[#0b2545] text-white shadow-lg sticky top-0 z-40 border-b border-blue-900/50">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-blue-500/20 rounded-xl border border-blue-400/30 flex items-center justify-center">
              <Activity className="w-5 h-5 text-emerald-400" />
            </div>
            <span className="font-extrabold tracking-tight text-base">{t("appName", lang)}</span>
            <span className="ml-1 hidden sm:flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-800/50">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              {t("live", lang)} NETWORK
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-1">
            {NAV_LINKS
              .filter((link) => !user || link.roles.includes(user.role))
              .map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all",
                    location.pathname === link.path
                      ? "bg-white/20 text-white shadow-inner"
                      : "text-white/70 hover:bg-white/10 hover:text-white"
                  )}
                >
                  {link.icon}
                  {t(link.labelKey, lang)}
                </Link>
              ))}
          </nav>

          <div className="flex items-center gap-2">
            {/* Security Audit & DPDP Shield Button */}
            <button
              onClick={onOpenSecurityAudit}
              title="Security, DPDP Act & Privacy Audit Shield"
              className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-blue-950/80 hover:bg-blue-900 border border-blue-800 text-cyan-300 text-xs font-bold transition shadow-sm"
            >
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              <span className="hidden sm:inline">DPDP Shield</span>
            </button>

            {/* Emergency audio: mute toggle + volume */}
            <div className="flex items-center gap-1.5 bg-blue-950/60 pl-1 pr-2 py-0.5 rounded-xl border border-blue-900/50">
              <button
                onClick={toggleMute}
                title={muted ? "Unmute emergency alerts" : "Mute emergency alerts"}
                aria-label={muted ? "Unmute emergency alerts" : "Mute emergency alerts"}
                className="p-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              >
                {muted ? <VolumeX className="w-4 h-4 text-red-300" /> : <Volume2 className="w-4 h-4 text-emerald-300" />}
              </button>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={muted ? 0 : volume}
                onChange={(e) => changeVolume(parseFloat(e.target.value))}
                title={`Alert volume ${Math.round((muted ? 0 : volume) * 100)}%`}
                aria-label="Alert volume"
                className="w-16 h-1 accent-emerald-400 cursor-pointer"
              />
              <button
                onClick={() => playEmergencyChime("CRITICAL")}
                title="Test the emergency chime"
                className="text-[10px] font-bold text-white/60 hover:text-white px-1 transition-colors"
              >
                TEST
              </button>
            </div>

            {!muted && (
              <span
                title={
                  speechEngine === "live"
                    ? `${lang.toUpperCase()}: using this machine's installed voice — announcements name the bed and vitals.`
                    : `${lang.toUpperCase()}: no OS voice pack, so VitalBand plays its own pre-recorded ${lang.toUpperCase()} audio (cached, works offline).`
                }
                className={cn(
                  "hidden lg:inline text-[10px] font-bold px-2 py-0.5 rounded-lg border",
                  speechEngine === "live"
                    ? "text-emerald-300 bg-emerald-950/50 border-emerald-800/60"
                    : "text-cyan-300 bg-cyan-950/50 border-cyan-800/60"
                )}
              >
                {lang.toUpperCase()} · {speechEngine === "live" ? "LIVE VOICE" : "CACHED AUDIO"}
              </span>
            )}

            {/* Language switcher */}
            <div className="flex gap-1 bg-blue-950/60 p-0.5 rounded-xl border border-blue-900/50">
              {LANG_OPTIONS.map((l) => (
                <button
                  key={l.code}
                  onClick={() => onLangChange(l.code)}
                  className={cn(
                    "px-2 py-0.5 rounded-lg text-xs font-bold transition-all",
                    lang === l.code
                      ? "bg-white/25 text-white shadow-sm"
                      : "text-white/60 hover:text-white"
                  )}
                >
                  {l.label}
                </button>
              ))}
            </div>

            {user && (
              <button
                onClick={logout}
                title={t("logout", lang)}
                className="flex items-center gap-1 text-white/70 hover:text-white text-xs font-semibold transition-colors ml-1 p-1.5 rounded-xl hover:bg-white/10"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden md:inline">{user.full_name}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {children}
      </main>

    </div>
  );
}
