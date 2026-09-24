"""Tree-sitter entities, call graph, PageRank, and Louvain communities."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from recoverage.models import ProjectProfile

try:
    from tree_sitter import Language, Parser
    import tree_sitter_python as _ts_python
    import tree_sitter_javascript as _ts_javascript

    _PYTHON = Language(_ts_python.language())
    _JAVASCRIPT = Language(_ts_javascript.language())
    _PARSERS = {
        "python": Parser(_PYTHON),
        "javascript": Parser(_JAVASCRIPT),
        "typescript": Parser(_JAVASCRIPT),
    }
    TREE_SITTER = True
except Exception:  # pragma: no cover - import guard
    _PARSERS = {}
    TREE_SITTER = False


@dataclass
class Entity:
    symbol: str
    qualname: str
    file: str
    kind: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    signature: str
    docstring: str
    calls: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class CodeGraph:
    entities: list[Entity]
    edges: list[tuple[str, str, str]]
    pagerank: dict[str, float]
    communities: dict[str, int]
    tree_sitter: bool

    def query_context(self, symbol: str, limit: int = 8) -> dict:
        """Dependency scope for one focal symbol. Not a raw file dump."""
        needle = symbol.split(".")[-1]
        matches = [
            entity
            for entity in self.entities
            if entity.qualname == symbol or entity.symbol == needle or entity.qualname.endswith("." + needle)
        ]
        if not matches:
            return {"symbol": symbol, "found": False, "dependencies": [], "community": None, "pagerank": 0.0}
        focal = matches[0]
        community = self.communities.get(focal.qualname, -1)
        neighbors = []
        for src, dst, kind in self.edges:
            other = dst if src == focal.qualname else src if dst == focal.qualname else None
            if other is None:
                continue
            neighbors.append(
                {
                    "symbol": other,
                    "relation": kind,
                    "pagerank": round(self.pagerank.get(other, 0.0), 6),
                    "same_community": self.communities.get(other) == community,
                }
            )
        neighbors.sort(key=lambda item: (-item["pagerank"], item["symbol"]))
        return {
            "symbol": focal.qualname,
            "found": True,
            "file": focal.file,
            "byte_range": [focal.start_byte, focal.end_byte],
            "line_range": [focal.start_line, focal.end_line],
            "signature": focal.signature,
            "docstring": focal.docstring,
            "pagerank": round(self.pagerank.get(focal.qualname, 0.0), 6),
            "community": community,
            "dependencies": neighbors[:limit],
        }


def index_project(profile: ProjectProfile) -> CodeGraph:
    root = Path(profile.root)
    entities: list[Entity] = []
    edges: list[tuple[str, str, str]] = []
    for relative in profile.source_files:
        path = root / relative
        language = _language(path)
        if language is None or language not in _PARSERS:
            continue
        source = path.read_bytes()
        tree = _PARSERS[language].parse(source)
        found, found_edges = _walk_file(relative, source, tree.root_node, language)
        entities.extend(found)
        edges.extend(found_edges)
    symbols = [entity.qualname for entity in entities]
    known = set(symbols)
    resolved = []
    for src, dst, kind in edges:
        target = _resolve(dst, known)
        if target is not None:
            resolved.append((src, target, kind))
    ranks = pagerank(symbols, [(src, dst) for src, dst, _kind in resolved])
    communities = louvain(symbols, [(src, dst) for src, dst, _kind in resolved])
    return CodeGraph(
        entities=entities,
        edges=resolved,
        pagerank=ranks,
        communities=communities,
        tree_sitter=TREE_SITTER and bool(entities or profile.source_files),
    )


def pagerank(nodes: list[str], edges: list[tuple[str, str]], *, damping: float = 0.85, steps: int = 40) -> dict[str, float]:
    """Inbound-call PageRank. A callee used from many callers outranks an isolated helper."""
    unique = list(dict.fromkeys(nodes))
    if not unique:
        return {}
    count = len(unique)
    outgoing: dict[str, list[str]] = {node: [] for node in unique}
    present = set(unique)
    for src, dst in edges:
        if src in present and dst in present and src != dst:
            outgoing[src].append(dst)
    rank = {node: 1.0 / count for node in unique}
    for _ in range(steps):
        nxt = {node: (1.0 - damping) / count for node in unique}
        for node in unique:
            targets = outgoing[node]
            if not targets:
                share = damping * rank[node] / count
                for other in unique:
                    nxt[other] += share
            else:
                share = damping * rank[node] / len(targets)
                for dst in targets:
                    nxt[dst] += share
        rank = nxt
    return {node: round(value, 6) for node, value in rank.items()}


def louvain(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, int]:
    """Louvain local-moving phase on the undirected projection of the call graph."""
    unique = list(dict.fromkeys(nodes))
    if not unique:
        return {}
    adj: dict[str, dict[str, float]] = {node: {} for node in unique}
    present = set(unique)
    for src, dst in edges:
        if src not in present or dst not in present or src == dst:
            continue
        adj[src][dst] = adj[src].get(dst, 0.0) + 1.0
        adj[dst][src] = adj[dst].get(src, 0.0) + 1.0
    twice_m = sum(sum(weights.values()) for weights in adj.values())
    if twice_m == 0:
        return {node: index for index, node in enumerate(unique)}
    community = {node: index for index, node in enumerate(unique)}
    degree = {node: sum(adj[node].values()) for node in unique}
    total = {index: degree[node] for index, node in enumerate(unique)}
    members: dict[int, set[str]] = {index: {node} for index, node in enumerate(unique)}

    def neighbor_weight(node: str) -> dict[int, float]:
        weights: dict[int, float] = {}
        for other, weight in adj[node].items():
            weights[community[other]] = weights.get(community[other], 0.0) + weight
        return weights

    improved = True
    passes = 0
    while improved and passes < 12:
        improved = False
        passes += 1
        for node in unique:
            current = community[node]
            strength = degree[node]
            weights = neighbor_weight(node)
            inside_current = weights.get(current, 0.0)
            total[current] -= strength
            members[current].discard(node)
            best = current
            best_gain = 0.0
            stay = inside_current - total[current] * strength / twice_m
            candidates = set(weights) | {current}
            for target in candidates:
                gain = weights.get(target, 0.0) - total.get(target, 0.0) * strength / twice_m
                delta = gain - stay
                if delta > best_gain + 1e-12:
                    best_gain = delta
                    best = target
            if best == current or best_gain <= 0:
                total[current] += strength
                members[current].add(node)
                community[node] = current
            else:
                community[node] = best
                total[best] = total.get(best, 0.0) + strength
                members.setdefault(best, set()).add(node)
                improved = True
    remap: dict[int, int] = {}
    assigned: dict[str, int] = {}
    for node in unique:
        raw = community[node]
        if raw not in remap:
            remap[raw] = len(remap)
        assigned[node] = remap[raw]
    return assigned


def _language(path: Path) -> str | None:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
    }.get(path.suffix.lower())


def _walk_file(relative: str, source: bytes, root, language: str) -> tuple[list[Entity], list[tuple[str, str, str]]]:
    entities: list[Entity] = []
    edges: list[tuple[str, str, str]] = []
    stack: list[tuple[object, str | None]] = [(root, None)]
    seen_spans: set[tuple[int, int]] = set()
    while stack:
        node, class_name = stack.pop()
        next_class = class_name
        if node.type in {"class_definition", "class_declaration"}:
            next_class = _field_text(node, source, "name") or class_name
        if node.type in {"function_definition", "function_declaration", "method_definition"} or _is_arrow(node):
            span = (node.start_byte, node.end_byte)
            if span not in seen_spans:
                seen_spans.add(span)
                entity = _entity_from(node, relative, source, class_name, language)
                if entity is not None:
                    entities.append(entity)
                    for callee in _calls(node):
                        edges.append((entity.qualname, callee, "call"))
        for child in reversed(list(node.children)):
            stack.append((child, next_class))
    return entities, edges


def _is_arrow(node) -> bool:
    if node.type != "variable_declarator":
        return False
    value = node.child_by_field_name("value") if hasattr(node, "child_by_field_name") else None
    return value is not None and value.type in {"arrow_function", "function"}


def _entity_from(node, relative: str, source: bytes, class_name: str | None, language: str) -> Entity | None:
    if _is_arrow(node):
        name = _field_text(node, source, "name")
        body = node.child_by_field_name("value")
    else:
        name = _field_text(node, source, "name")
        body = node
    if not name or name in {"if", "for", "while", "switch", "catch"}:
        return None
    qualname = f"{class_name}.{name}" if class_name else name
    segment = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    signature = segment.split("{", 1)[0].split(":", 1)[0].strip().splitlines()[0][:180]
    return Entity(
        symbol=name,
        qualname=qualname,
        file=relative,
        kind="method" if class_name else "function",
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        signature=signature,
        docstring=_docstring(body if body is not None else node, source, language),
        calls=_calls(body if body is not None else node),
        imports=[],
    )


def _field_text(node, source: bytes, field: str) -> str | None:
    child = node.child_by_field_name(field) if hasattr(node, "child_by_field_name") else None
    if child is None:
        return None
    return source[child.start_byte : child.end_byte].decode("utf-8", errors="replace")


def _docstring(node, source: bytes, language: str) -> str:
    if language != "python":
        return ""
    body = node.child_by_field_name("body") if hasattr(node, "child_by_field_name") else None
    target = body or node
    for child in getattr(target, "children", []):
        if child.type == "expression_statement":
            text = source[child.start_byte : child.end_byte].decode("utf-8", errors="replace").strip()
            if text.startswith(('"""', "'''")):
                return text.strip("\"' ")
            return ""
    return ""


