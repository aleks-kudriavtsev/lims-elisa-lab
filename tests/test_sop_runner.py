from sop_runner.workflow import WorkflowService


def test_workflow_enforces_step_order():
    service = WorkflowService()
    wf = service.create_workflow("run-1", ["prep", "measure"])
    start = service.record_step_start("run-1", operator="alice", reagent_lot="lot1")
    assert start.name == "prep"
    signed = service.record_step_signature("run-1", signature="sig1")
    assert signed.signature == "sig1"
    start2 = service.record_step_start("run-1", operator="bob", reagent_lot="lot2")
    assert start2.name == "measure"

    summary = service.get_workflow_summary("run-1")
    assert len(summary) == 2
    assert summary[0]["completed"] is True
