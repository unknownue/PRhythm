import asyncio
import json
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from .configuration import MockLLMMode
from .state import MockAnalysisResponse


class MockLLMService:
    """Mock LLM service for development and testing."""
    
    def __init__(self, mode: MockLLMMode = MockLLMMode.SIMPLE, delay_seconds: float = 1.0):
        self.mode = mode
        self.delay_seconds = delay_seconds
        self._response_templates = self._load_response_templates()
    
    def _load_response_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load response templates for different agent types."""
        return {
            "pr_supervisor": {
                "simple": {
                    "analysis_plan": "Analyze repository structure, examine PR diff, gather context, generate report",
                    "agent_assignments": ["repository_analyzer", "diff_analyzer", "context_gatherer", "report_generator"],
                    "coordination_strategy": "Sequential execution with parallel context gathering"
                },
                "realistic": {
                    "analysis_plan": """Based on the PR analysis request, I will coordinate the following analysis workflow:
1. Repository Analysis: Understand the codebase structure, technologies, and architecture
2. Diff Analysis: Examine the specific changes made in the PR
3. Context Gathering: Collect relevant code context and dependencies
4. Report Generation: Synthesize findings into a comprehensive analysis report

The analysis will be performed with standard depth, focusing on impact assessment and risk evaluation.""",
                    "agent_assignments": {
                        "repository_analyzer": ["analyze_repo_structure", "identify_technologies", "assess_complexity"],
                        "diff_analyzer": ["analyze_changes", "identify_risk_areas", "assess_impact"],
                        "context_gatherer": ["collect_related_files", "identify_dependencies", "gather_test_info"],
                        "report_generator": ["synthesize_findings", "generate_recommendations", "create_final_report"]
                    },
                    "coordination_strategy": "Parallel execution of repository and diff analysis, followed by context gathering and report generation"
                }
            },
            "repository_analyzer": {
                "simple": {
                    "summary": "JavaScript/TypeScript repository with React frontend and Node.js backend",
                    "technologies": ["React", "Node.js", "TypeScript", "Express"],
                    "architecture_patterns": ["MVC", "Component-based"],
                    "complexity_score": 6
                },
                "realistic": {
                    "summary": """This repository implements a modern web application using a full-stack JavaScript approach. The frontend is built with React and TypeScript, providing a component-based architecture with strong typing. The backend uses Node.js with Express framework, following RESTful API design principles. The codebase demonstrates good separation of concerns with distinct layers for routing, business logic, and data access.""",
                    "technologies": ["React 18", "TypeScript 4.9", "Node.js 18", "Express 4.18", "PostgreSQL", "Jest", "Webpack", "ESLint"],
                    "architecture_patterns": ["Model-View-Controller", "Component-based UI", "RESTful API", "Layered Architecture"],
                    "key_components": ["Authentication Service", "User Management", "API Gateway", "Database Layer", "Frontend Components"],
                    "complexity_score": 7
                }
            },
            "diff_analyzer": {
                "simple": {
                    "summary": "Added new API endpoint and updated frontend component",
                    "affected_components": ["API routes", "React components"],
                    "change_types": ["feature"],
                    "risk_level": "low"
                },
                "realistic": {
                    "summary": """The PR introduces a new user authentication feature with the following key changes:
