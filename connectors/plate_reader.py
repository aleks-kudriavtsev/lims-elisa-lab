"""Parsers for plate reader exports."""
import csv
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class WellReading:
    well: str
    value: float


@dataclass
class PlateRun:
    instrument: str
    assay: str
    readings: List[WellReading]

    def to_json(self) -> Dict[str, object]:
        return {
            "instrument": self.instrument,
            "assay": self.assay,
            "readings": [
                {"well": reading.well, "value": reading.value} for reading in self.readings
            ],
        }


def parse_plate_csv(path: str, instrument: str, assay: str) -> PlateRun:
    readings: List[WellReading] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            well = row.get("Well") or row.get("well")
            value_str = row.get("Value") or row.get("value")
            if not well or value_str is None:
                continue
            readings.append(WellReading(well=well.strip(), value=float(value_str)))
    return PlateRun(instrument=instrument, assay=assay, readings=readings)
