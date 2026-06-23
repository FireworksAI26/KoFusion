from __future__ import annotations

import json, re


def extract_json_block(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def files_from_model_output(text: str) -> tuple[list[dict[str, str]], str]:
    data = extract_json_block(text)
    return data.get("files", []), data.get("notes", "")


def build_repair_prompt(original_prompt: str, files: list[dict[str, str]], stdout: str, stderr: str) -> str:
    return (
        "Repair the candidate with the smallest possible patch. Return ONLY JSON: "
        '{"files":[{"path":"main.py","content":"..."}],"notes":"..."}\n'
        f"Original task:\n{original_prompt}\nCurrent files:\n{json.dumps(files)}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def _split_lines_keepends(content: str) -> list[str]:
    return content.splitlines(keepends=True)


def _target_path(header: str) -> str:
    path = header[4:].strip().split("\t", 1)[0].split(" ", 1)[0]
    return path[2:] if path.startswith("b/") or path.startswith("a/") else path


def apply_unified_diff(files: list[dict[str, str]], patch: str) -> list[dict[str, str]]:
    """Apply a small unified diff to in-memory files deterministically.

    Supports standard hunks with context, additions, and deletions. It is intentionally
    strict: malformed patches raise ValueError instead of guessing.
    """
    file_map = {f["path"]: f["content"] for f in files}
    lines = patch.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("--- "):
            i += 1
            continue
        old_header = lines[i]
        i += 1
        if i >= len(lines) or not lines[i].startswith("+++ "):
            raise ValueError("unified diff missing +++ header")
        new_path = _target_path(lines[i])
        old_path = _target_path(old_header)
        path = new_path if new_path != "/dev/null" else old_path
        i += 1
        original = _split_lines_keepends(file_map.get(path, ""))
        output: list[str] = []
        cursor = 0
        while i < len(lines) and lines[i].startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[i])
            if not match:
                raise ValueError(f"invalid hunk header: {lines[i].strip()}")
            old_start = int(match.group(1))
            hunk_start = old_start - 1
            if hunk_start < cursor:
                raise ValueError("overlapping hunks")
            output.extend(original[cursor:hunk_start])
            cursor = hunk_start
            i += 1
            while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("--- "):
                line = lines[i]
                if line.startswith("\\ No newline at end of file"):
                    i += 1
                    continue
                marker, body = line[0], line[1:]
                if marker == " ":
                    if cursor >= len(original) or original[cursor] != body:
                        raise ValueError("patch context does not match")
                    output.append(original[cursor])
                    cursor += 1
                elif marker == "-":
                    if cursor >= len(original) or original[cursor] != body:
                        raise ValueError("patch deletion does not match")
                    cursor += 1
                elif marker == "+":
                    output.append(body)
                else:
                    raise ValueError(f"invalid patch line: {line!r}")
                i += 1
        output.extend(original[cursor:])
        file_map[path] = "".join(output)
    return [{"path": path, "content": file_map[path]} for path in sorted(file_map)]
