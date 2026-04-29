"""OpenAPI spec fetcher + parser.

parse_spec(spec, device_name) -> [ToolDef]
Each ToolDef captures everything needed to:
  1. expose the operation as a tool to an AI (name, description, JSON schema)
  2. translate a tool call back into the right HTTP request (proxy.call uses path_keys / query_keys / body_keys)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _safe_identifier(s: str) -> str:
    """Sanitize a string into a valid Python/MCP tool name (^[a-zA-Z_][a-zA-Z0-9_]{0,63}$)."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)
    if s and s[0].isdigit():
        s = "_" + s
    return s[:64] or "tool"


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    device: str
    method: str
    path_template: str
    path_keys: set[str] = field(default_factory=set)
    query_keys: set[str] = field(default_factory=set)
    body_keys: set[str] = field(default_factory=set)


def load_spec(spec_url: str | None, spec_path: str | None) -> dict:
    if spec_path:
        text = Path(spec_path).read_text(encoding="utf-8")
        return yaml.safe_load(text) if spec_path.endswith((".yaml", ".yml")) else json.loads(text)
    if spec_url:
        resp = httpx.get(spec_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        if "yaml" in ct or spec_url.endswith((".yaml", ".yml")):
            return yaml.safe_load(resp.text)
        return resp.json()
    raise ValueError("Device must have spec_url or spec_path")


def _resolve_ref(spec: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        return {}
    node = spec
    for part in ref[2:].split("/"):
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _resolve_schema(spec: dict, schema: dict) -> dict:
    """Resolve a top-level $ref. Does not recurse — sufficient for OpenAPI 3.x bodies."""
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        return _resolve_ref(spec, schema["$ref"])
    return schema


def _slug(s: str) -> str:
    return s.strip("/").replace("/", "_").replace("{", "").replace("}", "").replace("-", "_") or "root"


def parse_spec(spec: dict, device_name: str) -> list[ToolDef]:
    tools: list[ToolDef] = []
    paths = spec.get("paths") or {}

    for path_template, ops in paths.items():
        if not isinstance(ops, dict):
            continue
        for method in HTTP_METHODS:
            op = ops.get(method)
            if not op:
                continue

            op_id = op.get("operationId") or f"{method}_{_slug(path_template)}"
            summary = op.get("summary") or op.get("description") or op_id
            description = (op.get("description") or summary).strip()

            properties: dict = {}
            required: list[str] = []
            path_keys: set[str] = set()
            query_keys: set[str] = set()
            body_keys: set[str] = set()

            # Path + query parameters
            for param in op.get("parameters") or []:
                pname = param.get("name")
                if not pname:
                    continue
                pschema = _resolve_schema(spec, param.get("schema") or {})
                prop = dict(pschema)
                if param.get("description") and "description" not in prop:
                    prop["description"] = param["description"]
                properties[pname] = prop
                if param.get("required"):
                    required.append(pname)
                if param.get("in") == "path":
                    path_keys.add(pname)
                elif param.get("in") == "query":
                    query_keys.add(pname)

            # Request body — flatten top-level object properties into the tool input
            body = op.get("requestBody")
            if body:
                content = body.get("content") or {}
                json_content = content.get("application/json") or next(iter(content.values()), {})
                bschema = _resolve_schema(spec, json_content.get("schema") or {})
                if bschema.get("type") == "object" or "properties" in bschema:
                    for prop_name, prop_schema in (bschema.get("properties") or {}).items():
                        properties[prop_name] = _resolve_schema(spec, prop_schema)
                        body_keys.add(prop_name)
                    for r in bschema.get("required") or []:
                        if r not in required:
                            required.append(r)

            input_schema = {
                "type": "object",
                "properties": properties,
                "required": required,
            }

            tools.append(ToolDef(
                name=_safe_identifier(f"{device_name}_{op_id}"),
                description=f"[{device_name}] {description}",
                input_schema=input_schema,
                device=device_name,
                method=method.upper(),
                path_template=path_template,
                path_keys=path_keys,
                query_keys=query_keys,
                body_keys=body_keys,
            ))

    return tools
