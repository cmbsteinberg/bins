#!/usr/bin/env python3
"""
patch_scrapers.py — AST-based transform: sync requests → async httpx.

Uses AST node positions (lineno, end_lineno, col_offset, end_col_offset)
to make precise source-level replacements, preserving formatting and comments.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


class SourceRewriter:
    """Collects edits (indexed by line/col) and applies them in reverse order."""

    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines(keepends=True)
        # Each edit: (start_line, start_col, end_line, end_col, replacement)
        # Lines are 1-indexed (matching ast), cols are 0-indexed
        self._edits: list[tuple[int, int, int, int, str]] = []

    def replace_node(self, node: ast.AST, replacement: str):
        """Replace an AST node's source span with replacement text."""
        self._edits.append(
            (
                node.lineno,
                node.col_offset,
                node.end_lineno,
                node.end_col_offset,
                replacement,
            )
        )

    def replace_range(
        self,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        replacement: str,
    ):
        self._edits.append((start_line, start_col, end_line, end_col, replacement))

    def delete_statement(self, node: ast.stmt):
        """Delete an entire statement including its line(s) and trailing newline."""
        start = node.lineno
        end = node.end_lineno
        # Delete entire lines
        for lineno in range(start, end + 1):
            self.lines[lineno - 1] = ""

    def apply(self) -> str:
        """Apply all edits and return new source."""
        # Sort edits in reverse order so positions don't shift
        edits = sorted(self._edits, key=lambda e: (e[0], e[1]), reverse=True)
        lines = list(self.lines)

        for start_line, start_col, end_line, end_col, replacement in edits:
            if start_line == end_line:
                # Single-line edit
                ln = lines[start_line - 1]
                lines[start_line - 1] = ln[:start_col] + replacement + ln[end_col:]
            else:
                # Multi-line edit: combine the affected lines, then splice
                combined = ""
                for i in range(start_line - 1, end_line):
                    combined += lines[i]

                # Calculate positions in the combined string
                before = ""
                for i in range(start_line - 1, start_line - 1):
                    before += lines[i]
                before = lines[start_line - 1][:start_col]

                last_line = lines[end_line - 1]
                after = last_line[end_col:]

                new_content = before + replacement + after
                lines[start_line - 1] = new_content
                for i in range(start_line, end_line):
                    lines[i] = ""

        return "".join(lines)


