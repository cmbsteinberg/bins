from pydantic import BaseModel
from typing import Optional, Union, Dict, Any, List
from datetime import datetime
from enum import Enum


class BinColour(Enum):
    GREY = "grey"
    BLACK = "black"
    ORANGE = "orange"
    BLUE = "blue"
    RED = "red"
    BROWN = "brown"
    GREEN = "green"


class BinInfo(BaseModel, use_enum_values=True):
    next_pickup_day: Union[datetime, str, None]
    frequency: Optional[str]
    bin_colour: Optional[BinColour]


class BinDays(BaseModel, use_enum_values=True):
    postcode: Optional[str]
    general_waste: BinInfo
    recycling: BinInfo
    food_waste: BinInfo
    garden_waste: BinInfo
    notes: Optional[str] = None


# Network tracking models
class NetworkRequest(BaseModel):
    """Captured network request/response from Chrome DevTools Protocol."""
    request_id: str
    url: str
    method: str
    request_headers: Dict[str, str]
    request_body: Optional[str] = None
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    response_body: Optional[str] = None
    resource_type: str  # xhr, fetch, document, script, etc.
    timing: Optional[Dict[str, float]] = None
    initiator: Optional[Dict[str, Any]] = None
    failed: bool = False
    error_text: Optional[str] = None


class APIAnalysis(BaseModel):
    """Analysis of discovered bin collection API."""
    api_url: str
    method: str
    parameters: Dict[str, Any]
    response_format: str  # json, xml, html, etc.
    response_sample: Optional[str] = None
    confidence: float  # 0.0 to 1.0
    reasoning: str


class CouncilDiscovery(BaseModel):
    """Complete discovery output for a council."""
    council: str
    url: str
    postcode_used: str
    visual_data: Optional[BinDays] = None
    network_requests: List[NetworkRequest]
    api_analysis: APIAnalysis
    timestamp: datetime
    error: Optional[str] = None


class CouncilConfig(BaseModel):
    """YAML config schema for runtime wrapper."""
    council: str
    slug: str
    discovered_at: str
    confidence: float
    api: Dict[str, Any]
    parsing: Optional[Dict[str, Any]] = None
    metadata: Dict[str, str]
