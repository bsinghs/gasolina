import { MISCELLANEOUS, type PaidOut, type PaidOutKind, type VendorName } from "../api/types";
import { VendorPicker } from "./VendorPicker";

interface Props {
  kind: PaidOutKind;
  lines: PaidOut[];
  disabled: boolean;
  onChange: (lines: PaidOut[]) => void;
  /** The owner's vendor list. Empty = no list yet: any name can be typed (with suggestions) */
  vendors?: VendorName[];
  /** Vendor names already used at this store (only used while there's no vendor list) */
  suggestions?: string[];
}

const isMisc = (payee: string) => payee.trim().toLowerCase() === MISCELLANEOUS.toLowerCase();

/** Editable list of paid-out lines of one kind (cash or check). */
export function PaidOutLines({ kind, lines, disabled, onChange, vendors = [], suggestions = [] }: Props) {
  const listId = `vendors-${kind}`;
  const title = kind === "cash" ? "Cash paid out" : "Check paid out";
  const useList = vendors.length > 0;

  const update = (index: number, patch: Partial<PaidOut>) =>
    onChange(lines.map((line, i) => (i === index ? { ...line, ...patch } : line)));

  return (
    <div>
      <div className="lines-head">{title}</div>
      {!useList && <datalist id={listId}>{suggestions.map((v) => <option key={v} value={v} />)}</datalist>}
      {lines.map((line, i) => (
        <div key={i}>
          <div className="line-item">
            {kind === "check" && (
              <input className="li-no" aria-label={`${title} ${i + 1} check number`} placeholder="Check #"
                value={line.check_no ?? ""} disabled={disabled} onChange={(e) => update(i, { check_no: e.target.value })} />
            )}
            {useList ? (
              <VendorPicker label={`${title} ${i + 1} vendor`} value={line.payee} vendors={vendors} disabled={disabled}
                onChange={(payee) => update(i, { payee, note: isMisc(payee) ? line.note ?? "" : null })} />
            ) : (
              <input className="li-name" aria-label={`${title} ${i + 1} vendor name`} placeholder="Vendor name" list={listId}
                value={line.payee} disabled={disabled} onChange={(e) => update(i, { payee: e.target.value })} />
            )}
            <input className="li-amt" aria-label={`${title} ${i + 1} amount`} placeholder="0.00" inputMode="decimal"
              value={line.amount} disabled={disabled} onChange={(e) => update(i, { amount: e.target.value })} />
            {!disabled && (
              <button type="button" className="icon-btn" aria-label={`Remove ${title} ${i + 1}`}
                onClick={() => onChange(lines.filter((_, j) => j !== i))}>✕</button>
            )}
          </div>
          {(isMisc(line.payee) || line.note) && (
            <div className="line-note">
              <input aria-label={`${title} ${i + 1} note`} maxLength={300} disabled={disabled}
                className={isMisc(line.payee) && !line.note?.trim() ? "input-warn" : ""}
                placeholder="What was it, and who was paid? (needed for Miscellaneous)"
                value={line.note ?? ""} onChange={(e) => update(i, { note: e.target.value })} />
            </div>
          )}
        </div>
      ))}
      {!disabled && (
        <button type="button" className="link-btn"
          onClick={() => onChange([...lines, { kind, check_no: "", payee: "", amount: "", gl_account: null, note: null }])}>
          + Add {title.toLowerCase()}
        </button>
      )}
    </div>
  );
}
