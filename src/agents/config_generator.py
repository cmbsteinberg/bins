"""
Generate YAML configuration files from discovery JSON.

Transforms raw discovery data into structured configs for runtime API wrapper.
"""

import yaml
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigGenerator:
    """Transform discovery JSON into structured YAML config."""

    def generate(self, discovery: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate config from discovery data.

        Args:
            discovery: Discovery dict with council, api_analysis, etc.

        Returns:
            Config dict ready to save as YAML
        """
        api_analysis = discovery.get('api_analysis', {})

        config = {
            'council': discovery['council'],
            'slug': self._slugify(discovery['council']),
            'discovered_at': discovery.get('timestamp', datetime.now().isoformat()),
            'confidence': api_analysis.get('confidence', 0.0),
            'api': {
                'method': api_analysis.get('method', 'GET'),
                'endpoint': api_analysis.get('api_url', ''),
                'parameters': self._extract_template_params(api_analysis.get('parameters', {})),
                'response_format': api_analysis.get('response_format', 'unknown')
            },
            'parsing': self._infer_parsing_rules(api_analysis),
            'metadata': {
                'postcode_tested': discovery.get('postcode_used', ''),
                'notes': api_analysis.get('reasoning', ''),
                'raw_discovery_file': ''  # To be filled when saving
            }
        }

        return config

    def save(self, config: Dict[str, Any], output_file: Path) -> None:
        """
        Save config as YAML.

        Args:
            config: Config dict
            output_file: Path to save YAML file
        """
        # Update metadata with file reference
        config['metadata']['config_file'] = str(output_file)

        with open(output_file, 'w') as f:
            yaml.dump(
                config,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )

    def generate_from_file(self, discovery_file: Path, output_file: Path) -> Dict[str, Any]:
        """
        Load discovery JSON and generate config.

        Args:
            discovery_file: Path to discovery JSON
            output_file: Path to save YAML config

        Returns:
            Generated config dict
        """
        with open(discovery_file) as f:
            discovery = json.load(f)

        config = self.generate(discovery)
        config['metadata']['raw_discovery_file'] = str(discovery_file)

        self.save(config, output_file)
        return config

    def _slugify(self, text: str) -> str:
        """
        Convert council name to slug.

        Args:
            text: Council name

        Returns:
            Slugified string
        """
        # Remove special chars, convert to lowercase, replace spaces with underscores
        slug = re.sub(r'[^\w\s-]', '', text.lower())
        slug = re.sub(r'[-\s]+', '_', slug)
        return slug.strip('_')

    def _extract_template_params(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert actual parameters to templates.

        Args:
            parameters: Extracted parameters from API call

        Returns:
            Template parameters with {postcode}, {uprn}, etc.
        """
        template_params = {}

        # Query parameters
        if 'query' in parameters:
            template_params['query'] = {}
            for key, value in parameters['query'].items():
                # Detect postcode parameters
                if self._looks_like_postcode_param(key, value):
                    template_params['query'][key] = '{postcode}'
                # Detect UPRN parameters
                elif self._looks_like_uprn_param(key, value):
                    template_params['query'][key] = '{uprn}'
                else:
                    # Keep as-is if it's a constant parameter
                    template_params['query'][key] = value

        # Path segments
        if 'path_segments' in parameters:
            template_params['path_segments'] = []
            for segment in parameters['path_segments']:
                if self._looks_like_postcode(segment):
                    template_params['path_segments'].append('{postcode}')
                elif self._looks_like_uprn(segment):
                    template_params['path_segments'].append('{uprn}')
                else:
                    template_params['path_segments'].append(segment)

        # Body parameters (POST requests)
        if 'body' in parameters:
            template_params['body'] = {}
            for key, value in parameters['body'].items():
                if self._looks_like_postcode_param(key, value):
                    template_params['body'][key] = '{postcode}'
                elif self._looks_like_uprn_param(key, value):
                    template_params['body'][key] = '{uprn}'
                else:
                    template_params['body'][key] = value

        return template_params

    def _looks_like_postcode_param(self, key: str, value: Any) -> bool:
        """Check if parameter is a postcode."""
        key_lower = key.lower()
        if 'postcode' in key_lower or 'postal' in key_lower or 'zip' in key_lower:
            return True

        if isinstance(value, str) and self._looks_like_postcode(value):
            return True

        return False

    def _looks_like_uprn_param(self, key: str, value: Any) -> bool:
        """Check if parameter is a UPRN."""
        key_lower = key.lower()
        if 'uprn' in key_lower:
            return True

        # UPRNs are typically 12-digit numbers
        if isinstance(value, (str, int)):
            value_str = str(value)
            if value_str.isdigit() and len(value_str) == 12:
                return True

        return False

    def _looks_like_postcode(self, value: str) -> bool:
        """Check if value looks like a UK postcode."""
        if not isinstance(value, str):
            return False

        # UK postcode pattern
        postcode_pattern = r'^[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}$'
        return bool(re.match(postcode_pattern, value.upper().strip()))

    def _looks_like_uprn(self, value: str) -> bool:
        """Check if value looks like a UPRN."""
        if not isinstance(value, str):
            return False

        return value.isdigit() and len(value) == 12

    def _infer_parsing_rules(self, api_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Infer JSON parsing rules from response sample.

        Args:
            api_analysis: API analysis with response sample

        Returns:
            Parsing rules dict or None
        """
        response_sample = api_analysis.get('response_sample')
        if not response_sample:
            return None

        # Try to parse as JSON
        try:
            data = json.loads(response_sample)

            # Attempt to infer JSONPath to bin collection data
            # This is a simple heuristic - real implementation would be more sophisticated
            parsing = {
                'response_type': 'json',
                'date_format': self._detect_date_format(response_sample),
                'bin_types': self._infer_bin_type_mapping(data)
            }

            return parsing

        except json.JSONDecodeError:
            # Not JSON, maybe XML or HTML
            return {
                'response_type': api_analysis.get('response_format', 'unknown'),
                'notes': 'Manual parsing required - not JSON'
            }

    def _detect_date_format(self, text: str) -> str:
        """
        Detect date format from response text.

        Args:
            text: Response body

        Returns:
            Detected format string
        """
        # Check for ISO format
        if re.search(r'\d{4}-\d{2}-\d{2}', text):
            return '%Y-%m-%d'

        # Check for DD/MM/YYYY
        if re.search(r'\d{2}/\d{2}/\d{4}', text):
            return '%d/%m/%Y'

        # Check for DD-MM-YYYY
        if re.search(r'\d{2}-\d{2}-\d{4}', text):
            return '%d-%m-%Y'

        return 'unknown'

    def _infer_bin_type_mapping(self, data: Any) -> Dict[str, str]:
        """
        Infer mapping from JSON keys to bin types.

        Args:
            data: Parsed JSON response

        Returns:
            Mapping dict like {'general_waste': 'generalWaste', ...}
        """
        mapping = {}

        # Recursively search for bin-related keys
        def find_keys(obj, prefix=''):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = key.lower()

                    # Check for bin type keywords
                    if any(word in key_lower for word in ['general', 'refuse', 'black']):
                        mapping['general_waste'] = f'{prefix}{key}'
                    elif any(word in key_lower for word in ['recycling', 'blue']):
                        mapping['recycling'] = f'{prefix}{key}'
                    elif any(word in key_lower for word in ['food', 'organic']):
                        mapping['food_waste'] = f'{prefix}{key}'
                    elif any(word in key_lower for word in ['garden', 'green']):
                        mapping['garden_waste'] = f'{prefix}{key}'

                    # Recurse
                    if isinstance(value, (dict, list)):
                        find_keys(value, f'{prefix}{key}.')

            elif isinstance(obj, list) and obj:
                find_keys(obj[0], prefix)

        find_keys(data)
        return mapping if mapping else None
