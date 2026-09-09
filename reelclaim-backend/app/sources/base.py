from typing import Protocol, List, Optional, Dict, Any, runtime_checkable
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class Fact(BaseModel):
    """
    Standardized fact extracted from an evidence source.
    """
    source_name: str = Field(..., description="Name of the evidence source: site_crawl, cross_reference, wayback, whois")
    trust_weight: float = Field(..., ge=0.0, le=1.0, description="Base trust weight or credibility modifier (0.0 to 1.0)")
    content: str = Field(..., description="Extracted fact text or evidence statement")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when evidence was fetched")
    raw_reference: str = Field(..., description="Raw URL, snapshot URI, or search query used to retrieve fact")
    category: str = Field("other", description="Standardized claim category")
    is_self_attested: bool = Field(False, description="True if fact is from the promoter's own domain; False if independent 3rd-party")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Source-specific metadata (domain age, snapshot date, search rank, etc.)")

    # Compatibility property for existing checker/crawler expectations
    @property
    def text(self) -> str:
        return self.content

    @property
    def source_url(self) -> str:
        return self.raw_reference

    @property
    def source_page(self) -> str:
        return self.metadata.get("source_page", self.source_name)

@runtime_checkable
class EvidenceSource(Protocol):
    """
    Protocol for pluggable evidence gathering sources.
    """
    source_name: str

    def fetch(self, claim: Any, target_url: Optional[str] = None, **kwargs) -> List[Fact]:
        """
        Fetches evidence facts relevant to a given claim and optional target URL.
        Must handle errors gracefully and never raise unhandled network exceptions.
        """
        ...
