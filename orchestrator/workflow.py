"""Workflow DAG chaining SOP execution, data ingestion, analytics, and QC."""
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from connectors.plate_reader import parse_plate_csv
from analytics.curve_fitting import fit_4pl, fit_5pl
from qc.westgard import ControlResult, check_westgard
from sop_runner.workflow import WorkflowService


@dataclass
class AuditLogger:
    entries: List[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.entries.append(message)


@dataclass
class WorkflowTask:
    name: str
    func: Callable[..., object]


class WorkflowDAG:
    def __init__(self, logger: AuditLogger):
        self.logger = logger
        self.tasks: List[WorkflowTask] = []

    def add_task(self, name: str, func: Callable[..., object]) -> None:
        self.tasks.append(WorkflowTask(name=name, func=func))

    def run(self) -> List[Tuple[str, object]]:
        results: List[Tuple[str, object]] = []
        for task in self.tasks:
            output = task.func()
            results.append((task.name, output))
            self.logger.log(f"executed:{task.name}")
        return results


def build_full_run(
    plate_path: str, instrument: str, assay: str, standards: List[Tuple[float, float]], controls: List[ControlResult]
) -> Tuple[WorkflowDAG, AuditLogger]:
    logger = AuditLogger()
    service = WorkflowService()
    workflow = service.create_workflow("elisa", ["prepare", "read", "analyze", "qc"])

    dag = WorkflowDAG(logger)

    dag.add_task(
        "prepare",
        lambda: service.record_step_start("elisa", operator="operator-1", reagent_lot="lot-1"),
    )
    dag.add_task("sign-prepare", lambda: service.record_step_signature("elisa", signature="sig-prepare"))

    dag.add_task(
        "ingest",
        lambda: parse_plate_csv(plate_path, instrument=instrument, assay=assay).to_json(),
    )

    def _fit():
        xs, ys = zip(*standards)
        fit = fit_4pl(xs, ys)
        return {"fit": fit, "curve": fit_5pl(xs, ys)}

    dag.add_task("analytics", _fit)

    dag.add_task("qc", lambda: check_westgard(controls))
    return dag, logger
