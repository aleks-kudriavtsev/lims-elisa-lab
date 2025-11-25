"""Configuration models for integrating with external LIMS/ELN systems."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class AuditTrailEntry:
    """Minimal audit entry capturing 21 CFR Part 11 attributes."""

    user_id: str
    action: str
    timestamp: datetime
    signature: str
    reason: Optional[str] = None


@dataclass
class LIMSConfig:
    """Configuration describing the external LIMS/ELN instance and policies."""

    system_name: str
    base_url: str
    api_key: str
    enforce_multi_factor: bool = True
    allowed_roles: List[str] = field(default_factory=lambda: ["technician", "qa", "admin"])


@dataclass
class CFRPart11Policy:
    """Policy settings reflecting 21 CFR Part 11 expectations."""

    require_unique_credentials: bool = True
    enforce_password_rotation_days: int = 90
    require_reason_for_changes: bool = True
    audit_retention_days: int = 365 * 5


@dataclass
class LIMSContext:
    """Bundle of configuration and audit trail entries for adapters."""

    config: LIMSConfig
    policy: CFRPart11Policy
    audit_trail: List[AuditTrailEntry] = field(default_factory=list)

    def record(self, entry: AuditTrailEntry) -> None:
        """Append a new audit trail entry."""
        self.audit_trail.append(entry)
