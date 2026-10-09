// Searchable vendor dropdown for a paid-out line: type part of a name, pick from the owner's vendor list,
// or pick "Miscellaneous" (the line then asks for a note). The API checks the same rule when the day is submitted.

import { useId, useMemo, useRef, useState } from "react";
import { MISCELLANEOUS, type VendorName } from "../api/types";

const key = (s: string) => s.toLowerCase().split(/\s+/).filter(Boolean).join(" ");

interface Props {
  value: string;
  vendors: VendorName[];
  disabled: boolean;
  label: string;
  onChange: (name: string) => void;
}

export function VendorPicker({ value, vendors, disabled, label, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null); // what's typed while searching; null = show the value
  const [active, setActive] = useState(0);
  const listId = useId();
  const box = useRef<HTMLDivElement>(null);

  const query = key(text ?? "");
  const options = useMemo(() => {
    const matches = vendors.filter((v) => !query || key(v.name).includes(query)).map((v) => v.name);
    return [...matches, MISCELLANEOUS];
  }, [vendors, query]);

  const known = !value || key(value) === key(MISCELLANEOUS) || vendors.some((v) => key(v.name) === key(value));

  const choose = (name: string) => {
    onChange(name);
    setText(null);
    setOpen(false);
  };

  const close = () => {
    // Typed an exact name (any case)? Use the list's spelling. Otherwise keep the old value.
    if (text !== null) {
      const exact = [...vendors.map((v) => v.name), MISCELLANEOUS].find((n) => key(n) === key(text));
      if (exact) onChange(exact);
      else if (!text.trim()) onChange("");
    }
    setText(null);
    setOpen(false);
  };

  return (
    <div className="vendor-picker li-name" ref={box}
      onBlur={(e) => { if (!box.current?.contains(e.relatedTarget as Node)) close(); }}>
      <input
        role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-label={label}
        className={known ? "" : "input-warn"} placeholder="Search vendor…" disabled={disabled}
        value={text ?? value}
        onFocus={() => { setOpen(true); setActive(0); }}
        onChange={(e) => { setText(e.target.value); setOpen(true); setActive(0); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, options.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && open) { e.preventDefault(); choose(options[active]); }
          else if (e.key === "Escape") { setText(null); setOpen(false); }
        }}
      />
      {open && !disabled && (
        <ul id={listId} role="listbox" className="vendor-options">
          {options.length === 1 && <li className="vendor-empty" aria-disabled>No vendor matches “{text}”</li>}
          {options.map((name, i) => (
            <li key={name} role="option" aria-selected={i === active} tabIndex={-1}
              className={`${i === active ? "on" : ""}${name === MISCELLANEOUS ? " misc" : ""}`}
              onMouseDown={(e) => e.preventDefault()} onClick={() => choose(name)}>
              {name === MISCELLANEOUS ? "Miscellaneous (not on the list: add a note)" : name}
            </li>
          ))}
        </ul>
      )}
      {!known && <div className="field-warn">Not on the vendor list. Pick one, or Miscellaneous with a note.</div>}
    </div>
  );
}