- Added new API endpoint `/api/auth/login` with JWT token generation
- Created LoginForm React component with form validation
- Updated user model to include authentication fields
- Added middleware for JWT token verification
- Modified existing UserService to handle authentication logic""",
                    "affected_components": ["Authentication System", "User Management", "API Layer", "Frontend Components", "Database Schema"],
                    "change_types": ["feature", "enhancement", "refactor"],
                    "complexity_score": 7,
                    "risk_level": "medium",
                    "breaking_changes": ["Modified user model schema may require database migration"]
                }
            },
            "context_gatherer": {
                "simple": {
                    "relevant_files": ["package.json", "README.md", "config/database.js"],
                    "dependencies": ["express", "react", "jsonwebtoken"],
                    "test_coverage": {"overall": "75%"}
                },
                "realistic": {
                    "relevant_files": [
                        {"file": "package.json", "relevance": 0.9, "type": "configuration"},
                        {"file": "src/models/User.js", "relevance": 0.95, "type": "source"},
                        {"file": "src/middleware/auth.js", "relevance": 0.8, "type": "source"},
                        {"file": "tests/auth.test.js", "relevance": 0.7, "type": "test"},
                        {"file": "docs/API.md", "relevance": 0.6, "type": "documentation"}
                    ],
                    "dependencies": ["jsonwebtoken", "bcrypt", "passport", "express-validator"],
                    "related_features": ["User Registration", "Password Reset", "Profile Management", "Session Management"],
                    "test_coverage": {
                        "overall": "78%",
                        "authentication": "85%",
                        "api_endpoints": "70%",
                        "frontend_components": "82%"
                    }
                }
            },
            "report_generator": {
                "simple": {
                    "title": "PR Analysis Report",
                    "executive_summary": "The PR adds authentication functionality with low risk.",
                    "recommendations": ["Test thoroughly", "Review security measures"]
                },
                "realistic": {
                    "title": "Pull Request Analysis: User Authentication Feature Implementation",
                    "executive_summary": """This PR introduces a comprehensive user authentication system to the application. The implementation follows security best practices with JWT token-based authentication, proper password hashing, and input validation. The changes are well-structured and maintain the existing codebase architecture. While the risk level is moderate due to security-critical functionality, the implementation appears robust with good test coverage.""",
                    "repository_overview": """The target repository is a full-stack JavaScript application with React frontend and Node.js backend. The codebase demonstrates good architectural practices with clear separation of concerns, comprehensive testing, and modern development practices.""",
                    "changes_summary": """The PR adds authentication capabilities including:
- JWT-based login/logout functionality
- Secure password hashing with bcrypt
- Authentication middleware for protected routes
- Frontend login form with validation
- Database schema updates for user authentication""",
                    "impact_analysis": """The changes primarily affect the authentication and user management systems. The implementation is additive, minimizing risk to existing functionality. Database schema changes require careful migration planning.""",
                    "risk_assessment": """Medium risk due to security-critical nature of authentication. Key risks include:
