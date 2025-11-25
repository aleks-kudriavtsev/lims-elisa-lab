"""Lightweight SOP execution workflow service."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class StepRecord:
    name: str
    operator: str
    reagent_lot: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    signature: Optional[str] = None


@dataclass
class SOPWorkflow:
    steps: List[str]
    _records: List[StepRecord] = field(default_factory=list)
    _current_index: int = 0

    def start_next_step(self, operator: str, reagent_lot: str) -> StepRecord:
        if self._current_index >= len(self.steps):
            raise IndexError("All steps completed")
        name = self.steps[self._current_index]
        record = StepRecord(name=name, operator=operator, reagent_lot=reagent_lot, started_at=datetime.utcnow())
        self._records.append(record)
        return record

    def sign_off_step(self, signature: str) -> StepRecord:
        if self._current_index >= len(self._records):
            raise ValueError("No step started")
        record = self._records[self._current_index]
        if record.completed_at is not None:
            raise ValueError("Step already signed")
        record.completed_at = datetime.utcnow()
        record.signature = signature
        self._current_index += 1
        return record

    def summary(self) -> List[Dict[str, str]]:
        return [
            {
                "name": record.name,
                "operator": record.operator,
                "reagent_lot": record.reagent_lot,
                "completed": record.completed_at is not None,
                "signature": record.signature or "",
            }
            for record in self._records
        ]


class WorkflowService:
    """Step-enforcing service tracking operator metadata and signatures."""

    def __init__(self):
        self._workflows: Dict[str, SOPWorkflow] = {}

    def create_workflow(self, workflow_id: str, steps: List[str]) -> SOPWorkflow:
        if workflow_id in self._workflows:
            raise KeyError("Workflow already exists")
        self._workflows[workflow_id] = SOPWorkflow(steps=steps)
        return self._workflows[workflow_id]

    def record_step_start(self, workflow_id: str, operator: str, reagent_lot: str) -> StepRecord:
        workflow = self._get_workflow(workflow_id)
        return workflow.start_next_step(operator, reagent_lot)

    def record_step_signature(self, workflow_id: str, signature: str) -> StepRecord:
        workflow = self._get_workflow(workflow_id)
        return workflow.sign_off_step(signature)

    def get_workflow_summary(self, workflow_id: str) -> List[Dict[str, str]]:
        return self._get_workflow(workflow_id).summary()

    def _get_workflow(self, workflow_id: str) -> SOPWorkflow:
        if workflow_id not in self._workflows:
            raise KeyError("Workflow not found")
        return self._workflows[workflow_id]
