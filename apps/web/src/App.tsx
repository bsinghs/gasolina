// Screens and who can see them.

import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthProvider";
import { Layout } from "./components/Layout";
import { Notice } from "./components/Notice";
import { DayDetailPage } from "./pages/DayDetailPage";
import { ExportPage } from "./pages/ExportPage";
import { MyDaysPage } from "./pages/MyDaysPage";
import { PeoplePage } from "./pages/PeoplePage";
import { ReviewPage } from "./pages/ReviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { NotInvitedPage, SignInPage } from "./pages/SignInPage";
import { WorksheetPage } from "./pages/WorksheetPage";

function OwnerOnly({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  return me?.role === "owner" ? <>{children}</> : <Navigate to="/worksheet" replace />;
}

export function App() {
  const { status, me, error } = useAuth();

  if (status === "loading") return <main className="page"><p className="muted">Loading…</p></main>;
  if (status === "signed_out") return <SignInPage />;
  if (status === "not_invited") return <NotInvitedPage />;
  if (status === "error") return <main className="page"><Notice kind="error">{error}</Notice></main>;

  const home = me?.role === "owner" ? "/review" : "/worksheet";
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to={home} replace />} />
        <Route path="/worksheet" element={<WorksheetPage />} />
        <Route path="/my" element={<MyDaysPage />} />
        <Route path="/review" element={<OwnerOnly><ReviewPage /></OwnerOnly>} />
        <Route path="/days/:id" element={<OwnerOnly><DayDetailPage /></OwnerOnly>} />
        <Route path="/export" element={<OwnerOnly><ExportPage /></OwnerOnly>} />
        <Route path="/people" element={<OwnerOnly><PeoplePage /></OwnerOnly>} />
        <Route path="/settings" element={<OwnerOnly><SettingsPage /></OwnerOnly>} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Route>
    </Routes>
  );
}
