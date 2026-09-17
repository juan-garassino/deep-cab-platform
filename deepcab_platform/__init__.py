"""deepcab-platform — CLI + library for the deepCab GCP platform.

Mirrors the 001 deepCab API package layout:

    deepcab_platform/
    ├── schemas/      pydantic models + str-Enums + settings
    ├── providers/    Protocols + Real/DryRun impls for gcloud / gh / terraform / http
    ├── services/     Dataclasses with DI providers; one per concern
    ├── cli/          Typer subcommands wrapping services
    └── deps.py       wires providers → services → cli

Documented entry point: `deepcab-platform <subcommand>` (see pyproject.toml
[project.scripts]).
"""

__version__ = "0.1.0"
