from datetime import datetime, timedelta

import pytest

from sop_runner.workflow import TemplateLibrary, WorkflowService


def test_workflow_enforces_step_order():
    service = WorkflowService()
    wf = service.create_workflow("run-1", ["prep", "measure"])
    start = service.record_step_start("run-1", operator="alice", inputs={"operator": "alice", "reagent_lot": "lot1"})
    assert start.name == "prep"
    signed = service.record_step_signature("run-1", signature="sig1", completion_inputs={})
    assert signed.signature == "sig1"
    start2 = service.record_step_start(
        "run-1", operator="bob", inputs={"operator": "bob", "reagent_lot": "lot2"}
    )
    assert start2.name == "measure"

    summary = service.get_workflow_summary("run-1")
    assert len(summary) == 2
    assert summary[0]["completed"] is True


def test_template_driven_workflow_exposes_requirements():
    service = WorkflowService()
    wf = service.create_workflow_from_template("elisa-run", "elisa_basic")

    requirements = service.get_workflow_requirements("elisa-run")
    assert len(requirements) == 3
    assert requirements[0]["required_start_fields"] == ["operator", "reagent_lot"]
    assert "controls" in requirements[1]
    assert "reagents" in requirements[0]


def test_step_cannot_complete_without_required_fields(tmp_path):
    custom_template = tmp_path / "custom.yaml"
    custom_template.write_text(
        """
name: custom
steps:
  - name: incubation
    required_start_fields: [operator, reagent_lot]
    required_completion_fields: [incubation_time_minutes]
    min_duration_minutes: 1
"""
    )

    library = TemplateLibrary(template_dir=tmp_path)
    service = WorkflowService(template_library=library)
    service.create_workflow_from_template("custom-run", "custom")

    record = service.record_step_start(
        "custom-run", operator="carol", inputs={"operator": "carol", "reagent_lot": "L1"}
    )

    with pytest.raises(ValueError):
        service.record_step_signature("custom-run", signature="sig")

    # simulate incubation for longer than required minimum
    record.started_at = datetime.utcnow() - timedelta(minutes=2)
    completed = service.record_step_signature(
        "custom-run", signature="sig", completion_inputs={"incubation_time_minutes": "2"}
    )
    assert completed.signature == "sig"