- Database migration complexity
- JWT token security configuration
- Session management implementation
Recommended mitigation: thorough security testing and code review""",
                    "recommendations": [
                        "Conduct thorough security testing of authentication flows",
                        "Review JWT token configuration and expiration policies", 
                        "Ensure database migration scripts are tested",
                        "Verify input validation on all authentication endpoints",
                        "Test for common authentication vulnerabilities (OWASP)"
                    ],
                    "conclusion": "The PR implements a well-structured authentication system that enhances application security. With proper testing and security review, this feature should integrate successfully."
                }
            }
        }
    
    async def _simulate_processing_delay(self) -> int:
        """Simulate processing delay and return processing time."""
        start_time = time.time()
        if self.delay_seconds > 0:
            # Add some randomness to make it more realistic
            actual_delay = self.delay_seconds + random.uniform(-0.3, 0.7)
            actual_delay = max(0.1, actual_delay)  # Minimum 0.1 seconds
            await asyncio.sleep(actual_delay)
        
        processing_time = int((time.time() - start_time) * 1000)
        return processing_time
    
    def _get_template_response(self, agent_type: str) -> Dict[str, Any]:
        """Get template response for agent type."""
        templates = self._response_templates.get(agent_type, {})
        
        if self.mode == MockLLMMode.SIMPLE:
            return templates.get("simple", {})
        elif self.mode in [MockLLMMode.REALISTIC, MockLLMMode.MIXED]:
            return templates.get("realistic", templates.get("simple", {}))
        
        return {}
    
    async def analyze_repository(self, repository_url: str, context_data: str) -> str:
        """Mock repository analysis."""
        processing_time = await self._simulate_processing_delay()
        
        template = self._get_template_response("repository_analyzer")
        
        response = MockAnalysisResponse(
            agent_type="repository_analyzer",
            analysis_summary=template.get("summary", "Repository analysis completed"),
            key_findings=[
                f"Technologies: {', '.join(template.get('technologies', ['Unknown']))}",
                f"Architecture: {', '.join(template.get('architecture_patterns', ['Standard']))}",
                f"Complexity Score: {template.get('complexity_score', 5)}/10"
            ],
            confidence_score=random.uniform(0.7, 0.95),
            processing_time_ms=processing_time
        )
        
        return json.dumps(template, indent=2)
    
    async def analyze_diff(self, pr_diff_data: str, repository_context: Optional[str] = None) -> str:
        """Mock diff analysis."""
        processing_time = await self._simulate_processing_delay()
        
        template = self._get_template_response("diff_analyzer")
        
        response = MockAnalysisResponse(
            agent_type="diff_analyzer",
            analysis_summary=template.get("summary", "Diff analysis completed"),
            key_findings=[
                f"Change Types: {', '.join(template.get('change_types', ['modification']))}",
                f"Risk Level: {template.get('risk_level', 'low')}",
                f"Components Affected: {len(template.get('affected_components', []))}"
            ],
            confidence_score=random.uniform(0.75, 0.92),
            processing_time_ms=processing_time
        )
        
        return json.dumps(template, indent=2)
    
    async def gather_context(self, repository_url: str, pr_number: int, changed_files: List[str]) -> str:
        """Mock context gathering."""
        processing_time = await self._simulate_processing_delay()
        
        template = self._get_template_response("context_gatherer")
        
        response = MockAnalysisResponse(
            agent_type="context_gatherer",
            analysis_summary="Context gathering completed",
            key_findings=[
                f"Relevant Files: {len(template.get('relevant_files', []))}",
                f"Dependencies: {len(template.get('dependencies', []))}",
                f"Test Coverage: {template.get('test_coverage', {}).get('overall', 'N/A')}"
            ],
            confidence_score=random.uniform(0.8, 0.95),
            processing_time_ms=processing_time
        )
        
        return json.dumps(template, indent=2)
    
    async def generate_report(self, analysis_data: str) -> str:
        """Mock report generation."""
        processing_time = await self._simulate_processing_delay()
        
        template = self._get_template_response("report_generator")
        
        response = MockAnalysisResponse(
            agent_type="report_generator",
            analysis_summary="Report generation completed",
            key_findings=[
                f"Report Title: {template.get('title', 'Analysis Report')}",
                f"Recommendations: {len(template.get('recommendations', []))}",
                "Full report generated successfully"
            ],
            confidence_score=random.uniform(0.85, 0.98),
            processing_time_ms=processing_time
        )
        
        return json.dumps(template, indent=2)
    
    async def coordinate_analysis(self, analysis_request: str) -> str:
        """Mock supervisor coordination."""
        processing_time = await self._simulate_processing_delay()
        
        template = self._get_template_response("pr_supervisor")
        
        response = MockAnalysisResponse(
            agent_type="pr_supervisor",
            analysis_summary="Analysis coordination completed",
            key_findings=[
                f"Analysis Plan: {template.get('analysis_plan', 'Standard analysis workflow')}",
                f"Agents Assigned: {len(template.get('agent_assignments', []))}",
                "Coordination strategy defined"
            ],
            confidence_score=random.uniform(0.9, 0.99),
            processing_time_ms=processing_time
        )
        
        return json.dumps(template, indent=2)
    
    def is_enabled(self) -> bool:
        """Check if mock LLM is enabled."""
        return self.mode != MockLLMMode.DISABLED
    
    def should_use_mock_for_agent(self, agent_type: str) -> bool:
        """Determine if mock should be used for specific agent type."""
        if self.mode == MockLLMMode.DISABLED:
            return False
        elif self.mode in [MockLLMMode.SIMPLE, MockLLMMode.REALISTIC]:
            return True
        elif self.mode == MockLLMMode.MIXED:
            # In mixed mode, randomly decide for each agent
            return random.choice([True, False])
        
        return False