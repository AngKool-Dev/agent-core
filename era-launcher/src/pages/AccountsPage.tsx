import { useState } from "react";
import type { Config } from "../types";
import { saveConfig } from "../api";

interface AccountsPageProps {
  config: Config;
  refreshConfig: () => void;
}

export default function AccountsPage({ config, refreshConfig }: AccountsPageProps) {
  const [showAdd, setShowAdd] = useState(false);
  const [username, setUsername] = useState("");

  const handleCreate = async () => {
    if (!username.trim()) return;
    const id = crypto.randomUUID();
    const account = {
      id,
      name: username.trim(),
      uuid: id,
      type: "offline" as const,
      created_at: Date.now(),
    };
    await saveConfig({ ...config, accounts: [...config.accounts, account] });
    setUsername("");
    setShowAdd(false);
    refreshConfig();
  };

  const handleDelete = async (uuid: string) => {
    if (!confirm("Delete this account?")) return;
    await saveConfig({ ...config, accounts: config.accounts.filter((a) => a.uuid !== uuid) });
    refreshConfig();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Accounts</h2>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>+ Add Account</button>
      </div>
      {config.accounts.length === 0 ? (
        <div className="empty-state">
          <p>No accounts yet</p>
          <p className="subtitle">Add an account to start playing</p>
        </div>
      ) : (
        <div className="accounts-list">
          {config.accounts.map((account) => (
            <div key={account.uuid} className="account-card">
              <div className="account-info">
                <div className="account-name">{account.name}</div>
                <div className="account-meta">{account.uuid.slice(0, 8)}... · {account.type} · {new Date(account.created_at).toLocaleDateString()}</div>
              </div>
              <button className="btn btn-danger btn-sm" onClick={() => handleDelete(account.uuid)}>Delete</button>
            </div>
          ))}
        </div>
      )}
      {showAdd && (
        <div className="modal-overlay" onClick={() => setShowAdd(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New Offline Account</h3>
            <div className="form-group">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Player" />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
