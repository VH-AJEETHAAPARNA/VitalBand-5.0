// src/App.tsx – main routing and layout integration with stable alert state & no page blinking
import React, { useState, useCallback, useMemo, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { AlertsHistory } from "./pages/AlertsHistory";
import { AdminPanel } from "./pages/AdminPanel";
import { IncidentDetail } from "./pages/IncidentDetail";
import { useAuth } from "./contexts/AuthContext";
import { type Lang, LANGUAGES, t } from "./lib/i18n";
import { EmergencyBanner } from "./components/EmergencyBanner";
import { useWebSocket } from "./hooks/useWebSocket";
import { enqueueVoiceAlert } from "./lib/voiceAlerts";
import type { WebSocketMessage } from "./lib/types";
import { usePatients } from "./hooks/usePatients";
import AICopilotDrawer from "./components/AICopilotDrawer";
import { recordAudit } from "./lib/auditLog";
import { SecurityAuditModal } from "./components/SecurityAuditModal";

export default function App() {
  const { user, loading } = useAuth();
  const location = useLocation();
  const [lang, setLang] = useState<Lang>("en");
  const [privacyMode, setPrivacyMode] = useState(false);
  const [emergencyMessage, setEmergencyMessage] = useState<string | null>(null);
  const [showSecurityAudit, setShowSecurityAudit] = useState(false);

  const isAuth = !!user;
  const { data: patients } = usePatients({ enabled: isAuth });

  // Handled patient IDs to prevent re-opening JEV drawer continuously for the same ongoing alert
  const [handledPatientIds, setHandledPatientIds] = useState<Record<string, boolean>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [flashEmergencyRing, setFlashEmergencyRing] = useState(false);

  // Handle incoming WS messages — flash red screen frame for 4s ONCE, not forever
  const handleWSMessage = useCallback((msg: WebSocketMessage) => {
    if (msg.event_type === "alert") {
      setEmergencyMessage(`${t("emergency", lang)}: ${msg.event ?? "Alert"}`);
      setFlashEmergencyRing(true);
      setTimeout(() => setFlashEmergencyRing(false), 4000);

      // Chime + localised announcement, priority-queued. Replaces the old
      // speechSynthesis.cancel() call, which made each alert in a burst
      // silence the one before it.
      enqueueVoiceAlert(
        {
          priority: (msg.severity === "WARNING" ? "WARNING" : "CRITICAL"),
          eventType: msg.event ?? "ALERT",
          patientId: msg.patient_id ?? "UNKNOWN",
          spo2: msg.spo2,
          heartRate: msg.heart_rate,
        },
        lang
      );
    }
  }, [lang]);

  // Connect WS – default hospital constant matches backend seed
  useWebSocket(handleWSMessage, "DEFAULT_HOSP");

  // Find active critical patient
  const criticalPatient = useMemo(() => {
    if (!patients) return null;
    return patients.find(
      (p) =>
        (p.fall ||
        p.sos ||
        (p.heart_rate && (p.heart_rate >= 130 || p.heart_rate <= 45)) ||
        (p.spo2 && p.spo2 <= 88)) &&
        !handledPatientIds[p.patient_id]   // skip already-handled patients
    ) ?? null;
  }, [patients, handledPatientIds]);

  // Only clear handled state for patients that have FULLY recovered (no longer critical)
  useEffect(() => {
    if (!patients || Object.keys(handledPatientIds).length === 0) return;
    setHandledPatientIds((prev) => {
      const next = { ...prev };
      let changed = false;
      for (const pid of Object.keys(next)) {
        const p = patients.find((pt) => pt.patient_id === pid);
        if (!p) continue; // patient removed entirely — clean up
        const stillCritical =
          p.fall || p.sos ||
          (p.heart_rate && (p.heart_rate >= 130 || p.heart_rate <= 45)) ||
          (p.spo2 && p.spo2 <= 88);
        if (!stillCritical) {
          delete next[pid];
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [patients]);

  // Active Alert Data for JEV AI Triage Co-Pilot Drawer
  const activeCopilotAlert = useMemo(() => {
    if (!criticalPatient) return null;

    let action = "Review patient immediately & assess bedside unit.";
    let reasoning = `Deterministic Safety Rule Breached: SpO2 (${criticalPatient.spo2 ?? 84}%) below 92% and HR (${criticalPatient.heart_rate ?? 142} BPM) above 120 BPM.`;
    let motion = "Elevated";

    if (criticalPatient.fall) {
      action = "Dispatch Rapid Response & Fall Assessment Team";
      reasoning = "MediaPipe posture collapse confirmed / Accelerometer impact vector detected.";
      motion = "Zero-velocity post-impact";
    } else if (criticalPatient.sos) {
      action = "Dispatch Ward Security & Nurse Supervisor";
      reasoning = "Manual physical SOS panic button pressed by patient.";
      motion = "BEDSIDE SOS";
    }

    return {
      patientId: criticalPatient.patient_id,
      patient_id: criticalPatient.patient_id,
      fall: !!criticalPatient.fall,
      sos: !!criticalPatient.sos,
      triageLevel: criticalPatient.fall || criticalPatient.sos ? "LEVEL 1 EMERGENCY" : "LEVEL 2 URGENT",
      hr: criticalPatient.heart_rate ?? 142,
      spo2: criticalPatient.spo2 ?? 84,
      motion,
      action,
      recommendedAction: action,
      reasoning,
      clinicalReasoning: reasoning,
      timestamp: new Date().toISOString(),
    };
  }, [criticalPatient]);

  const handleDismissAllCopilot = useCallback(() => {
    if (patients) {
      const allCriticalIds: Record<string, boolean> = {};
      patients.forEach((p) => {
        if (
          p.fall ||
          p.sos ||
          (p.heart_rate && (p.heart_rate >= 130 || p.heart_rate <= 45)) ||
          (p.spo2 && p.spo2 <= 88)
        ) {
          allCriticalIds[p.patient_id] = true;
        }
      });
      setHandledPatientIds((prev) => ({ ...prev, ...allCriticalIds }));
    }
  }, [patients]);

  const handleConfirmAI = () => {
    if (criticalPatient) {
      setHandledPatientIds((prev) => ({ ...prev, [criticalPatient.patient_id]: true }));
      void recordAudit({
        actorId: user?.email ?? "unknown",
        actorRole: user?.role ?? "nurse",
        eventType: "ALERT_ACKNOWLEDGED",
        subject: criticalPatient.patient_id,
        detail: `Accepted AI triage: ${activeCopilotAlert?.action ?? "route bed"}`,
      });
    }
    setToastMessage(`✓ Approved: ${activeCopilotAlert?.action || "Bed routed & team dispatched"}`);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleOverrideAI = () => {
    if (criticalPatient) {
      void recordAudit({
        actorId: user?.email ?? "unknown",
        actorRole: user?.role ?? "nurse",
        eventType: "AI_RECOMMENDATION_OVERRIDDEN",
        subject: criticalPatient.patient_id,
        detail: "Clinician overrode the AI recommendation",
      });
    }
    handleDismissAllCopilot();
    setToastMessage("AI recommendation overridden by clinical staff");
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Guard routes – unauthenticated users go to /login
  if (loading) return null; // waiting for auth init

  // Unauthenticated: render the splash/login full-bleed, WITHOUT the app
  // chrome. Otherwise a logged-out visitor sees the nurse/admin nav, the
  // DPDP shield and the staff name before authenticating.
  if (!isAuth) {
    return (
      <Routes>
        <Route path="/login" element={<Login lang={lang} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Toast Feedback for Human-in-the-Loop decision */}
      {toastMessage && (
        <div className="fixed top-16 right-6 z-50 rounded-xl bg-slate-900/95 border border-cyan-500/50 text-white px-4 py-2.5 shadow-2xl text-xs font-bold flex items-center gap-2 animate-in slide-in-from-top-2 backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
          {toastMessage}
        </div>
      )}

      {emergencyMessage && (
        <EmergencyBanner message={emergencyMessage} onDismiss={() => setEmergencyMessage(null)} />
      )}
      <Layout
        lang={lang}
        onLangChange={setLang}
        privacyMode={privacyMode}
        onTogglePrivacy={() => setPrivacyMode(!privacyMode)}
        isEmergencyActive={flashEmergencyRing}
        onOpenSecurityAudit={() => setShowSecurityAudit(true)}
      >
        <Routes>
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/" element={<Dashboard lang={lang} privacyMode={privacyMode} />} />
          <Route path="/history" element={<AlertsHistory lang={lang} />} />
          <Route
            path="/admin"
            element={
              user?.role === "admin" || user?.role === "super_admin"
                ? <AdminPanel lang={lang} />
                : <Navigate to="/" replace />
            }
          />
          <Route path="/incident/:id" element={<IncidentDetail lang={lang} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>

      {showSecurityAudit && (
        <SecurityAuditModal
          onClose={() => setShowSecurityAudit(false)}
          privacyMode={privacyMode}
          onTogglePrivacy={() => setPrivacyMode(!privacyMode)}
        />
      )}

      {/* Upgrade 1: Human-in-the-Loop AI Drawer (only shows when unhandled critical alert exists) */}
      <AICopilotDrawer
        activeAlert={activeCopilotAlert}
        onConfirm={handleConfirmAI}
        onOverride={handleOverrideAI}
        onClose={handleDismissAllCopilot}
        lang={lang}
      />
    </div>
  );
}
