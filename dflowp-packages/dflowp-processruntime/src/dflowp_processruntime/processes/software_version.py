"""Zentrale Versionsdefinition für DFlowP-Process-Dokumente."""

import re

MAJOR_VERSION = 0
MINOR_VERSION = 1


def build_semantic_software_version(raw_version: str | int) -> str:
    """
    Erzeugt eine Version im Format major.minor.build.

    - Wenn bereits eine semantische Version (x.y.z) übergeben wird, bleibt sie unverändert.
    - Andernfalls wird der Wert als Build-Nummer interpretiert.
    """
    raw = str(raw_version).strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", raw):
        return raw
    return f"{MAJOR_VERSION}.{MINOR_VERSION}.{raw}"


def build_software_version(build_number: str | int) -> str:
    """Kompatibilitätsalias."""
    return build_semantic_software_version(build_number)
