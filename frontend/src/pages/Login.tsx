// src/pages/Login.tsx – Award-winning Luxury Glassmorphism Login with Intro Splash sequence
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { t, type Lang } from "../lib/i18n";
import { cn } from "../lib/utils";
import { AlertTriangle, Activity, Lock, Mail, ArrowRight, ShieldCheck, User, Sparkles } from "lucide-react";
import { IntroSplashScreen } from "../components/IntroSplashScreen";

interface LoginProps {
  lang: Lang;
}

export function Login({ lang }: LoginProps) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Show splash screen initially unless coming from another page
  const [showSplash, setShowSplash] = useState(true);
  const [email, setEmail] = useState("nurse@vitalband.com");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const from = (location.state as any)?.from?.pathname || "/";

  const handleProceedFromSplash = (fillRole?: "nurse" | "admin") => {
    if (fillRole === "admin") {
      setEmail("admin@vitalband.com");
      setPassword("password");
    } else if (fillRole === "nurse") {
      setEmail("nurse@vitalband.com");
      setPassword("password");
    }
    setShowSplash(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message ?? "Login failed");
    } finally {
      setLoading(false);
    }
  };

  if (showSplash) {
    return <IntroSplashScreen onProceedToLogin={handleProceedFromSplash} />;
  }

  return (
    <div className="relative min-h-screen w-full bg-[#020b18] flex items-center justify-center p-4 overflow-hidden select-none">
      {/* Background Animated Gradient Orbs */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b15_1px,transparent_1px),linear-gradient(to_bottom,#1e293b15_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-cyan-500/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-blue-600/20 rounded-full blur-[120px] pointer-events-none" />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md bg-slate-900/90 backdrop-blur-xl rounded-3xl border border-slate-800 p-8 shadow-2xl space-y-6">
        {/* Card Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex p-3 bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl shadow-lg shadow-cyan-500/20 border border-cyan-300/30 mb-2">
            <Activity className="w-8 h-8 text-white animate-pulse" />
          </div>
          <h2 className="text-2xl font-black tracking-tight text-white">VitalBand Console Login</h2>
          <p className="text-xs text-slate-400">Authenticated Access for Hospital Triage Staff</p>
        </div>

        {/* Quick Demo Credentials Selection Pills */}
        <div className="p-1.5 bg-slate-950 rounded-2xl border border-slate-800 grid grid-cols-2 gap-1 text-xs">
          <button
            type="button"
            onClick={() => {
              setEmail("nurse@vitalband.com");
              setPassword("password");
            }}
            className={cn(
              "py-2 rounded-xl font-bold transition flex items-center justify-center gap-1.5",
              email === "nurse@vitalband.com"
                ? "bg-cyan-500 text-white shadow-md shadow-cyan-500/20"
                : "text-slate-400 hover:text-white"
            )}
          >
            <User className="w-3.5 h-3.5" /> Nurse Account
          </button>
          <button
            type="button"
            onClick={() => {
              setEmail("admin@vitalband.com");
              setPassword("password");
            }}
            className={cn(
              "py-2 rounded-xl font-bold transition flex items-center justify-center gap-1.5",
              email === "admin@vitalband.com"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/20"
                : "text-slate-400 hover:text-white"
            )}
          >
            <ShieldCheck className="w-3.5 h-3.5" /> Admin Account
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 bg-red-950/80 border border-red-800 text-red-300 rounded-xl p-3 text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5" htmlFor="email">
              {t("email", lang)}
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 text-white rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500 transition font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5" htmlFor="password">
              {t("password", lang)}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-950 border border-slate-800 text-white rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-500 transition font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className={cn(
              "w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 text-white font-extrabold text-sm tracking-wide shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:scale-[1.01] active:scale-[0.99] transition-all flex items-center justify-center gap-2 border border-cyan-300/30",
              loading && "opacity-70 cursor-not-allowed"
            )}
          >
            {loading ? "Authenticating..." : "ENTER CLINICAL CONSOLE"}
            {!loading && <ArrowRight className="w-4 h-4" />}
          </button>
        </form>

        {/* Footer info */}
        <div className="pt-2 text-center text-[11px] text-slate-500 flex items-center justify-between border-t border-slate-800/80">
          <button
            type="button"
            onClick={() => setShowSplash(true)}
            className="text-cyan-400 hover:underline font-semibold"
          >
            ← Back to Intro Splash
          </button>
          <span>DPDP Act 2023 Shield</span>
        </div>
      </div>
    </div>
  );
}
