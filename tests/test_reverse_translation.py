import pytest

from proteinhub.application.reverse_translation import (
    reverse_translate_protein,
    translate_dna,
    translation_matches,
)
from proteinhub.domain.errors import DomainError


def test_reverse_translation_encodes_original_protein_sequence() -> None:
    dna_sequence = reverse_translate_protein("ACDEFG")

    assert len(dna_sequence) == 18
    assert translate_dna(dna_sequence) == "ACDEFG"
    assert translation_matches("ACDEFG", dna_sequence)


def test_reverse_translation_rejects_unverified_dna_sequence() -> None:
    with pytest.raises(DomainError):
        reverse_translate_protein("AX")
