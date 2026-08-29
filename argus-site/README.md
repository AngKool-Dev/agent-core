# ARGUS Website

Static website for the ARGUS Minecraft Launcher. Deployable for free on Cloudflare Pages.

## Project Structure

```
argus-site/
├── index.html
├── download/
│   └── index.html
├── assets/
│   ├── logo.svg
│   ├── icon.svg
│   └── favicon.svg
├── css/
│   └── style.css
├── js/
│   └── main.js
└── README.md
```

## Configuration

The download URL is configured in `js/main.js`:

```javascript
const ARGUS_DOWNLOAD_URL = "https://github.com/AngKool-Dev/argus-releases/releases/latest/download/era-launcher.exe";
```

If the GitHub repository or release asset name changes, update this constant.

## Local Testing

Serve the site locally and open `http://localhost:8080` (or your server of choice):

```bash
# Python 3
python -m http.server 8080 --directory "D:\agent-core\argus-site"

# Node.js (npx)
npx serve "D:\agent-core\argus-site" -l 8080
```

Then verify:
- `/` loads and displays the landing page
- `/download` loads and displays the download page
- Navigation links work
- Download buttons redirect to the configured GitHub release asset
- No broken asset paths
- Mobile layout at 390px width
- Desktop layout at 1920px width

## Deploy to Cloudflare Pages (Free)

1. Push this repository (or the `argus-site/` folder) to GitHub.
2. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) → **Workers & Pages**.
3. Click **Create application** → **Pages** → **Connect to Git**.
4. Authorize Cloudflare for your GitHub account and select the repository.
5. Select the production branch (e.g. `main` or `master`).
6. Configure build settings:
   - **Build command**: leave empty (no build step required)
   - **Publish directory**: `/` or `argus-site` depending on your repo layout
   - If the site files are in the repo root, use `/`
   - If the site files are in `argus-site/`, use `argus-site`
7. Click **Save and Deploy**.
8. Cloudflare will build and deploy the site. You will get a `*.pages.dev` URL.

### Custom Domain (Optional)

If you want `argus-launcher.pages.dev` specifically:
- In the Cloudflare Pages project settings, go to **Custom domains**
- Add `argus-launcher.pages.dev` as a custom domain

Note: `*.pages.dev` domains are provided for free by Cloudflare Pages. You do not need to purchase a custom domain.

## Updating the Site

After pushing changes to GitHub, Cloudflare Pages automatically redeploys the site on the next push to the production branch.

## Verified Repository Facts

- **Source repository**: `AngKool-Dev/agent-core` (private)
- **Release repository**: `AngKool-Dev/argus-releases` (public)
- **Release asset**: `era-launcher.exe`
- **Download URL pattern**: `https://github.com/AngKool-Dev/argus-releases/releases/latest/download/era-launcher.exe`
- **Current Windows executable size**: ~6 MB
- **Rust package name**: `era-launcher`
- **Latest release tag**: `v0.1.2`
- **TUI module**: `argus`
- **Interfaces**: Terminal TUI (Ratatui)

## License

The website source code is MIT licensed. ARGUS itself is an independent project.

Minecraft is a trademark of Mojang Studios. ARGUS is not affiliated with Mojang or Microsoft.
