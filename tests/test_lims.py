from datetime import datetime

from lims.adapter import AuthenticationError, LIMSAdapter
from lims.config import CFRPart11Policy, LIMSConfig, LIMSContext


def test_lims_adapter_audit_and_sample_creation():
    context = LIMSContext(
        config=LIMSConfig(system_name="SENAITE", base_url="http://example", api_key="abc"),
        policy=CFRPart11Policy(),
    )
    adapter = LIMSAdapter(context)
    adapter.register_user("alice", role="technician", password="p@ss")
    token = adapter.authenticate("alice", "p@ss", otp="123456")
    sample_id = adapter.create_sample(token, {"type": "serum"})
    adapter.approve_record(token, sample_id, reason="Verified")

    audit_actions = [entry.action for entry in adapter.get_audit_trail()]
    assert "login" in audit_actions
    assert any(action.startswith("create_sample") for action in audit_actions)
    assert any(action.startswith("approve") for action in audit_actions)


def test_authentication_requires_otp():
    context = LIMSContext(
        config=LIMSConfig(system_name="eLabFTW", base_url="http://example", api_key="abc"),
        policy=CFRPart11Policy(),
    )
    adapter = LIMSAdapter(context)
    adapter.register_user("bob", role="qa", password="secure")
    try:
        adapter.authenticate("bob", "secure")
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Expected authentication failure without OTP")
