"""
Test suite for the agentic search system.
Tests the multi-round search workflow, token optimization, and tool behavior.
"""

import os
import json
import time
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from tools import (
    file_metadata,
    keyword_search,
    pdf_page_search,
    extract_page_text,
    code_search,
    read_file_lines,
    _truncate,
    MAX_CONTEXT_CHARS,
    MAX_TOTAL_CHARS,
)


# ============================================================
# 1. Unit tests for token optimization
# ============================================================
def test_truncate():
    """Test that _truncate respects character limits and sentence boundaries."""
    short = "Hello world."
    assert _truncate(short, 100) == short, "Short text should not be truncated"

    long_text = "First sentence. Second sentence. Third sentence. " * 100
    result = _truncate(long_text, 200)
    assert len(result) <= 220, f"Truncated text too long: {len(result)}"
    assert result.endswith("[truncated]"), "Should end with truncation marker"
    print("  ✓ _truncate works correctly")


# ============================================================
# 2. Unit tests for tools with sample files
# ============================================================
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "test_files")


def setup_test_files():
    """Create sample test files."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)

    # Sample text file
    with open(os.path.join(SAMPLE_DIR, "sample.txt"), "w") as f:
        f.write("""Introduction to Machine Learning
Machine learning is a subset of artificial intelligence.
It focuses on building systems that learn from data.
Supervised learning uses labeled training data.
Unsupervised learning finds patterns without labels.
Reinforcement learning uses rewards and penalties.
Deep learning uses neural networks with many layers.
Transformers revolutionized natural language processing.
BERT and GPT are popular transformer models.
RAG combines retrieval with generation for better accuracy.
""")

    # Sample markdown file
    with open(os.path.join(SAMPLE_DIR, "blockchain.md"), "w") as f:
        f.write("""# Blockchain Technology

## Hyperledger Fabric
Hyperledger Fabric has three main components:
1. **Membership** - Provides identification services
2. **Blockchain** - Provides consensus services for the distributed ledger
3. **Chaincode** - Smart contracts that execute on the network

## Solana
Solana uses Proof of History for consensus.
It achieves high throughput of 65,000 TPS.
The architecture includes validators and leaders.
""")

    # Sample PHP file
    os.makedirs(os.path.join(SAMPLE_DIR, "src"), exist_ok=True)
    with open(os.path.join(SAMPLE_DIR, "src", "UserController.php"), "w") as f:
        f.write("""<?php

namespace App\\Controllers;

use App\\Models\\User;
use App\\Services\\AuthService;

class UserController extends BaseController
{
    private AuthService $authService;

    public function __construct(AuthService $authService)
    {
        $this->authService = $authService;
    }

    public function login(Request $request): Response
    {
        $email = $request->input('email');
        $password = $request->input('password');
        $token = $this->authService->authenticate($email, $password);
        return response()->json(['token' => $token]);
    }

    public function getProfile(int $userId): Response
    {
        $user = User::findOrFail($userId);
        return response()->json($user->toArray());
    }

    public function updateProfile(Request $request, int $userId): Response
    {
        $user = User::findOrFail($userId);
        $user->update($request->validated());
        return response()->json(['status' => 'updated']);
    }
}
""")

    with open(os.path.join(SAMPLE_DIR, "src", "AuthService.php"), "w") as f:
        f.write("""<?php

namespace App\\Services;

use App\\Models\\User;
use Firebase\\JWT\\JWT;

class AuthService
{
    private string $jwtSecret;

    public function __construct(string $jwtSecret)
    {
        $this->jwtSecret = $jwtSecret;
    }

    public function authenticate(string $email, string $password): string
    {
        $user = User::where('email', $email)->first();
        if (!$user || !password_verify($password, $user->password)) {
            throw new \\RuntimeException('Invalid credentials');
        }
        return $this->generateToken($user);
    }

