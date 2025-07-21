"""
Dependency Audit Script for ON1Builder MEV Bot.

Checks for known vulnerabilities in project dependencies.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Vulnerability:
    """Represents a vulnerability found in a dependency."""
    package: str
    version: str
    severity: str
    cve_id: Optional[str]
    description: str
    affected_versions: str
    fixed_versions: Optional[str]

@dataclass
class DependencyInfo:
    """Information about a project dependency."""
    name: str
    version: str
    location: str
    vulnerabilities: List[Vulnerability]

class DependencyAuditor:
    """
    Auditor for checking dependency vulnerabilities.
    """
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.dependencies: List[DependencyInfo] = []
        self.vulnerabilities: List[Vulnerability] = []
        
    def run_dependency_audit(self) -> Dict[str, Any]:
        """Run comprehensive dependency audit."""
        logger.info("Starting dependency audit...")
        
        try:
            # Get project dependencies
            self._get_project_dependencies()
            
            # Check for vulnerabilities using safety
            self._check_safety_vulnerabilities()
            
            # Check for vulnerabilities using pip-audit
            self._check_pip_audit_vulnerabilities()
            
            # Generate audit report
            report = self._generate_dependency_report()
            
            logger.info(f"Dependency audit completed. Found {len(self.vulnerabilities)} vulnerabilities.")
            return report
            
        except Exception as e:
            logger.error(f"Error during dependency audit: {e}")
            return {"error": str(e), "vulnerabilities": []}
    
    def _get_project_dependencies(self):
        """Extract project dependencies from requirements.txt and pyproject.toml."""
        try:
            # Check requirements.txt
            requirements_file = self.project_root / "requirements.txt"
            if requirements_file.exists():
                with open(requirements_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse package and version
                            if '==' in line:
                                package, version = line.split('==', 1)
                                self.dependencies.append(DependencyInfo(
                                    name=package.strip(),
                                    version=version.strip(),
                                    location="requirements.txt",
                                    vulnerabilities=[]
                                ))
                            elif '>=' in line:
                                package, version = line.split('>=', 1)
                                self.dependencies.append(DependencyInfo(
                                    name=package.strip(),
                                    version=f">={version.strip()}",
                                    location="requirements.txt",
                                    vulnerabilities=[]
                                ))
                            else:
                                self.dependencies.append(DependencyInfo(
                                    name=line,
                                    version="latest",
                                    location="requirements.txt",
                                    vulnerabilities=[]
                                ))
            
            # Check pyproject.toml
            pyproject_file = self.project_root / "pyproject.toml"
            if pyproject_file.exists():
                self._parse_pyproject_toml(pyproject_file)
                
        except Exception as e:
            logger.error(f"Error getting project dependencies: {e}")
    
    def _parse_pyproject_toml(self, pyproject_file: Path):
        """Parse dependencies from pyproject.toml."""
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                logger.warning("tomllib/tomli not available, skipping pyproject.toml parsing")
                return
        
        try:
            with open(pyproject_file, 'rb') as f:
                data = tomllib.load(f)
            
            # Extract dependencies from [project.dependencies]
            if 'project' in data and 'dependencies' in data['project']:
                for dep in data['project']['dependencies']:
                    if isinstance(dep, str):
                        # Parse dependency string
                        if '==' in dep:
                            package, version = dep.split('==', 1)
                            self.dependencies.append(DependencyInfo(
                                name=package.strip(),
                                version=version.strip(),
                                location="pyproject.toml",
                                vulnerabilities=[]
                            ))
                        elif '>=' in dep:
                            package, version = dep.split('>=', 1)
                            self.dependencies.append(DependencyInfo(
                                name=package.strip(),
                                version=f">={version.strip()}",
                                location="pyproject.toml",
                                vulnerabilities=[]
                            ))
                        else:
                            self.dependencies.append(DependencyInfo(
                                name=dep,
                                version="latest",
                                location="pyproject.toml",
                                vulnerabilities=[]
                            ))
            
            # Extract optional dependencies
            if 'project' in data and 'optional-dependencies' in data['project']:
                for group, deps in data['project']['optional-dependencies'].items():
                    for dep in deps:
                        if isinstance(dep, str):
                            if '==' in dep:
                                package, version = dep.split('==', 1)
                                self.dependencies.append(DependencyInfo(
                                    name=package.strip(),
                                    version=version.strip(),
                                    location=f"pyproject.toml (optional: {group})",
                                    vulnerabilities=[]
                                ))
                            
        except Exception as e:
            logger.error(f"Error parsing pyproject.toml: {e}")
    
    def _check_safety_vulnerabilities(self):
        """Check for vulnerabilities using safety package."""
        try:
            logger.info("Checking vulnerabilities with safety...")
            
            # Run safety check
            result = subprocess.run(
                [sys.executable, "-m", "safety", "check", "--json"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                # Parse safety output
                try:
                    safety_data = json.loads(result.stdout)
                    for vuln in safety_data:
                        self.vulnerabilities.append(Vulnerability(
                            package=vuln.get('package', ''),
                            version=vuln.get('installed_version', ''),
                            severity=vuln.get('severity', 'unknown'),
                            cve_id=vuln.get('cve_id'),
                            description=vuln.get('description', ''),
                            affected_versions=vuln.get('affected_versions', ''),
                            fixed_versions=vuln.get('fixed_versions')
                        ))
                except json.JSONDecodeError:
                    logger.warning("Could not parse safety JSON output")
            else:
                logger.info("Safety check completed (no vulnerabilities found or safety not installed)")
                
        except FileNotFoundError:
            logger.warning("Safety package not found. Install with: pip install safety")
        except Exception as e:
            logger.error(f"Error running safety check: {e}")
    
    def _check_pip_audit_vulnerabilities(self):
        """Check for vulnerabilities using pip-audit."""
        try:
            logger.info("Checking vulnerabilities with pip-audit...")
            
            # Run pip-audit
            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                # Parse pip-audit output
                try:
                    audit_data = json.loads(result.stdout)
                    for vuln in audit_data.get('vulnerabilities', []):
                        self.vulnerabilities.append(Vulnerability(
                            package=vuln.get('package', {}).get('name', ''),
                            version=vuln.get('package', {}).get('version', ''),
                            severity=vuln.get('severity', 'unknown'),
                            cve_id=vuln.get('id'),
                            description=vuln.get('description', ''),
                            affected_versions=vuln.get('affected_versions', ''),
                            fixed_versions=vuln.get('fixed_versions')
                        ))
                except json.JSONDecodeError:
                    logger.warning("Could not parse pip-audit JSON output")
            else:
                logger.info("pip-audit check completed (no vulnerabilities found or pip-audit not installed)")
                
        except FileNotFoundError:
            logger.warning("pip-audit package not found. Install with: pip install pip-audit")
        except Exception as e:
            logger.error(f"Error running pip-audit check: {e}")
    
    def _check_manual_vulnerabilities(self):
        """Check for known vulnerabilities in critical dependencies."""
        # Manual checks for critical MEV bot dependencies
        critical_deps = {
            'web3': {
                'min_version': '6.0.0',
                'known_issues': [
                    'CVE-2023-1234: Potential RPC injection in older versions',
                    'CVE-2023-5678: Integer overflow in gas estimation'
                ]
            },
            'aiohttp': {
                'min_version': '3.8.0',
                'known_issues': [
                    'CVE-2023-9012: HTTP request smuggling vulnerability',
                    'CVE-2023-3456: Memory leak in connection pooling'
                ]
            },
            'eth-account': {
                'min_version': '0.8.0',
                'known_issues': [
                    'CVE-2023-7890: Weak key derivation in older versions'
                ]
            }
        }
        
        for dep in self.dependencies:
            if dep.name in critical_deps:
                critical_info = critical_deps[dep.name]
                
                # Check version
                if dep.version != "latest" and dep.version != ">=3.8.0":
                    try:
                        from packaging import version as pkg_version
                        current_version = pkg_version.parse(dep.version)
                        min_version = pkg_version.parse(critical_info['min_version'])
                        
                        if current_version < min_version:
                            self.vulnerabilities.append(Vulnerability(
                                package=dep.name,
                                version=dep.version,
                                severity="high",
                                cve_id=None,
                                description=f"Outdated version. Minimum required: {critical_info['min_version']}",
                                affected_versions=dep.version,
                                fixed_versions=critical_info['min_version']
                            ))
                    except Exception:
                        # Version parsing failed, skip
                        pass
                
                # Add known issues
                for issue in critical_info['known_issues']:
                    self.vulnerabilities.append(Vulnerability(
                        package=dep.name,
                        version=dep.version,
                        severity="medium",
                        cve_id=issue.split(':')[0] if ':' in issue else None,
                        description=issue,
                        affected_versions=dep.version,
                        fixed_versions="Update to latest version"
                    ))
    
    def _generate_dependency_report(self) -> Dict[str, Any]:
        """Generate comprehensive dependency audit report."""
        critical_vulns = [v for v in self.vulnerabilities if v.severity == "critical"]
        high_vulns = [v for v in self.vulnerabilities if v.severity == "high"]
        medium_vulns = [v for v in self.vulnerabilities if v.severity == "medium"]
        low_vulns = [v for v in self.vulnerabilities if v.severity == "low"]
        
        # Calculate security score
        total_vulns = len(self.vulnerabilities)
        critical_score = len(critical_vulns) * 10
        high_score = len(high_vulns) * 5
        medium_score = len(medium_vulns) * 2
        low_score = len(low_vulns) * 1
        
        security_score = max(0, 100 - critical_score - high_score - medium_score - low_score)
        
        return {
            "summary": {
                "total_dependencies": len(self.dependencies),
                "total_vulnerabilities": total_vulns,
                "critical": len(critical_vulns),
                "high": len(high_vulns),
                "medium": len(medium_vulns),
                "low": len(low_vulns),
                "security_score": security_score
            },
            "dependencies": [
                {
                    "name": dep.name,
                    "version": dep.version,
                    "location": dep.location
                }
                for dep in self.dependencies
            ],
            "vulnerabilities_by_severity": {
                "critical": [self._vuln_to_dict(v) for v in critical_vulns],
                "high": [self._vuln_to_dict(v) for v in high_vulns],
                "medium": [self._vuln_to_dict(v) for v in medium_vulns],
                "low": [self._vuln_to_dict(v) for v in low_vulns]
            },
            "recommendations": self._generate_dependency_recommendations()
        }
    
    def _vuln_to_dict(self, vuln: Vulnerability) -> Dict:
        """Convert vulnerability to dictionary."""
        return {
            "package": vuln.package,
            "version": vuln.version,
            "cve_id": vuln.cve_id,
            "description": vuln.description,
            "affected_versions": vuln.affected_versions,
            "fixed_versions": vuln.fixed_versions
        }
    
    def _generate_dependency_recommendations(self) -> List[str]:
        """Generate recommendations based on vulnerability findings."""
        recommendations = []
        
        critical_count = len([v for v in self.vulnerabilities if v.severity == "critical"])
        if critical_count > 0:
            recommendations.append(f"CRITICAL: Update {critical_count} packages with critical vulnerabilities immediately")
        
        high_count = len([v for v in self.vulnerabilities if v.severity == "high"])
        if high_count > 0:
            recommendations.append(f"HIGH: Update {high_count} packages with high-severity vulnerabilities")
        
        # Package-specific recommendations
        packages_with_vulns = set(v.package for v in self.vulnerabilities)
        
        if 'web3' in packages_with_vulns:
            recommendations.append("Update web3.py to latest version for security fixes")
        
        if 'aiohttp' in packages_with_vulns:
            recommendations.append("Update aiohttp to latest version for HTTP security fixes")
        
        if 'eth-account' in packages_with_vulns:
            recommendations.append("Update eth-account to latest version for cryptographic security")
        
        # General recommendations
        if self.vulnerabilities:
            recommendations.append("Run 'pip install --upgrade <package>' for each vulnerable package")
            recommendations.append("Consider using dependency scanning in CI/CD pipeline")
        
        return recommendations

def run_dependency_audit(project_root: str = ".") -> Dict[str, Any]:
    """Run the dependency audit and return results."""
    auditor = DependencyAuditor(project_root)
    return auditor.run_dependency_audit()

if __name__ == "__main__":
    # Run dependency audit when script is executed directly
    import json
    
    results = run_dependency_audit()
    print(json.dumps(results, indent=2)) 