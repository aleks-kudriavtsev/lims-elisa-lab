from pathlib import Path

from orchestrator.workflow import build_full_run
from qc.westgard import ControlResult


def test_build_full_run_executes_tasks(tmp_path):
    plate_path = tmp_path / "plate.csv"
    plate_path.write_text("Well,Value\nA1,0.1\nA2,0.2\n")
    standards = [(0.1, 0.2), (0.5, 0.4), (1.0, 0.8)]
    controls = [ControlResult(run=i, value=10 + i * 0.5, mean=10, sd=0.5) for i in range(1, 4)]

    dag, logger = build_full_run(str(plate_path), instrument="SpectraMax", assay="IgG", standards=standards, controls=controls)
    results = dag.run()
    names = [name for name, _ in results]
    assert "prepare" in names
    assert "ingest" in names
    assert "analytics" in names
    assert "qc" in names
    assert any(entry.startswith("executed") for entry in logger.entries)
