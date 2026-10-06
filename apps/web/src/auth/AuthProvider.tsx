// Sign-in state for the whole app.
//   - "supabase" mode: Google or emailed link through Supabase Auth; the token is sent to our API.
//   - "dev" mode: type any invited email (local testing only).

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api, setAuthHeaderSource } from "../api/client";
import type { Me } from "../api/types";

export const AUTH_MODE = (import.meta.env.VITE_AUTH_MODE ?? "dev") as "dev" | "supabase";

const supabase: SupabaseClient | null =
  AUTH_MODE === "supabase"
    ? createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_ANON_KEY)
    : null;

const DEV_EMAIL_KEY = "gasolina.devEmail";

function readDevEmail(): string | null {
  try {
    return localStorage.getItem(DEV_EMAIL_KEY);
  } catch {
    return null;
  }
}

function writeDevEmail(email: string | null) {
  try {
    if (email) localStorage.setItem(DEV_EMAIL_KEY, email);
    else localStorage.removeItem(DEV_EMAIL_KEY);
  } catch {
    /* storage blocked: stays signed in for this tab only */
  }
}

let devEmail: string | null = readDevEmail();

// App admin's "View as": which person to look at the app as (read-only). Per browser tab.
const VIEW_AS_KEY = "gasolina.viewAs";
let viewAsId: string | null = (() => {
  try {
    return sessionStorage.getItem(VIEW_AS_KEY);
  } catch {
    return null;
  }
})();
function writeViewAs(id: string | null) {
  viewAsId = id;
  try {
    if (id) sessionStorage.setItem(VIEW_AS_KEY, id);
    else sessionStorage.removeItem(VIEW_AS_KEY);
  } catch {
    /* storage blocked: lasts until reload */
  }
}
const viewAsHeader = (): Record<string, string> => (viewAsId ? { "X-View-As": viewAsId } : {});

setAuthHeaderSource(async (): Promise<Record<string, string>> => {
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}`, ...viewAsHeader() } : {};
  }
  return devEmail ? { "X-Dev-Email": devEmail, ...viewAsHeader() } : {};
});

type Status = "loading" | "signed_out" | "not_invited" | "signed_in" | "error";

interface AuthValue {
  status: Status;
  me: Me | null;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  sendEmailLink: (email: string) => Promise<void>;
  devSignIn: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
  /** App admin only: look at the app as this person (read-only); null = back to yourself */
  viewAs: (personId: string | null) => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      setMe(await api.me());
      setStatus("signed_in");
    } catch (e) {
      if (viewAsId && e instanceof ApiError && (e.status === 403 || e.status === 404)) {
        writeViewAs(null); // that person was removed, or you're no longer admin: back to yourself
        return refresh();
      }
      setMe(null);
      if (e instanceof ApiError && e.status === 403) setStatus("not_invited");
      else if (e instanceof ApiError && e.status === 401) setStatus("signed_out");
      else {
        setError(e instanceof Error ? e.message : "Couldn't reach the server");
        setStatus("error");
      }
    }
  }, []);

  useEffect(() => {
    if (supabase) {
      const { data } = supabase.auth.onAuthStateChange((_event, session) => {
        if (session) refresh();
        else {
          setMe(null);
          setStatus("signed_out");
        }
      });
      return () => data.subscription.unsubscribe();
    }
    if (devEmail) refresh();
    else setStatus("signed_out");
  }, [refresh]);

  const value: AuthValue = {
    status,
    me,
    error,
    refresh,
    signInWithGoogle: async () => {
      await supabase?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });
    },
    sendEmailLink: async (email) => {
      if (!supabase) return;
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: window.location.origin, shouldCreateUser: true },
      });
      if (error) throw error;
    },
    devSignIn: async (email) => {
      devEmail = email.trim();
      writeDevEmail(devEmail);
      setStatus("loading");
      await refresh();
    },
    viewAs: async (personId) => {
      writeViewAs(personId);
      await refresh();
    },
    signOut: async () => {
      writeViewAs(null);
      if (supabase) await supabase.auth.signOut();
      devEmail = null;
      writeDevEmail(null);
      setMe(null);
      setStatus("signed_out");
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be inside AuthProvider");
  return value;
}