def transform_source(source: str) -> tuple[str, list[str]]:
    """Transform a single source file. Returns (new_source, warnings)."""
    warnings: list[str] = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return source, [f"Parse error: {e}"]

    # --- Analysis pass ---
    has_requests_import = False
    has_cloudscraper_import = False
    has_time_import = False
    has_from_time_import_sleep = False
    uses_time_sleep = False
    uses_time_other = False
    httpadapter_classes: dict[str, ast.ClassDef] = {}
    session_var_names: set[str] = set()
    init_session_attr: str | None = None
    methods_needing_async: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "requests":
                    has_requests_import = True
                if alias.name == "cloudscraper":
                    has_cloudscraper_import = True
                if alias.name == "time":
                    has_time_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "requests" or (
                node.module and node.module.startswith("requests.")
            ):
                has_requests_import = True
            if node.module == "time":
                for alias in node.names:
                    if alias.name == "sleep":
                        has_from_time_import_sleep = True

    if not has_requests_import and not has_cloudscraper_import:
        # Still apply waste_collection_schedule import rewrite
        patched = _final_requests_cleanup(source)
        if patched != source:
            return patched, []
        return source, [
            "No 'import requests' or 'import cloudscraper' found — skipping"
        ]

    # Find HTTPAdapter subclasses
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if _name_contains(base, "HTTPAdapter"):
                    httpadapter_classes[node.name] = node

    # Find session variables
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if _is_requests_session(node.value):
                tgt = node.targets[0]
                if isinstance(tgt, ast.Name):
                    session_var_names.add(tgt.id)
                elif (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                ):
                    init_session_attr = tgt.attr
                    session_var_names.add(f"self.{tgt.attr}")
        # Track context manager sessions: with requests.Session() as var:
        if isinstance(node, ast.With):
            for item in node.items:
                if (
                    isinstance(item.context_expr, ast.Call)
                    and _is_requests_session(item.context_expr)
                    and item.optional_vars
                    and isinstance(item.optional_vars, ast.Name)
                ):
                    session_var_names.add(item.optional_vars.id)

    # Find time.sleep / sleep usage
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _is_attr_call(node, "time", "sleep"):
                uses_time_sleep = True
            elif (
                isinstance(node.func, ast.Name)
                and node.func.id == "sleep"
                and has_from_time_import_sleep
            ):
                uses_time_sleep = True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "time" and node.attr != "sleep":
                uses_time_other = True

    # Find helper methods that need async: session param, self._session, or bare requests calls
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name != "__init__"
            and node.name != "fetch"
        ):
            # Check if any param is named s/session
            param_names = {a.arg for a in node.args.args}
            has_session_param = bool(param_names & {"s", "session"})
            # Check if method uses self._session
            uses_session_attr = init_session_attr and _body_uses_attr(
                node, "self", init_session_attr
            )
            # Check if method uses bare requests.get/post/etc calls
            has_bare_requests = any(
                isinstance(n, ast.Call) and _is_bare_requests_call(n)
                for n in ast.walk(node)
            )
            # Check if method creates a local requests.Session()
            has_local_session = any(
                isinstance(n, ast.Call) and _is_requests_session(n)
                for n in ast.walk(node)
            )
            if (
                has_session_param
                or uses_session_attr
                or has_bare_requests
                or has_local_session
            ):
                methods_needing_async.add(node.name)

    # Transitive closure: if a method calls another method that needs async, it does too
    # Also build a call graph of self.method() calls for propagation
    method_calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            callees = set()
            for n in ast.walk(node):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "self"
                ):
                    callees.add(n.func.attr)
            method_calls[node.name] = callees

    changed = True
    while changed:
        changed = False
        for method_name, callees in method_calls.items():
            if method_name not in methods_needing_async and method_name not in (
                "__init__",
                "fetch",
            ):
                if callees & methods_needing_async:
                    methods_needing_async.add(method_name)
                    changed = True

    # --- Build edits using line-based approach with AST guidance ---
    # We'll do targeted string replacements using AST node positions

    lines = source.splitlines(keepends=True)
    # Collect line-level operations
    delete_lines: set[int] = set()  # 1-indexed lines to remove entirely
    line_replacements: dict[int, str] = {}  # 1-indexed line -> replacement

    # We need to track multiline statement ranges too
    delete_ranges: list[tuple[int, int]] = []  # (start, end) 1-indexed inclusive

    # 1. Handle imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "requests":
                    # Replace the whole import statement
                    _mark_stmt_replace(
                        node,
                        lines,
                        delete_ranges,
                        line_replacements,
                        _get_stmt_text(node, lines),
                        "import httpx",
                    )
                if alias.name == "cloudscraper":
                    _mark_stmt_replace(
                        node,
                        lines,
                        delete_ranges,
                        line_replacements,
                        _get_stmt_text(node, lines),
                        "import httpx",
                    )
                if alias.name == "time" and uses_time_sleep and not uses_time_other:
                    _mark_stmt_replace(
                        node,
                        lines,
                        delete_ranges,
                        line_replacements,
                        _get_stmt_text(node, lines),
                        "import asyncio",
                    )

        elif isinstance(node, ast.ImportFrom):
            if node.module == "requests":
                # from requests import Session, etc → import httpx
                _mark_stmt_replace(
                    node,
                    lines,
                    delete_ranges,
                    line_replacements,
                    _get_stmt_text(node, lines),
                    "import httpx",
                )

            elif node.module and node.module.startswith("requests.adapters"):
                # Remove entirely
                for ln in range(node.lineno, node.end_lineno + 1):
                    delete_lines.add(ln)

            elif node.module and node.module.startswith("requests.exceptions"):
                # Replace with httpx equivalents
                old_text = _get_stmt_text(node, lines)
                new_text = old_text.replace(
                    "from requests.exceptions import", "from httpx import"
                )
                new_text = _replace_exception_names(new_text)
                _mark_stmt_replace(
                    node, lines, delete_ranges, line_replacements, old_text, new_text
                )

            elif node.module == "time":
                for alias in node.names:
                    if alias.name == "sleep":
                        if uses_time_sleep:
                            old_text = _get_stmt_text(node, lines)
                            _mark_stmt_replace(
                                node,
                                lines,
                                delete_ranges,
                                line_replacements,
                                old_text,
                                "import asyncio",
                            )

    # 2. Remove HTTPAdapter subclass definitions
    for cls_name, cls_node in httpadapter_classes.items():
        for ln in range(cls_node.lineno, cls_node.end_lineno + 1):
            delete_lines.add(ln)

    # 3. Process Source class body
    source_class = _find_source_class(tree)
    if source_class:
        _process_class(
            source_class,
            lines,
            delete_lines,
            delete_ranges,
            line_replacements,
            session_var_names,
            httpadapter_classes,
            methods_needing_async,
            init_session_attr,
            source,
        )

    # 4. Process module-level functions that use requests
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in ("fetch",):
            _process_module_function(
                node,
                lines,
                delete_lines,
                delete_ranges,
                line_replacements,
                session_var_names,
                source,
            )

    # --- Apply edits ---
    result_lines = []
    need_asyncio_import = uses_time_sleep and has_time_import and uses_time_other
    asyncio_inserted = False
    i = 1  # 1-indexed
    while i <= len(lines):
        # line_replacements take priority over deletions
        if i in line_replacements:
            pass  # will be handled below
        elif i in delete_lines:
            i += 1
            continue
        else:
            # Check if this line starts a delete range
            in_range = False
            for rs, re_ in delete_ranges:
                if rs <= i <= re_:
                    in_range = True
                    break
            if in_range:
                i += 1
                continue

        line = line_replacements.get(i, lines[i - 1])
        result_lines.append(line)

        # Insert asyncio import after time import if needed
        if need_asyncio_import and not asyncio_inserted:
            stripped = lines[i - 1].strip()
            if stripped.startswith("import time"):
                result_lines.append("import asyncio\n")
                asyncio_inserted = True

        i += 1

    result = "".join(result_lines)
    # Clean up excessive blank lines
    result = re.sub(r"\n{4,}", "\n\n\n", result)

    # --- Final text-level cleanup for remaining requests references ---
    # These catch edge cases the AST transform doesn't handle structurally:
    # type annotations, lowercase session(), context managers, bare exception refs
    result = _final_requests_cleanup(result)

    return result, warnings


