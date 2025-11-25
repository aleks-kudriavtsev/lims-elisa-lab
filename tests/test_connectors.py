from connectors.liquid_handler import MockLiquidHandler, Transfer
from connectors.plate_reader import parse_plate_csv


def test_plate_reader_parser(tmp_path):
    csv_path = tmp_path / "plate.csv"
    csv_path.write_text("Well,Value\nA1,0.5\nB1,1.2\n")
    run = parse_plate_csv(str(csv_path), instrument="SpectraMax", assay="IgG")
    assert run.instrument == "SpectraMax"
    assert len(run.readings) == 2
    assert run.to_json()["readings"][0]["well"] == "A1"


def test_mock_liquid_handler_tracks_volumes():
    handler = MockLiquidHandler()
    handler.load_well("A1", 100)
    handler.transfer(Transfer(source="A1", destination="B1", volume_ul=25))
    assert handler.summary()["A1"] == 75
    assert handler.summary()["B1"] == 25
    assert any(entry.startswith("transfer") for entry in handler.audit_log)
