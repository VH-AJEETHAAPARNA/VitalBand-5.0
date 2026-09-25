// Status badge component
import { cn } from "../../lib/utils";

interface BadgeProps {
  variant: "ok" | "warning" | "critical" | "info";
  children: React.ReactNode;
  className?: string;
}

const variants = {
  ok: "bg-green-100 text-green-800 border-green-300",
  warning: "bg-yellow-100 text-yellow-800 border-yellow-300",
  critical: "bg-red-100 text-red-800 border-red-300",
  info: "bg-blue-100 text-blue-800 border-blue-300",
};

export function Badge({ variant, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

// Helper to pick badge variant from severity
export function severityVariant(severity: string): BadgeProps["variant"] {
  if (severity === "CRITICAL") return "critical";
  if (severity === "WARNING") return "warning";
  return "info";
}
