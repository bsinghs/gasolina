import { formatMoney, formatOverShort } from "../lib/money";

/** The big green / red / amber box from the prototype. */
export function OverShortGauge({ cents, hasCashDrop }: { cents: number; hasCashDrop: boolean }) {
  const kind = !hasCashDrop || cents === 0 ? "balanced" : cents < 0 ? "short" : "over";
  const sub = !hasCashDrop
    ? "Enter today's cash drop to reconcile"
    : cents === 0
      ? "Balanced"
      : cents < 0
        ? `Short by ${formatMoney(-cents)}`
        : `Over by ${formatMoney(cents)}`;
  return (
    <div className={`gauge g-${kind}`} aria-live="polite">
      <div className="g-label">OVER / (SHORT)</div>
      <div className="g-value">{formatOverShort(cents)}</div>
      <div className="g-sub">{sub}</div>
    </div>
  );
}
