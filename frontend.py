import os
from datetime import datetime
from typing import Dict, List, Tuple

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from lims.adapter import AuthenticationError, LIMSAdapter
from lims.config import CFRPart11Policy, LIMSConfig, LIMSContext
from orchestrator.workflow import build_full_run
from qc.westgard import ControlResult

app = Flask(__name__)
app.secret_key = os.environ.get("FRONTEND_SECRET_KEY", "dev-secret-key")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")

ASSAY_OPTIONS = ["IRT", "hTSH", "17-OHP", "TGal", "CPK-MM"]

lim_config = LIMSConfig(
    system_name="DemoLIMS",
    base_url="http://localhost",
    api_key="demo",
)
lim_policy = CFRPart11Policy()
lim_context = LIMSContext(config=lim_config, policy=lim_policy)
adapter = LIMSAdapter(lim_context)
adapter.register_user("alice", role="technician", password="p@ss")
adapter.register_user("bob", role="qa", password="secure")
adapter.register_user("carol", role="admin", password="root")

ACTION_ROLES = {
    "create_sample": {"technician", "admin"},
    "approve_record": {"qa", "admin"},
}


operator_journal: List[str] = []


def record_action(actor: str, action: str) -> None:
    timestamp = datetime.utcnow().isoformat()
    entry = f"{timestamp}Z - {actor}: {action}"
    operator_journal.append(entry)


def ensure_upload_folder() -> None:
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def current_user() -> Dict[str, str]:
    return session.get("auth", {})


def require_login():
    if not session.get("auth"):
        flash("Войдите в систему для продолжения")
        return redirect(url_for("login"))
    return None


def role_allowed(action: str) -> bool:
    role = current_user().get("role")
    allowed = ACTION_ROLES.get(action, set(lim_config.allowed_roles))
    return bool(role and role in allowed)


def get_audit_entries() -> List[Dict[str, str]]:
    entries = []
    for entry in adapter.get_audit_trail():
        entries.append(
            {
                "user": entry.user_id,
                "action": entry.action,
                "timestamp": entry.timestamp.isoformat(),
                "signature": entry.signature,
                "reason": entry.reason,
            }
        )
    return entries


@app.context_processor
def inject_globals() -> Dict[str, object]:
    return {"current_user": current_user(), "lim_config": lim_config, "lim_policy": lim_policy}


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")
        otp = request.form.get("otp") or None
        if not user_id or not password:
            flash("Укажите логин и пароль")
            return redirect(url_for("login"))
        try:
            token = adapter.authenticate(user_id, password, otp=otp)
        except AuthenticationError as exc:
            flash(str(exc))
            return redirect(url_for("login"))
        role = adapter.get_role(user_id) or ""
        session["auth"] = {"user_id": user_id, "role": role, "token": token}
        flash(f"Вход выполнен, роль: {role}")
        return redirect(url_for("select_test"))
    return render_template("login.html", allowed_roles=lim_config.allowed_roles, policy=lim_policy)


@app.route("/logout")
def logout():
    session.pop("auth", None)
    session.pop("wizard", None)
    flash("Вы вышли из системы")
    return redirect(url_for("login"))


@app.route("/")
def index() -> str:
    return redirect(url_for("select_test"))


@app.route("/wizard/test", methods=["GET", "POST"])
def select_test():
    if redirect_response := require_login():
        return redirect_response
    if request.method == "POST":
        assay = request.form.get("assay")
        instrument = request.form.get("instrument")
        operator = request.form.get("operator") or current_user().get("user_id", "unknown")
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
    if redirect_response := require_login():
        return redirect_response
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
    if redirect_response := require_login():
        return redirect_response
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
        if not standards_list:
            flash("Введите хотя бы одну строку стандарта перед продолжением")
            return redirect(url_for("standards"))
        wizard.update({
            "standards": standards_list,
            "controls": controls_list,
            "standards_raw": standards_raw,
            "controls_raw": controls_raw,
        })
        session["wizard"] = wizard
        record_action(wizard.get("operator", "unknown"), "подтвердил стандарты и контроли")
        if not wizard.get("sample_id"):
            if not role_allowed("create_sample"):
                flash("Недостаточно прав для создания записи образца")
                return redirect(url_for("standards"))
            token = current_user().get("token", "")
            sample_id = adapter.create_sample(
                token,
                {
                    "assay": wizard.get("assay", ""),
                    "instrument": wizard.get("instrument", ""),
                    "operator": wizard.get("operator", ""),
                },
            )
            wizard["sample_id"] = sample_id
            session["wizard"] = wizard
            flash(f"Создана запись образца {sample_id}")
        return redirect(url_for("review"))
    return render_template(
        "standards.html",
        wizard=wizard,
        default_standards=default_standards,
        default_controls=default_controls,
    )


@app.route("/wizard/review")
def review():
    if redirect_response := require_login():
        return redirect_response
    wizard = session.get("wizard")
    if not wizard or "controls" not in wizard:
        return redirect(url_for("standards"))
    if not wizard.get("standards"):
        flash("Введите стандарты перед просмотром результатов")
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
    audit_log = get_audit_entries()
    approval = wizard.get("approved_by")
    can_approve = role_allowed("approve_record")
    return render_template(
        "review.html",
        wizard=wizard,
        ingest=result_map.get("ingest"),
        analytics=analytics_result,
        westgard=westgard,
        audit_entries=audit_entries,
        audit_log=audit_log,
        approval=approval,
        can_approve=can_approve,
    )


@app.route("/wizard/approve", methods=["POST"])
def approve():
    if redirect_response := require_login():
        return redirect_response
    wizard = session.get("wizard") or {}
    approver = request.form.get("approver") or current_user().get("user_id", "approver-unknown")
    reason = request.form.get("reason") or None
    if lim_policy.require_reason_for_changes and not reason:
        flash("Укажите причину изменения для аудита")
        return redirect(url_for("review"))
    if not role_allowed("approve_record"):
        flash("Недостаточно прав для утверждения")
        return redirect(url_for("review"))
    token = current_user().get("token", "")
    record_id = wizard.get("sample_id") or "result"
    adapter.approve_record(token, record_id, reason=reason)
    wizard["approved_by"] = approver
    wizard["approval_reason"] = reason
    session["wizard"] = wizard
    record_action(approver, "утвердил результаты анализа")
    flash("Результаты утверждены")
    return redirect(url_for("review"))


if __name__ == "__main__":
    ensure_upload_folder()
    app.run(debug=True)
