// The invite list. Adding someone here is what allows them to sign in.

import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Person, Role, Store } from "../api/types";
import { Notice } from "../components/Notice";

type Draft = Omit<Person, "id" | "has_signed_in">;
const ROLE_LABEL: Record<Role, string> = { employee: "Employee", manager: "Manager", owner: "Owner", admin: "App admin (support)" };
const BLANK: Draft = { email: "", name: "", role: "employee", active: true, store_ids: [] };

export function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [error, setError] = useState<string | null>(null);

  const load = () => Promise.all([api.people.list(), api.stores.list()]).then(([p, s]) => { setPeople(p); setStores(s); });
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  const startEdit = (p: Person | null) => {
    setError(null);
    setEditing(p ? p.id : "new");
    setDraft(p ? { email: p.email, name: p.name, role: p.role, active: p.active, store_ids: p.store_ids } : BLANK);
  };

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (draft.role !== "owner" && draft.active && draft.store_ids.length === 0) {
      setError("Pick at least one store for this person (owners see all stores).");
      return;
    }
    try {
      if (editing === "new") await api.people.invite(draft);
      else if (editing) await api.people.update(editing, draft);
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    }
  };

  const toggleStore = (id: string) =>
    setDraft((d) => ({ ...d, store_ids: d.store_ids.includes(id) ? d.store_ids.filter((s) => s !== id) : [...d.store_ids, id] }));
  const storeName = (id: string) => stores.find((s) => s.id === id)?.name ?? "?";

  return (
    <main className="page stack">
      <div className="page-head">
        <div><h1>People</h1><div className="muted">Only people on this list can sign in. Add their Gmail; their name fills in from Google when they first sign in.</div></div>
        <button className="btn btn-primary" onClick={() => startEdit(null)}>+ Add person</button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}

      {editing && (
        <form className="card card-pad stack" onSubmit={save}>
          <div className="row-wrap">
            <label className="label-stack" style={{ flex: 1, minWidth: 220 }}>Gmail address
              <input className="text" type="email" required placeholder="name@gmail.com" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} /></label>
            <label className="label-stack" style={{ flex: 1, minWidth: 200 }}>Name (optional)
              <input className="text" placeholder="From their Google account" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
            <label className="label-stack">Role
              <select value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}>
                <option value="employee">Employee</option><option value="manager">Manager</option><option value="owner">Owner</option>
              </select></label>
          </div>
          <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
            <legend className="label-stack" style={{ marginBottom: 6 }}>Stores</legend>
            <div className="row-wrap">
              {stores.map((s) => (
                <label key={s.id} style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 14, minHeight: 36 }}>
                  <input type="checkbox" checked={draft.store_ids.includes(s.id)} onChange={() => toggleStore(s.id)} /> {s.name}
                </label>
              ))}
              {stores.length === 0 && <span className="muted">No stores yet. Add one in <a href="/settings">Settings</a> first.</span>}
              {draft.role === "owner" && stores.length > 0 && <span className="muted">Owners see all stores.</span>}
            </div>
          </fieldset>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
            <input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} /> Active (can sign in)
          </label>
          <div className="row-wrap">
            <button className="btn btn-primary" type="submit">{editing === "new" ? "Add" : "Save"}</button>
            <button className="btn btn-ghost" type="button" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </form>
      )}

      <div className="table-wrap">
        <table>
          <thead><tr><th className="left">Name</th><th className="left">Email</th><th className="left">Role</th><th className="left">Stores</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.id} style={p.active ? undefined : { opacity: 0.5 }}>
                <td className="left">{p.name}</td>
                <td className="left">{p.email}</td>
                <td className="left">{ROLE_LABEL[p.role] ?? p.role}</td>
                <td className="left">{p.role === "owner" || p.role === "admin" ? "All"
                  : p.store_ids.length ? p.store_ids.map(storeName).join(", ")
                  : <span className="neg">No store: Edit to add one</span>}</td>
                <td>{!p.active ? "Deactivated" : p.has_signed_in ? "Active" : "Invited"}</td>
                <td>{p.role === "admin"
                  ? <span className="muted" title="Runs the app and helps with support. Set up by the app, not on this page.">Managed by app</span>
                  : <button className="link-btn" onClick={() => startEdit(p)}>Edit</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