    private function generateToken(User $user): string
    {
        $payload = [
            'sub' => $user->id,
            'email' => $user->email,
            'exp' => time() + 3600,
        ];
        return JWT::encode($payload, $this->jwtSecret, 'HS256');
    }
}
""")

    print(f"  ✓ Test files created in {SAMPLE_DIR}")


def _call_tool(tool_obj, **kwargs) -> str:
    """Call a strands @tool decorated function directly and extract text."""
    result = tool_obj._tool_func(**kwargs)
    if isinstance(result, str):
        return result
    if isinstance(result, dict) and "content" in result:
        return result["content"][0]["text"]
    return str(result)


def test_file_metadata():
    """Test file_metadata tool."""
    content = _call_tool(file_metadata, folder=SAMPLE_DIR)
    assert "sample.txt" in content, "Should list sample.txt"
    assert "blockchain.md" in content, "Should list blockchain.md"
    print("  ✓ file_metadata lists files correctly")


def test_keyword_search_single():
    """Test keyword_search with a single keyword."""
    content = _call_tool(keyword_search, folder=SAMPLE_DIR, keywords="transformer")
    assert "transformer" in content.lower() or "Transformer" in content, \
        f"Should find 'transformer' in results: {content[:200]}"
    print("  ✓ keyword_search finds single keyword")


def test_keyword_search_multi():
    """Test keyword_search with OR pattern."""
    content = _call_tool(keyword_search, folder=SAMPLE_DIR, keywords="Hyperledger|Solana")
    assert "Hyperledger" in content or "Solana" in content, \
        "Should find at least one of the OR keywords"
    print("  ✓ keyword_search handles OR patterns")


def test_keyword_search_no_match():
    """Test keyword_search with non-existent keyword."""
    content = _call_tool(keyword_search, folder=SAMPLE_DIR, keywords="xyznonexistent123")
    assert "No matches" in content or "no output" in content.lower(), \
        f"Should report no matches: {content[:200]}"
    print("  ✓ keyword_search handles no-match gracefully")


def test_keyword_search_specific_file():
    """Test keyword_search targeting a specific file."""
    content = _call_tool(keyword_search, folder=SAMPLE_DIR, keywords="neural network", filename="sample.txt")
    assert "neural" in content.lower(), "Should find 'neural' in sample.txt"
    print("  ✓ keyword_search works with specific file")


# ============================================================
# 3. Code search tests (PHP + general)
# ============================================================
def test_file_metadata_recursive():
    """Test that file_metadata finds files in subdirectories."""
    content = _call_tool(file_metadata, folder=SAMPLE_DIR)
    assert "UserController.php" in content, "Should find PHP file in subdirectory"
    assert "code:.php" in content, "Should identify PHP as code file"
    print("  ✓ file_metadata finds files recursively with code type detection")


def test_keyword_search_php():
    """Test keyword_search finds content in PHP files."""
    content = _call_tool(keyword_search, folder=SAMPLE_DIR, keywords="authenticate", file_ext="php")
    assert "authenticate" in content, f"Should find 'authenticate' in PHP files: {content[:200]}"
    print("  ✓ keyword_search finds content in PHP files")


def test_code_search_php_function():
    """Test code_search finds PHP function definitions."""
    content = _call_tool(code_search, folder=SAMPLE_DIR, query="login", file_ext="php")
    assert "login" in content, f"Should find 'login' in PHP: {content[:200]}"
    print("  ✓ code_search finds PHP functions")


def test_code_search_definitions_only():
    """Test code_search with definitions_only filters to function/class defs."""
    content = _call_tool(code_search, folder=SAMPLE_DIR, query="authenticate", file_ext="php", definitions_only=True)
    assert "function" in content.lower(), f"Should find function definition: {content[:300]}"
    print("  ✓ code_search definitions_only works for PHP")


def test_code_search_class():
    """Test code_search finds PHP class definitions."""
    content = _call_tool(code_search, folder=SAMPLE_DIR, query="AuthService", file_ext="php")
    assert "AuthService" in content, "Should find AuthService class"
    print("  ✓ code_search finds PHP classes")


def test_read_file_lines():
    """Test read_file_lines reads specific line ranges."""
    php_path = os.path.join(SAMPLE_DIR, "src", "UserController.php")
    content = _call_tool(read_file_lines, filepath=php_path, start_line=17, end_line=25)
    assert "login" in content.lower(), f"Should contain login function: {content[:200]}"
    assert "17" in content or "18" in content, "Should show line numbers"
    print("  ✓ read_file_lines reads specific line ranges")


# ============================================================
# 4. Integration test: full agent workflow (requires Bedrock)
# ============================================================
def test_agent_workflow():
    """Test the full agent workflow with a real question.
    Requires AWS credentials and Bedrock access.
    """
    try:
        from agent import create_agent, ask
    except ImportError as e:
        print(f"  ⚠ Skipping agent test (import error): {e}")
        return

    try:
        agent = create_agent()
    except Exception as e:
        print(f"  ⚠ Skipping agent test (model init error): {e}")
        return

    question = "What are the three main components of Hyperledger Fabric?"
    print(f"  Testing agent with question: {question}")

    start = time.time()
    answer = ask(agent, question, SAMPLE_DIR)
    elapsed = time.time() - start

    print(f"  Agent answer ({elapsed:.1f}s): {answer[:300]}...")

    # Check answer quality
    answer_lower = answer.lower()
    found = sum(1 for kw in ["membership", "blockchain", "chaincode"]
                if kw in answer_lower)
    assert found >= 2, f"Expected at least 2 of 3 components, found {found}"

    # Check metrics
    print(f"  ✓ Agent answered correctly in {elapsed:.1f}s")


# ============================================================
# 4. Token budget test
# ============================================================
def test_token_budget():
    """Verify search results respect token budget limits."""
    # Create a large file
    large_file = os.path.join(SAMPLE_DIR, "large.txt")
    with open(large_file, "w") as f:
        for i in range(5000):
            f.write(f"Line {i}: The keyword appears here in this test document.\n")

    result = _call_tool(keyword_search,
        folder=SAMPLE_DIR,
        keywords="keyword",
        filename="large.txt",
    )
    content = result
    assert len(content) <= MAX_TOTAL_CHARS + 200, \
        f"Result exceeds token budget: {len(content)} chars"
    print(f"  ✓ Token budget respected ({len(content)} chars <= {MAX_TOTAL_CHARS})")

    os.remove(large_file)


# ============================================================
# Run all tests
# ============================================================
def run_tests(include_agent=False):
    print("=" * 60)
    print("Agentic Search - Test Suite")
    print("=" * 60)

    print("\n[1] Token optimization tests:")
    test_truncate()

    print("\n[2] Tool unit tests:")
    setup_test_files()
    test_file_metadata()
    test_keyword_search_single()
    test_keyword_search_multi()
    test_keyword_search_no_match()
    test_keyword_search_specific_file()

    print("\n[3] Code search tests (PHP):")
    test_file_metadata_recursive()
    test_keyword_search_php()
    test_code_search_php_function()
    test_code_search_definitions_only()
    test_code_search_class()
    test_read_file_lines()

    print("\n[4] Token budget tests:")
    test_token_budget()

    if include_agent:
        print("\n[5] Agent integration test (requires Bedrock):")
        test_agent_workflow()
    else:
        print("\n[5] Agent integration test: SKIPPED (use --agent flag)")

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    include_agent = "--agent" in sys.argv
    run_tests(include_agent=include_agent)
