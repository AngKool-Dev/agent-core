import { useState } from "react";
import type { Config, LaunchState } from "../types";
import { createInstance, deleteInstance, updateInstance, launchInstance } from "../api";

interface InstancesPageProps {
  config: Config;
  refreshConfig: () => void;
  launchState: LaunchState;
  setLaunchState: (s: LaunchState) => void;
}

export default function InstancesPage({ config, refreshConfig, launchState, setLaunchState }: InstancesPageProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [selectedAccount, setSelectedAccount] = useState(config.default_account || config.accounts[0]?.uuid || "");
  const [consoleLog, setConsoleLog] = useState<string[]>([]);

  const [form, setForm] = useState({
    name: "",
    game_version: "1.21.1",
    loader: "vanilla",
    memory: 4096,
  });

  const startCreate = () => {
    setForm({ name: "", game_version: "1.21.1", loader: "vanilla", memory: 4096 });
    setShowCreate(true);
    setEditId(null);
  };

  const startEdit = (inst: any) => {
    setForm({ name: inst.name, game_version: inst.game_version, loader: inst.loader, memory: inst.memory });
    setEditId(inst.id);
    setShowCreate(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) return;
    if (editId) {
      const inst = config.instances.find((i) => i.id === editId);
      if (inst) {
        await updateInstance({ ...inst, name: form.name, game_version: form.game_version, loader: form.loader, memory: form.memory });
      }
    } else {
      await createInstance({
        id: crypto.randomUUID(),
        name: form.name,
        game_version: form.game_version,
        loader: form.loader,
        memory: form.memory,
        loader_version: undefined,
        java: undefined,
        game_dir: undefined,
        resolution_width: undefined,
        resolution_height: undefined,
        account_uuid: undefined,
        minecraft_dir: undefined,
      });
    }
    setShowCreate(false);
    refreshConfig();
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
      setConsoleLog((prev) => [...prev, "No account selected"]);
      return;
    }
    setLaunchState({ status: "launching" });
    setConsoleLog((prev) => [...prev, `Launching ${instance.name}...`]);
    try {
      const result = await launchInstance({
        instance_id: instance.id,
        account_name: account.name,
        account_uuid: account.uuid,
        java_path: instance.java,
        minecraft_dir: instance.minecraft_dir,
        fresh: false,
        memory: instance.memory,
        game_version: instance.game_version,
      });
      setLaunchState({ status: result.success ? "finished" : "failed", exitCode: result.exit_code, message: result.message });
      setConsoleLog((prev) => [...prev, result.message]);
    } catch (e) {
      setLaunchState({ status: "failed", message: String(e) });
      setConsoleLog((prev) => [...prev, `Error: ${e}`]);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Instances</h2>
        <button className="btn btn-primary" onClick={startCreate}>+ New Instance</button>
      </div>
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
                <div>v{inst.game_version} ({inst.loader})</div>
                <div>{(inst.memory / 1024).toFixed(1)} GB RAM</div>
              </div>
              <div className="instance-actions">
                <button className="btn btn-primary btn-sm" disabled={launchState.status === "launching" || launchState.status === "running"} onClick={() => handleLaunch(inst.id)}>▶ Launch</button>
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
              <select value={form.game_version} onChange={(e) => setForm({ ...form, game_version: e.target.value })}>
                <option value="1.21.1">1.21.1</option>
                <option value="1.20.4">1.20.4</option>
                <option value="1.20.1">1.20.1</option>
              </select>
            </div>
            <div className="form-group">
              <label>Loader</label>
              <select value={form.loader} onChange={(e) => setForm({ ...form, loader: e.target.value })}>
                <option value="vanilla">Vanilla</option>
                <option value="fabric">Fabric</option>
                <option value="forge">Forge</option>
              </select>
            </div>
            <div className="form-group">
              <label>Memory (MB)</label>
              <input type="number" value={form.memory} onChange={(e) => setForm({ ...form, memory: parseInt(e.target.value) || 4096 })} />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave}>Save</button>
            </div>
          </div>
        </div>
      )}
      {consoleLog.length > 0 && (
        <div className="card console-card">
          <h3>Console Output</h3>
          <div className="console-output">
            {consoleLog.map((line, i) => (
              <div key={i} className="console-line">{line}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
