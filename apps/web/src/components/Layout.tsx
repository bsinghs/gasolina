import { NavLink, Outlet } from "react-router-dom";
import { hasOwnerAccess } from "../api/types";
import { useAuth } from "../auth/AuthProvider";

export function Layout() {
  const { me, signOut } = useAuth();
  const isOwner = hasOwnerAccess(me?.role);
  const link = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">Shift Close</NavLink>
        <nav aria-label="Main">
          {isOwner && <NavLink to="/review" className={link}>Review</NavLink>}
          <NavLink to="/worksheet" className={link}>Worksheet</NavLink>
          {!isOwner && <NavLink to="/my" className={link}>My days</NavLink>}
          {isOwner && <NavLink to="/export" className={link}>Export</NavLink>}
          {isOwner && <NavLink to="/people" className={link}>People</NavLink>}
          {isOwner && <NavLink to="/settings" className={link}>Settings</NavLink>}
        </nav>
        <div className="who">
          <span>{me?.name}{me?.role === "admin" ? " · Admin" : ""}</span>
          <button className="btn btn-ghost" style={{ minHeight: 36, fontSize: 12 }} onClick={signOut}>Sign out</button>
        </div>
      </header>
      <Outlet />
    </>
  );
}
