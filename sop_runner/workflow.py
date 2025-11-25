"""Lightweight SOP execution workflow service."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class StepTemplate:
    """Definition of a workflow step driven by a template file."""

    name: str
    required_start_fields: List[str] = field(default_factory=list)
    required_completion_fields: List[str] = field(default_factory=list)
    min_duration_seconds: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    controls: List[str] = field(default_factory=list)
    reagents: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class StepRecord:
    definition: StepTemplate
    operator: str
    started_at: datetime
    start_data: Dict[str, str]
    completed_at: Optional[datetime] = None
    completion_data: Dict[str, str] = field(default_factory=dict)
    signature: Optional[str] = None

    @property
    def name(self) -> str:
        return self.definition.name


@dataclass
class SOPWorkflow:
    templates: List[StepTemplate]
    _records: List[StepRecord] = field(default_factory=list)
    _current_index: int = 0

    def start_next_step(self, operator: str, inputs: Dict[str, str]) -> StepRecord:
        if self._current_index >= len(self.templates):
            raise IndexError("All steps completed")

        definition = self.templates[self._current_index]
        missing_fields = [field for field in definition.required_start_fields if field not in inputs]
        if missing_fields:
            raise ValueError(f"Missing required start fields: {', '.join(missing_fields)}")

        record = StepRecord(
            definition=definition,
            operator=operator,
            started_at=datetime.utcnow(),
            start_data=inputs,
        )
        self._records.append(record)
        return record

    def sign_off_step(self, signature: str, completion_inputs: Optional[Dict[str, str]] = None) -> StepRecord:
        completion_inputs = completion_inputs or {}
        if self._current_index >= len(self._records):
            raise ValueError("No step started")
        record = self._records[self._current_index]
        if record.completed_at is not None:
            raise ValueError("Step already signed")

        missing_fields = [
            field for field in record.definition.required_completion_fields if field not in completion_inputs
        ]
        if missing_fields:
            raise ValueError(f"Missing required completion fields: {', '.join(missing_fields)}")

        now = datetime.utcnow()
        duration = now - record.started_at

        if record.definition.min_duration_seconds is not None and duration < timedelta(
            seconds=record.definition.min_duration_seconds
        ):
            raise ValueError("Step completed too quickly")

        if record.definition.max_duration_seconds is not None and duration > timedelta(
            seconds=record.definition.max_duration_seconds
        ):
            raise ValueError("Step exceeded maximum duration")

        record.completed_at = now
        record.completion_data = completion_inputs
        record.signature = signature
        self._current_index += 1
        return record

    def summary(self) -> List[Dict[str, str]]:
        return [
            {
                "name": record.name,
                "operator": record.operator,
                "started_at": record.started_at.isoformat(),
                "start_data": record.start_data,
                "completed": record.completed_at is not None,
                "completion_data": record.completion_data,
                "signature": record.signature or "",
            }
            for record in self._records
        ]

    def step_requirements(self) -> List[Dict[str, object]]:
        return [
            {
                "name": template.name,
                "required_start_fields": template.required_start_fields,
                "required_completion_fields": template.required_completion_fields,
                "min_duration_seconds": template.min_duration_seconds,
                "max_duration_seconds": template.max_duration_seconds,
                "controls": template.controls,
                "reagents": template.reagents,
            }
            for template in self.templates
        ]


class TemplateLibrary:
    """Loads SOP templates from YAML/JSON definitions."""

    def __init__(self, template_dir: Optional[Path] = None):
        base_dir = template_dir or Path(__file__).parent / "templates"
        self.template_dir = Path(base_dir)

    def get_template(self, template_name: str) -> List[StepTemplate]:
        template_path = self._resolve_template_path(template_name)
        with template_path.open() as f:
            raw = yaml.safe_load(f)
        steps: List[StepTemplate] = []
        for step in raw.get("steps", []):
            steps.append(
                StepTemplate(
                    name=step["name"],
                    required_start_fields=step.get("required_start_fields", []),
                    required_completion_fields=step.get("required_completion_fields", []),
                    min_duration_seconds=self._parse_duration(step, "min_duration_minutes"),
                    max_duration_seconds=self._parse_duration(step, "max_duration_minutes"),
                    controls=step.get("controls", []),
                    reagents=step.get("reagents", []),
                )
            )
        return steps

    def _resolve_template_path(self, template_name: str) -> Path:
        path = self.template_dir / f"{template_name}.yaml"
        if path.exists():
            return path
        path = self.template_dir / f"{template_name}.yml"
        if path.exists():
            return path
        path = self.template_dir / f"{template_name}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"Template {template_name} not found in {self.template_dir}")

    def _parse_duration(self, step: Dict[str, object], key: str) -> Optional[int]:
        minutes = step.get(key)
        if minutes is None:
            return None
        return int(minutes) * 60


class WorkflowService:
    """Step-enforcing service tracking operator metadata and signatures."""

    def __init__(self, template_library: Optional[TemplateLibrary] = None):
        self._workflows: Dict[str, SOPWorkflow] = {}
        self.template_library = template_library or TemplateLibrary()

    def create_workflow(self, workflow_id: str, steps: List[str]) -> SOPWorkflow:
        if workflow_id in self._workflows:
            raise KeyError("Workflow already exists")
        templates = [StepTemplate(name=step) for step in steps]
        self._workflows[workflow_id] = SOPWorkflow(templates=templates)
        return self._workflows[workflow_id]

    def create_workflow_from_template(self, workflow_id: str, template_name: str) -> SOPWorkflow:
        if workflow_id in self._workflows:
            raise KeyError("Workflow already exists")
        templates = self.template_library.get_template(template_name)
        self._workflows[workflow_id] = SOPWorkflow(templates=templates)
        return self._workflows[workflow_id]

    def record_step_start(self, workflow_id: str, operator: str, inputs: Dict[str, str]) -> StepRecord:
        workflow = self._get_workflow(workflow_id)
        return workflow.start_next_step(operator, inputs)

    def record_step_signature(self, workflow_id: str, signature: str, completion_inputs: Optional[Dict[str, str]] = None) -> StepRecord:
        workflow = self._get_workflow(workflow_id)
        return workflow.sign_off_step(signature, completion_inputs)

    def get_workflow_summary(self, workflow_id: str) -> List[Dict[str, str]]:
        return self._get_workflow(workflow_id).summary()

    def get_workflow_requirements(self, workflow_id: str) -> List[Dict[str, object]]:
        return self._get_workflow(workflow_id).step_requirements()

    def _get_workflow(self, workflow_id: str) -> SOPWorkflow:
        if workflow_id not in self._workflows:
            raise KeyError("Workflow not found")
        return self._workflows[workflow_id]
