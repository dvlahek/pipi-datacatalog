from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

SH = Namespace("http://www.w3.org/ns/shacl#")
_SHAPES_PATH = Path(__file__).with_name("shapes") / "pipi-dcat-core.ttl"
_PROFILE = "pipi-dcat-core-shacl-v2"


def validate_dataset_jsonld(document: dict[str, Any]) -> dict[str, Any]:
    """Validate one catalog JSON-LD document against the PiPi DCAT core profile.

    The local profile checks provider-neutral structural requirements used by
    the PiPi catalog. It is not a claim of full DCAT-AP conformance.
    """

    data_graph = Graph()
    data_graph.parse(data=json.dumps(document), format="json-ld")

    shapes_graph = Graph()
    shapes_graph.parse(_SHAPES_PATH, format="turtle")

    conforms, report_graph, _ = validate(
        data_graph,
        shacl_graph=shapes_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )

    results: list[dict[str, str | None]] = []
    for result in report_graph.subjects(RDF.type, SH.ValidationResult):
        message = report_graph.value(result, SH.resultMessage)
        path = report_graph.value(result, SH.resultPath)
        focus_node = report_graph.value(result, SH.focusNode)
        severity = report_graph.value(result, SH.resultSeverity)
        source_shape = report_graph.value(result, SH.sourceShape)

        results.append(
            {
                "severity": str(severity) if severity is not None else None,
                "message": str(message) if message is not None else None,
                "path": str(path) if path is not None else None,
                "focus_node": str(focus_node) if focus_node is not None else None,
                "source_shape": str(source_shape) if source_shape is not None else None,
            }
        )

    return {
        "profile": _PROFILE,
        "conforms": bool(conforms),
        "result_count": len(results),
        "results": results,
    }
