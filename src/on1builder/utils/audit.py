"""
Code Audit Script for ON1Builder MEV Bot.

Performs comprehensive static analysis and security checks on the codebase.
"""

import ast
import inspect
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class AuditIssue:
    """Represents an audit issue found in the code."""
    severity: str  # 'critical', 'warning', 'info'
    file_path: str
    line_number: int
    issue_type: str
    description: str
    suggestion: str

class CodeAuditor:
    """
    Comprehensive code auditor for MEV bot security and best practices.
    """
    
    def __init__(self, project_root: str = "src/on1builder"):
        self.project_root = Path(project_root)
        self.issues: List[AuditIssue] = []
        
        # Patterns to check for
        self.sensitive_patterns = [
            r'private_key',
            r'secret',
            r'password',
            r'api_key',
            r'seed',
            r'mnemonic'
        ]
        
        self.async_patterns = [
            r'async def',
            r'await ',
            r'asyncio\.'
        ]
        
        self.logging_patterns = [
            r'logger\.',
            r'logging\.',
            r'print\('
        ]
    
    def run_full_audit(self) -> Dict[str, Any]:
        """Run complete code audit and return results."""
        logger.info("Starting comprehensive code audit...")
        
        try:
            # Find all Python files
            python_files = list(self.project_root.rglob("*.py"))
            
            for file_path in python_files:
                self._audit_file(file_path)
            
            # Generate audit report
            report = self._generate_report()
            
            logger.info(f"Audit completed. Found {len(self.issues)} issues.")
            return report
            
        except Exception as e:
            logger.error(f"Error during audit: {e}")
            return {"error": str(e), "issues": []}
    
    def _audit_file(self, file_path: Path):
        """Audit a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                self.issues.append(AuditIssue(
                    severity="critical",
                    file_path=str(file_path),
                    line_number=e.lineno,
                    issue_type="syntax_error",
                    description=f"Syntax error: {e.msg}",
                    suggestion="Fix syntax error before deployment"
                ))
                return
            
            # Run various checks
            self._check_input_validation(tree, file_path)
            self._check_async_handling(tree, file_path)
            self._check_exception_handling(tree, file_path)
            self._check_sensitive_data_logging(content, file_path)
            self._check_gas_efficiency(tree, file_path)
            self._check_security_patterns(content, file_path)
            
        except Exception as e:
            logger.error(f"Error auditing {file_path}: {e}")
    
    def _check_input_validation(self, tree: ast.AST, file_path: Path):
        """Check for proper input validation."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check function parameters
                for arg in node.args.args:
                    if arg.arg == 'self':
                        continue
                    
                    # Look for validation in function body
                    has_validation = self._has_validation_in_body(node.body, arg.arg)
                    
                    if not has_validation:
                        self.issues.append(AuditIssue(
                            severity="warning",
                            file_path=str(file_path),
                            line_number=node.lineno,
                            issue_type="missing_input_validation",
                            description=f"Parameter '{arg.arg}' lacks validation",
                            suggestion=f"Add validation for parameter '{arg.arg}' (e.g., type checking, range validation)"
                        ))
    
    def _has_validation_in_body(self, body: List[ast.stmt], param_name: str) -> bool:
        """Check if function body contains validation for a parameter."""
        validation_patterns = [
            f"if {param_name}",
            f"assert {param_name}",
            f"isinstance({param_name}",
            f"len({param_name}",
            f"{param_name} is None",
            f"{param_name} <",
            f"{param_name} >"
        ]
        
        body_str = ast.unparse(body) if hasattr(ast, 'unparse') else str(body)
        
        for pattern in validation_patterns:
            if pattern in body_str:
                return True
        
        return False
    
    def _check_async_handling(self, tree: ast.AST, file_path: Path):
        """Check for proper async/await usage."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for unawaited async calls
                if hasattr(node, 'func') and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['get', 'post', 'send', 'submit']:
                        # Check if this is awaited
                        parent = self._get_parent_node(tree, node)
                        if not self._is_awaited(parent):
                            self.issues.append(AuditIssue(
                                severity="warning",
                                file_path=str(file_path),
                                line_number=node.lineno,
                                issue_type="unawaited_async_call",
                                description=f"Async call '{node.func.attr}' not awaited",
                                suggestion="Add 'await' before the async call"
                            ))
    
    def _is_awaited(self, node: ast.AST) -> bool:
        """Check if a node is wrapped in await."""
        if isinstance(node, ast.Await):
            return True
        return False
    
    def _get_parent_node(self, tree: ast.AST, target_node: ast.AST) -> ast.AST:
        """Get parent node of target node."""
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if child is target_node:
                    return node
        return target_node
    
    def _check_exception_handling(self, tree: ast.AST, file_path: Path):
        """Check for proper exception handling."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Check if exceptions are properly caught and logged
                has_logging = False
                for handler in node.handlers:
                    if handler.body:
                        handler_str = ast.unparse(handler.body) if hasattr(ast, 'unparse') else str(handler.body)
                        if 'logger.' in handler_str or 'logging.' in handler_str:
                            has_logging = True
                            break
                
                if not has_logging:
                    self.issues.append(AuditIssue(
                        severity="warning",
                        file_path=str(file_path),
                        line_number=node.lineno,
                        issue_type="incomplete_exception_handling",
                        description="Exception caught but not logged",
                        suggestion="Add proper logging in exception handler"
                    ))
    
    def _check_sensitive_data_logging(self, content: str, file_path: Path):
        """Check for potential logging of sensitive data."""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for sensitive data patterns in logging statements
            if any(pattern in line.lower() for pattern in ['logger.', 'logging.', 'print(']):
                for sensitive_pattern in self.sensitive_patterns:
                    if sensitive_pattern in line.lower():
                        self.issues.append(AuditIssue(
                            severity="critical",
                            file_path=str(file_path),
                            line_number=i,
                            issue_type="sensitive_data_logging",
                            description=f"Potential logging of sensitive data: {sensitive_pattern}",
                            suggestion="Remove or mask sensitive data from logs"
                        ))
    
    def _check_gas_efficiency(self, tree: ast.AST, file_path: Path):
        """Check for gas-inefficient patterns."""
        for node in ast.walk(tree):
            # Check for loops that might be gas-intensive
            if isinstance(node, ast.For):
                # Check if loop iterates over large collections
                if hasattr(node, 'iter') and isinstance(node.iter, ast.Call):
                    if hasattr(node.iter.func, 'attr') and node.iter.func.attr in ['range', 'enumerate']:
                        # Check for large ranges
                        if hasattr(node.iter.args, '0') and isinstance(node.iter.args[0], ast.Constant):
                            if node.iter.args[0].value > 1000:
                                self.issues.append(AuditIssue(
                                    severity="warning",
                                    file_path=str(file_path),
                                    line_number=node.lineno,
                                    issue_type="gas_inefficient_loop",
                                    description=f"Large loop range: {node.iter.args[0].value}",
                                    suggestion="Consider pagination or batch processing for large loops"
                                ))
    
    def _check_security_patterns(self, content: str, file_path: Path):
        """Check for security-related patterns."""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for hardcoded private keys
            if '0x' in line and len(line.strip()) > 66:  # Potential private key
                if re.match(r'0x[a-fA-F0-9]{64}', line.strip()):
                    self.issues.append(AuditIssue(
                        severity="critical",
                        file_path=str(file_path),
                        line_number=i,
                        issue_type="hardcoded_private_key",
                        description="Potential hardcoded private key detected",
                        suggestion="Move private keys to environment variables or secure storage"
                    ))
            
            # Check for eval() usage
            if 'eval(' in line:
                self.issues.append(AuditIssue(
                    severity="critical",
                    file_path=str(file_path),
                    line_number=i,
                    issue_type="eval_usage",
                    description="eval() function usage detected",
                    suggestion="Replace eval() with safer alternatives"
                ))
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report."""
        critical_issues = [i for i in self.issues if i.severity == "critical"]
        warning_issues = [i for i in self.issues if i.severity == "warning"]
        info_issues = [i for i in self.issues if i.severity == "info"]
        
        # Group issues by type
        issue_types = {}
        for issue in self.issues:
            if issue.issue_type not in issue_types:
                issue_types[issue.issue_type] = []
            issue_types[issue.issue_type].append(issue)
        
        return {
            "summary": {
                "total_issues": len(self.issues),
                "critical": len(critical_issues),
                "warnings": len(warning_issues),
                "info": len(info_issues)
            },
            "issues_by_severity": {
                "critical": [self._issue_to_dict(i) for i in critical_issues],
                "warnings": [self._issue_to_dict(i) for i in warning_issues],
                "info": [self._issue_to_dict(i) for i in info_issues]
            },
            "issues_by_type": {
                issue_type: [self._issue_to_dict(i) for i in issues]
                for issue_type, issues in issue_types.items()
            },
            "recommendations": self._generate_recommendations()
        }
    
    def _issue_to_dict(self, issue: AuditIssue) -> Dict:
        """Convert audit issue to dictionary."""
        return {
            "file_path": issue.file_path,
            "line_number": issue.line_number,
            "description": issue.description,
            "suggestion": issue.suggestion
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on audit findings."""
        recommendations = []
        
        critical_count = len([i for i in self.issues if i.severity == "critical"])
        if critical_count > 0:
            recommendations.append(f"Fix {critical_count} critical issues before deployment")
        
        warning_count = len([i for i in self.issues if i.severity == "warning"])
        if warning_count > 0:
            recommendations.append(f"Review {warning_count} warnings for potential improvements")
        
        # Specific recommendations based on issue types
        issue_types = set(i.issue_type for i in self.issues)
        
        if "sensitive_data_logging" in issue_types:
            recommendations.append("Implement secure logging practices - never log private keys or secrets")
        
        if "unawaited_async_call" in issue_types:
            recommendations.append("Review async/await usage to ensure proper concurrency handling")
        
        if "missing_input_validation" in issue_types:
            recommendations.append("Add input validation for all public functions")
        
        return recommendations

def run_audit(project_root: str = "src/on1builder") -> Dict[str, Any]:
    """Run the code audit and return results."""
    auditor = CodeAuditor(project_root)
    return auditor.run_full_audit()

if __name__ == "__main__":
    # Run audit when script is executed directly
    import json
    
    results = run_audit()
    print(json.dumps(results, indent=2)) 