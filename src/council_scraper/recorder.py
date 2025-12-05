"""Recorder for capturing network and session data."""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page, Request, Response

from .models import Action, ExecutionResult, NetworkEntry, Observation


class Recorder:
    """Records all activity for later analysis."""

    def __init__(self, output_dir: str, council_id: str):
        self.output_dir = Path(output_dir) / council_id
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Open file handles for streaming writes
        self._network_file = open(self.output_dir / "network.jsonl", "a")
        self._action_file = open(self.output_dir / "actions.jsonl", "a")
        self._observation_file = open(self.output_dir / "observations.jsonl", "a")

        # Track pending requests
        self._pending_requests: dict[str, NetworkEntry] = {}

    def setup_network_capture(self, page: Page) -> None:
        """Attach network event handlers to the page."""
        page.on("request", self._on_request)
        page.on("response", lambda response: self._on_response(response))

    def _on_request(self, request: Request) -> None:
        """Handle outgoing request."""
        entry = NetworkEntry(
            timestamp=datetime.now(),
            request_url=request.url,
            request_method=request.method,
            request_headers=dict(request.headers),
            request_body=request.post_data,
            response_status=None,
            response_headers=None,
            response_body=None,
            duration_ms=0,
            resource_type=request.resource_type,
        )
        # Use URL + timestamp as key
        key = f"{request.url}:{entry.timestamp.timestamp()}"
        self._pending_requests[key] = entry

    async def _on_response(self, response: Response) -> None:
        """Handle incoming response."""
        url = response.url
        # Find matching request
        matching_key = None
        for key in list(self._pending_requests.keys()):
            if key.startswith(url + ":"):
                matching_key = key
                break

        if matching_key:
            entry = self._pending_requests.pop(matching_key)
            entry.response_status = response.status
            entry.response_headers = dict(response.headers)
            entry.duration_ms = int((datetime.now() - entry.timestamp).total_seconds() * 1000)

            # Capture response body for text-based content types
            content_type = response.headers.get("content-type", "")
            if any(t in content_type for t in ["json", "xml", "html", "text", "javascript"]):
                try:
                    entry.response_body = await response.text()
                except Exception:
                    entry.response_body = None

            # Stream to disk immediately
            self._write_network_entry(entry)

    def _write_network_entry(self, entry: NetworkEntry) -> None:
        """Append a network entry to the JSONL file."""
        self._network_file.write(json.dumps(asdict(entry), default=str) + "\n")
        self._network_file.flush()

    def record_observation(self, observation: Observation) -> None:
        """Log an observation."""
        data = asdict(observation)
        # Convert timestamp to ISO format
        data["timestamp"] = observation.timestamp.isoformat()
        self._observation_file.write(json.dumps(data, default=str) + "\n")
        self._observation_file.flush()

    def record_action(self, action: Action, result: ExecutionResult) -> None:
        """Log an action and its result."""
        entry = {
            "action": asdict(action),
            "result": asdict(result),
            "timestamp": datetime.now().isoformat(),
        }
        self._action_file.write(json.dumps(entry, default=str) + "\n")
        self._action_file.flush()

    async def take_screenshot(self, page: Page, name: str) -> str:
        """Take a screenshot and return the path."""
        screenshots_dir = self.output_dir / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        path = screenshots_dir / f"{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)

    def close(self) -> None:
        """Close file handles."""
        self._network_file.close()
        self._action_file.close()
        self._observation_file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
