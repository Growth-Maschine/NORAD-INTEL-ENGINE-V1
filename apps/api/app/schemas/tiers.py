"""Tier helpers: build the trimmed engine "contract" schema and stub Tier-C
gap fields on incoming engine outputs.

The contract schema is what we send Parallel + Exa as their JSON output target.
Tier C fields are dropped from the contract because no public-web crawl can
fill them — they require Phyllo / Similarweb / SPINS / Apollo / etc. Once the
engines return, the worker auto-stubs those fields with `confidence="unknown"`
and a `gap_reason` so the saved card always conforms to the full schema.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def strip_tier_c(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the JSON Schema with all `tier: "C"` properties removed.

    Walks the schema recursively, including `$defs`. Mutates only the copy.
    """
    out = deepcopy(schema)
    _strip_node(out)
    if "$defs" in out:
        for defn in out["$defs"].values():
            _strip_node(defn)
    return out


def _strip_node(node: dict[str, Any]) -> None:
    props = node.get("properties")
    if not isinstance(props, dict):
        return
    to_delete: list[str] = []
    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("tier") == "C":
            to_delete.append(name)
            continue
        # Recurse into nested object schemas
        if "properties" in prop:
            _strip_node(prop)
    for name in to_delete:
        del props[name]
        if "required" in node and name in node["required"]:
            node["required"].remove(name)


def enforce_contract_required(
    schema: dict[str, Any],
    required_top_level: list[str],
) -> dict[str, Any]:
    """Strengthen JSON Schema for the engine contract.

    Pydantic v2 omits fields-with-defaults from `required`, which lets engines
    return half-empty cards. We post-process the schema to (a) require the
    top-level blocks and (b) force `confidence` to be required on every
    `Valued_*` sub-model in `$defs`. Engines must still return structure even
    when they can't fill values.
    """
    out = deepcopy(schema)
    # Top-level required blocks
    existing_required = set(out.get("required", []))
    existing_required.update(required_top_level)
    # Only keep names that actually exist in properties (so trimmed contract
    # doesn't list non-existent fields).
    props = out.get("properties", {})
    out["required"] = sorted(name for name in existing_required if name in props)

    # Every Valued_* sub-model must require `confidence`
    for def_name, defn in out.get("$defs", {}).items():
        if not def_name.startswith("Valued"):
            continue
        if not isinstance(defn, dict) or "properties" not in defn:
            continue
        req = set(defn.get("required", []))
        req.add("confidence")
        defn["required"] = sorted(req)
    return out


def list_tier_c_paths(schema: dict[str, Any]) -> list[str]:
    """Return dotted paths for every Tier-C field (UI display + worker stubbing)."""
    paths: list[str] = []
    _walk_collect(schema, "", paths, schema.get("$defs", {}))
    return paths


def _walk_collect(
    node: dict[str, Any],
    prefix: str,
    out: list[str],
    defs: dict[str, Any],
) -> None:
    if not isinstance(node, dict):
        return
    # Resolve $ref one level if needed
    if "$ref" in node:
        ref = node["$ref"].split("/")[-1]
        if ref in defs:
            _walk_collect(defs[ref], prefix, out, defs)
        return
    props = node.get("properties")
    if not isinstance(props, dict):
        return
    for name, prop in props.items():
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(prop, dict):
            if prop.get("tier") == "C":
                out.append(path)
            else:
                _walk_collect(prop, path, out, defs)
