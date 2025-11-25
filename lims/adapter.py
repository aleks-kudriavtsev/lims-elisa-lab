"""Adapter stubs for connecting to common LIMS/ELN platforms."""
from datetime import datetime
from typing import Dict, List, Optional

from .config import AuditTrailEntry, CFRPart11Policy, LIMSConfig, LIMSContext


class AuthenticationError(Exception):
    """Raised when authentication fails."""


class AuthorizationError(Exception):
    """Raised when a user is not permitted to perform an action."""


class LIMSAdapter:
    """Stub implementation simulating calls into a LIMS/ELN instance."""

    def __init__(self, context: LIMSContext):
        self.context = context
        self._users: Dict[str, Dict[str, str]] = {}

    def register_user(self, user_id: str, role: str, password: str) -> None:
        if role not in self.context.config.allowed_roles:
            raise AuthorizationError(f"Role {role} is not permitted")
        self._users[user_id] = {"role": role, "password": password}

    def authenticate(self, user_id: str, password: str, otp: Optional[str] = None) -> str:
        user = self._users.get(user_id)
        if not user or user["password"] != password:
            raise AuthenticationError("Invalid credentials")
        if self.context.config.enforce_multi_factor and otp is None:
            raise AuthenticationError("Missing one-time passcode")
        token = f"token-{user_id}-{datetime.utcnow().timestamp()}"
        self._record_action(user_id, "login", signature=token)
        return token

    def _record_action(self, user_id: str, action: str, reason: Optional[str] = None, signature: str = "") -> None:
        entry = AuditTrailEntry(
            user_id=user_id,
            action=action,
            timestamp=datetime.utcnow(),
            signature=signature or f"sig-{user_id}",
            reason=reason if self.context.policy.require_reason_for_changes else None,
        )
        self.context.record(entry)

    def create_sample(self, token: str, sample_meta: Dict[str, str]) -> str:
        self._assert_token(token)
        user_id = token.split("-")[1]
        sample_id = f"S-{len(self.context.audit_trail):04d}"
        self._record_action(user_id, f"create_sample:{sample_id}", signature=token)
        return sample_id

    def approve_record(self, token: str, record_id: str, reason: Optional[str] = None) -> None:
        self._assert_token(token)
        user_id = token.split("-")[1]
        self._record_action(user_id, f"approve:{record_id}", reason=reason, signature=token)

    def _assert_token(self, token: str) -> None:
        if not token.startswith("token-"):
            raise AuthenticationError("Invalid token format")

    def get_audit_trail(self) -> List[AuditTrailEntry]:
        return list(self.context.audit_trail)


__all__ = [
    "AuditTrailEntry",
    "CFRPart11Policy",
    "LIMSAdapter",
    "LIMSConfig",
    "LIMSContext",
    "AuthenticationError",
    "AuthorizationError",
]
