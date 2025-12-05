"""Session for exploring a single council website."""

from datetime import datetime

from playwright.async_api import Page

from .executor import Executor
from .models import (
    Action,
    Config,
    Council,
    ExecutionResult,
    FailureCategory,
    HistoryEntry,
    Observation,
    SessionResult,
)
from .observer import Observer
from .recorder import Recorder
from .strategist import Strategist


class Session:
    """Manages a single exploration attempt for one council."""

    def __init__(
        self,
        page: Page,
        council: Council,
        config: Config,
        recorder: Recorder,
    ):
        self.page = page
        self.council = council
        self.config = config
        self.recorder = recorder
        self.observer = Observer()
        self.strategist = Strategist(config)
        self.executor = Executor(config)
        self.history: list[HistoryEntry] = []
        self.phase = "initial"

    async def run(self) -> SessionResult:
        """Main exploration loop."""
        try:
            # Navigate to start URL
            await self._navigate_to_start_url()

            # Main loop
            for iteration in range(self.config.max_iterations):
                # 1. Observe current state
                observation = await self.observer.observe(self.page)
                self.recorder.record_observation(observation)

                # 2. Check termination conditions
                if self._is_success(observation):
                    return SessionResult(
                        status="success",
                        council_id=self.council.council_id,
                        final_url=self.page.url,
                        iterations=iteration,
                        history=self.history,
                    )

                if self._is_dead_end(observation):
                    category, detail = self._classify_failure(observation, None, None)
                    return SessionResult(
                        status="failure",
                        council_id=self.council.council_id,
                        final_url=self.page.url,
                        iterations=iteration,
                        history=self.history,
                        failure_category=category,
                        failure_detail=detail,
                        is_recoverable=category not in [
                            FailureCategory.CAPTCHA_PRESENT,
                            FailureCategory.LOGIN_REQUIRED,
                        ],
                    )

                if self._is_loop(observation):
                    return SessionResult(
                        status="failure",
                        council_id=self.council.council_id,
                        final_url=self.page.url,
                        iterations=iteration,
                        history=self.history,
                        failure_category=FailureCategory.LOOP_DETECTED,
                        failure_detail="Loop detected in navigation",
                        is_recoverable=True,
                    )

                # 3. Get candidate actions
                candidates = self.strategist.get_actions(observation, self.history, self.council.test_postcode)

                if not candidates:
                    return SessionResult(
                        status="failure",
                        council_id=self.council.council_id,
                        final_url=self.page.url,
                        iterations=iteration,
                        history=self.history,
                        failure_category=FailureCategory.NO_ACTIONS,
                        failure_detail="No more actions available",
                        is_recoverable=True,
                    )

                # 4. Execute top action
                action = candidates[0]
                result = await self.executor.execute(self.page, action)

                # 5. Record the action
                self.history.append(HistoryEntry(observation=observation, action=action, result=result))
                self.recorder.record_action(action, result)

                if not result.success:
                    # Action failed, continue to next iteration to reassess
                    continue

                # 6. Wait for page to settle
                await self._wait_for_settle()

            # Max iterations exceeded
            return SessionResult(
                status="failure",
                council_id=self.council.council_id,
                final_url=self.page.url,
                iterations=self.config.max_iterations,
                history=self.history,
                failure_category=FailureCategory.MAX_ITERATIONS,
                failure_detail=f"Exceeded max iterations ({self.config.max_iterations})",
                is_recoverable=True,
            )

        except Exception as e:
            category, detail = self._classify_failure(None, None, e)
            return SessionResult(
                status="failure",
                council_id=self.council.council_id,
                final_url=self.page.url,
                iterations=len(self.history),
                history=self.history,
                failure_category=category,
                failure_detail=detail,
                is_recoverable=True,
            )

    async def _navigate_to_start_url(self) -> None:
        """Navigate to the council's bin lookup URL."""
        await self.page.goto(self.council.url, wait_until="load", timeout=self.config.page_load_timeout_ms)
        await self._wait_for_settle()

    def _is_success(self, observation: Observation) -> bool:
        """Check if page indicates success."""
        if observation.contains_success_indicators:
            return True

        # Check for dates in near future (simple heuristic)
        text_lower = observation.visible_text_sample.lower()
        date_patterns = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "jan", "feb"]
        if any(pattern in text_lower for pattern in date_patterns):
            # Also check for month/day pattern
            import re

            if re.search(r"\d{1,2}\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", text_lower):
                return True

        return False

    def _is_dead_end(self, observation: Observation) -> bool:
        """Check if we're in a dead end."""
        if observation.contains_error_message:
            return True

        # Check for "not found" type messages
        text_lower = observation.visible_text_sample.lower()
        dead_end_indicators = [
            "postcode not found",
            "invalid postcode",
            "no results",
            "page not found",
            "404",
            "login required",
            "sign in",
        ]

        if any(indicator in text_lower for indicator in dead_end_indicators):
            return True

        # If page is empty
        if len(observation.visible_text_sample.strip()) < 100:
            return True

        return False

    def _is_loop(self, observation: Observation) -> bool:
        """Detect if we're in a loop."""
        # Check if we've visited the same URL many times
        url_count = sum(1 for entry in self.history[-10:] if entry.observation.url == observation.url)
        if url_count > self.config.max_same_url_visits:
            return True

        # Check if we've seen the same observation hash recently
        current_hash = observation.hash
        hash_count = sum(1 for entry in self.history[-10:] if entry.observation.hash == current_hash)
        if hash_count > 3:
            return True

        return False

    def _classify_failure(
        self,
        observation: Observation | None,
        last_action: Action | None,
        error: Exception | None,
    ) -> tuple[FailureCategory, str]:
        """Determine failure category from available evidence."""
        if observation:
            page_text = observation.visible_text_sample.lower()

            if any(phrase in page_text for phrase in ["captcha", "robot", "verify you're human"]):
                return FailureCategory.CAPTCHA_PRESENT, "CAPTCHA detected on page"

            if any(phrase in page_text for phrase in ["sign in", "log in", "login required"]):
                return FailureCategory.LOGIN_REQUIRED, "Login wall detected"

            if any(phrase in page_text for phrase in ["postcode not found", "invalid postcode", "not recognised"]):
                return FailureCategory.POSTCODE_NOT_FOUND, "Site rejected the test postcode"

            if any(phrase in page_text for phrase in ["no addresses", "address not found"]):
                return FailureCategory.ADDRESS_NOT_FOUND, "No addresses found for postcode"

            if "404" in page_text or observation.url.endswith("/404"):
                return FailureCategory.PAGE_NOT_FOUND, "Page not found (404)"

        if error:
            error_str = str(error).lower()
            if "net::" in error_str or "connection" in error_str:
                return FailureCategory.NETWORK_ERROR, str(error)
            if "crash" in error_str or "target closed" in error_str:
                return FailureCategory.BROWSER_CRASH, str(error)

        return FailureCategory.UNKNOWN, "Could not determine failure reason"

    async def _wait_for_settle(self) -> None:
        """Wait for page to be stable enough to observe."""
        try:
            # Wait for network idle with timeout
            await self.page.wait_for_load_state("networkidle", timeout=self.config.settle_timeout_ms)
        except Exception:
            # Network didn't idle, but that's okay
            pass

        # Additional short wait for any final DOM updates
        await self.page.wait_for_timeout(self.config.settle_check_interval_ms)
