"""Landmark, heading-order and page-language lint for one HTML document, standard library only.

The linter reads markup; it never runs scripts or loads style sheets. Run it on a rendered DOM
snapshot for pages built by scripts. Content hidden only by a style sheet still counts as visible
here; content inside the hidden attribute, aria-hidden="true", template, script, style or noscript
does not. Every result names the WCAG 2.2 success criterion it relates to and whether it is a
failure of that criterion or advisory, a practice that supports it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIPPED = {"template", "script", "style", "noscript"}
SECTIONING = {"article", "aside", "main", "nav", "section"}
LANDMARK_ROLES = {"banner", "complementary", "contentinfo", "form", "main", "navigation", "region", "search"}
LANG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*$")

RULES: dict[str, dict[str, str]] = {
    "page-lang": {"sc": "3.1.1", "name": "Language of Page", "level": "A", "conformance": "failure"},
    "page-title": {"sc": "2.4.2", "name": "Page Titled", "level": "A", "conformance": "failure"},
    "main-missing": {"sc": "2.4.1", "name": "Bypass Blocks", "level": "A", "conformance": "advisory"},
    "main-multiple": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "main-nested": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "banner-multiple": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "contentinfo-multiple": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "landmark-unlabeled": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "landmark-duplicate-label": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "content-outside-landmarks": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "h1-missing": {"sc": "2.4.6", "name": "Headings and Labels", "level": "AA", "conformance": "advisory"},
    "h1-multiple": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "heading-skipped-level": {"sc": "1.3.1", "name": "Info and Relationships", "level": "A", "conformance": "advisory"},
    "heading-empty": {"sc": "2.4.6", "name": "Headings and Labels", "level": "AA", "conformance": "advisory"},
    "skip-link-target-missing": {"sc": "2.4.1", "name": "Bypass Blocks", "level": "A", "conformance": "advisory"},
}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, 1)
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.getpos()[0], self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.getpos()[0], self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse(html: str) -> Node:
    builder = _Builder()
    builder.feed(html)
    builder.close()
    return builder.root


def hidden(node: Node) -> bool:
    for item in (node, *node.ancestors()):
        if item.tag in SKIPPED or "hidden" in item.attrs or item.attrs.get("aria-hidden", "").strip().lower() == "true":
            return True
        if item.tag == "input" and item.attrs.get("type", "").lower() == "hidden":
            return True
    return False


def walk(node: Node):
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from walk(child)


def text_of(node: Node, ids: dict[str, Node]) -> str:
    parts: list[str] = []

    def collect(item: Node) -> None:
        if item.tag in SKIPPED or "hidden" in item.attrs or item.attrs.get("aria-hidden", "").lower() == "true":
            return
        label = item.attrs.get("aria-label", "").strip()
        if label:
            parts.append(label)
            return
        if item.tag == "img":
            parts.append(item.attrs.get("alt", "").strip())
            return
        for child in item.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                collect(child)

    collect(node)
    return " ".join(" ".join(parts).split())


def accessible_name(node: Node, ids: dict[str, Node]) -> str:
    refs = node.attrs.get("aria-labelledby", "").split()
    if refs:
        named = " ".join(text_of(ids[r], ids) for r in refs if r in ids).strip()
        if named:
            return named
    return (node.attrs.get("aria-label", "") or node.attrs.get("title", "")).strip()


def role_of(node: Node, ids: dict[str, Node]) -> str | None:
    explicit = node.attrs.get("role", "").split()
    if explicit:
        return explicit[0].lower()
    tag = node.tag
    if tag == "main":
        return "main"
    if tag == "nav":
        return "navigation"
    if tag == "aside":
        return "complementary"
    if tag == "search":
        return "search"
    if tag in ("header", "footer"):
        if any(a.tag in SECTIONING for a in node.ancestors()):
            return None
        return "banner" if tag == "header" else "contentinfo"
    if tag in ("section", "form"):
        return ("region" if tag == "section" else "form") if accessible_name(node, ids) else None
    if re.fullmatch(r"h[1-6]", tag):
        return "heading"
    return None


def heading_level(node: Node, role: str | None) -> int | None:
    """A heading's level: aria-level when it is a whole number, else the tag's level, else 2."""
    if role != "heading":
        return None
    level = node.attrs.get("aria-level", "").strip()
    if level.isdigit() and int(level) >= 1:
        return int(level)
    if re.fullmatch(r"h[1-6]", node.tag):
        return int(node.tag[1])
    return 2


def _result(rule: str, message: str, line: int | None = None) -> dict[str, Any]:
    return {"rule": rule, **RULES[rule], "message": message, "line": line}


def lint(html: str) -> dict[str, Any]:
    """Lint one document. Returns the landmarks, headings, language, title and every result."""
    root = parse(html)
    nodes = list(walk(root))
    ids = {n.attrs["id"]: n for n in nodes if n.attrs.get("id")}
    results: list[dict[str, Any]] = []

    html_node = next((n for n in nodes if n.tag == "html"), None)
    lang = html_node.attrs.get("lang", "").strip() if html_node else ""
    if not lang or not LANG.fullmatch(lang):
        results.append(_result("page-lang", f"The html element's lang is {lang!r}; it must name the page's language, such as en.",
                               html_node.line if html_node else None))
    title_node = next((n for n in nodes if n.tag == "title" and not any(a.tag == "svg" for a in n.ancestors())), None)
    title = " ".join("".join(c for c in title_node.children if isinstance(c, str)).split()) if title_node else ""
    if not title:
        results.append(_result("page-title", "The page has no title, or an empty one.", title_node.line if title_node else None))

    visible = [n for n in nodes if not hidden(n)]
    landmarks = []
    headings = []
    for node in visible:
        role = role_of(node, ids)
        if role in LANDMARK_ROLES:
            landmarks.append({"role": role, "name": accessible_name(node, ids), "line": node.line, "node": node})
        level = heading_level(node, role)
        if level is not None:
            headings.append({"level": level, "text": text_of(node, ids), "line": node.line})

    mains = [m for m in landmarks if m["role"] == "main"]
    if not mains:
        results.append(_result("main-missing", "The page has no main landmark, so there is no landmark to jump to the content."))
    if len(mains) > 1:
        results.append(_result("main-multiple", f"The page has {len(mains)} main landmarks; keep one.", mains[1]["line"]))
    landmark_nodes = {id(m["node"]) for m in landmarks}
    for m in mains:
        if any(id(a) in landmark_nodes for a in m["node"].ancestors()):
            results.append(_result("main-nested", "The main landmark sits inside another landmark.", m["line"]))
    for role, rule in (("banner", "banner-multiple"), ("contentinfo", "contentinfo-multiple")):
        found = [m for m in landmarks if m["role"] == role]
        if len(found) > 1:
            results.append(_result(rule, f"The page has {len(found)} {role} landmarks at the top level; keep one.", found[1]["line"]))
    by_role: dict[str, list[dict[str, Any]]] = {}
    for m in landmarks:
        by_role.setdefault(m["role"], []).append(m)
    for role, group in sorted(by_role.items()):
        # main, banner and contentinfo should each appear once; their own rules report extras.
        if len(group) < 2 or role in ("main", "banner", "contentinfo"):
            continue
        for m in group:
            if not m["name"]:
                results.append(_result("landmark-unlabeled", f"One of {len(group)} {role} landmarks has no accessible name, so they cannot be told apart.", m["line"]))
        names = [m["name"].lower() for m in group if m["name"]]
        for name in sorted({n for n in names if names.count(n) > 1}):
            results.append(_result("landmark-duplicate-label", f"{names.count(name)} {role} landmarks share the name {name!r}."))
    for m in landmarks:
        if m["role"] == "region" and m["node"].attrs.get("role") and not m["name"]:
            results.append(_result("landmark-unlabeled", "An element with role region has no accessible name.", m["line"]))

    # Visible text outside every landmark. In-page links before the first landmark, such as a skip link, are allowed.
    outside: list[str] = []
    seen_landmark = False

    def scan(node: Node, inside: bool, skip_link: bool) -> None:
        nonlocal seen_landmark
        for child in node.children:
            if isinstance(child, str):
                if not inside and not skip_link and child.strip() and node.tag not in ("title", "html", "head"):
                    outside.append(" ".join(child.split())[:60])
                continue
            if child.tag == "head" or hidden(child):
                continue
            is_landmark = id(child) in landmark_nodes
            if is_landmark:
                seen_landmark = True
            in_page = child.tag == "a" and child.attrs.get("href", "").startswith("#") and not seen_landmark
            scan(child, inside or is_landmark, skip_link or in_page)

    scan(root, False, False)
    if outside:
        results.append(_result("content-outside-landmarks", f"{len(outside)} pieces of text sit outside every landmark, starting with {outside[0]!r}."))

    h1 = [h for h in headings if h["level"] == 1]
    if not h1:
        results.append(_result("h1-missing", "The page has no level-one heading naming its topic."))
    if len(h1) > 1:
        results.append(_result("h1-multiple", f"The page has {len(h1)} level-one headings.", h1[1]["line"]))
    previous = None
    for h in headings:
        if previous is not None and h["level"] > previous + 1:
            results.append(_result("heading-skipped-level", f"A level-{h['level']} heading follows a level-{previous} heading: {h['text'][:60]!r}.", h["line"]))
        if previous is None and h["level"] > 1:
            results.append(_result("heading-skipped-level", f"The first heading is level {h['level']}, not level 1: {h['text'][:60]!r}.", h["line"]))
        if not h["text"]:
            results.append(_result("heading-empty", f"A level-{h['level']} heading has no text.", h["line"]))
        previous = h["level"]

    first_links = []
    for node in visible:
        if id(node) in landmark_nodes and by_role.get("main") and node is mains[0]["node"]:
            break
        if node.tag == "a" and node.attrs.get("href", "").startswith("#") and len(node.attrs["href"]) > 1:
            first_links.append(node)
    if first_links:
        target = first_links[0].attrs["href"][1:]
        if target not in ids and not any(n.attrs.get("name") == target for n in nodes):
            results.append(_result("skip-link-target-missing", f"The first in-page link points to #{target}, which does not exist.", first_links[0].line))

    return {
        "lang": lang,
        "title": title,
        "landmarks": [{k: v for k, v in m.items() if k != "node"} for m in landmarks],
        "headings": headings,
        "results": results,
        "failures": sum(1 for r in results if r["conformance"] == "failure"),
        "advisories": sum(1 for r in results if r["conformance"] == "advisory"),
    }


def rule_ids(report: dict[str, Any]) -> list[str]:
    """The sorted rule ids a report found, each once."""
    return sorted({r["rule"] for r in report["results"]})
