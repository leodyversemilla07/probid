"""Shared output rendering helpers for probid CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click


_TEXT_EXPORT_FORMATS = {"markdown", "timeline", "findings_table", "csv"}
_MARKDOWN_EXPORT_FORMATS = {"markdown", "timeline", "findings_table"}


def resolve_output_text(
    *,
    result: dict,
    json_output: bool,
    export_output: bool,
    output_path: str | None,
) -> str:
    if export_output:
        export = result.get("export")
        if not export:
            raise click.UsageError("Query did not produce export content. Run an export-oriented follow-up first.")
        export_format = str(export.get("format", "")).strip().lower()
        export_content = export.get("content")
        suffix = Path(output_path).suffix.lower() if output_path else ""

        if suffix == ".json":
            if export_format in _TEXT_EXPORT_FORMATS:
                raise click.UsageError("Text export should be written to .md, .csv, or stdout, not .json.")
            return json.dumps(export_content, indent=2, ensure_ascii=False)

        if suffix in {".md", ".markdown"}:
            if export_format not in _MARKDOWN_EXPORT_FORMATS or not isinstance(export_content, str):
                raise click.UsageError("Structured export should be written to .json, and CSV export should be written to .csv.")
            return export_content

        if suffix == ".csv":
            if export_format != "csv" or not isinstance(export_content, str):
                raise click.UsageError("Only CSV export should be written to .csv.")
            return export_content

        if json_output or not isinstance(export_content, str):
            return json.dumps(export_content, indent=2, ensure_ascii=False)
        return export_content

    if json_output:
        return json.dumps(result, indent=2, ensure_ascii=False)
    return str(result)
