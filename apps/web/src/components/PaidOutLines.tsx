import type { PaidOut, PaidOutKind } from "../api/types";

interface Props {
  kind: PaidOutKind;
  lines: PaidOut[];
  disabled: boolean;
  onChange: (lines: PaidOut[]) => void;
  /** Vendor names to suggest (already used at this store) */
  suggestions?: string[];
}

/** Editable list of paid-out lines of one kind (cash or check). */
export function PaidOutLines({ kind, lines, disabled, onChange, suggestions = [] }: Props) {
  const listId = `vendors-${kind}`;
  const title = kind === "cash" ? "Cash paid out" : "Check paid out";

  const update = (index: number, patch: Partial<PaidOut>) =>
    onChange(lines.map((line, i) => (i === index ? { ...line, ...patch } : line)));

  return (
    <div>
      <div className="lines-head">{title}</div>
      <datalist id={listId}>{suggestions.map((v) => <option key={v} value={v} />)}</datalist>
      {lines.map((line, i) => (
        <div className="line-item" key={i}>
          {kind === "check" && (
            <input className="li-no" aria-label={`${title} ${i + 1} check number`} placeholder="Check #"
              value={line.check_no ?? ""} disabled={disabled} onChange={(e) => update(i, { check_no: e.target.value })} />
          )}
          <input className="li-name" aria-label={`${title} ${i + 1} vendor name`} placeholder="Vendor name" list={listId}
            value={line.payee} disabled={disabled} onChange={(e) => update(i, { payee: e.target.value })} />
          <input className="li-amt" aria-label={`${title} ${i + 1} amount`} placeholder="0.00" inputMode="decimal"
            value={line.amount} disabled={disabled} onChange={(e) => update(i, { amount: e.target.value })} />
          {!disabled && (
            <button type="button" className="icon-btn" aria-label={`Remove ${title} ${i + 1}`}
              onClick={() => onChange(lines.filter((_, j) => j !== i))}>✕</button>
          )}
        </div>
      ))}
      {!disabled && (
        <button type="button" className="link-btn"
          onClick={() => onChange([...lines, { kind, check_no: "", payee: "", amount: "", gl_account: null }])}>
          + Add {title.toLowerCase()}
        </button>
      )}
    </div>
  );
}
