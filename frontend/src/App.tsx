import { BrowserRouter, Route, Routes } from "react-router-dom";

import { DiagnosisPage } from "./pages/DiagnosisPage";
import { HomePage } from "./pages/HomePage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/diagnose" element={<DiagnosisPage />} />
      </Routes>
    </BrowserRouter>
  );
}
