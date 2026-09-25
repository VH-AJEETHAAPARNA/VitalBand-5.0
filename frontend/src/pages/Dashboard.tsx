// src/pages/Dashboard.tsx – Enhanced Nurse Dashboard with camera glow, shimmer loading & tactile interactions
import React, { useState, useMemo } from "react";
import { usePatients } from "../hooks/usePatients";
import { PatientCard } from "../components/PatientCard";
import { PatientDetailModal } from "../components/PatientDetailModal";
import { DemoController } from "../components/DemoController";
import { WardMapView } from "../components/WardMapView";
import { SafeCameraStream } from "../components/SafeCameraStream";
import type { Patient } from "../lib/types";
import { t, type Lang } from "../lib/i18n";
import {
  Loader2, Search, Filter, AlertTriangle, CheckCircle, Users, Camera,
  Activity, ShieldAlert, RefreshCw, LayoutGrid, MapPin
} from "lucide-react";
import { cn } from "../lib/utils";

interface DashboardProps {
  lang: Lang;
  privacyMode?: boolean;
}

export function Dashboard({ lang, privacyMode = false }: DashboardProps) {
  const { data: patients, isLoading, error, refetch } = usePatients();
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "alert" | "normal">("all");
  const [viewMode, setViewMode] = useState<"grid" | "map">("grid");
  const [showLiveCamera, setShowLiveCamera] = useState(false);
  const [cameraConnecting, setCameraConnecting] = useState(true);

  const filteredPatients = useMemo(() => {
    if (!patients) return [];
    return patients.filter((p) => {
      const matchesSearch =
        p.patient_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.name && p.name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (p.rfid_uid && p.rfid_uid.toLowerCase().includes(searchQuery.toLowerCase()));

      const isAlert = p.fall || p.sos || p.distress || p.abnormal;

      if (!matchesSearch) return false;
      if (statusFilter === "alert") return isAlert;
      if (statusFilter === "normal") return !isAlert;
      return true;
    });
  }, [patients, searchQuery, statusFilter]);

  if (isLoading) {
  return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-2xl animate-shimmer border border-slate-200" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 rounded-2xl animate-shimmer border border-slate-200" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-2xl text-[#d92b2b] flex items-center justify-between shadow-sm">
        <div>
          <h4 className="font-bold text-base">Connection Disrupted</h4>
          <p className="text-sm text-red-600 mt-1">Unable to fetch patient status from FastAPI backend.</p>
        </div>
        <button
          onClick={() => refetch()}
          className="tactile-button px-4 py-2 bg-[#d92b2b] text-white font-bold text-xs rounded-xl shadow-md hover:bg-red-700 transition"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const alertCount = patients?.filter((p) => p.fall || p.sos || p.distress || p.abnormal).length ?? 0;
  const normalCount = (patients?.length ?? 0) - alertCount;
  const connectedWrist = patients?.filter((p) => p.wrist_connected).length ?? 0;

  return (
    <div className="space-y-6">
      {/* 1-Click Demo Trigger Controller for Live Presentations */}
      <DemoController onRefetchPatients={() => refetch()} lang={lang} />

      {/* Executive Stat Widgets */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Patients */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Monitored Ward</p>
            <h3 className="text-2xl font-black text-slate-800 mt-0.5">{patients?.length ?? 0}</h3>
          </div>
          <div className="p-3 bg-blue-50 text-[#0b2545] rounded-xl">
            <Users className="w-5 h-5" />
          </div>
        </div>

        {/* Active Emergency Alerts (Red strictly for active alerts) */}
        <div className={cn(
          "p-4 rounded-2xl border shadow-sm flex items-center justify-between transition-colors duration-200",
          alertCount > 0 ? "bg-red-50/90 border-red-200 shadow-red-100" : "bg-white border-slate-200/80"
        )}>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Emergency Alerts</p>
            <h3 className={cn("text-2xl font-black mt-0.5", alertCount > 0 ? "text-[#d92b2b]" : "text-slate-800")}>
              {alertCount}
            </h3>
          </div>
          <div className={cn("p-3 rounded-xl transition-colors duration-200", alertCount > 0 ? "bg-[#d92b2b] text-white animate-bounce" : "bg-slate-100 text-slate-500")}>
            <ShieldAlert className="w-5 h-5" />
          </div>
        </div>

        {/* Stable Patients */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Stable Status</p>
            <h3 className="text-2xl font-black text-[#1e8e3e] mt-0.5">{normalCount}</h3>
          </div>
          <div className="p-3 bg-emerald-50 text-[#1e8e3e] rounded-xl">
            <CheckCircle className="w-5 h-5" />
          </div>
        </div>

        {/* Live Wrist Connectivity */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Hardware Online</p>
            <h3 className="text-2xl font-black text-slate-800 mt-0.5">{connectedWrist}</h3>
          </div>
          <div className="p-3 bg-slate-100 text-slate-700 rounded-xl">
            <Activity className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Control Toolbar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm">
        {/* Search */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search Patient ID, Name, or RFID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0b2545]/20 focus:border-[#0b2545] transition"
          />
        </div>

        {/* View Mode & Filter Controls */}
        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto justify-between md:justify-end">
          {/* Grid vs Map Toggle */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "tactile-button px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all",
                viewMode === "grid" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"
              )}
            >
              <LayoutGrid className="w-3.5 h-3.5" /> Grid
            </button>
            <button
              onClick={() => setViewMode("map")}
              className={cn(
                "tactile-button px-2.5 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all",
                viewMode === "map" ? "bg-[#0b2545] text-white shadow-sm" : "text-slate-500 hover:text-slate-900"
              )}
            >
              <MapPin className="w-3.5 h-3.5" /> Spatial Map
            </button>
          </div>

          {/* Status Filter Buttons */}
          <div className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl">
            <button
              onClick={() => setStatusFilter("all")}
              className={cn(
                "tactile-button px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                statusFilter === "all"
                  ? "bg-[#0b2545] text-white shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              )}
            >
              All ({patients?.length ?? 0})
            </button>
            <button
              onClick={() => setStatusFilter("alert")}
              className={cn(
                "tactile-button px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1",
                statusFilter === "alert"
                  ? "bg-[#d92b2b] text-white shadow-sm"
                  : "text-[#d92b2b] hover:bg-red-50"
              )}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Alerts ({alertCount})
            </button>
            <button
              onClick={() => setStatusFilter("normal")}
              className={cn(
                "tactile-button px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                statusFilter === "normal"
                  ? "bg-[#1e8e3e] text-white shadow-sm"
                  : "text-[#1e8e3e] hover:bg-emerald-50"
              )}
            >
              Stable ({normalCount})
            </button>
          </div>

          {/* Live Camera Stream Toggle */}
          <button
            onClick={() => {
              setShowLiveCamera(!showLiveCamera);
              setCameraConnecting(true);
            }}
            className={cn(
              "tactile-button px-3 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 border transition-all shadow-sm",
              showLiveCamera
                ? "bg-[#0b2545] text-white border-[#0b2545]"
                : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
            )}
          >
            <Camera className="w-3.5 h-3.5" />
            {showLiveCamera ? "Hide Camera" : "Scan Camera"}
          </button>
        </div>
      </div>

      {/* Live Camera Stream Panel (SafeCameraStream with MediaPipe + HTML5 getUserMedia dual mode) */}
      {showLiveCamera && (
        <SafeCameraStream />
      )}

      {/* View Switch: Grid vs Spatial Map */}
      {viewMode === "map" ? (
        <WardMapView
          patients={patients ?? []}
          onSelectPatient={(p) => setSelectedPatient(p)}
          privacyMode={privacyMode}
          lang={lang}
        />
      ) : (
        <div className="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {filteredPatients.length > 0 ? (
            filteredPatients.map((p, idx) => (
              <PatientCard
                key={p.patient_id}
                patient={p}
                lang={lang}
                index={idx}
                onClick={() => setSelectedPatient(p)}
              />
            ))
          ) : (
            <div className="col-span-full text-center text-slate-500 py-16 bg-white rounded-2xl border border-slate-200">
              <Users className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              <p className="font-semibold text-slate-700">No Patient Records Found</p>
              <p className="text-xs text-slate-400 mt-1">
                {patients && patients.length > 0
                  ? "Try adjusting your search query or filter settings."
                  : "Waiting for telemetry POST from Wrist Patch or Scan Machine."}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Patient Detail & Recharts History Modal */}
      {selectedPatient && (
        <PatientDetailModal
          patient={selectedPatient}
          lang={lang}
          onClose={() => setSelectedPatient(null)}
        />
      )}
    </div>
  );
}