def _process_class(
    cls: ast.ClassDef,
    lines: list[str],
    delete_lines: set[int],
    delete_ranges: list[tuple[int, int]],
    line_replacements: dict[int, str],
    session_var_names: set[str],
    adapter_classes: dict[str, ast.ClassDef],
    methods_needing_async: set[str],
    init_session_attr: str | None,
    full_source: str,
):
    """Process the Source class: transform methods, session creation, HTTP calls."""

    for node in ast.iter_child_nodes(cls):
        if isinstance(node, ast.FunctionDef):
            _process_method(
                node,
                lines,
                delete_lines,
                delete_ranges,
                line_replacements,
                session_var_names,
                adapter_classes,
                methods_needing_async,
                init_session_attr,
                full_source,
            )


def _process_module_function(
    func: ast.FunctionDef,
    lines: list[str],
    delete_lines: set[int],
    delete_ranges: list[tuple[int, int]],
    line_replacements: dict[int, str],
    session_var_names: set[str],
    full_source: str,
):
    """Process module-level functions for bare requests.get/post calls."""
    has_requests_call = False
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _is_bare_requests_call(node):
            has_requests_call = True
            _transform_bare_request(node, lines, line_replacements)
        if isinstance(node, ast.Call) and _is_attr_call(node, "time", "sleep"):
            _replace_time_sleep(node, lines, line_replacements)

    # Make the function async if it had requests calls
    if has_requests_call:
        line = lines[func.lineno - 1]
        if "async def" not in line:
            line_replacements[func.lineno] = line.replace(
                f"def {func.name}(", f"async def {func.name}(", 1
            )


def _process_method(
    method: ast.FunctionDef,
    lines: list[str],
    delete_lines: set[int],
    delete_ranges: list[tuple[int, int]],
    line_replacements: dict[int, str],
    session_var_names: set[str],
    adapter_classes: dict[str, ast.ClassDef],
    methods_needing_async: set[str],
    init_session_attr: str | None,
    full_source: str,
):
    """Process a single method within Source class."""

    # Make fetch() and helper methods async
    if method.name == "fetch" or method.name in methods_needing_async:
        line = lines[method.lineno - 1]
        if "async def" not in line:
            line_replacements[method.lineno] = line.replace(
                f"def {method.name}(", f"async def {method.name}(", 1
            )

    # Build local session var names that include method parameters named s/session
    local_session_vars = set(session_var_names)
    for arg in method.args.args:
        if arg.arg in ("s", "session"):
            local_session_vars.add(arg.arg)

    # Pre-pass: detect chained bare requests calls (requests.get(...).json() etc)
    chained_bare_requests: set[int] = set()
    for node in ast.walk(method):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            inner = node.func.value
            if isinstance(inner, ast.Call) and _is_bare_requests_call(inner):
                chained_bare_requests.add(id(inner))

    # Walk all nodes in the method body
    for node in ast.walk(method):
        # --- requests.Session() → httpx.AsyncClient(...) ---
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and _is_requests_session(node.value)
        ):
            _transform_session_assign(
                node,
                lines,
                delete_lines,
                delete_ranges,
                line_replacements,
                adapter_classes,
                method,
                full_source,
            )
            continue

        # --- s.mount(...) → delete ---
        if isinstance(node, (ast.Expr,)) and isinstance(node.value, ast.Call):
            if _is_method_call_on(node.value, local_session_vars, "mount"):
                for ln in range(node.lineno, node.end_lineno + 1):
                    delete_lines.add(ln)
                continue

        # --- s.get(...) / s.post(...) etc → await s.get(...) ---
        if isinstance(node, ast.Call) and _is_session_http_call(
            node, local_session_vars
        ):
            _add_await_before_call(node, lines, line_replacements)

        # --- requests.get(...) / requests.post(...) → await httpx client call ---
        if isinstance(node, ast.Call) and _is_bare_requests_call(node):
            if id(node) in chained_bare_requests:
                # Chained call like requests.get(...).json() — handled separately
                pass
            else:
                _transform_bare_request(node, lines, line_replacements)

        # --- Chained bare requests: requests.get(...).json() → (await ...).json() ---
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
            and _is_bare_requests_call(node.func.value)
        ):
            _transform_chained_bare_request(
                node.func.value, node, lines, line_replacements
            )

        # --- time.sleep(x) → await asyncio.sleep(x) ---
        if isinstance(node, ast.Call) and _is_attr_call(node, "time", "sleep"):
            _replace_time_sleep(node, lines, line_replacements)

        # --- sleep(x) from `from time import sleep` → await asyncio.sleep(x) ---
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sleep"
        ):
            _replace_bare_sleep(node, lines, line_replacements)

        # --- self.helper_method(s) → await self.helper_method(s) ---
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr in methods_needing_async
            ):
                _add_await_before_call(node, lines, line_replacements)

        # --- requests.exceptions.X → httpx.X ---
        if isinstance(node, ast.Attribute):
            _replace_requests_exceptions_in_node(node, lines, line_replacements)

    # Handle __init__ with self._session = requests.Session()
    if method.name == "__init__" and init_session_attr:
        for node in ast.walk(method):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and _is_requests_session(node.value)
            ):
                indent = _get_indent(lines[node.lineno - 1])
                new = f"{indent}self.{init_session_attr} = httpx.AsyncClient(follow_redirects=True)\n"
                for ln in range(node.lineno, node.end_lineno + 1):
                    if ln == node.lineno:
                        line_replacements[ln] = new
                    else:
                        delete_lines.add(ln)


