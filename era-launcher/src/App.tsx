import { useState, useEffect } from "react";
import type { Page, Config, LaunchState, DownloadProgress } from "./types";
import { listen } from "@tauri-apps/api/event";
import Sidebar from "./components/Sidebar";
import HomePage from "./pages/HomePage";
import InstancesPage from "./pages/InstancesPage";
import ModsPage from "./pages/ModsPage";
import SettingsPage from "./pages/SettingsPage";
import AccountsPage from "./pages/AccountsPage";
import InstallPage from "./pages/InstallPage";

interface MinecraftStatusPayload {
  status: string;
  message: string;
}

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [config, setConfig] = useState<Config | null>(null);
  const [launchState, setLaunchState] = useState<LaunchState>({ status: "idle" });
  const [instancesDir, setInstancesDir] = useState("");
  const [consoleLines, setConsoleLines] = useState<string[]>([]);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);

  useEffect(() => {
    import("./api").then(({ getConfig, getInstancesDir }) =>
      Promise.all([getConfig(), getInstancesDir()])
        .then(([cfg, dir]) => {
          setConfig(cfg);
          setInstancesDir(dir);
        })
        .catch(console.error)
    );

    const savedTheme = localStorage.getItem("theme");
    const systemPrefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const theme = savedTheme || (systemPrefersDark ? "dark" : "light");
    const effectiveTheme = theme === "system" ? (systemPrefersDark ? "dark" : "light") : theme;
    applyTheme(effectiveTheme);
  }, []);

    function applyTheme(theme: string) {
      const body = document.body;
      if (theme === "dark") {
        body.classList.add("dark");
      } else {
        body.classList.remove("dark");
      }
    }

    useEffect(() => {
      const statusUnlisten = listen<MinecraftStatusPayload>("minecraft:status", (event) => {
      const { status, message } = event.payload;
      setLaunchState((prev) => ({
        ...prev,
        status: mapBackendStatus(status),
        message,
      }));
    });

    const stdoutUnlisten = listen<string>("minecraft:stdout", (event) => {
      setConsoleLines((prev) => [...prev, event.payload]);
    });

    const stderrUnlisten = listen<string>("minecraft:stderr", (event) => {
      setConsoleLines((prev) => [...prev, `[stderr] ${event.payload}`]);
    });

    const exitUnlisten = listen<number>("minecraft:exit", (event) => {
      setLaunchState((prev) => ({
        ...prev,
        status: "stopped",
        message: `Minecraft exited (PID ${event.payload})`,
      }));
      setConsoleLines((prev) => [...prev, `Process exited (PID ${event.payload})`]);
    });

    const downloadUnlisten = listen<DownloadProgress>("minecraft:download", (event) => {
      const { file, bytes_downloaded, total_bytes, is_complete } = event.payload;
      setDownloadProgress({
        file,
        bytes_downloaded,
        total_bytes,
        is_complete,
      });
      if (is_complete) {
        setConsoleLines((prev) => [...prev, `Downloaded: ${file}`]);
      }
    });

    return () => {
      statusUnlisten.then((f) => f());
      stdoutUnlisten.then((f) => f());
      stderrUnlisten.then((f) => f());
      exitUnlisten.then((f) => f());
      downloadUnlisten.then((f) => f());
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'L') {
        e.preventDefault();
        if (config && config.instances.length > 0 && config.accounts.length > 0) {
          const instance = config.instances.find(i => i.loader === "fabric") || config.instances[0];
          const account = config.accounts.find((a) => a.uuid === config.default_account) || config.accounts[0];
          if (instance && account) {
            import("./api").then(({ launchInstance }) => {
              launchInstance({
                instance_id: instance.id,
                account_name: account.name,
                account_uuid: account.uuid,
                java_path: instance.java,
                minecraft_dir: instance.minecraft_dir,
                fresh: false,
                memory: instance.memory,
                game_version: instance.game_version,
                loader: instance.loader,
                loader_version: instance.loader_version,
              }, instancesDir);
            });
          }
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [config, instancesDir]);

  function mapBackendStatus(status: string): LaunchState["status"] {
    switch (status) {
      case "PREPARING":
        return "launching";
      case "DOWNLOADING":
        return "launching";
      case "VERIFYING":
        return "launching";
      case "LAUNCHING":
        return "launching";
      case "RUNNING":
        return "running";
      case "FAILED":
        return "failed";
      case "STOPPED":
        return "finished";
      default:
        return "idle";
    }
  }

  const refreshConfig = () => {
    import("./api").then(({ getConfig }) =>
      getConfig().then(setConfig).catch(console.error)
    );
  };

  const renderPage = () => {
    if (!config) return <div className="loading">Loading...</div>;
    switch (page) {
      case "home":
        return <HomePage config={config} refreshConfig={refreshConfig} launchState={launchState} setLaunchState={setLaunchState} instancesDir={instancesDir} consoleLines={consoleLines} setConsoleLines={setConsoleLines} downloadProgress={downloadProgress} />;
      case "instances":
        return <InstancesPage config={config} refreshConfig={refreshConfig} launchState={launchState} setLaunchState={setLaunchState} instancesDir={instancesDir} consoleLines={consoleLines} setConsoleLines={setConsoleLines} downloadProgress={downloadProgress} />;
        case "mods":
          return <ModsPage config={config} instancesDir={instancesDir} />;
      case "settings":
        return <SettingsPage config={config} refreshConfig={refreshConfig} />;
      case "accounts":
        return <AccountsPage config={config} refreshConfig={refreshConfig} />;
      case "install":
        return <InstallPage />;
    }
  };

  return (
    <div className="app">
      <Sidebar currentPage={page} onNavigate={setPage} launchState={launchState} />
      <main className="main-content">{renderPage()}</main>
    </div>
  );
}
