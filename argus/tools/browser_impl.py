"""Playwright browser implementation for Argus."""

from typing import Any, Dict, Optional

from ..tools import ToolResult


class BrowserImpl:
    def __init__(self):
        self._page = None
        self._context = None
        self._browser = None

    def run(self, action: str, **kwargs) -> ToolResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                tool="browser",
                success=False,
                error="playwright is not installed",
            )

        try:
            if action == "navigate":
                return self._navigate(**kwargs)
            elif action == "snapshot":
                return self._snapshot(**kwargs)
            elif action == "screenshot":
                return self._screenshot(**kwargs)
            elif action == "click":
                return self._click(**kwargs)
            elif action == "type":
                return self._type(**kwargs)
            elif action == "press":
                return self._press(**kwargs)
            elif action == "evaluate":
                return self._evaluate(**kwargs)
            elif action == "close":
                return self._close()
            else:
                return ToolResult(tool="browser", success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(tool="browser", success=False, error=str(e))

    def _ensure_page(self, sync_playwright):
        if self._page is None:
            p = sync_playwright().start()
            self._browser = p.chromium.launch(headless=True)
            self._context = self._browser.new_context(viewport={"width": 1280, "height": 720})
            self._page = self._context.new_page()
        return self._page

    def _navigate(self, url: str, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            page.goto(url, wait_until="domcontentloaded")
            return ToolResult(tool="browser", success=True, output=f"Navigated to {url}")

    def _snapshot(self, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            snapshot = page.accessibility.snapshot()
            return ToolResult(tool="browser", success=True, output=str(snapshot))

    def _screenshot(self, path: str = "screenshot.png", full_page: bool = False, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            page.screenshot(path=path, full_page=full_page)
            return ToolResult(tool="browser", success=True, output=f"Screenshot saved to {path}")

    def _click(self, selector: str, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            page.click(selector)
            return ToolResult(tool="browser", success=True, output=f"Clicked {selector}")

    def _type(self, selector: str, text: str, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            page.type(selector, text)
            return ToolResult(tool="browser", success=True, output=f"Typed into {selector}")

    def _press(self, key: str, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            page.keyboard.press(key)
            return ToolResult(tool="browser", success=True, output=f"Pressed {key}")

    def _evaluate(self, script: str, **kwargs) -> ToolResult:
        with self._sync() as p:
            page = self._ensure_page(p)
            result = page.evaluate(script)
            return ToolResult(tool="browser", success=True, output=str(result))

    def _close(self, **kwargs) -> ToolResult:
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
        return ToolResult(tool="browser", success=True, output="Browser closed")

    def _sync(self):
        class SyncContext:
            def __enter__(self_inner):
                from playwright.sync_api import sync_playwright
                self_inner.playwright = sync_playwright().start()
                return self_inner.playwright

            def __exit__(self_inner, exc_type, exc_val, exc_tb):
                try:
                    if self_inner.playwright:
                        self_inner.playwright.stop()
                except Exception:
                    pass

        return SyncContext()
