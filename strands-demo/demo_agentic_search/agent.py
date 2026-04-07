"""
Agentic Search Agent - based on arXiv:2602.23368
"Keyword search is all you need: Achieving RAG-Level Performance
 without vector databases using agentic tool use"

Key design principles from the paper:
1. ReAct reasoning loop: observe → think → act → repeat
2. Multi-round iterative search: metadata → broad search → targeted search → extract
3. Token optimization: truncation, context windowing, budget limits
4. No vector database needed - pure keyword/regex search
"""

import os
import sys
from strands import Agent
from strands.models import BedrockModel
from tools import (
    file_metadata,
    keyword_search,
    pdf_page_search,
    extract_page_text,
    code_search,
    read_file_lines,
)

SYSTEM_PROMPT = """You are a document and code research agent that answers questions by searching through files.
You have access to a folder of documents and code files, and must find answers using search tools.

## Workflow (MUST follow this order):

1. **Metadata first**: ALWAYS start with `file_metadata` to see what files are available.
2. **Broad search**: Use `keyword_search` with relevant keywords extracted from the question.
   - Try multiple keyword variations if first search yields poor results.
   - Use '|' for OR patterns: 'keyword1|keyword2'.
   - Use `file_ext` parameter to filter by file type, e.g. 'php', 'py'.
3. **Code search**: For code-related questions, use `code_search` to find functions, classes, etc.
   - Set `definitions_only=True` to find only function/class definitions.
   - Supports PHP, Python, JS, TS, Java, Go, Ruby, Rust, C/C++, etc.
4. **Targeted search**: Once you identify relevant files/pages, use `pdf_page_search`
   for PDFs or `read_file_lines` for code/text files to get more context.
5. **Extract context**: Use `extract_page_text` for PDF pages, `read_file_lines` for code files.
6. **Synthesize answer**: Combine findings into a clear, cited answer.

## Search Strategy Tips:
- If a complex query fails, break it into simpler queries.
- Try synonyms and related terms if initial keywords don't match.
- Always note which file and line number your evidence comes from.
- For code: search function names, class names, variable names directly.
- Do NOT guess - if you can't find the answer, say so.

## Token Efficiency:
- Search results are automatically truncated to stay within budget.
- Prefer targeted searches over broad ones when you know the file/line.
- Don't re-search for information you already found.

## Answer Format:
- Provide a clear, direct answer.
- Cite the source file and line number (or page number for PDFs).
- If the answer spans multiple sources, synthesize and cite all.
"""


def create_agent(
    model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
    region: str = "us-west-2",
    temperature: float = 0.001,
    max_tokens: int = 4096,
):
    """Create the agentic search agent."""
    model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[file_metadata, keyword_search, pdf_page_search, extract_page_text, code_search, read_file_lines],
    )


def ask(agent: Agent, question: str, folder: str) -> str:
    """Ask a question about documents in the given folder."""
    prompt = f"""Answer the following question by searching documents in the folder: {folder}

Question: {question}

Remember: Start with file_metadata, then search iteratively."""

    result = agent(prompt)
    return result.message["content"][0]["text"] if result.message else str(result)


# ---------- CLI entry point ----------
if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "./files"
    folder = os.path.abspath(folder)

    if not os.path.isdir(folder):
        print(f"Error: folder '{folder}' does not exist")
        sys.exit(1)

    agent = create_agent()
    print(f"Agentic Search Agent ready. Documents folder: {folder}")
    print("Type your question (or 'quit' to exit):\n")

    while True:
        try:
            q = input("Q: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("quit", "exit", "q"):
            break
        answer = ask(agent, q, folder)
        print(f"\nA: {answer}\n")
