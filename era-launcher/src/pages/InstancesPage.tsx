import { useState, useEffect, type Dispatch, type SetStateAction } from "react";
import type { Config, LaunchState, InstanceConfig, DownloadProgress } from "../types";
import { createInstance, deleteInstance, updateInstance, launchInstance, prepareInstance, getAllVersions, getFabricLoaderVersions, getForgeVersions } from "../api";

interface InstancesPageProps {
  config: Config;
  refreshConfig: () => void;
  launchState: LaunchState;
  setLaunchState: Dispatch<SetStateAction<LaunchState>>;
  instancesDir: string;
  consoleLines: string[];
  setConsoleLines: Dispatch<SetStateAction<string[]>>;
  downloadProgress: DownloadProgress | null;
}

export default function InstancesPage({ config, refreshConfig, launchState, setLaunchState, instancesDir, consoleLines, setConsoleLines, downloadProgress }: InstancesPageProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [selectedAccount, setSelectedAccount] = useState(config.default_account || config.accounts[0]?.uuid || "");
   const [versions, setVersions] = useState<string[]>([]);
   const [loaderVersions, setLoaderVersions] = useState<string[]>([]);
   const [loadingVersions, setLoadingVersions] = useState(false);
   const [preparing, setPreparing] = useState(false);

   const [form, setForm] = useState({
     name: "",
     game_version: "1.21.5",
     loader: "vanilla",
     loader_version: undefined as string | undefined,
     memory: 4096,
   });

   useEffect(() => {
     getAllVersions().then(setVersions).catch(() => {});
   }, []);

   const fetchLoaderVersions = async (gameVersion: string, loader: string) => {
     if (!gameVersion || loader === "vanilla") {
       setLoaderVersions([]);
       return;
     }
     setLoadingVersions(true);
     try {
       if (loader === "fabric") {
         setLoaderVersions(await getFabricLoaderVersions(gameVersion));
       } else if (loader === "forge") {
         setLoaderVersions(await getForgeVersions(gameVersion));
       }
     } catch {
       setLoaderVersions([]);
     } finally {
       setLoadingVersions(false);
     }
   };

   const startCreate = () => {
      setForm({ name: "", game_version: versions[0] || "1.21.5", loader: "vanilla", loader_version: undefined, memory: 4096 });
     setShowCreate(true);
     setEditId(null);
   };

   const startEdit = (inst: any) => {
       setForm({ name: inst.name, game_version: inst.game_version, loader: inst.loader, loader_version: inst.loader_version ?? "", memory: inst.memory });
     setShowCreate(true);
     setEditId(inst.id);
     fetchLoaderVersions(inst.game_version, inst.loader);
   };

   const handleLoaderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
     const newLoader = e.target.value;
      setForm({ ...form, loader: newLoader, loader_version: "" });
      fetchLoaderVersions(form.game_version, newLoader);
   };

   const handleGameVersionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
     const newVer = e.target.value;
     setForm({ ...form, game_version: newVer });
     fetchLoaderVersions(newVer, form.loader);
   };

   const handleSave = async () => {
     if (!form.name.trim()) return;
      if (form.loader !== "vanilla" && form.loader_version === undefined) {
        alert("Please select a loader version");
        return;
      }
     setPreparing(true);
     try {
       let instance: InstanceConfig;
       if (editId) {
         const inst = config.instances.find((i) => i.id === editId);
         if (!inst) return;
          instance = { ...inst, name: form.name, game_version: form.game_version, loader: form.loader, loader_version: form.loader_version || undefined, memory: form.memory };
         await updateInstance(instance);
       } else {
         instance = {
           id: crypto.randomUUID(),
           name: form.name,
           game_version: form.game_version,
           loader: form.loader,
             loader_version: form.loader_version || undefined,
           memory: form.memory,
           java: undefined,
           game_dir: undefined,
           resolution_width: undefined,
           resolution_height: undefined,
           account_uuid: undefined,
           minecraft_dir: undefined,
         };
         await createInstance(instance);
       }
       await prepareInstance(instance, instancesDir);
       setShowCreate(false);
       refreshConfig();
     } catch (e) {
       setConsoleLines((prev) => [...prev, `Error: ${e}`]);
     } finally {
       setPreparing(false);
     }
   };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this instance?")) return;
    await deleteInstance(id);
    refreshConfig();
  };

  const handleLaunch = async (instanceId: string) => {
    const instance = config.instances.find((i) => i.id === instanceId);
    if (!instance) return;
    const account = config.accounts.find((a) => a.uuid === selectedAccount) || config.accounts[0];
    if (!account) {
      setConsoleLines((prev) => [...prev, "No account selected"]);
      return;
    }
    setLaunchState({ status: "launching" });
    setConsoleLines((prev) => [...prev, `Launching ${instance.name}...`]);
    try {
       const result = await launchInstance(
         {
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
         },
         instancesDir
       );
      setConsoleLines((prev) => [...prev, result.message]);
      if (result.success && result.java_path && result.java_path !== instance.java) {
        const updated = { ...instance, java: result.java_path };
        await updateInstance(updated);
        refreshConfig();
      }
    } catch (e) {
      setLaunchState({ status: "failed", message: String(e) });
      setConsoleLines((prev) => [...prev, `Error: ${e}`]);
    }
  };

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Instances</h2>
        <button className="btn btn-primary" onClick={startCreate}>+ New Instance</button>
      </div>
      {downloadProgress && !downloadProgress.is_complete && downloadProgress.total_bytes && (
        <div className="download-progress">
          <div className="download-progress-bar">
            <div
              className="download-progress-fill"
              style={{
                width: `${(downloadProgress.bytes_downloaded / downloadProgress.total_bytes) * 100}%`,
              }}
            />
          </div>
          <span className="download-filename">{downloadProgress.file}</span>
          <span className="download-bytes">
            {formatBytes(downloadProgress.bytes_downloaded)} / {formatBytes(downloadProgress.total_bytes)}
          </span>
        </div>
      )}
      {config.accounts.length > 0 && (
        <div className="form-group">
          <label>Account</label>
          <select value={selectedAccount} onChange={(e) => setSelectedAccount(e.target.value)}>
            {config.accounts.map((a) => (
              <option key={a.uuid} value={a.uuid}>{a.name}</option>
            ))}
          </select>
        </div>
      )}
      {config.instances.length === 0 ? (
        <div className="empty-state">
          <p>No instances yet</p>
          <p className="subtitle">Click "New Instance" to create your first Minecraft instance</p>
        </div>
      ) : (
        <div className="instance-grid">
          {config.instances.map((inst) => (
            <div key={inst.id} className="instance-card">
              <div className="instance-header">
                <span className="instance-icon">{inst.loader === "fabric" ? "🟦" : inst.loader === "forge" ? "🟧" : "⛏️"}</span>
                <h3>{inst.name}</h3>
              </div>
              <div className="instance-info">
                 <div>v{inst.game_version} ({inst.loader}{inst.loader_version ? ` ${inst.loader_version}` : ""})</div>
                 <div>{(inst.memory / 1024).toFixed(1)} GB RAM</div>
              </div>
              <div className="instance-actions">
                <button className={`btn btn-primary btn-sm${launchState.status === "launching" ? " btn-loading" : ""}`} disabled={launchState.status === "launching" || launchState.status === "running"} onClick={() => handleLaunch(inst.id)}>▶ Launch</button>
                <button className="btn btn-secondary btn-sm" onClick={() => startEdit(inst)}>Edit</button>
                <button className="btn btn-danger btn-sm" onClick={() => handleDelete(inst.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{editId ? "Edit Instance" : "New Instance"}</h3>
            <div className="form-group">
              <label>Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="My Instance" />
            </div>
             <div className="form-group">
               <label>Version</label>
               <select value={form.game_version} onChange={handleGameVersionChange}>
                 {versions.map((v) => (
                   <option key={v} value={v}>{v}</option>
                 ))}
               </select>
             </div>
             <div className="form-group">
               <label>Loader</label>
               <select value={form.loader} onChange={handleLoaderChange}>
                 <option value="vanilla">Vanilla</option>
                 <option value="fabric">Fabric</option>
                 <option value="forge">Forge</option>
               </select>
             </div>
             {form.loader !== "vanilla" && (
               <div className="form-group">
                 <label>Loader Version</label>
                 <select
                   value={form.loader_version}
                    onChange={(e) => setForm({ ...form, loader_version: e.target.value })}
                   disabled={loadingVersions}
                 >
                   <option value="">Auto-select latest</option>
                   {loaderVersions.map((v) => (
                     <option key={v} value={v}>{v}</option>
                   ))}
                 </select>
                 {loadingVersions && <span className="loading">Loading loader versions...</span>}
               </div>
             )}
            <div className="form-group">
              <label>Memory (MB)</label>
              <input type="number" value={form.memory} onChange={(e) => setForm({ ...form, memory: parseInt(e.target.value) || 4096 })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)} disabled={preparing}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave} disabled={preparing}>{preparing ? <><span className="spinner" style={{ marginRight: '6px' }}></span>Preparing... </> : "Save"}</button>
            </div>
          </div>
        </div>
      )}
      {consoleLines.length > 0 && (
        <div className="card console-card">
          <h3>Console Output</h3>
          <div className="console-output">
            {consoleLines.map((line: string, i: number) => (
              <div key={i} className="console-line">{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
