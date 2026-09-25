// Shared TypeScript types matching backend schemas

export interface Patient {
  patient_id: string;
  hospital_id: string;
  name?: string;
  rfid_uid?: string;
  device_id?: string;
  heart_rate?: number;
  spo2?: number;
  fall_status: string;
  sos_status: string;
  distress_status: string;
  wrist_connected: number;
  scan_connected: number;
  last_updated: string;
  // computed fields from backend
  fall?: boolean;
  sos?: boolean;
  distress?: boolean;
  abnormal?: boolean;
}

export interface VitalsReading {
  id: number;
  hospital_id: string;
  patient_id: string;
  heart_rate?: number;
  spo2?: number;
  timestamp: string;
}

export interface AlertEvent {
  id: number;
  hospital_id: string;
  patient_id: string;
  event_type: string;
  details?: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  timestamp: string;
}

export interface WebSocketMessage {
  event_type: "vitals_update" | "alert" | "rfid_scan";
  patient_id?: string;
  heart_rate?: number;
  spo2?: number;
  fall?: boolean;
  abnormal?: boolean;
  reasons?: string[];
  event?: string;
  detail?: string;
  severity?: string;
  rfid_uid?: string;
  timestamp?: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "nurse" | "admin" | "super_admin";
  hospital_id?: string;
  created_at: string;
}

// MEWS Triage Level Calculator
export function getMEWSTriage(p: Patient): { level: 1 | 2 | 3; label: string; bg: string; text: string } {
  if (p.fall || p.sos || (p.heart_rate && (p.heart_rate > 130 || p.heart_rate < 45)) || (p.spo2 && p.spo2 < 88)) {
    return { level: 1, label: "Level 1: Resuscitation / Immediate", bg: "bg-red-600 text-white border-red-700", text: "text-red-600" };
  }
  if (p.distress || p.abnormal || (p.heart_rate && (p.heart_rate > 110 || p.heart_rate < 55)) || (p.spo2 && p.spo2 < 93)) {
    return { level: 2, label: "Level 2: Emergency / Urgent", bg: "bg-amber-500 text-white border-amber-600", text: "text-amber-600" };
  }
  return { level: 3, label: "Level 3: Non-Urgent / Stable", bg: "bg-emerald-600 text-white border-emerald-700", text: "text-emerald-600" };
}

// --- JEV Deterioration Index (POST /api/v1/jev-triage) ---

export interface JEVContributor {
  factor: string;
  value: string;
  weighted_points: number;
}

export interface JEVTriageResponse {
  patient_id: string;
  deterioration_index: number;
  confidence_score: number;
  warmed_up: boolean;
  frames_analysed: number;
  contributors: JEVContributor[];
  escalate: boolean;
  severity: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  clinical_rationale: string;
  recommended_action: string;
  deterministic_triage?: {
    triage_level: string;
    jev_confidence: number;
    clinical_reasoning: string;
    recommended_action: string;
    deterministic_override: boolean;
  } | null;
  timestamp: string;
}

// --- Clinical record (GET /api/patient/{id}/record) ---

export interface MedicalTest {
  id: number;
  test_type: string;
  result_summary?: string | null;
  status: "COMPLETED" | "PENDING" | "ABNORMAL" | string;
  taken_at: string;
}

export interface PatientRecord {
  patient_id: string;
  identified: boolean;
  full_name?: string | null;
  age?: number | null;
  gender?: string | null;
  relation?: string | null;
  attendant_name?: string | null;
  attendant_phone?: string | null;
  blood_group?: string | null;
  allergies?: string | null;
  conditions?: string | null;
  medications?: string | null;
  notes?: string | null;
  admitted_at?: string | null;
  tests: MedicalTest[];
}
