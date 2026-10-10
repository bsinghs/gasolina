// Small line at the bottom of every page: which version of the screens and the API is running.
// If they differ, one of them hasn't been deployed yet (shown in amber).
import { useEffect, useState } from "react";
import { api } from "../api/client";

export const SCREENS_VERSION = __APP_VERSION__;
export const SCREENS_COMMIT = __APP_COMMIT__;

export function VersionFooter() {
  const [apiVersion, setApiVersion] = useState<string | null>(null);
  useEffect(() => {
    api.health().then((h) => setApiVersion(h.version)).catch(() => setApiVersion(null));
  }, []);
  const mismatch = apiVersion !== null && apiVersion !== SCREENS_VERSION;
  return (
    <footer className={`version-footer${mismatch ? " mismatch" : ""}`}
      title={mismatch ? "The screens and the API are on different versions: one of them hasn't been deployed yet" : undefined}>
      Shift Close {SCREENS_VERSION} · screens {SCREENS_COMMIT} · API {apiVersion ?? "…"}
    </footer>
  );
}
