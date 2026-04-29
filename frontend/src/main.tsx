import React from "react";
import { createRoot } from "react-dom/client";

import "./i18n";
import "./styles/bit.css";
import App from "./App";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
