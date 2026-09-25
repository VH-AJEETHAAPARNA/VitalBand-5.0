// Emergency alert banner — instant full-width flash on critical alert (~8s auto-dismiss)
import { useState, useEffect } from "react";
import { cn } from "../lib/utils";
import { X, Siren } from "lucide-react";

interface EmergencyBannerProps {
  message: string | null;
  onDismiss: () => void;
}

export function EmergencyBanner({ message, onDismiss }: EmergencyBannerProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (message) {
      // INSTANT appearance — no animated delay before it becomes visible
      setVisible(true);
      // Auto-dismiss after ~8 seconds (non-negotiable prompt requirement)
      const timer = setTimeout(() => {
        setVisible(false);
        onDismiss();
      }, 8000);
      return () => clearTimeout(timer);
    }
  }, [message, onDismiss]);

  if (!visible || !message) return null;

  return (
    <div
      className={cn(
        "fixed top-14 left-0 right-0 z-50 flex items-center justify-between shadow-2xl",
        "bg-[#d92b2b] text-white px-4 py-3 border-b border-red-700"
      )}
    >
      <div className="flex items-center gap-2 max-w-7xl mx-auto w-full justify-between">
        <div className="flex items-center gap-2">
          <Siren className="w-5 h-5 flex-shrink-0 animate-bounce" />
          <span className="font-extrabold text-sm tracking-wide">{message}</span>
        </div>
        <button
          onClick={() => { setVisible(false); onDismiss(); }}
          className="tactile-button text-white/80 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
