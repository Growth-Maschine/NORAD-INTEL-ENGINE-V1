import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import Home from "./pages/Home";
import Discover from "./pages/Discover";
import Run from "./pages/Run";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/runs/:id" element={<Run />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyDetail />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
