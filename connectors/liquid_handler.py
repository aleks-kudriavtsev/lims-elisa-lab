"""Mock liquid handler interface for tests."""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Transfer:
    source: str
    destination: str
    volume_ul: float


@dataclass
class MockLiquidHandler:
    audit_log: List[str] = field(default_factory=list)
    deck_state: Dict[str, float] = field(default_factory=dict)

    def load_well(self, well: str, volume_ul: float) -> None:
        self.deck_state[well] = self.deck_state.get(well, 0.0) + volume_ul
        self.audit_log.append(f"load:{well}:{volume_ul}")

    def transfer(self, transfer: Transfer) -> None:
        available = self.deck_state.get(transfer.source, 0.0)
        if available < transfer.volume_ul:
            raise ValueError("Insufficient volume")
        self.deck_state[transfer.source] = available - transfer.volume_ul
        self.deck_state[transfer.destination] = self.deck_state.get(transfer.destination, 0.0) + transfer.volume_ul
        self.audit_log.append(
            f"transfer:{transfer.source}->{transfer.destination}:{transfer.volume_ul}"
        )

    def summary(self) -> Dict[str, float]:
        return dict(self.deck_state)
