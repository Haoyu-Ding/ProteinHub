from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Mapping

from proteinhub.domain.errors import DomainError


@dataclass(frozen=True)
class BatchExperiment:
    experiment_type: ClassVar[str]
    detail_table: ClassVar[str]
    name: str
    description: str = ""
    details: dict[str, Any] | None = None

    @classmethod
    def normalize_details(cls, details: Mapping[str, Any] | None) -> dict[str, Any]:
        if details is None:
            return {}
        return {str(key): value for key, value in details.items()}


class FPLCExperiment(BatchExperiment):
    experiment_type = "FPLC"
    detail_table = "fplc_experiments"


class SPRExperiment(BatchExperiment):
    experiment_type = "SPR"
    detail_table = "spr_experiments"


class HPLCExperiment(BatchExperiment):
    experiment_type = "HPLC"
    detail_table = "hplc_experiments"


EXPERIMENT_TYPES: dict[str, type[BatchExperiment]] = {
    FPLCExperiment.experiment_type: FPLCExperiment,
    SPRExperiment.experiment_type: SPRExperiment,
    HPLCExperiment.experiment_type: HPLCExperiment,
}


def experiment_class_for(experiment_type: str) -> type[BatchExperiment]:
    normalized = experiment_type.strip().upper()
    experiment_class = EXPERIMENT_TYPES.get(normalized)
    if experiment_class is None:
        raise DomainError("Experiment type must be FPLC, SPR, or HPLC")
    return experiment_class
