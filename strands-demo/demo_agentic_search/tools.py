"""
Agentic keyword search tools - inspired by arXiv:2602.23368
"Keyword search is all you need"

Implements multi-round iterative search with token-aware context truncation.
"""

import os
import re
import subprocess
from pathlib import Path
from strands import tool

# ---------- Token optimization config ----------
MAX_CONTEXT_CHARS = 4000  # ~1000 tokens per search result
MAX_TOTAL_CHARS = 12000   # total chars across all results in one call
CONTEXT_LINES = 3         # lines of context around each match

# ---------- Code file extensions ----------
CODE_EXTENSIONS = {
    ".php", ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala", ".sh", ".bash",
    ".sql", ".html", ".css", ".scss", ".vue", ".svelte", ".lua", ".pl", ".r",
}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".log"}


def _truncate(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Truncate text to stay within token budget, preserving sentence boundaries."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # try to cut at last sentence boundary
    last_period = cut.rfind(".")
    if last_period > max_chars * 0.6:
        cut = cut[: last_period + 1]
    return cut + "\n... [truncated]"


def _run_cmd(cmd: list[str], cwd: str | None = None) -> str:
    """Run a shell command and return stdout, with error handling."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)
        return r.stdout or r.stderr or "(no output)"
    except FileNotFoundError:
        return f"Error: command '{cmd[0]}' not found. Install it first."
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s"


# ============================================================
# Tool 1: PDF / file metadata
# ============================================================
@tool
def file_metadata(folder: str, recursive: bool = True) -> str:
    """List metadata of all files in the given folder.
    Returns file names, sizes, page counts for PDFs, and line counts for code/text files.
    Always call this FIRST to understand what documents are available.

    Args:
        folder: Path to the folder containing documents.
        recursive: Whether to scan subdirectories. Default True.
    """
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return f"Error: '{folder}' is not a directory"

    lines = []
    if recursive:
        file_list = sorted(Path(folder).rglob("*"))
    else:
        file_list = sorted(Path(folder).iterdir())

    for fp in file_list:
        if not fp.is_file():
            continue
        rel = fp.relative_to(folder)
        size_kb = fp.stat().st_size / 1024
        ext = fp.suffix.lower()
        info = f"  {rel}  ({size_kb:.0f} KB)"

        if ext == ".pdf":
            try:
                from PyPDF2 import PdfReader
                pages = len(PdfReader(str(fp)).pages)
                info += f"  [PDF, {pages} pages]"
            except Exception:
                info += "  [PDF]"
        elif ext in CODE_EXTENSIONS:
            try:
                lc = sum(1 for _ in open(fp, errors="ignore"))
                info += f"  [code:{ext}, {lc} lines]"
            except Exception:
                info += f"  [code:{ext}]"
        elif ext in TEXT_EXTENSIONS:
            try:
                lc = sum(1 for _ in open(fp, errors="ignore"))
                info += f"  [text, {lc} lines]"
            except Exception:
                info += "  [text]"

        lines.append(info)

    if not lines:
        return "No files found."
    header = f"Files in {folder} ({len(lines)} files):\n"
    return _truncate(header + "\n".join(lines), MAX_TOTAL_CHARS)


# ============================================================
# Tool 2: Keyword search (ripgrep-all style)
# ============================================================
@tool
def keyword_search(folder: str, keywords: str, filename: str = "", case_insensitive: bool = True, file_ext: str = "") -> str:
    """Search for keywords across documents using regex pattern matching.
    Supports PDF, code files (PHP, Python, JS, etc.), text, markdown, and more.
    Returns matching lines with surrounding context. Searches recursively.

    Use '|' to search multiple keywords at once, e.g. 'keyword1|keyword2'.
    If a complex query fails, try simpler queries.

    Args:
        folder: Path to the folder containing documents.
        keywords: Regex pattern to search for. Use '|' for OR.
        filename: Optional specific filename to search in. Empty = search all.
        case_insensitive: Whether to ignore case. Default True.
        file_ext: Optional file extension filter, e.g. 'php' or 'py'. Empty = all files.
    """
    folder = os.path.expanduser(folder)
    target = os.path.join(folder, filename) if filename else folder

    # Try ripgrep-all first, fall back to grep
    for cmd_name in ["rga", "grep"]:
        cmd = [cmd_name]
        if case_insensitive:
            cmd.append("-i")
        if cmd_name == "grep":
            cmd.append("-E")  # extended regex for OR patterns
        cmd.extend(["-n", f"-C{CONTEXT_LINES}"])
        if cmd_name == "grep" and file_ext:
            cmd.extend(["--include", f"*.{file_ext}"])
        if cmd_name == "rga" and file_ext:
            cmd.extend(["-t", file_ext] if not file_ext.startswith(".") else ["--glob", f"*{file_ext}"])
        cmd.append(keywords)
        cmd.append(target)
        if not filename:
            cmd.insert(-2, "-r")

        result = _run_cmd(cmd)
        if "not found" not in result:
            return _truncate(result, MAX_TOTAL_CHARS)

    # Fallback: pure Python search
    return _python_search(folder, keywords, filename, case_insensitive, file_ext)


def _python_search(folder: str, pattern: str, filename: str, case_insensitive: bool, file_ext: str = "") -> str:
    """Fallback pure-Python search for when rga/grep unavailable."""
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Invalid regex: {e}"

    results = []
    total_chars = 0

    if filename:
        files = [Path(folder) / filename]
    else:
        files = sorted(Path(folder).rglob(f"*.{file_ext}" if file_ext else "*"))
        files = [f for f in files if f.is_file()]

    for fp in files:
        fp = str(fp)
        try:
            # Try PDF
            if fp.lower().endswith(".pdf"):
                from PyPDF2 import PdfReader
                reader = PdfReader(fp)
                for i, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    for ln, line in enumerate(text.split("\n")):
                        if regex.search(line):
                            ctx = f"{os.path.basename(fp)}:page{i+1}:L{ln+1}: {line.strip()}"
                            results.append(ctx)
                            total_chars += len(ctx)
            else:
                with open(fp, "r", errors="ignore") as fh:
                    lines = fh.readlines()
                    for ln, line in enumerate(lines):
                        if regex.search(line):
                            # gather context
                            start = max(0, ln - CONTEXT_LINES)
                            end = min(len(lines), ln + CONTEXT_LINES + 1)
                            ctx_block = "".join(lines[start:end])
                            header = f"{os.path.basename(fp)}:L{ln+1}:"
                            results.append(header + "\n" + ctx_block)
                            total_chars += len(header) + len(ctx_block)
        except Exception:
            continue

        if total_chars > MAX_TOTAL_CHARS:
            results.append("... [results truncated due to token budget]")
            break

    return "\n---\n".join(results) if results else "No matches found."


# ============================================================
# Tool 3: Page-range PDF search (pdfgrep style)
# ============================================================
@tool
def pdf_page_search(filepath: str, keywords: str, page_start: int = 1, page_end: int = -1) -> str:
    """Search within a specific page range of a PDF file.
    Use this for targeted deep-dive after initial keyword_search locates relevant pages.

    Args:
        filepath: Full path to the PDF file.
        keywords: Regex pattern to search for.
        page_start: Starting page number (1-based). Default 1.
        page_end: Ending page number (1-based). -1 means last page.
    """
    filepath = os.path.expanduser(filepath)
    if not os.path.isfile(filepath):
        return f"Error: file '{filepath}' not found"

    # Try pdfgrep first
    if page_end > 0:
        page_range = f"{page_start}-{page_end}"
    else:
        page_range = f"{page_start}-"

    cmd = ["pdfgrep", "-inP", f"--page-range={page_range}", f"-C{CONTEXT_LINES}", f"({keywords})", filepath]
    result = _run_cmd(cmd)
    if "not found" not in result and "Error" not in result:
        return _truncate(result, MAX_TOTAL_CHARS)

    # Fallback: PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)
        end = page_end if page_end > 0 else total_pages
        end = min(end, total_pages)

        flags = re.IGNORECASE
        regex = re.compile(keywords, flags)
        results = []
        total_chars = 0

        for i in range(page_start - 1, end):
            text = reader.pages[i].extract_text() or ""
            lines = text.split("\n")
            for ln, line in enumerate(lines):
                if regex.search(line):
                    start_ctx = max(0, ln - CONTEXT_LINES)
                    end_ctx = min(len(lines), ln + CONTEXT_LINES + 1)
                    ctx = "\n".join(lines[start_ctx:end_ctx])
                    entry = f"Page {i+1}, Line {ln+1}:\n{ctx}"
                    results.append(entry)
                    total_chars += len(entry)
                    if total_chars > MAX_TOTAL_CHARS:
                        results.append("... [truncated]")
                        return "\n---\n".join(results)

        return "\n---\n".join(results) if results else "No matches found in specified page range."
    except Exception as e:
        return f"Error reading PDF: {e}"


# ============================================================
# Tool 4: Extract full page text (for final context gathering)
# ============================================================
@tool
def extract_page_text(filepath: str, page_number: int) -> str:
    """Extract the full text content of a specific page from a PDF.
    Use this to get complete context after locating relevant pages.

    Args:
        filepath: Full path to the PDF file.
        page_number: Page number to extract (1-based).
    """
    filepath = os.path.expanduser(filepath)
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        if page_number < 1 or page_number > len(reader.pages):
            return f"Error: page {page_number} out of range (1-{len(reader.pages)})"
        text = reader.pages[page_number - 1].extract_text() or ""
        return _truncate(text, MAX_CONTEXT_CHARS)
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# Tool 5: Code-aware search (functions, classes, definitions)
# ============================================================

# Language-specific definition patterns
_CODE_PATTERNS = {
    ".php": r"(function\s+\w+|class\s+\w+|interface\s+\w+|trait\s+\w+|namespace\s+[\w\\]+)",
    ".py": r"(def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+)",
    ".js": r"(function\s+\w+|class\s+\w+|const\s+\w+\s*=|export\s+(default\s+)?)",
    ".ts": r"(function\s+\w+|class\s+\w+|interface\s+\w+|type\s+\w+|const\s+\w+\s*=|export\s+)",
    ".java": r"(class\s+\w+|interface\s+\w+|public\s+\w+\s+\w+\(|private\s+\w+\s+\w+\()",
    ".go": r"(func\s+(\(\w+\s+\*?\w+\)\s+)?\w+|type\s+\w+\s+(struct|interface))",
    ".rb": r"(def\s+\w+|class\s+\w+|module\s+\w+)",
    ".rs": r"(fn\s+\w+|struct\s+\w+|impl\s+\w+|trait\s+\w+|enum\s+\w+)",
    ".c": r"(\w+\s+\w+\s*\([^)]*\)\s*\{|struct\s+\w+|typedef\s+)",
    ".cpp": r"(\w+\s+\w+::\w+\s*\(|class\s+\w+|namespace\s+\w+)",
}


@tool
def code_search(folder: str, query: str, file_ext: str = "", definitions_only: bool = False) -> str:
    """Search through code files with code-structure awareness.
    Can find function/class definitions, or do general code search.
    Supports PHP, Python, JavaScript, TypeScript, Java, Go, Ruby, Rust, C/C++, etc.

    Args:
        folder: Path to the folder containing code files.
        query: Search term - function name, class name, or any code pattern.
        file_ext: File extension filter, e.g. 'php', 'py', 'js'. Empty = all code files.
        definitions_only: If True, only show function/class definitions, not all usages.
    """
    folder = os.path.expanduser(folder)
    if not os.path.isdir(folder):
        return f"Error: '{folder}' is not a directory"

    glob_pattern = f"*.{file_ext}" if file_ext else None
    results = []
    total_chars = 0

    for fp in sorted(Path(folder).rglob(glob_pattern or "*")):
        if not fp.is_file():
            continue
        ext = fp.suffix.lower()
        if not file_ext and ext not in CODE_EXTENSIONS:
            continue

        try:
            lines = fp.read_text(errors="ignore").splitlines()
        except Exception:
            continue

        rel = str(fp.relative_to(folder))
        query_re = re.compile(re.escape(query), re.IGNORECASE)

        for ln, line in enumerate(lines):
            if not query_re.search(line):
                continue

            # If definitions_only, check against language patterns
            if definitions_only:
                def_pattern = _CODE_PATTERNS.get(ext)
                if def_pattern and not re.search(def_pattern, line):
                    continue

            start = max(0, ln - CONTEXT_LINES)
            end = min(len(lines), ln + CONTEXT_LINES + 1)
            ctx = "\n".join(f"  {i+1:4d} | {lines[i]}" for i in range(start, end))
            entry = f"{rel}:{ln+1}:\n{ctx}"
            results.append(entry)
            total_chars += len(entry)

            if total_chars > MAX_TOTAL_CHARS:
                results.append("... [truncated due to token budget]")
                return "\n---\n".join(results)

    return "\n---\n".join(results) if results else f"No matches for '{query}' in code files."


# ============================================================
# Tool 6: Read file content by line range
# ============================================================
@tool
def read_file_lines(filepath: str, start_line: int = 1, end_line: int = 50) -> str:
    """Read specific lines from any text or code file.
    Use this to get full context of a code section after locating it via search.

    Args:
        filepath: Full path to the file.
        start_line: Starting line number (1-based). Default 1.
        end_line: Ending line number (1-based). Default 50.
    """
    filepath = os.path.expanduser(filepath)
    if not os.path.isfile(filepath):
        return f"Error: file '{filepath}' not found"

    try:
        lines = Path(filepath).read_text(errors="ignore").splitlines()
        total = len(lines)
        start = max(0, start_line - 1)
        end = min(total, end_line)
        numbered = [f"  {i+1:4d} | {lines[i]}" for i in range(start, end)]
        header = f"{os.path.basename(filepath)} (lines {start_line}-{end} of {total}):\n"
        return _truncate(header + "\n".join(numbered), MAX_CONTEXT_CHARS)
    except Exception as e:
        return f"Error: {e}"