def _transform_session_assign(
    node: ast.Assign,
    lines: list[str],
    delete_lines: set[int],
    delete_ranges: list[tuple[int, int]],
    line_replacements: dict[int, str],
    adapter_classes: dict[str, ast.ClassDef],
    method: ast.FunctionDef,
    full_source: str,
):
    """Transform s = requests.Session() to s = httpx.AsyncClient(...)."""
    tgt = node.targets[0]
    if isinstance(tgt, ast.Name):
        var_name = tgt.id
    elif isinstance(tgt, ast.Attribute):
        var_name = f"self.{tgt.attr}"
    else:
        return

    indent = _get_indent(lines[node.lineno - 1])

    # Look for .mount() calls with adapter in the method to get SSL context
    ssl_context_var = None
    ssl_context_code = None
    mount_nodes: list[ast.stmt] = []

    for stmt in method.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            # .mount() call
            if (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "mount"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == var_name
            ):
                mount_nodes.append(stmt)
                # Check if adapter class is used
                if call.args and len(call.args) >= 2:
                    adapter_arg = call.args[1]
                    if isinstance(adapter_arg, ast.Call):
                        adapter_name = None
                        if isinstance(adapter_arg.func, ast.Name):
                            adapter_name = adapter_arg.func.id
                        # Check if adapter constructor takes a ctx arg
                        # e.g. CustomHttpAdapter(ctx) — ctx already exists in method body
                        if adapter_arg.args:
                            first_arg = adapter_arg.args[0]
                            if isinstance(first_arg, ast.Name):
                                ssl_context_var = first_arg.id
                        # Adapter with no args — SSL context is internal to adapter class
                        # e.g. LegacyTLSAdapter() — extract SSL setup lines
                        elif adapter_name and adapter_name in adapter_classes:
                            ssl_context_code = _extract_ssl_lines(
                                adapter_classes[adapter_name], full_source
                            )
                            ssl_context_var = "ctx"

    # Build AsyncClient kwargs
    kwargs_parts = []
    if ssl_context_var:
        kwargs_parts.append(f"verify={ssl_context_var}")
    kwargs_parts.append("follow_redirects=True")

    asyncclient_line = (
        f"{indent}{var_name} = httpx.AsyncClient({', '.join(kwargs_parts)})\n"
    )

    if ssl_context_code:
        # Adapter class has internal SSL setup — prepend extracted lines before the client
        ssl_lines = ssl_context_code.strip().splitlines()
        prefix = "\n".join(indent + sl for sl in ssl_lines) + "\n"
        asyncclient_line = prefix + asyncclient_line

    if ssl_context_var and not ssl_context_code and mount_nodes:
        # ctx is defined in the method body and passed to the adapter constructor.
        # The ctx may be defined between the Session() and mount() lines.
        # Place AsyncClient at the mount() position (where ctx is guaranteed defined).
        mount_stmt = mount_nodes[0]
        # Delete original Session() line
        for ln in range(node.lineno, node.end_lineno + 1):
            delete_lines.add(ln)
        # Replace mount line with AsyncClient creation
        line_replacements[mount_stmt.lineno] = asyncclient_line
        for ln in range(mount_stmt.lineno + 1, mount_stmt.end_lineno + 1):
            delete_lines.add(ln)
        # Delete any other mount statements
        for stmt in mount_nodes[1:]:
            for ln in range(stmt.lineno, stmt.end_lineno + 1):
                delete_lines.add(ln)
    else:
        # Replace the Session() assignment in-place
        line_replacements[node.lineno] = asyncclient_line
        for ln in range(node.lineno + 1, node.end_lineno + 1):
            delete_lines.add(ln)
        # Delete mount statements
        for stmt in mount_nodes:
            for ln in range(stmt.lineno, stmt.end_lineno + 1):
                delete_lines.add(ln)


def _extract_ssl_lines(cls_node: ast.ClassDef, source: str) -> str | None:
    """Extract SSL context setup lines from an HTTPAdapter subclass."""
    for method in cls_node.body:
        if isinstance(method, ast.FunctionDef) and method.name in (
            "init_poolmanager",
            "__init__",
        ):
            ctx_lines = []
            for stmt in method.body:
                seg = ast.get_source_segment(source, stmt)
                if seg and (
                    "ssl" in seg or "ctx" in seg or "create_default_context" in seg
                ):
                    if (
                        "kwargs" not in seg
                        and "super()" not in seg
                        and "return" not in seg
                        and "poolmanager" not in seg
                    ):
                        # Dedent the line
                        ctx_lines.append(seg.strip())
            if ctx_lines:
                return "\n".join(ctx_lines)
    return None


def _find_ssl_context_setup(
    method: ast.FunctionDef, var_name: str, source: str
) -> str | None:
    """Find ssl context setup for a named variable in method body."""
    ctx_lines = []
    for stmt in method.body:
        seg = ast.get_source_segment(source, stmt)
        if (
            seg
            and var_name in seg
            and ("ssl" in seg or "create_default_context" in seg)
        ):
            ctx_lines.append(seg.strip())
    return "\n".join(ctx_lines) if ctx_lines else None


def _add_await_before_call(
    call_node: ast.Call, lines: list[str], line_replacements: dict[int, str]
):
    """Add 'await' before a call expression on its line."""
    lineno = call_node.lineno
    col = call_node.col_offset
    line = line_replacements.get(lineno, lines[lineno - 1])

    # Check if 'await' is already there
    before_call = line[:col]
    if before_call.rstrip().endswith("await"):
        return

    # Insert 'await ' at the call's column offset
    # But we need to be careful: if this is `r = s.get(...)`, we want `r = await s.get(...)`
    new_line = line[:col] + "await " + line[col:]
    line_replacements[lineno] = new_line


