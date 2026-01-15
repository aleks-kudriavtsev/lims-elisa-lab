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
    workflow = service.create_workflow_from_template("elisa", "elisa_basic")

    dag = WorkflowDAG(logger)

    dag.add_task(
        "plate-preparation-start",
        lambda: service.record_step_start(
            "elisa", operator="operator-1", inputs={"operator": "operator-1", "reagent_lot": "lot-1"}
        ),
    )
    dag.add_task(
        "plate-preparation-complete",
        lambda: service.record_step_signature(
            "elisa", signature="sig-prepare", completion_inputs={"incubation_time_minutes": "30"}
        ),
    )

    dag.add_task(
        "ingest",
        lambda: parse_plate_csv(plate_path, instrument=instrument, assay=assay).to_json(),
    )

    dag.add_task(
        "plate-reading-start",
        lambda: service.record_step_start(
            "elisa", operator="operator-2", inputs={"operator": "operator-2", "instrument": instrument}
        ),
    )
    dag.add_task(
        "plate-reading-complete",
        lambda: service.record_step_signature(
            "elisa", signature="sig-read", completion_inputs={"runtime_minutes": "6"}
        ),
    )

    def _fit():
        xs, ys = zip(*standards)
        fit = fit_4pl(xs, ys)
        return {"fit": fit, "curve": fit_5pl(xs, ys)}

    dag.add_task("analytics", _fit)

    dag.add_task(
        "analysis-and-qc-start",
        lambda: service.record_step_start(
            "elisa", operator="analyst-1", inputs={"analyst": "analyst-1"}
        ),
    )
    dag.add_task("qc", lambda: check_westgard(controls))

    dag.add_task(
        "analysis-and-qc-complete",
        lambda: service.record_step_signature(
            "elisa", signature="sig-qc", completion_inputs={"qc_rule": "westgard", "report_path": "/tmp/report"}
        ),
    )
    return dag, logger
