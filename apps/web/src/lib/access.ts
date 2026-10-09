// Who may change things. The API enforces it; the screens hide buttons that would be refused.
import { useAuth } from "../auth/AuthProvider";

/** True for a co-owner (sees everything, changes nothing) and while the admin is viewing as someone. */
export function useViewOnly(): boolean {
  const { me } = useAuth();
  return Boolean(me?.viewed_by_name) || me?.role === "coowner";
}
