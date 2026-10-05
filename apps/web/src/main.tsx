import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthProvider";
import { EnvBanner } from "./components/EnvBanner";
import { APP_ENV, IS_DEMO, IS_TEST } from "./lib/env";
import "./styles.css";

if (IS_TEST || IS_DEMO) {
  document.title = `[${APP_ENV.toUpperCase()}] ${document.title}`;
  document.body.classList.add(`env-${APP_ENV}`);
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <EnvBanner />
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
