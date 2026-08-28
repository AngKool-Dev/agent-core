// ARGUS Website Configuration
const ARGUS_DOWNLOAD_URL = "https://github.com/AngKool-Dev/argus-releases/releases/latest/download/era-launcher.exe";

const RELEASES_API = "https://api.github.com/repos/AngKool-Dev/argus-releases/releases?per_page=100";

async function loadDownloadCounts() {
  const nodes = document.querySelectorAll("[data-dl-count]");
  if (!nodes.length) return;
  try {
    const res = await fetch(RELEASES_API, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) throw new Error(String(res.status));
    const releases = await res.json();
    let total = 0;
    for (const rel of releases) {
      for (const asset of rel.assets || []) {
        total += asset.download_count || 0;
      }
    }
    const formatted = new Intl.NumberFormat("en-US").format(total);
    nodes.forEach((n) => {
      n.textContent = formatted;
    });
  } catch (_err) {
    document.querySelectorAll("[data-dl-stat]").forEach((el) => el.remove());
  }
}

loadDownloadCounts();

document.querySelectorAll("[data-download]").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    window.location.href = ARGUS_DOWNLOAD_URL;
  });
});
