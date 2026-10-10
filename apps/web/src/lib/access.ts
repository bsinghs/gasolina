// Who may do what: the same table as the API (services/api/app/core/permissions.py).
// The API enforces it; the screens use it to show only the options a person can actually use.
import { useAuth } from "../auth/AuthProvider";
import type { Role } from "../api/types";

export type Permission = "see_all_stores" | "make_changes" | "manage_owners";

const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  owner: ["see_all_stores", "make_changes", "manage_owners"],
  admin: ["see_all_stores", "make_changes", "manage_owners"], // app support
  coowner: ["see_all_stores"], // sees everything, changes nothing
  manager: ["make_changes"], // own stores' worksheets
  employee: ["make_changes"],
};

export const can = (role: Role | string | undefined, permission: Permission) =>
  Boolean(role && ROLE_PERMISSIONS[role as Role]?.includes(permission));

/** True when nothing can be changed: a co-owner, or the admin viewing as someone. Hide change buttons then. */
export function useViewOnly(): boolean {
  const { me } = useAuth();
  return Boolean(me?.viewed_by_name) || !can(me?.role, "make_changes");
}
