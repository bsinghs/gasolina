import type { Status } from "../api/types";

const LABELS: Record<Status | "missing", string> = {
  draft: "Draft",
  submitted: "Submitted",
  returned: "Sent back",
  approved: "Approved",
  exported: "Exported",
  missing: "Missing",
};

export function StatusChip({ status }: { status: Status | "missing" }) {
  return <span className={`chip chip-${status}`}>{LABELS[status]}</span>;
}
