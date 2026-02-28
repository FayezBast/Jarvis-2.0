"""
Web Tools - Fetch content from URLs with enhanced capabilities.
"""

import urllib.request
import urllib.error
import ssl
import json
import re
import time
from html.parser import HTMLParser

from tools.base import BaseTool, ToolArg, ToolResult


class HTMLTextExtractor(HTMLParser):
    """Extract readable text from HTML."""
    
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {"script", "style", "head", "meta", "link", "noscript"}
        self.current_tag = None
    
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in ("br", "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.text.append("\n")
    
    def handle_endtag(self, tag):
        self.current_tag = None
    
    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            text = data.strip()
            if text:
                self.text.append(text)
    
    def get_text(self) -> str:
        raw = " ".join(self.text)
        # Clean up whitespace
        raw = re.sub(r'\n\s*\n', '\n\n', raw)
        raw = re.sub(r' +', ' ', raw)
        return raw.strip()


def extract_text_from_html(html: str) -> str:
    """Convert HTML to readable text."""
    try:
        parser = HTMLTextExtractor()
        parser.feed(html)
        return parser.get_text()
    except Exception:
        clean = re.sub(r'<[^>]+>', ' ', html)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()


class FetchUrlTool(BaseTool):
    """Fetch content from a URL with enhanced options."""

    TOOL_NAME = "fetch_url"
    TOOL_DESCRIPTION = "Fetch content from a URL. Supports GET/POST, custom headers, JSON parsing, and HTML-to-text extraction."
    TOOL_ARGS = [
        ToolArg(
            name="url",
            type="string",
            description="The URL to fetch",
            required=True,
        ),
        ToolArg(
            name="method",
            type="string",
            description="HTTP method: GET, POST, PUT, DELETE (default: GET)",
            required=False,
            default="GET",
        ),
        ToolArg(
            name="headers",
            type="object",
            description="Custom headers as key-value pairs (e.g., {\"Authorization\": \"Bearer xxx\"})",
            required=False,
        ),
        ToolArg(
            name="body",
            type="string",
            description="Request body for POST/PUT requests (JSON string or form data)",
            required=False,
        ),
        ToolArg(
            name="parse_json",
            type="boolean",
            description="Parse response as JSON and return structured data (default: False)",
            required=False,
            default=False,
        ),
        ToolArg(
            name="extract_text",
            type="boolean",
            description="Extract readable text from HTML, removing tags (default: False)",
            required=False,
            default=False,
        ),
        ToolArg(
            name="max_chars",
            type="integer",
            description="Maximum characters to return (default: 10000)",
            required=False,
            default=10000,
        ),
    ]

    def run(
        self,
        url: str = "",
        method: str = "GET",
        headers: dict = None,
        body: str = None,
        parse_json: bool = False,
        extract_text: bool = False,
        max_chars: int = 10000,
        **kwargs
    ) -> ToolResult:
        
        headers = headers or {}
        method = method.upper()
        
        # Build request headers
        default_headers = {
            "User-Agent": "Jarvis-Agent/2.0 (Local-First AI Assistant)",
            "Accept": "text/html,application/json,application/xml,*/*",
        }
        if body and "Content-Type" not in headers:
            default_headers["Content-Type"] = "application/json"
        default_headers.update(headers)
        
        # Encode body
        data = body.encode("utf-8") if body else None
        
        req = urllib.request.Request(
            url,
            data=data,
            headers=default_headers,
            method=method,
        )
        
        # SSL context
        ctx = ssl.create_default_context()
        
        # Retry loop
        retries = 2
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                    raw_content = response.read()
                    content = raw_content.decode("utf-8", errors="replace")
                    status_code = response.status
                    content_type = response.headers.get("Content-Type", "")
                
                # Auto-detect JSON
                if parse_json or "application/json" in content_type:
                    try:
                        parsed = json.loads(content)
                        # Truncate if it's huge
                        json_str = json.dumps(parsed, indent=2)
                        if len(json_str) > max_chars:
                            json_str = json_str[:max_chars] + "\n... [truncated]"
                        return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                            "url": url,
                            "status": status_code,
                            "content_type": "json",
                            "data": parsed if len(json.dumps(parsed)) < max_chars else json_str,
                        })
                    except json.JSONDecodeError:
                        pass  # Not valid JSON, continue with text
                
                # Extract text from HTML
                if extract_text or "text/html" in content_type:
                    content = extract_text_from_html(content)
                
                # Truncate
                truncated = False
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n... [truncated]"
                    truncated = True
                
                return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                    "url": url,
                    "status": status_code,
                    "content_type": "text",
                    "content": content,
                    "truncated": truncated,
                })
                
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code < 500:  # Don't retry client errors
                    break
            except urllib.error.URLError as e:
                last_error = f"Connection failed: {e.reason}"
            except Exception as e:
                last_error = str(e)
            
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
        
        return ToolResult(ok=False, tool=self.TOOL_NAME, error=last_error)


class ApiCallTool(BaseTool):
    """Make API calls with JSON payloads."""

    TOOL_NAME = "api_call"
    TOOL_DESCRIPTION = "Make REST API calls. Automatically handles JSON encoding/decoding. Great for integrating with external services."
    TOOL_ARGS = [
        ToolArg(
            name="url",
            type="string",
            description="The API endpoint URL",
            required=True,
        ),
        ToolArg(
            name="method",
            type="string",
            description="HTTP method: GET, POST, PUT, PATCH, DELETE",
            required=True,
        ),
        ToolArg(
            name="data",
            type="object",
            description="Data to send (will be JSON encoded for POST/PUT/PATCH)",
            required=False,
        ),
        ToolArg(
            name="headers",
            type="object",
            description="Custom headers (e.g., {\"Authorization\": \"Bearer token\"})",
            required=False,
        ),
    ]

    def run(
        self,
        url: str = "",
        method: str = "GET",
        data: dict = None,
        headers: dict = None,
        **kwargs
    ) -> ToolResult:
        
        headers = headers or {}
        method = method.upper()
        
        # Build headers
        req_headers = {
            "User-Agent": "Jarvis-Agent/2.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        req_headers.update(headers)
        
        # Encode body
        body = None
        if data and method in ("POST", "PUT", "PATCH"):
            body = json.dumps(data).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method,
        )
        
        ctx = ssl.create_default_context()
        
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                content = response.read().decode("utf-8", errors="replace")
                status_code = response.status
            
            # Try to parse as JSON
            try:
                result_data = json.loads(content)
            except json.JSONDecodeError:
                result_data = content
            
            return ToolResult(ok=True, tool=self.TOOL_NAME, result={
                "status": status_code,
                "data": result_data,
            })
            
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=f"HTTP {e.code}: {e.reason}. Body: {error_body[:500]}")
        except Exception as e:
            return ToolResult(ok=False, tool=self.TOOL_NAME, error=str(e))
