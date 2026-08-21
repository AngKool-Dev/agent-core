import { useState, useEffect } from "react";
import type { Page, Config, LaunchState } from "./types";
import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";
import InstancesPage from "./pages/InstancesPage";
import ModsPage from "./pages/ModsPage";
import SettingsPage from "./pages/SettingsPage";
import AccountsPage from "./pages/AccountsPage";

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [config, setConfig] = useState<Config | null>(null);
  const [launchState, setLaunchState] = useState<LaunchState>({ status: "idle" });

      useEffect(() => {
    import("./api").then(({ getConfig }) =>
      getConfig().then(setConfig).catch(console.error)
    );
  }, []);

  const refreshConfig = () => {
    import("./api").then(({ getConfig }) =>
      getConfig().then(setConfig).catch(console.error)
    );
  };

  const renderPage = () => {
    if (!config) return <div className="loading">Loading...</div>;
    switch (page) {
      case "home":
        return <HomePage config={config} refreshConfig={refreshConfig} launchState={launchState} setLaunchState={setLaunchState} />;
      case "instances":
        return <InstancesPage config={config} refreshConfig={refreshConfig} launchState={launchState} setLaunchState={setLaunchState} />;
      case "mods":
        return <ModsPage config={config} />;
      case "settings":
        return <SettingsPage config={config} refreshConfig={refreshConfig} />;
      case "accounts":
        return <AccountsPage config={config} refreshConfig={refreshConfig} />;
    }
  };

  return (
    <div className="app">
      <Sidebar currentPage={page} onNavigate={setPage} launchState={launchState} />
      <main className="main-content">{renderPage()}</main>
    </div>
  );
}
