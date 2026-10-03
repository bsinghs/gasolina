import type { ReactNode } from "react";

export function Notice({ kind, children }: { kind: "error" | "warn" | "ok" | "info"; children: ReactNode }) {
  return (
    <div className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}