def _calls(node) -> list[str]:
    found: list[str] = []

    def walk(current) -> None:
        if current.type in {"call", "call_expression"}:
            fn = current.child_by_field_name("function") if hasattr(current, "child_by_field_name") else None
            name = _callee(fn) if fn is not None else None
            if name and name not in found and name not in {"print", "range", "len", "round", "str", "int", "float"}:
                found.append(name)
        for child in current.children:
            if current.type in {"function_definition", "function_declaration"} and child.type in {
                "function_definition",
                "function_declaration",
            }:
                continue
            walk(child)

    walk(node)
    return found


def _callee(node) -> str | None:
    if node is None:
        return None
    if node.type in {"identifier", "property_identifier"}:
        return node.text.decode("utf-8", errors="replace") if isinstance(node.text, bytes) else str(node.text)
    if node.type in {"attribute", "member_expression"}:
        attr = node.child_by_field_name("attribute") if hasattr(node, "child_by_field_name") else None
        if attr is None:
            # javascript member_expression uses field "property"
            attr = node.child_by_field_name("property") if hasattr(node, "child_by_field_name") else None
        if attr is not None and attr.type in {"identifier", "property_identifier"}:
            return attr.text.decode("utf-8", errors="replace") if isinstance(attr.text, bytes) else str(attr.text)
    return None


def _resolve(name: str, known: set[str]) -> str | None:
    if name in known:
        return name
    suffix = "." + name
    hits = [item for item in known if item.endswith(suffix)]
    if len(hits) == 1:
        return hits[0]
    return None