def _transform_bare_request(
    call_node: ast.Call, lines: list[str], line_replacements: dict[int, str]
):
    """Transform requests.get(...) / requests.post(...).

    Since these need an async context manager, we wrap them.
    For simplicity in this mechanical transform, we replace `requests.METHOD(` with
    `await httpx.AsyncClient().METHOD(` — the client will be GC'd.
    A more proper approach would use `async with`, but that requires restructuring
    the surrounding code which is complex for an automated transform.
    """
    func = call_node.func
    if not isinstance(func, ast.Attribute):
        return
    method_name = func.attr  # get, post, etc.

    lineno = func.value.lineno
    line = line_replacements.get(lineno, lines[lineno - 1])

    # Find 'requests.get(' or 'requests.post(' in the line and replace
    old_pattern = f"requests.{method_name}("
    if old_pattern not in line:
        return

    # Replace requests.METHOD( with await httpx.AsyncClient().METHOD(
    new_pattern = f"await httpx.AsyncClient(follow_redirects=True).{method_name}("
    new_line = line.replace(old_pattern, new_pattern, 1)
    line_replacements[lineno] = new_line


def _transform_chained_bare_request(
    inner_call: ast.Call,
    outer_call: ast.Call,
    lines: list[str],
    line_replacements: dict[int, str],
):
    """Transform requests.get(...).json() → (await httpx.AsyncClient(...).get(...)).json()."""
    func = inner_call.func
    if not isinstance(func, ast.Attribute):
        return
    method_name = func.attr

    start_lineno = func.value.lineno
    line = line_replacements.get(start_lineno, lines[start_lineno - 1])

    old_pattern = f"requests.{method_name}("
    if old_pattern not in line:
        return

    new_pattern = f"(await httpx.AsyncClient(follow_redirects=True).{method_name}("
    new_line = line.replace(old_pattern, new_pattern, 1)
    line_replacements[start_lineno] = new_line

    # Insert closing paren ')' after the inner call's closing paren
    end_lineno = inner_call.end_lineno
    end_col = inner_call.end_col_offset

    if start_lineno == end_lineno:
        # Same line — account for the shift from the replacement above
        shift = len(new_pattern) - len(old_pattern)
        adjusted_col = end_col + shift
        el = line_replacements[start_lineno]
        line_replacements[start_lineno] = el[:adjusted_col] + ")" + el[adjusted_col:]
    else:
        # Different lines — insert ')' at the inner call's end position
        el = line_replacements.get(end_lineno, lines[end_lineno - 1])
        line_replacements[end_lineno] = el[:end_col] + ")" + el[end_col:]


def _replace_time_sleep(
    call_node: ast.Call, lines: list[str], line_replacements: dict[int, str]
):
    """Replace time.sleep(x) with await asyncio.sleep(x)."""
    lineno = call_node.lineno
    line = line_replacements.get(lineno, lines[lineno - 1])
    # Find time.sleep and replace, adding await
    new_line = line.replace("time.sleep(", "await asyncio.sleep(", 1)
    # Ensure there's not already an await
    if "await await" in new_line:
        new_line = new_line.replace("await await", "await", 1)
    line_replacements[lineno] = new_line


def _replace_bare_sleep(
    call_node: ast.Call, lines: list[str], line_replacements: dict[int, str]
):
    """Replace sleep(x) (from `from time import sleep`) with await asyncio.sleep(x)."""
    lineno = call_node.lineno
    col = call_node.col_offset
    line = line_replacements.get(lineno, lines[lineno - 1])
    # Replace sleep( with await asyncio.sleep( at the right position
    before = line[:col]
    after = line[col:]
    if after.startswith("sleep("):
        new_line = before + "await asyncio.sleep(" + after[len("sleep(") :]
        line_replacements[lineno] = new_line


def _replace_requests_exceptions_in_node(
    node: ast.Attribute, lines: list[str], line_replacements: dict[int, str]
):
    """Replace requests.exceptions.X references in code lines."""
    lineno = node.lineno
    line = line_replacements.get(lineno, lines[lineno - 1])
    replacements = {
        "requests.exceptions.RequestException": "httpx.HTTPError",
        "requests.exceptions.HTTPError": "httpx.HTTPStatusError",
        "requests.exceptions.ConnectionError": "httpx.ConnectError",
        "requests.exceptions.Timeout": "httpx.TimeoutException",
    }
    changed = False
    for old, new in replacements.items():
        if old in line:
            line = line.replace(old, new)
            changed = True
    if changed:
        line_replacements[lineno] = line


# --- Predicates ---


