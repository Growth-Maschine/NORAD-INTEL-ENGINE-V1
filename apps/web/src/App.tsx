import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import Home from "./pages/Home";
import Discover from "./pages/Discover";
import WebDiscovery from "./pages/WebDiscovery";
import WebDiscoveryCluster from "./pages/WebDiscoveryCluster";
import WebDiscoveryQueryNew from "./pages/WebDiscoveryQueryNew";
import WebDiscoveryQueryResults from "./pages/WebDiscoveryQueryResults";
import Run from "./pages/Run";
import Companies from "./pages/Companies";
import CompanyDetail from "./pages/CompanyDetail";
import DiscoveryClusters from "./pages/DiscoveryClusters";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/discover-web" element={<WebDiscovery />} />
        <Route path="/discover-web/clusters/:clusterId" element={<WebDiscoveryCluster />} />
        <Route
          path="/discover-web/clusters/:clusterId/queries/new"
          element={<WebDiscoveryQueryNew />}
        />
        <Route
          path="/discover-web/clusters/:clusterId/queries/:queryId"
          element={<WebDiscoveryQueryNew />}
        />
        <Route
          path="/discover-web/clusters/:clusterId/queries/:queryId/results"
          element={<WebDiscoveryQueryResults />}
        />
        <Route path="/discovery-clusters" element={<DiscoveryClusters />} />
        <Route path="/runs/:id" element={<Run />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyDetail />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
