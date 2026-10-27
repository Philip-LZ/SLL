"""Check the public entry points without importing model or database dependencies."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectStructureTests(unittest.TestCase):
    def test_api_paths_are_preserved(self):
        routes = set()
        for path in (ROOT / "backend" / "api").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if (isinstance(decorator, ast.Call)
                                and isinstance(decorator.func, ast.Attribute)
                                and isinstance(decorator.func.value, ast.Name)
                                and decorator.func.value.id == "router"):
                            routes.add((decorator.func.attr, ast.literal_eval(decorator.args[0])))
        self.assertEqual(routes, {
            ("post", "/api/auth/login"),
            ("post", "/api/auth/register"),
            ("get", "/api/generation_records"),
            ("get", "/api/chat_history/{conversation_id}"),
            ("post", "/api/chat/{conversation_id}"),
            ("get", "/api/longtext_history/{conversation_id}"),
            ("post", "/api/longtext/generate/{conversation_id}"),
        })

    def test_backend_imports_resolve_to_existing_modules(self):
        for path in (ROOT / "backend").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith("backend."):
                        target = ROOT.joinpath(*node.module.split("."))
                        self.assertTrue(target.with_suffix(".py").is_file()
                                        or (target / "__init__.py").is_file(),
                                        f"{path}: {node.module}")

    def test_offline_tools_help_without_server_dependencies(self):
        for tool in ("finetune_embedding", "benchmark_embedding", "score_longtext_facts"):
            with self.subTest(tool=tool):
                result = subprocess.run(
                    [sys.executable, "-m", f"backend.tools.{tool}", "--help"],
                    cwd=ROOT, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
