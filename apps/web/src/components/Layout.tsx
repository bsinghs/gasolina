import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { hasOwnerAccess, ROLE_NAMES, type Role } from "../api/types";
import { useAuth } from "../auth/AuthProvider";

const ROLE_LABEL: Record<string, string> = { owner: "Owners", coowner: "Co-owners", manager: "Managers", employee: "Employees" };

export function Layout() {
  const { me, signOut, viewAs } = useAuth();
  const navigate = useNavigate();
  const isOwner = hasOwnerAccess(me?.role);
  const isCoowner = me?.role === "coowner"; // sees every page, view only
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
  const options = me?.view_as_options ?? null; // only the app admin gets these
  const viewing = Boolean(me?.viewed_by_name);

  const switchTo = async (personId: string) => {
    await viewAs(personId || null);
    navigate("/"); // each role has a different home page
  };

  const groups = (["owner", "coowner", "manager", "employee"] as Role[])
    .map((role) => ({ role, people: (options ?? []).filter((o) => o.role === role) }))
    .filter((g) => g.people.length > 0);

  return (
    <>
      {viewing && (
        <div className="viewas-bar" role="status">
          <span>Viewing as <strong>{me?.name}</strong> ({me ? ROLE_NAMES[me.role].toLowerCase() : ""}) · read-only, nothing can be saved</span>
          <button className="btn btn-sm" onClick={() => switchTo("")}>Back to me</button>
        </div>
      )}
      {isCoowner && !viewing && (
        <div className="viewas-bar" role="status"><span><strong>View only.</strong> Co-owners can see everything but can&apos;t change anything.</span></div>
      )}
      <header className="topbar">
        <NavLink to="/" className="brand">Shift Close</NavLink>
        <nav aria-label="Main">
          {isOwner && <NavLink to="/inventory" className={link}>Inventory</NavLink>}
          {isOwner && <NavLink to="/review" className={link}>Review</NavLink>}
          <NavLink to="/worksheet" className={link}>Worksheet</NavLink>
          {!isOwner && <NavLink to="/my" className={link}>My days</NavLink>}
          {isOwner && <NavLink to="/reports" className={link}>Reports</NavLink>}
          {isOwner && <NavLink to="/export" className={link}>Export</NavLink>}
          {isOwner && <NavLink to="/people" className={link}>People</NavLink>}
          {isOwner && <NavLink to="/settings" className={link}>Settings</NavLink>}
        </nav>
        <div className="who">
          {options ? (
            <label className="viewas">
              <span className="sr-only">View as</span>
              <select value={viewing ? me?.id : ""} onChange={(e) => switchTo(e.target.value)} title="Admin only: see the app as someone else (read-only)">
                <option value="">{viewing ? me?.viewed_by_name : me?.name} · Admin</option>
                {groups.map((g) => (
                  <optgroup key={g.role} label={`View as: ${ROLE_LABEL[g.role]}`}>
                    {g.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </optgroup>
                ))}
              </select>
            </label>
          ) : (
            <span>{me?.name}</span>
          )}
          <button className="btn btn-ghost" style={{ minHeight: 36, fontSize: 12 }} onClick={signOut}>Sign out</button>
        </div>
      </header>
      <Outlet />
    </>
  );
}
