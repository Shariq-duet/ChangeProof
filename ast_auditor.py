import ast
from pathlib import Path
from typing import Dict,List, Set

class AssertionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.asserted_keys:Set[str]=set()
        self.assert_lines:List[int]=[]
   
   
    def visit_Assert(self, node: ast.Assert):
        self.assert_lines.append(node.lineno)
        # Search for Subscript access inside assert, e.g., event["tenant_id"]
        for child in ast.walk(node.test):
            if isinstance(child, ast.Subscript):
                if isinstance(child.slice, ast.Constant):
                    self.asserted_keys.add(str(child.slice.value))
            # Also catch 'in' comparisons: "tenant_id" in event
            elif isinstance(child, ast.Compare):
                for comparator in child.comparators:
                    if isinstance(comparator, ast.Constant):
                        self.asserted_keys.add(str(comparator.value))
                if isinstance(child.left, ast.Constant):
                    self.asserted_keys.add(str(child.left.value))
        self.generic_visit(node)

def audit_test_assertions(test_file_path: str, target_key: str) -> Dict:
    path = Path(test_file_path)
    if not path.exists():
        return {"error": "Test file not found", "covered": False}

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = AssertionVisitor()
    visitor.visit(tree)

    is_covered = target_key in visitor.asserted_keys
    return {
        "target_key": target_key,
        "is_asserted": is_covered,
        "asserted_keys_found": list(visitor.asserted_keys),
        "total_assert_statements": len(visitor.assert_lines)
    }

if __name__ == "__main__":
    result = audit_test_assertions("tests/test_payment.py", "tenant_id")
    print("Deterministic AST Audit:", result)