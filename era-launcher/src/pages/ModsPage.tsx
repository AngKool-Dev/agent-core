import { useState, useEffect } from "react";
import type { Config } from "../types";
import { searchModrinth, getModVersions, installMod } from "../api";

interface ModsPageProps {
  config: Config;
  instancesDir: string;
}

type ContentType = "mod" | "modpack" | "resourcepack" | "shader";

export default function ModsPage({ config, instancesDir }: ModsPageProps) {
  const [query, setQuery] = useState("");
  const [contentType, setContentType] = useState<ContentType>("mod");
  const [gameVersion, setGameVersion] = useState("");
  const [loader, setLoader] = useState("");
  const [installTarget, setInstallTarget] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedProject, setSelectedProject] = useState<any>(null);
  const [versions, setVersions] = useState<any[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<{ file: string; percent: number } | null>(null);

  useEffect(() => {
    if (!installTarget && config.instances.length > 0) {
      setInstallTarget(config.instances[0].id);
    }
  }, [config.instances, installTarget]);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const hits = await searchModrinth({ query, contentType, gameVersion, loader });
      setResults(hits);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetails = async (project: any) => {
    setSelectedProject(project);
    setLoadingVersions(true);
    try {
      const vs = await getModVersions(project.id);
      setVersions(vs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleInstall = async (version: any) => {
    if (!installTarget) return;
    const file = version.files?.[0];
    if (!file) return;
    setDownloadProgress({ file: file.filename, percent: 0 });
    try {
      await installMod({
        projectId: selectedProject.id,
        versionId: version.id,
        fileUrl: file.url,
        fileName: file.filename,
        instanceId: installTarget,
        contentType,
        instancesDir: instancesDir,
      });
      setDownloadProgress({ file: file.filename, percent: 100 });
      setTimeout(() => setDownloadProgress(null), 2000);
    } catch (e) {
      console.error(e);
      setDownloadProgress(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Mods</h2>
        <span className="subtitle">Browse Modrinth</span>
      </div>
      <div className="card filter-card">
        <div className="filter-row">
          <div className="search-box">
            <input
              placeholder="Search..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button className="btn btn-primary" onClick={handleSearch}>Search</button>
          </div>
          <select value={contentType} onChange={(e) => setContentType(e.target.value as ContentType)}>
            <option value="mod">Mods</option>
            <option value="modpack">Modpacks</option>
            <option value="resourcepack">Resource Packs</option>
            <option value="shader">Shaders</option>
          </select>
          <input placeholder="MC Version" value={gameVersion} onChange={(e) => setGameVersion(e.target.value)} />
          <input placeholder="Loader" value={loader} onChange={(e) => setLoader(e.target.value)} />
          <select value={installTarget} onChange={(e) => setInstallTarget(e.target.value)}>
            <option value="">Select instance</option>
            {config.instances.map((i) => (
              <option key={i.id} value={i.id}>{i.name}</option>
            ))}
          </select>
        </div>
      </div>
      {loading && <div className="loading">Loading...</div>}
      {results.length === 0 && !loading && (query || gameVersion || loader) && <div className="empty-state"><p>No results found. Try adjusting your search filters.</p></div>}
      {downloadProgress && (
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${downloadProgress.percent}%` }} />
          <span>{downloadProgress.file} {downloadProgress.percent}%</span>
        </div>
      )}
      <div className="results-grid">
        {results.map((project) => (
          <div key={project.id} className="result-card">
            {project.icon_url && <img src={project.icon_url} alt={project.title} className="result-icon" />}
            <h4>{project.title}</h4>
            <p className="result-author">{project.author}</p>
            <p className="result-desc">{project.description.slice(0, 100)}...</p>
            <div className="result-actions">
              <button className="btn btn-secondary btn-sm" onClick={() => handleViewDetails(project)}>View Details</button>
              <button className="btn btn-primary btn-sm" onClick={() => handleInstall(project.versions[0])} disabled={!installTarget}>Install</button>
            </div>
          </div>
        ))}
      </div>
      {selectedProject && (
        <div className="modal-overlay" onClick={() => setSelectedProject(null)}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h3>{selectedProject.title}</h3>
            <p>{selectedProject.description}</p>
            {loadingVersions ? (
              <div className="loading">Loading versions...</div>
            ) : (
              <div className="versions-list">
                {versions.map((v) => (
                  <div key={v.id} className="version-item">
                    <div>
                      <strong>{v.version_number}</strong>
                      <span className="badge">{v.game_versions.join(", ")}</span>
                      <span className="badge">{v.loaders.join(", ")}</span>
                    </div>
                    {v.files?.[0] && <button className="btn btn-primary btn-sm" onClick={() => handleInstall(v)}>Install</button>}
                  </div>
                ))}
              </div>
            )}
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setSelectedProject(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
