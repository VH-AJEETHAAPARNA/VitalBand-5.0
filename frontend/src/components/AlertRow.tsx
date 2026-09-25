// Alert row component for alert feed
import type { AlertEvent } from "../lib/types";
import { Badge, severityVariant } from "./ui/Badge";
import { AlertTriangle, Info } from "lucide-react";

interface AlertRowProps {
  alert: AlertEvent;
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  SOS: <AlertTriangle className="w-4 h-4 text-red-600" />,
  FALL: <AlertTriangle className="w-4 h-4 text-red-500" />,
  DISTRESS: <AlertTriangle className="w-4 h-4 text-orange-500" />,
  ABNORMAL_VITALS: <Info className="w-4 h-4 text-yellow-500" />,
};

export function AlertRow({ alert: a }: AlertRowProps) {
  const icon = Object.entries(EVENT_ICONS).find(([key]) =>
    a.event_type.toUpperCase().includes(key)
  )?.[1] ?? <Info className="w-4 h-4 text-gray-400" />;

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-white hover:bg-gray-50 transition-colors">
      <div className="mt-0.5 flex-shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-sm text-gray-900">{a.event_type}</span>
          <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
          <span className="text-xs text-gray-500">Patient {a.patient_id}</span>
        </div>
        {a.details && (
          <div className="text-sm text-gray-600 mt-0.5 truncate">{a.details}</div>
        )}
        <div className="text-xs text-gray-400 mt-1">
          {new Date(a.timestamp).toLocaleString()}
        </div>
      </div>
    </div>
  );
}
