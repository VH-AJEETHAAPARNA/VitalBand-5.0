// API client functions — all routes match the FastAPI backend

const BASE = "/api";

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("vb_token");
  if (token) return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  return { "Content-Type": "application/json" };
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options?.headers ?? {}) },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API error");
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => apiFetch<import("./types").User>("/auth/me"),

  patients: () => apiFetch<import("./types").Patient[]>("/patients"),

  patient: (id: string) => apiFetch<import("./types").Patient>(`/patient/${id}`),

  alerts: () => apiFetch<import("./types").AlertEvent[]>("/alerts"),

  history: () => apiFetch<import("./types").AlertEvent[]>("/history"),

  patientHistory: (id: string, limit = 60) =>
    apiFetch<import("./types").VitalsReading[]>(`/patient/${id}/history?limit=${limit}`),

  patientRecord: (id: string) =>
    apiFetch<import("./types").PatientRecord>(`/patient/${id}/record`),

  jevTriage: (body: {
    patient_id: string;
    heart_rate: (number | null)[];
    spo2: (number | null)[];
    motion?: (number | null)[];
    fall?: boolean;
    sos?: boolean;
  }) =>
    apiFetch<import("./types").JEVTriageResponse>("/v1/jev-triage", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
