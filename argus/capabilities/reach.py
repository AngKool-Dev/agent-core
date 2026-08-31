"""Reach subsystem - web, GitHub, YouTube, Reddit capabilities."""

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ReachResult:
    """Result from a reach operation."""
    success: bool
    content: str = ""
    error: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "metadata": self.metadata,
        }


class WebReach:
    """Web page reading capability."""

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    def read(self, url: str, max_chars: int = 50000) -> ReachResult:
        """Read a web page and return its content."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                charset = "utf-8"
                if "charset=" in content_type:
                    charset = content_type.split("charset=")[-1].strip()

                raw = response.read()
                try:
                    text = raw.decode(charset)
                except (UnicodeDecodeError, LookupError):
                    text = raw.decode("utf-8", errors="replace")

                # Basic HTML tag stripping
                if "text/html" in content_type:
                    text = self._strip_html(text)

                if len(text) > max_chars:
                    text = text[:max_chars] + "\n... (truncated)"

                return ReachResult(
                    success=True,
                    content=text,
                    metadata={"url": url, "content_type": content_type, "length": len(text)},
                )
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def search(self, query: str, num_results: int = 5) -> ReachResult:
        """Search the web using DuckDuckGo."""
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as response:
                html = response.read().decode("utf-8", errors="replace")

            results = self._parse_ddg_results(html, num_results)
            return ReachResult(
                success=True,
                content=json.dumps(results, indent=2),
                metadata={"query": query, "num_results": len(results)},
            )
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def _strip_html(self, html: str) -> str:
        """Basic HTML tag stripping."""
        # Remove script and style elements
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        # Replace <br> and <p> with newlines
        html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
        # Remove remaining tags
        html = re.sub(r"<[^>]+>", "", html)
        # Decode entities
        html = html.replace("&nbsp;", " ")
        html = html.replace("&amp;", "&")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&quot;", '"')
        # Collapse whitespace
        html = re.sub(r"\n{3,}", "\n\n", html)
        html = re.sub(r" {2,}", " ", html)
        return html.strip()

    def _parse_ddg_results(self, html: str, num: int) -> List[Dict[str, str]]:
        """Parse DuckDuckGo HTML results."""
        results = []
        # Simple regex-based parsing
        pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for url, title in matches[:num]:
            title = re.sub(r"<[^>]+>", "", title).strip()
            results.append({"title": title, "url": url})

        return results


class GitHubReach:
    """GitHub API capability."""

    def __init__(self, token: str = ""):
        self._token = token
        self._base_url = "https://api.github.com"

    def _headers(self) -> Dict[str, str]:
        h = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Argus-Agent",
        }
        if self._token:
            h["Authorization"] = f"token {self._token}"
        return h

    def _request(self, path: str) -> ReachResult:
        """Make a GitHub API request."""
        try:
            url = f"{self._base_url}{path}"
            req = urllib.request.Request(url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            return ReachResult(success=True, content=json.dumps(data, indent=2), metadata={"path": path})
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def search_repos(self, query: str, sort: str = "stars", limit: int = 10) -> ReachResult:
        """Search GitHub repositories."""
        encoded = urllib.parse.quote(query)
        return self._request(f"/search/repositories?q={encoded}&sort={sort}&per_page={limit}")

    def search_issues(self, query: str, state: str = "open", limit: int = 10) -> ReachResult:
        """Search GitHub issues."""
        encoded = urllib.parse.quote(query)
        return self._request(f"/search/issues?q={encoded}&state={state}&per_page={limit}")

    def get_repo(self, owner: str, repo: str) -> ReachResult:
        """Get repository information."""
        return self._request(f"/repos/{owner}/{repo}")

    def get_readme(self, owner: str, repo: str) -> ReachResult:
        """Get repository README."""
        return self._request(f"/repos/{owner}/{repo}/readme")

    def list_issues(self, owner: str, repo: str, state: str = "open", limit: int = 30) -> ReachResult:
        """List repository issues."""
        return self._request(f"/repos/{owner}/{repo}/issues?state={state}&per_page={limit}")

    def get_issue(self, owner: str, repo: str, issue_number: int) -> ReachResult:
        """Get a specific issue."""
        return self._request(f"/repos/{owner}/{repo}/issues/{issue_number}")

    def create_issue(self, owner: str, repo: str, title: str, body: str = "") -> ReachResult:
        """Create an issue."""
        try:
            url = f"{self._base_url}/repos/{owner}/{repo}/issues"
            data = json.dumps({"title": title, "body": body}).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            return ReachResult(success=True, content=json.dumps(result, indent=2))
        except Exception as e:
            return ReachResult(success=False, error=str(e))


class YouTubeReach:
    """YouTube capability using noembed and basic scraping."""

    def __init__(self):
        self._noembed_url = "https://noembed.com/embed"

    def get_video_info(self, video_id: str) -> ReachResult:
        """Get video information via noembed."""
        try:
            url = f"{self._noembed_url}?url=https://www.youtube.com/watch?v={video_id}"
            req = urllib.request.Request(url, headers={"User-Agent": "Argus-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            return ReachResult(
                success=True,
                content=json.dumps(data, indent=2),
                metadata={"video_id": video_id},
            )
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def search_videos(self, query: str, max_results: int = 5) -> ReachResult:
        """Search YouTube videos (basic)."""
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")

            # Extract video IDs from initial data
            video_ids = self._extract_video_ids(html, max_results)
            results = []
            for vid in video_ids:
                results.append({
                    "video_id": vid,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "title": "Title unavailable (use get_video_info for details)",
                })

            return ReachResult(
                success=True,
                content=json.dumps(results, indent=2),
                metadata={"query": query, "num_results": len(results)},
            )
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def get_transcript_placeholder(self, video_id: str) -> ReachResult:
        """Placeholder for transcript retrieval."""
        return ReachResult(
            success=False,
            error="Transcript retrieval requires youtube-transcript-api package. Install with: pip install youtube-transcript-api",
            metadata={"video_id": video_id},
        )

    def _extract_video_ids(self, html: str, max_results: int) -> List[str]:
        """Extract video IDs from YouTube search results HTML."""
        pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
        matches = re.findall(pattern, html)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for m in matches:
            if m not in seen and len(unique) < max_results:
                seen.add(m)
                unique.append(m)
        return unique


class RedditReach:
    """Reddit capability using JSON API."""

    def __init__(self):
        self._base_url = "https://www.reddit.com"

    def _request(self, path: str) -> ReachResult:
        """Make a Reddit JSON API request."""
        try:
            url = f"{self._base_url}{path}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Argus-Agent/1.0 (by /u/argus_agent)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            return ReachResult(
                success=True,
                content=json.dumps(data, indent=2),
                metadata={"path": path},
            )
        except Exception as e:
            return ReachResult(success=False, error=str(e))

    def search_posts(self, query: str, subreddit: str = "", limit: int = 10) -> ReachResult:
        """Search Reddit posts."""
        encoded = urllib.parse.quote(query)
        if subreddit:
            path = f"/r/{subreddit}/search.json?q={encoded}&limit={limit}&restrict_sr=1"
        else:
            path = f"/search.json?q={encoded}&limit={limit}"
        return self._request(path)

    def get_subreddit(self, subreddit: str, sort: str = "hot", limit: int = 25) -> ReachResult:
        """Get subreddit posts."""
        return self._request(f"/r/{subreddit}/{sort}.json?limit={limit}")

    def get_post(self, post_id: str) -> ReachResult:
        """Get a specific post."""
        return self._request(f"/comments/{post_id}.json")

    def get_user(self, username: str) -> ReachResult:
        """Get user information."""
        return self._request(f"/user/{username}.about.json")


class ReachSubsystem:
    """Unified reach subsystem."""

    def __init__(self, github_token: str = ""):
        self.web = WebReach()
        self.github = GitHubReach(token=github_token)
        self.youtube = YouTubeReach()
        self.reddit = RedditReach()

    def execute(self, capability: str, **kwargs) -> ReachResult:
        """Execute a reach capability."""
        parts = capability.split(".", 1)
        if len(parts) != 2:
            return ReachResult(success=False, error=f"Invalid capability format: {capability}")

        subsystem, action = parts
        subsystem_obj = getattr(self, subsystem, None)
        if not subsystem_obj:
            return ReachResult(success=False, error=f"Unknown subsystem: {subsystem}")

        method = getattr(subsystem_obj, action, None)
        if not method:
            return ReachResult(success=False, error=f"Unknown action: {action}")

        try:
            return method(**kwargs)
        except Exception as e:
            return ReachResult(success=False, error=str(e))