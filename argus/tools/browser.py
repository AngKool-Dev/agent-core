"""Browser tool for Argus."""

from typing import Optional

from . import Tool, ToolResult


class BrowserTool(Tool):
    name = "browser"
    description = "Web browser automation (requires playwright)"

    def execute(self, action: str, **kwargs) -> ToolResult:
        try:
            from argus.tools.browser_impl import BrowserImpl

            impl = BrowserImpl()
            result = impl.run(action, **kwargs)
            return result
        except ImportError:
            return ToolResult(
                tool=self.name,
                success=False,
                error="playwright is not installed. Run: pip install playwright && playwright install",
            )
        except Exception as e:
            return ToolResult(tool=self.name, success=False, error=str(e))
