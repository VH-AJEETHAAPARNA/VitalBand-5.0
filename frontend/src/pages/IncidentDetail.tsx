// src/pages/IncidentDetail.tsx – detailed view of a single alert/incident
import React from "react";
import { useParams } from "react-router-dom";
import { useAlertDetail } from "../hooks/useAlertDetail";
import { usePatient } from "../hooks/usePatients";
import { t, type Lang } from "../lib/i18n";
import { Loader2 } from "lucide-react";
import { Badge, severityVariant } from "../components/ui/Badge";

interface IncidentDetailProps {
  lang: Lang;
}

export function IncidentDetail({ lang }: IncidentDetailProps) {
  const { id } = useParams<{ id: string }>();
  const alertId = Number(id);
  const { data: alert, isLoading: alertLoading, error: alertError } = useAlertDetail(alertId);
  const patientId = alert?.patient_id;
  const { data: patient, isLoading: patientLoading, error: patientError } = usePatient(patientId ?? "");

  if (alertLoading || patientLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-6 h-6 animate-spin text-brand-navy" />
        <span className="ml-2 text-gray-600">{t("loading", lang) ?? "Loading..."}</span>
      </div>
    );
  }

  if (alertError || patientError) {
    return (
      <div className="p-4 text-red-600">
        {t("errorFetchingPatients", lang) ?? "Error loading data"}
      </div>
    );
  }

  if (!alert) {
    return <div className="p-4 text-gray-600">{t("noAlerts", lang)}</div>;
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* Alert header */}
      <div className="border rounded-lg p-4 bg-white shadow-sm">
        <h2 className="text-xl font-semibold mb-2">{t("incidentDetail", lang)}</h2>
        <div className="flex items-center gap-2 mb-2">
          <Badge variant={severityVariant(alert.severity)}>{alert.severity}</Badge>
          <span className="text-sm text-gray-500">{new Date(alert.timestamp).toLocaleString()}</span>
        </div>
        <p className="text-gray-800">{alert.event_type}: {alert.details ?? ""}</p>
      </div>

      {/* Patient vitals snapshot */}
      {patient && (
        <div className="border rounded-lg p-4 bg-white shadow-sm">
          <h3 className="text-lg font-medium mb-2">{t("patient", lang)}: {patient.name ?? patient.patient_id}</h3>
          <ul className="list-disc list-inside text-gray-700 space-y-1">
            <li>{t("heartRate", lang)}: {patient.heart_rate ?? "-"} {t("bpm", lang)}</li>
            <li>{t("spo2", lang)}: {patient.spo2 ?? "-"}%</li>
            <li>{t("fall", lang)}: {patient.fall ? t("fall", lang) : t("normal", lang)}</li>
            <li>{t("sos", lang)}: {patient.sos ? t("sos", lang) : t("ok", lang)}</li>
            <li>{t("distress", lang)}: {patient.distress ? t("distress", lang) : t("calm", lang)}</li>
          </ul>
        </div>
      )}
    </div>
  );
}