def _name_contains(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return name in node.id
    if isinstance(node, ast.Attribute):
        return name in node.attr or _name_contains(node.value, name)
    return False


def _is_requests_session(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    # requests.Session() or requests.session()
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        if node.func.value.id == "requests" and node.func.attr in (
            "Session",
            "session",
        ):
            return True
        # cloudscraper.create_scraper(...)
        if node.func.value.id == "cloudscraper" and node.func.attr == "create_scraper":
            return True
    # Bare Session() — from `from requests import Session`
    if isinstance(node.func, ast.Name) and node.func.id == "Session":
        return True
    return False


def _is_attr_call(node: ast.Call, obj: str, attr: str) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == obj
    )


def _is_session_http_call(node: ast.Call, session_var_names: set[str]) -> bool:
    """Check if node is s.get/s.post/self._session.get etc."""
    http_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in http_methods:
        return False
    val = func.value
    if isinstance(val, ast.Name) and val.id in session_var_names:
        return True
    if (
        isinstance(val, ast.Attribute)
        and isinstance(val.value, ast.Name)
        and val.value.id == "self"
        and f"self.{val.attr}" in session_var_names
    ):
        return True
    return False


def _is_bare_requests_call(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in ("get", "post", "put", "delete", "patch")
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "requests"
    )


def _is_method_call_on(call: ast.Call, var_names: set[str], method: str) -> bool:
    if isinstance(call.func, ast.Attribute) and call.func.attr == method:
        val = call.func.value
        if isinstance(val, ast.Name) and val.id in var_names:
            return True
    return False


def _is_headers_update(call: ast.Call, session_var_names: set[str]) -> bool:
    """Check for s.headers.update(...) or session.headers.update(...)."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "update"):
        return False
    val = func.value
    if not (isinstance(val, ast.Attribute) and val.attr == "headers"):
        return False
    obj = val.value
    if isinstance(obj, ast.Name) and obj.id in session_var_names:
        return True
    return False


def _body_uses_attr(func_node: ast.FunctionDef, obj: str, attr: str) -> bool:
    """Check if function body references obj.attr (e.g. self._session)."""
    for node in ast.walk(func_node):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == attr
            and isinstance(node.value, ast.Name)
            and node.value.id == obj
        ):
            return True
    return False


def _find_source_class(tree: ast.Module) -> ast.ClassDef | None:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Source":
            return node
    return None


# --- Helpers ---


def _final_requests_cleanup(source: str) -> str:
    """Final text-level pass to replace remaining requests.* references."""
    replacements = [
        # Type annotations
        ("requests.Response", "httpx.Response"),
        ("requests.Session", "httpx.AsyncClient"),
        # Lowercase session() constructor
        ("requests.session()", "httpx.AsyncClient(follow_redirects=True)"),
        # Exception classes used directly on requests module
        ("requests.HTTPError", "httpx.HTTPStatusError"),
        ("requests.RequestException", "httpx.HTTPError"),
        # cloudscraper remnants
        ("cloudscraper.create_scraper()", "httpx.AsyncClient(follow_redirects=True)"),
        # requests kwarg → httpx kwarg
        ("allow_redirects=", "follow_redirects="),
    ]
    for old, new in replacements:
        source = source.replace(old, new)

    # Handle `with httpx.AsyncClient(...) as var:` → `async with httpx.AsyncClient(...) as var:`
    source = re.sub(
        r"(\s*)with (httpx\.AsyncClient\([^)]*\)) as (\w+):",
        r"\1async with \2 as \3:",
        source,
    )

    # Move verify=False from per-request kwarg to client constructor
    # Pattern: await httpx.AsyncClient(follow_redirects=True).METHOD(..., verify=False, ...)
    # → await httpx.AsyncClient(verify=False, follow_redirects=True).METHOD(... without verify=False ...)
    def _move_verify_to_client(m):
        pre = m.group(1)
        client_args = m.group(2)
        method = m.group(3)
        call_args = m.group(4)
        # Remove verify=False from call args
        call_args = re.sub(r",?\s*verify=False", "", call_args)
        call_args = re.sub(r"verify=False,?\s*", "", call_args)
        # Add verify=False to client args
        if "verify=" not in client_args:
            client_args = "verify=False, " + client_args if client_args else "verify=False"
        return f"{pre}httpx.AsyncClient({client_args}).{method}({call_args})"

    source = re.sub(
        r"(await\s+)httpx\.AsyncClient\(([^)]*)\)\.(get|post|put|delete|patch|head)\(([^)]*verify=False[^)]*)\)",
        _move_verify_to_client,
        source,
    )

    # Handle verify=False on session method calls:
    # 1. Find session vars that use verify=False in their requests (multiline aware)
    # 2. Add verify=False to their AsyncClient() constructor
    # 3. Remove verify=False lines/occurrences from request calls

    # Find vars whose HTTP calls use verify=False (multiline: look for await VAR.method(\n...\nverify=False)
    verify_false_vars: set[str] = set()
    for m in re.finditer(
        r"await\s+(\w+)\.(get|post|put|delete|patch|head)\(",
        source,
    ):
        var = m.group(1)
        # Check if verify=False appears in the argument block (up to closing paren)
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
            i += 1
        arg_block = source[start:i]
        if "verify=False" in arg_block:
            verify_false_vars.add(var)

    # Also check self._session style
    for m in re.finditer(
        r"await\s+(self\.\w+)\.(get|post|put|delete|patch|head)\(",
        source,
    ):
        var = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
            i += 1
        arg_block = source[start:i]
        if "verify=False" in arg_block:
            verify_false_vars.add(var)

    # Add verify=False to AsyncClient constructors for those vars
    if verify_false_vars:
        lines = source.split("\n")
        new_lines = []
        for line in lines:
            for var in verify_false_vars:
                escaped_var = re.escape(var)
                pattern = rf"(\s*){escaped_var}\s*=\s*httpx\.AsyncClient\(([^)]*)\)"
                m_line = re.match(pattern, line)
                if m_line and "verify=" not in m_line.group(2):
                    args = m_line.group(2)
                    args = f"verify=False, {args}" if args else "verify=False"
                    line = f"{m_line.group(1)}{var} = httpx.AsyncClient({args})"
            new_lines.append(line)
        source = "\n".join(new_lines)

    # Remove verify=False from HTTP method call arguments only (not from AsyncClient constructors)
    # Match lines containing verify=False that are NOT AsyncClient constructor lines
    lines = source.split("\n")
    new_lines = []
    for line in lines:
        if "verify=False" in line and "AsyncClient(" not in line:
            line = re.sub(r",\s*verify=False", "", line)
            line = re.sub(r"verify=False,\s*", "", line)
            # If line is now just whitespace or empty after removing, skip it
            if line.strip() == "" or line.strip() == ",":
                continue
        new_lines.append(line)
    source = "\n".join(new_lines)

    # Handle verify=VARIABLE (not just False) in session HTTP calls
    # Find vars whose HTTP calls use verify=EXPR (variable, not a literal)
    verify_var_mapping: dict[str, str] = {}  # session_var → verify_value
    for m in re.finditer(
        r"await\s+((?:self\.)?\w+)\.(get|post|put|delete|patch|head)\(",
        source,
    ):
        var = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while i < len(source) and depth > 0:
            if source[i] == "(":
                depth += 1
            elif source[i] == ")":
                depth -= 1
            i += 1
        arg_block = source[start:i]
        verify_m = re.search(r"verify=(self\.\w+|\w+)", arg_block)
        if verify_m and verify_m.group(1) not in ("False", "True"):
            verify_var_mapping[var] = verify_m.group(1)

    # Add verify=EXPR to AsyncClient constructors for those vars
    if verify_var_mapping:
        lines = source.split("\n")
        new_lines = []
        for line in lines:
            for var, verify_val in verify_var_mapping.items():
                escaped_var = re.escape(var)
                pattern = rf"(\s*){escaped_var}\s*=\s*httpx\.AsyncClient\(([^)]*)\)"
                m_line = re.match(pattern, line)
                if m_line and "verify=" not in m_line.group(2):
                    args = m_line.group(2)
                    args = f"verify={verify_val}, {args}" if args else f"verify={verify_val}"
                    line = f"{m_line.group(1)}{var} = httpx.AsyncClient({args})"
            new_lines.append(line)
        source = "\n".join(new_lines)

    # Remove verify=VARIABLE from per-request calls (not AsyncClient constructors)
    if verify_var_mapping:
        lines = source.split("\n")
        new_lines = []
        for line in lines:
            for verify_val in verify_var_mapping.values():
                escaped_val = re.escape(verify_val)
                if f"verify={verify_val}" in line and "AsyncClient(" not in line:
                    line = re.sub(rf",\s*verify={escaped_val}", "", line)
                    line = re.sub(rf"verify={escaped_val},\s*", "", line)
            if line.strip() == "" or line.strip() == ",":
                continue
            new_lines.append(line)
        source = "\n".join(new_lines)

    # Convert positional data arg in .post()/.put()/.patch() calls
    # s.post(url, payload) → s.post(url, data=payload)
    # Match: .post(EXPR, VARNAME) where VARNAME is not a keyword arg
    source = re.sub(
        r"(\.\s*(?:post|put|patch)\([^,\n]+),\s+(?!data=|json=|files=|headers=|params=|timeout=|content=|cookies=|auth=|follow_redirects=)(\w+)\)",
        r"\1, data=\2)",
        source,
    )

    # Convert requests-style multipart files= with (None, val) tuples to plain values
    # Only match (None, value) in dict value contexts (preceded by ": ")
    if re.search(r":\s*\(None,\s*.+?\)", source):
        source = re.sub(r"(:\s*)\(None,\s*(.+?)\)", r"\1\2", source)
        # Also convert files= to data= since (None, val) pattern indicates non-file form data
        source = re.sub(r"\bfiles=", "data=", source)

    # Convert response.url (httpx URL object) to str when string methods are called
    # r.url.replace(...) → str(r.url).replace(...)
    source = re.sub(
        r"(\w+)\.url\.(replace|split|startswith|endswith|strip|lower|upper)\(",
        r"str(\1.url).\2(",
        source,
    )

    # Convert response.url used as a bare value (not calling methods on it)
    # e.g. "Referer": r1.url  → "Referer": str(r1.url)
    source = re.sub(
        r"(\w+)\.url(?=\s*[,)\]}])",
        r"str(\1.url)",
        source,
    )

    # Fix raise_for_status without () — upstream bug that causes silent failures
    source = re.sub(r"\.raise_for_status\b(?!\()", ".raise_for_status()", source)

    # Handle get_legacy_session() callers — SSLError.py returns httpx.AsyncClient
    # but the calling scrapers were not converted since they don't import requests
    if "get_legacy_session" in source:
        # Make fetch() async
        source = re.sub(
            r"(\s+)def fetch\(self\)",
            r"\1async def fetch(self)",
            source,
        )
        # Add await to chained get_legacy_session().get/post calls
        source = re.sub(
            r"(?<!await )get_legacy_session\(\)\.(get|post|put|delete|patch)\(",
            r"await get_legacy_session().\1(",
            source,
        )
        # Find vars assigned from get_legacy_session() and add await to their HTTP calls
        for m in re.finditer(r"(\w+)\s*=\s*get_legacy_session\(\)", source):
            var = m.group(1)
            escaped = re.escape(var)
            source = re.sub(
                rf"(?<!await ){escaped}\.(get|post|put|delete|patch)\(",
                rf"await {var}.\1(",
                source,
            )
        # Delete get_adapter() lines (requests-only, no httpx equivalent)
        source = re.sub(r"[^\n]*\.get_adapter\([^)]*\)[^\n]*\n", "", source)

    # Handle urllib.request callers — convert to async httpx
    if "urllib.request" in source and "import requests" not in source:
        # Replace import
        source = re.sub(
            r"import urllib\.request\b",
            "import httpx",
            source,
        )
        # Make fetch() async
        source = re.sub(
            r"(\s+)def fetch\(self\)",
            r"\1async def fetch(self)",
            source,
        )
        # Convert urllib.request.Request + urlopen pattern:
        #   req = urllib.request.Request(URL, headers=HEADERS)
        #   with urllib.request.urlopen(req) as response:
        #       html_doc = response.read()
        # → response = await httpx.AsyncClient().get(URL, headers=HEADERS)
        #   html_doc = response.content

        # Remove Request object creation lines and capture URL/headers
        source = re.sub(
            r"(\s+)\w+\s*=\s*urllib\.request\.Request\(([^,\n]+?)(?:,\s*headers=(\w+))?\)\n",
            r"\1__urllib_url__ = \2\n\1__urllib_headers__ = \3\n",
            source,
        )
        # Convert with urlopen pattern to httpx
        source = re.sub(
            r"(\s+)with urllib\.request\.urlopen\(\w+\) as (\w+):\n\s+(\w+)\s*=\s*\2\.read\(\)\n",
            r"\1__urllib_resp__ = await httpx.AsyncClient(follow_redirects=True).get(__urllib_url__, headers=__urllib_headers__)\n\1\3 = __urllib_resp__.content\n",
            source,
        )
        # Clean up temp placeholders — inline the values
        # Find __urllib_url__ and __urllib_headers__ assignments and inline them
        url_match = re.search(r"__urllib_url__\s*=\s*(.+)", source)
        headers_match = re.search(r"__urllib_headers__\s*=\s*(.+)", source)
        if url_match and headers_match:
            url_val = url_match.group(1).strip()
            headers_val = headers_match.group(1).strip()
            # Remove temp assignments
            source = re.sub(r"[^\n]*__urllib_url__\s*=\s*[^\n]+\n", "", source)
            source = re.sub(r"[^\n]*__urllib_headers__\s*=\s*[^\n]+\n", "", source)
            # Replace placeholders in the response line
            source = source.replace("__urllib_url__", url_val)
            if headers_val and headers_val != "None":
                source = source.replace("__urllib_headers__", headers_val)
            else:
                source = re.sub(r",\s*headers=__urllib_headers__", "", source)
            source = source.replace("__urllib_resp__", "response")

    # Rewrite waste_collection_schedule imports to use api prefix
    source = re.sub(
        r"from (?:src\.)?api\.waste_collection_schedule(\b)",
        r"from api.waste_collection_schedule\1",
        source,
    )
    source = re.sub(
        r"from waste_collection_schedule(\b)",
        r"from api.waste_collection_schedule\1",
        source,
    )

    return source


def _get_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _get_stmt_text(node: ast.stmt, lines: list[str]) -> str:
    """Get the full source text of a statement."""
    result = []
    for i in range(node.lineno - 1, node.end_lineno):
        result.append(lines[i])
    return "".join(result)


def _replace_exception_names(text: str) -> str:
    text = text.replace("RequestException", "HTTPError")
    text = text.replace("ConnectionError", "ConnectError")
    text = text.replace("Timeout", "TimeoutException")
    return text


def _mark_stmt_replace(
    node: ast.stmt,
    lines: list[str],
    delete_ranges: list[tuple[int, int]],
    line_replacements: dict[int, str],
    old_text: str,
    new_text: str,
):
    """Replace a statement, handling multiline."""
    indent = _get_indent(lines[node.lineno - 1])
    line_replacements[node.lineno] = indent + new_text.lstrip() + "\n"
    # Delete extra lines if multiline
    if node.end_lineno > node.lineno:
        for ln in range(node.lineno + 1, node.end_lineno + 1):
            delete_ranges.append((ln, ln))


# --- File-level entry points ---


def transform_file(source_path: Path, output_path: Path) -> list[str]:
    source = source_path.read_text()
    transformed, warnings = transform_source(source)
    output_path.write_text(transformed)
    return warnings


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Patch waste collection scrapers from sync requests to async httpx"
    )
    parser.add_argument(
        "input_dir", type=Path, help="Directory with raw upstream scrapers"
    )
    parser.add_argument(
        "output_dir", type=Path, help="Directory to write patched files"
    )
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Error: {args.input_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    source_files = sorted(args.input_dir.glob("*_gov_uk.py"))
    if not source_files:
        print(f"No *_gov_uk.py files found in {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Patching {len(source_files)} files...")

    all_warnings: dict[str, list[str]] = {}
    for src in source_files:
        out = args.output_dir / src.name
        warns = transform_file(src, out)
        if warns:
            all_warnings[src.name] = warns

    patched = len(source_files) - len(all_warnings)
    print(f"Patched: {patched}/{len(source_files)}")

    if all_warnings:
        print("\nWarnings:")
        for filename, warns in sorted(all_warnings.items()):
            for w in warns:
                print(f"  {filename}: {w}")


if __name__ == "__main__":
    main()
