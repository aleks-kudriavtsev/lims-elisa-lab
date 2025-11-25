import os
from datetime import datetime
from typing import Dict, List, Tuple

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from orchestrator.workflow import build_full_run
from qc.westgard import ControlResult

app = Flask(__name__)
app.secret_key = os.environ.get("FRONTEND_SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

ASSAY_OPTIONS = ["IRT", "hTSH", "17-OHP", "TGal", "CPK-MM"]


operator_journal: List[str] = []


def record_action(actor: str, action: str) -> None:
    timestamp = datetime.utcnow().isoformat()
    entry = f"{timestamp}Z - {actor}: {action}"
    operator_journal.append(entry)


def ensure_upload_folder() -> None:
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def parse_standards(raw: str) -> List[Tuple[float, float]]:
    standards: List[Tuple[float, float]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            conc, signal = [float(part.strip()) for part in line.split(",")]
        except ValueError as exc:  # pragma: no cover - guarded by user input
            raise ValueError(f"Invalid standard entry '{line}': {exc}")
        standards.append((conc, signal))
    return standards


def parse_controls(raw: str) -> List[Dict[str, float]]:
    controls: List[Dict[str, float]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            run_id, value, mean, sd = [float(part.strip()) for part in line.split(",")]
        except ValueError as exc:  # pragma: no cover - guarded by user input
            raise ValueError(f"Invalid control entry '{line}': {exc}")
        controls.append({"run": int(run_id), "value": value, "mean": mean, "sd": sd})
    return controls


@app.route("/")
def index() -> str:
    return redirect(url_for("select_test"))


@app.route("/wizard/test", methods=["GET", "POST"])
def select_test():
    if request.method == "POST":
        assay = request.form.get("assay")
        instrument = request.form.get("instrument")
        operator = request.form.get("operator") or "unknown"
        if not assay or assay not in ASSAY_OPTIONS:
            flash("Выберите тест из списка")
            return redirect(url_for("select_test"))
        session["wizard"] = {"assay": assay, "instrument": instrument or "", "operator": operator}
        record_action(operator, f"выбрал тест {assay} на приборе '{instrument or 'не указан'}'")
        return redirect(url_for("upload_csv"))
    wizard = session.get("wizard", {})
    return render_template("test_select.html", assays=ASSAY_OPTIONS, wizard=wizard)


@app.route("/wizard/upload", methods=["GET", "POST"])
def upload_csv():
    wizard = session.get("wizard")
    if not wizard:
        return redirect(url_for("select_test"))
    if request.method == "POST":
        ensure_upload_folder()
        file = request.files.get("plate_csv")
        operator = request.form.get("uploader") or wizard.get("operator", "unknown")
        if not file or file.filename == "":
            flash("Загрузите CSV файл с показаниями")
            return redirect(url_for("upload_csv"))
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        wizard.update({"plate_path": filepath, "uploaded_by": operator})
        session["wizard"] = wizard
        record_action(operator, f"загрузил CSV {filename}")
        return redirect(url_for("standards"))
    return render_template("upload.html", wizard=wizard)


@app.route("/wizard/standards", methods=["GET", "POST"])
def standards():
    wizard = session.get("wizard")
    if not wizard or "plate_path" not in wizard:
        return redirect(url_for("upload_csv"))
    default_standards = wizard.get("standards_raw", "0.5, 0.6\n1.0, 1.1\n2.0, 2.1\n4.0, 4.2")
    default_controls = wizard.get("controls_raw", "1, 0.9, 1.0, 0.05\n2, 1.1, 1.0, 0.05\n3, 1.0, 1.0, 0.05\n4, 1.05, 1.0, 0.05")
    if request.method == "POST":
        standards_raw = request.form.get("standards") or ""
        controls_raw = request.form.get("controls") or ""
        try:
            standards_list = parse_standards(standards_raw)
            controls_list = parse_controls(controls_raw)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("standards"))
        wizard.update({
            "standards": standards_list,
            "controls": controls_list,
            "standards_raw": standards_raw,
            "controls_raw": controls_raw,
        })
        session["wizard"] = wizard
        record_action(wizard.get("operator", "unknown"), "подтвердил стандарты и контроли")
        return redirect(url_for("review"))
    return render_template(
        "standards.html",
        wizard=wizard,
        default_standards=default_standards,
        default_controls=default_controls,
    )


@app.route("/wizard/review")
def review():
    wizard = session.get("wizard")
    if not wizard or "controls" not in wizard:
        return redirect(url_for("standards"))
    controls_objects = [
        ControlResult(run=ctrl["run"], value=ctrl["value"], mean=ctrl["mean"], sd=ctrl["sd"])
        for ctrl in wizard.get("controls", [])
    ]
    dag, run_logger = build_full_run(
        plate_path=wizard["plate_path"],
        instrument=wizard.get("instrument", ""),
        assay=wizard.get("assay", ""),
        standards=wizard.get("standards", []),
        controls=controls_objects,
    )
    dag_results = dag.run()
    result_map = {name: result for name, result in dag_results}
    analytics_result = result_map.get("analytics", {})
    westgard = result_map.get("qc", {})
    audit_entries = operator_journal + run_logger.entries
    approval = wizard.get("approved_by")
    return render_template(
        "review.html",
        wizard=wizard,
        ingest=result_map.get("ingest"),
        analytics=analytics_result,
        westgard=westgard,
        audit_entries=audit_entries,
        approval=approval,
    )


@app.route("/wizard/approve", methods=["POST"])
def approve():
    wizard = session.get("wizard") or {}
    approver = request.form.get("approver") or "approver-unknown"
    wizard["approved_by"] = approver
    session["wizard"] = wizard
    record_action(approver, "утвердил результаты анализа")
    flash("Результаты утверждены")
    return redirect(url_for("review"))


if __name__ == "__main__":
    ensure_upload_folder()
    app.run(debug=True)
