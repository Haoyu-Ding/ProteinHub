from __future__ import annotations

from Bio.Seq import Seq
from dnachisel import reverse_translate

from proteinhub.domain.errors import DomainError


def reverse_translate_protein(sequence: str) -> str:
    protein_sequence = _normalize_protein_sequence(sequence)
    if not protein_sequence:
        raise DomainError("Sequence is required")

    try:
        dna_sequence = _normalize_dna_sequence(str(reverse_translate(protein_sequence)))
    except Exception as exc:
        raise DomainError("Protein sequence could not be reverse translated") from exc

    if translation_matches(protein_sequence, dna_sequence):
        return dna_sequence

    raise DomainError("DNA sequence could not be verified against protein sequence")


def translate_dna(dna_sequence: str) -> str:
    normalized = _normalize_dna_sequence(dna_sequence)
    full_codon_length = len(normalized) - (len(normalized) % 3)
    return str(Seq(normalized[:full_codon_length]).translate())


def translation_matches(protein_sequence: str, dna_sequence: str) -> bool:
    return translate_dna(dna_sequence) == _normalize_protein_sequence(protein_sequence)


def _normalize_protein_sequence(sequence: str) -> str:
    return "".join(sequence.upper().split())


def _normalize_dna_sequence(sequence: str) -> str:
    return "".join(sequence.upper().replace("U", "T").split())

#import dnachisel
#str1 = dnachisel.biotools.CODON_TABLE_NAMES
#print(str1)