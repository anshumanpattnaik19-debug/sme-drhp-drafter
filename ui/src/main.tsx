import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource/source-serif-4/400.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/400-italic.css";
import "./index.css";
import App from "./App";
import { ToastProvider } from "./components/ui";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppProvider } from "./lib/state";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AppProvider>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </AppProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
