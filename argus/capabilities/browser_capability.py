"""Polished browser capability with proper lifecycle management."""

from typing import Any, Dict, Optional

from argus.capabilities import (
    Capability,
    CapabilityMetadata,
    CapabilitySchema,
    CapabilityType,
)


class BrowserCapability(Capability):
    """Browser capability with proper lifecycle management."""

    def __init__(self, metadata: CapabilityMetadata, headless: bool = True):
        super().__init__(metadata)
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def check_availability(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            return False

    def health_check(self) -> Dict[str, Any]:
        if not self.check_availability():
            return {"status": "unavailable", "message": "playwright not installed"}

        if self._page is None:
            return {"status": "healthy", "message": "Browser ready (not started)"}

        try:
            _ = self._page.url
            return {"status": "healthy", "message": "Browser active"}
        except Exception:
            return {"status": "degraded", "message": "Browser session stale"}

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        import time
        start = time.time()

        try:
            action = input_data.get("action", "navigate")

            if action == "start":
                return self._action_start()
            elif action == "navigate":
                return self._action_navigate(input_data.get("url", ""))
            elif action == "snapshot":
                return self._action_snapshot()
            elif action == "screenshot":
                return self._action_screenshot(
                    path=input_data.get("path", "screenshot.png"),
                    full_page=input_data.get("full_page", False),
                )
            elif action == "click":
                return self._action_click(input_data.get("selector", ""))
            elif action == "type":
                return self._action_type(
                    input_data.get("selector", ""),
                    input_data.get("text", ""),
                )
            elif action == "fill":
                return self._action_fill(
                    input_data.get("selector", ""),
                    input_data.get("text", ""),
                )
            elif action == "press":
                return self._action_press(input_data.get("key", ""))
            elif action == "evaluate":
                return self._action_evaluate(input_data.get("script", ""))
            elif action == "scroll":
                return self._action_scroll(
                    input_data.get("direction", "down"),
                    input_data.get("amount", 300),
                )
            elif action == "wait":
                return self._action_wait(input_data.get("timeout", 1000))
            elif action == "content":
                return self._action_content()
            elif action == "close":
                return self._action_close()
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "execution_time": time.time() - start,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start,
            }

    def _ensure_browser(self) -> Any:
        """Ensure browser is started, return the page."""
        from playwright.sync_api import sync_playwright

        if self._page is not None:
            try:
                _ = self._page.url
                return self._page
            except Exception:
                self._cleanup()

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        self._page = self._context.new_page()
        return self._page

    def _cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self._page:
                self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def _action_start(self) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            self._ensure_browser()
            return {
                "success": True,
                "output": "Browser started",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start,
            }

    def _action_navigate(self, url: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {
                "success": True,
                "output": f"Navigated to {url}",
                "url": page.url,
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Navigation failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_snapshot(self) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            snapshot = page.accessibility.snapshot()
            return {
                "success": True,
                "output": str(snapshot),
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Snapshot failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_screenshot(self, path: str = "screenshot.png", full_page: bool = False) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.screenshot(path=path, full_page=full_page)
            return {
                "success": True,
                "output": f"Screenshot saved to {path}",
                "path": path,
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Screenshot failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_click(self, selector: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.click(selector, timeout=10000)
            return {
                "success": True,
                "output": f"Clicked {selector}",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Click failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_type(self, selector: str, text: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.type(selector, text, delay=50)
            return {
                "success": True,
                "output": f"Typed into {selector}",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Type failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_fill(self, selector: str, text: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.fill(selector, text)
            return {
                "success": True,
                "output": f"Filled {selector}",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Fill failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_press(self, key: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.keyboard.press(key)
            return {
                "success": True,
                "output": f"Pressed {key}",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Key press failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_evaluate(self, script: str) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            result = page.evaluate(script)
            return {
                "success": True,
                "output": str(result),
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Evaluate failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_scroll(self, direction: str = "down", amount: int = 300) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                page.evaluate(f"window.scrollBy(0, -{amount})")
            else:
                return {
                    "success": False,
                    "error": f"Unknown direction: {direction}",
                    "execution_time": time.time() - start,
                }
            return {
                "success": True,
                "output": f"Scrolled {direction} by {amount}",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Scroll failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_wait(self, timeout: int = 1000) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            page.wait_for_timeout(timeout)
            return {
                "success": True,
                "output": f"Waited {timeout}ms",
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Wait failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_content(self) -> Dict[str, Any]:
        import time
        start = time.time()
        try:
            page = self._ensure_browser()
            content = page.content()
            return {
                "success": True,
                "output": content,
                "execution_time": time.time() - start,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Content retrieval failed: {e}",
                "execution_time": time.time() - start,
            }

    def _action_close(self) -> Dict[str, Any]:
        import time
        start = time.time()
        self._cleanup()
        return {
            "success": True,
            "output": "Browser closed",
            "execution_time": time.time() - start,
        }

    def __del__(self):
        self._cleanup()


def create_browser_capability(headless: bool = True) -> BrowserCapability:
    """Create a browser capability instance."""
    schema = CapabilitySchema(
        name="browser",
        description="Web browser automation with Playwright",
        parameters={"type": "object"},
        required_parameters=["action"],
    )

    metadata = CapabilityMetadata(
        id="browser.navigate",
        name="Browser",
        description="Web browser automation (navigate, click, type, screenshot, etc.)",
        type=CapabilityType.BROWSER,
        schema=schema,
        tags=["navigation", "interaction", "screenshot", "automation"],
    )

    return BrowserCapability(metadata, headless=headless)