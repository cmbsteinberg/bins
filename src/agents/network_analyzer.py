"""
Network analyzer to identify bin collection API from captured network traffic.

Uses two-stage analysis:
1. Keyword scoring to filter candidates
2. Claude AI analysis to identify the best match
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from .models import NetworkRequest, APIAnalysis, BinDays


class NetworkAnalyzer:
    """
    Identify which network request contains bin collection data.

    Per user requirements, uses keyword matching combined with AI analysis.
    """

    BIN_KEYWORDS = [
        'bin', 'waste', 'recycling', 'collection', 'refuse',
        'rubbish', 'garden', 'food', 'calendar', 'schedule',
        'pickup', 'refuse', 'wheelie'
    ]

    def __init__(self, anthropic_client=None):
        """
        Initialize analyzer.

        Args:
            anthropic_client: Optional Anthropic client for AI analysis
        """
        self.client = anthropic_client

    def analyze(
        self,
        network_log: List[Dict[str, Any]],
        visual_data: Optional[BinDays] = None
    ) -> APIAnalysis:
        """
        Identify the API call that fetches bin data.

        Args:
            network_log: List of network requests from chrome-ws
            visual_data: Optional bin data extracted from page (for validation)

        Returns:
            APIAnalysis with identified API and confidence score
        """
        # Stage 1: Filter candidates using keyword scoring
        candidates = self._filter_candidates(network_log)

        if not candidates:
            return APIAnalysis(
                api_url="",
                method="",
                parameters={},
                response_format="unknown",
                confidence=0.0,
                reasoning="No bin-related requests found in network log"
            )

        # Stage 2: If we have Anthropic client, use AI analysis
        if self.client and len(candidates) > 1:
            best_match = self._ai_analyze(candidates, visual_data)
        else:
            # Use highest scoring candidate
            best_match = candidates[0][1]

        return self._build_analysis(best_match, candidates[0][0])

    def _filter_candidates(
        self,
        network_log: List[Dict[str, Any]]
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """
        Score and filter network requests based on keyword matching.

        Args:
            network_log: Raw network log from chrome-ws

        Returns:
            List of (score, request) tuples, sorted by score descending
        """
        scored_requests = []

        for req in network_log:
            score = self._score_request(req)
            if score > 0.3:  # Threshold from plan
                scored_requests.append((score, req))

        # Sort by score descending
        scored_requests.sort(reverse=True, key=lambda x: x[0])

        # Return top 5 candidates
        return scored_requests[:5]

    def _score_request(self, req: Dict[str, Any]) -> float:
        """
        Score a request based on likelihood of containing bin data.

        Scoring criteria:
        - URL contains bin keywords: +0.3 per keyword
        - Resource type is XHR/Fetch: +0.2
        - Response body contains bin keywords: +0.15 per keyword
        - Response contains dates: +0.15

        Args:
            req: Network request dict

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        url_lower = req.get('url', '').lower()
        response_body = req.get('responseBody', '') or ''
        resource_type = req.get('resourceType', '')

        # Check URL for bin-related keywords
        for keyword in self.BIN_KEYWORDS:
            if keyword in url_lower:
                score += 0.3
                break  # Only count once per URL

        # Prioritize XHR/Fetch over page loads
        if resource_type in ['xhr', 'fetch']:
            score += 0.2

        # Check response body for bin-related content
        if response_body:
            response_lower = response_body.lower()
            keyword_count = sum(1 for kw in self.BIN_KEYWORDS if kw in response_lower)
            score += min(keyword_count * 0.05, 0.15)  # Max 0.15

            # Check if response contains dates
            if self._contains_dates(response_body):
                score += 0.15

        # Check for JSON responses (more likely to be API)
        mime_type = req.get('mimeType', '')
        if 'json' in mime_type.lower():
            score += 0.1

        return min(score, 1.0)

    def _contains_dates(self, text: str) -> bool:
        """
        Check if text contains date-like patterns.

        Args:
            text: Text to search

        Returns:
            True if dates found
        """
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # ISO format: 2025-12-03
            r'\d{2}/\d{2}/\d{4}',  # DD/MM/YYYY
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # Various date formats
            r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*',  # Day names
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*',  # Month names
        ]

        for pattern in date_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _ai_analyze(
        self,
        candidates: List[Tuple[float, Dict[str, Any]]],
        visual_data: Optional[BinDays]
    ) -> Dict[str, Any]:
        """
        Use Claude AI to analyze top candidates and pick the best match.

        Args:
            candidates: List of (score, request) tuples
            visual_data: Optional visual bin data for context

        Returns:
            Best matching request dict
        """
        # Build prompt for Claude
        prompt = self._build_ai_prompt(candidates, visual_data)

        # Call Claude (this would integrate with anthropic client)
        # For now, return highest scoring candidate
        # TODO: Implement full AI analysis when anthropic client is integrated

        return candidates[0][1]

    def _build_ai_prompt(
        self,
        candidates: List[Tuple[float, Dict[str, Any]]],
        visual_data: Optional[BinDays]
    ) -> str:
        """
        Build prompt for Claude AI analysis.

        Args:
            candidates: List of (score, request) tuples
            visual_data: Optional visual bin data

        Returns:
            Prompt string
        """
        prompt = "# Identify Bin Collection API\n\n"
        prompt += "I captured network traffic while loading a council bin collection page. "
        prompt += "Which of these requests contains the bin collection data?\n\n"

        if visual_data:
            prompt += f"## Visual Data (what user sees):\n"
            prompt += f"- Postcode: {visual_data.postcode}\n"
            prompt += f"- General waste: {visual_data.general_waste.next_pickup_day}\n"
            prompt += f"- Recycling: {visual_data.recycling.next_pickup_day}\n\n"

        prompt += "## Network Requests:\n\n"

        for i, (score, req) in enumerate(candidates, 1):
            prompt += f"### Request {i} (score: {score:.2f}):\n"
            prompt += f"- URL: {req.get('url')}\n"
            prompt += f"- Method: {req.get('method')}\n"
            prompt += f"- Type: {req.get('resourceType')}\n"
            prompt += f"- Status: {req.get('responseStatus')}\n"

            # Include snippet of response body
            body = req.get('responseBody', '')
            if body:
                snippet = body[:500] + "..." if len(body) > 500 else body
                prompt += f"- Response snippet:\n```\n{snippet}\n```\n\n"

        prompt += "Which request contains the bin collection data? "
        prompt += "Provide the request number and explain your reasoning."

        return prompt

    def _build_analysis(
        self,
        request: Dict[str, Any],
        score: float
    ) -> APIAnalysis:
        """
        Build APIAnalysis from best matching request.

        Args:
            request: Best matching network request
            score: Confidence score

        Returns:
            APIAnalysis object
        """
        # Extract parameters from URL
        parameters = self._extract_parameters(request)

        # Determine response format
        response_format = self._detect_response_format(request)

        # Get response sample (truncated)
        response_body = request.get('responseBody', '')
        response_sample = response_body[:1000] if response_body else None

        return APIAnalysis(
            api_url=request.get('url', ''),
            method=request.get('method', 'GET'),
            parameters=parameters,
            response_format=response_format,
            response_sample=response_sample,
            confidence=score,
            reasoning=f"Matched bin keywords with score {score:.2f}. "
                     f"Resource type: {request.get('resourceType')}"
        )

    def _extract_parameters(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract query and path parameters from URL.

        Args:
            request: Network request dict

        Returns:
            Dict with 'query' and 'path_segments' keys
        """
        url = request.get('url', '')
        parsed = urlparse(url)

        parameters = {}

        # Query parameters
        if parsed.query:
            parameters['query'] = parse_qs(parsed.query)

        # Path segments (may contain UPRN, postcode, etc.)
        path_segments = [s for s in parsed.path.split('/') if s]
        if path_segments:
            parameters['path_segments'] = path_segments

        # Check for request body (POST requests)
        request_body = request.get('requestBody')
        if request_body:
            try:
                body_params = json.loads(request_body)
                parameters['body'] = body_params
            except:
                parameters['body_raw'] = request_body

        return parameters

    def _detect_response_format(self, request: Dict[str, Any]) -> str:
        """
        Detect response format (json, xml, html, etc.).

        Args:
            request: Network request dict

        Returns:
            Format string
        """
        mime_type = request.get('mimeType', '').lower()
        response_body = request.get('responseBody', '')

        if 'json' in mime_type or (response_body and response_body.strip().startswith('{')):
            return 'json'
        elif 'xml' in mime_type or (response_body and response_body.strip().startswith('<')):
            return 'xml'
        elif 'html' in mime_type:
            return 'html'
        else:
            return 'unknown'
