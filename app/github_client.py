"""GitHub Classroom API integration."""
from github import Github
from datetime import datetime
from typing import List, Dict, Optional, Any
from app.config import Config
import requests
import json

class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token. If None, uses Config.GITHUB_TOKEN
        """
        self.token = token or Config.GITHUB_TOKEN

        if not self.token:
            raise ValueError("GitHub token is required")

        self.github = Github(self.token)
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Classroom-Guardian-Bot"
        }

    def _get_paginated(self, url: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Generic helper to fetch all pages for a GitHub REST endpoint."""
        items: List[Any] = []
        page = 1
        while True:
            q = {"per_page": 100, "page": page}
            if params:
                q.update(params)
            try:
                resp = requests.get(url, headers=self.headers, params=q)
                if resp.status_code != 200:
                    print(f"Error GET {url}: {resp.status_code} - {resp.text}")
                    break
                batch = resp.json()
                if not isinstance(batch, list):
                    # Some endpoints might return a dict; normalize to list where possible
                    break
                if not batch:
                    break
                items.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            except Exception as e:
                print(f"Exception GET {url}: {e}")
                break
        return items

    def get_all_classrooms(self) -> List[Dict]:
        """
        Get all classrooms accessible to the authenticated user.

        Returns:
            List of classroom dictionaries
        """
        classrooms = []

        try:
            url = f"{self.base_url}/classrooms"
            classrooms_data = self._get_paginated(url)
            for classroom in classrooms_data:
                classrooms.append({
                    'id': classroom.get('id'),
                    'name': classroom.get('name'),
                    'url': classroom.get('url'),
                    'archived': classroom.get('archived', False),
                    'organization': classroom.get('organization', {}),
                })
        except Exception as e:
            print(f"Exception getting classrooms: {e}")

        return classrooms

    def get_assignments_for_classroom(self, classroom_id: int) -> List[Dict]:
        """
        Get all assignments for a specific classroom.

        Args:
            classroom_id: ID of the classroom

        Returns:
            List of assignment dictionaries
        """
        assignments = []

        try:
            url = f"{self.base_url}/classrooms/{classroom_id}/assignments"
            assignments_data = self._get_paginated(url)
            for assignment in assignments_data:
                # Parse deadline if it exists
                deadline = assignment.get('deadline')
                if deadline:
                    try:
                        deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                    except Exception:
                        pass

                assignments.append({
                    'id': assignment.get('id'),
                    'title': assignment.get('title'),
                    'description': assignment.get('description'),
                    'deadline': deadline,
                    'student_repository_url': assignment.get('student_repository_url'),
                    'state': assignment.get('state'),
                    'type': assignment.get('type'),
                    'invitations_url': assignment.get('invitations_url'),
                    'accepted': assignment.get('accepted', 0),
                    'submitted': assignment.get('submitted', 0),
                    'passing': assignment.get('passing', 0),
                    'language': assignment.get('language'),
                    'starter_code_repository': assignment.get('starter_code_repository', {}),
                    'classroom': assignment.get('classroom', {}),
                })
        except Exception as e:
            print(f"Exception getting assignments for classroom {classroom_id}: {e}")

        return assignments

    def get_all_classrooms_with_assignments(self) -> List[Dict]:
        """
        Get all classrooms with their assignments.

        Returns:
            List of classroom dictionaries with nested assignments
        """
        result = []

        # Get all classrooms
        classrooms = self.get_all_classrooms()
        print(f"Found {len(classrooms)} classrooms")

        for classroom in classrooms:
            classroom_id = classroom['id']
            print(f"Processing classroom: {classroom['name']} (ID: {classroom_id})")

            # Get assignments for this classroom
            assignments = self.get_assignments_for_classroom(classroom_id)
            classroom['assignments'] = assignments
            classroom['assignments_count'] = len(assignments)

            result.append(classroom)

            print(f"  Found {len(assignments)} assignments in classroom '{classroom['name']}'")

        return result

    def _get_assignment_grades(self, assignment_id: int) -> List[Dict]:
        """Fetch grades (or per-student records) for a specific assignment."""
        try:
            url = f"{self.base_url}/assignments/{assignment_id}/grades"
            # Grades may be a list; use pagination helper for safety
            return self._get_paginated(url)
        except Exception as e:
            print(f"Exception getting grades for assignment {assignment_id}: {e}")
            return []

    def get_classroom_assignments(self, github_username: Optional[str] = None) -> List[Dict]:
        """
        Get all available classrooms and their assignments, flattened for bot display.

        Returns:
            A flat list of dictionaries with keys compatible with the bot UI:
            - name: assignment title
            - url: invitations_url (if available)
            - description: assignment description
            - classroom_id, classroom_name for reference
        """
        flat: List[Dict] = []
        classrooms = self.get_all_classrooms()
        for classroom in classrooms:
            class_id = classroom.get('id')
            class_name = classroom.get('name')
            assignments = self.get_assignments_for_classroom(class_id)
            for a in assignments:
                # Resolve per-user repository URL via grades endpoint if username provided
                repo_url = ''
                if github_username:
                    grades = self._get_assignment_grades(a.get('id'))
                    for g in grades:
                        # Try multiple shapes to extract username
                        u = None
                        if isinstance(g.get('student'), dict):
                            u = g['student'].get('github_username') or g['student'].get('login')
                        if not u:
                            u = g.get('github_username') or g.get('login')
                        if u and u.lower() == github_username.lower():
                            repo_url = (
                                g.get('student_repository_url')
                                or (isinstance(g.get('repository'), dict) and (g['repository'].get('html_url') or g['repository'].get('url')))
                                or ''
                            )
                            break
                # Fallbacks if grades did not yield a repo URL
                if not repo_url:
                    sr = a.get('student_repository_url')
                    if isinstance(sr, str):
                        repo_url = sr
                if not repo_url:
                    repo_obj = a.get('starter_code_repository') or {}
                    if isinstance(repo_obj, dict):
                        repo_url = repo_obj.get('html_url') or repo_obj.get('url') or ''
                if not repo_url:
                    repo_url = a.get('invitations_url') or ''

                flat.append({
                    'name': a.get('title'),
                    'url': repo_url,
                    'description': a.get('description') or '',
                    'deadline': a.get('deadline'),
                    'assignment_id': a.get('id'),
                    'classroom_id': class_id,
                    'classroom_name': class_name,
                })
        return flat

    def get_assignment_details(self, classroom_id: int, assignment_id: int) -> Optional[Dict]:
        """
        Get detailed information about a specific assignment.

        Args:
            classroom_id: ID of the classroom
            assignment_id: ID of the assignment

        Returns:
            Assignment details dictionary or None if not found
        """
        try:
            url = f"{self.base_url}/classrooms/{classroom_id}/assignments/{assignment_id}"
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting assignment details: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Exception getting assignment details: {e}")
            return None

    def get_accepted_assignments(self, classroom_id: int, assignment_id: int) -> List[Dict]:
        """
        Get list of students who accepted an assignment.

        Args:
            classroom_id: ID of the classroom
            assignment_id: ID of the assignment

        Returns:
            List of accepted assignment dictionaries
        """
        accepted = []

        try:
            url = f"{self.base_url}/classrooms/{classroom_id}/assignments/{assignment_id}/accepted_assignments"
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                accepted_data = response.json()

                for acceptance in accepted_data:
                    accepted.append({
                        'id': acceptance.get('id'),
                        'student': acceptance.get('student', {}),
                        'repository': acceptance.get('repository', {}),
                        'assignment': acceptance.get('assignment', {}),
                        'commit_count': acceptance.get('commit_count', 0),
                        'grade': acceptance.get('grade'),
                        'submitted': acceptance.get('submitted', False),
                        'passed': acceptance.get('passed', False),
                        'created_at': acceptance.get('created_at'),
                        'updated_at': acceptance.get('updated_at'),
                    })
            else:
                print(f"Error getting accepted assignments: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"Exception getting accepted assignments: {e}")

        return accepted

    # Keep the existing methods for backward compatibility
    def get_user_repositories(self) -> List[Dict]:
        """
        Get assignments from user's repositories.
        Returns all repositories accessible by the user.
        """
        assignments = []

        try:
            user = self.github.get_user()
            repos = user.get_repos()

            for repo in repos:
                assignments.append({
                    'name': repo.name,
                    'full_name': repo.full_name,
                    'url': repo.html_url,
                    'description': repo.description,
                    'created_at': repo.created_at,
                    'updated_at': repo.updated_at,
                })
        except Exception as e:
            print(f"Error getting user repositories: {e}")

        return assignments

    def parse_repo_url(self, repo_url: str) -> Optional[str]:
        """
        Parse repository name from GitHub URL.
        Examples:
        - https://github.com/org/repo -> org/repo
        - https://github.com/org/repo.git -> org/repo
        - org/repo -> org/repo
        """
        if not repo_url:
            return None

        # Remove .git suffix if present
        repo_url = repo_url.rstrip('.git')

        # Extract repo name from URL
        if 'github.com' in repo_url:
            # Extract from full URL
            parts = repo_url.split('github.com/')
            if len(parts) > 1:
                repo_path = parts[1].split('/')
                if len(repo_path) >= 2:
                    return f"{repo_path[0]}/{repo_path[1]}"
                elif len(repo_path) == 1:
                    return repo_path[0]

        # If it's already in org/repo format, return as is
        if '/' in repo_url:
            return repo_url

        return None

    def get_repository_commits(self, repo_name: str, since: Optional[datetime] = None) -> List[Dict]:
        """Get commits from a repository."""
        repo = None

        try:
            # Try full repository path (e.g., "org/repo" or "username/repo")
            if '/' in repo_name:
                repo = self.github.get_repo(repo_name)
            else:
                # Try to get user's own repo
                user = self.github.get_user()
                repo = user.get_repo(repo_name)
        except Exception as e:
            print(f"Error getting repository {repo_name}: {e}")
            return []

        if not repo:
            return []

        commits = []
        try:
            if since:
                commits_list = repo.get_commits(since=since)
            else:
                commits_list = repo.get_commits()

            for commit in commits_list[:10]:  # Limit to last 10 commits
                commits.append({
                    'sha': commit.sha,
                    'message': commit.commit.message,
                    'author': commit.commit.author.name if commit.commit.author else 'Unknown',
                    'date': commit.commit.author.date if commit.commit.author else None,
                    'url': commit.html_url,
                })
        except Exception as e:
            print(f"Error getting commits for {repo_name}: {e}")

        return commits

    def get_latest_commit(self, repo_name: str) -> Optional[Dict]:
        """Get the latest commit from a repository."""
        commits = self.get_repository_commits(repo_name)
        return commits[0] if commits else None

    def check_repository_exists(self, repo_name: str) -> bool:
        """Check if a repository exists."""
        try:
            # Try full repository path (e.g., "org/repo" or "username/repo")
            if '/' in repo_name:
                repo = self.github.get_repo(repo_name)
            else:
                # Try to get user's own repo
                user = self.github.get_user()
                repo = user.get_repo(repo_name)
            return repo is not None
        except Exception:
            return False

    def get_repository_activity(self, repo_name: str) -> Dict:
        """Get repository activity information."""
        repo = None

        try:
            # Try full repository path (e.g., "org/repo" or "username/repo")
            if '/' in repo_name:
                repo = self.github.get_repo(repo_name)
            else:
                # Try to get user's own repo
                user = self.github.get_user()
                repo = user.get_repo(repo_name)
        except Exception as e:
            print(f"Error getting repository {repo_name}: {e}")
            return {
                'exists': False,
                'has_commits': False,
                'last_commit': None,
                'url': None,
            }

        if not repo:
            return {
                'exists': False,
                'has_commits': False,
                'last_commit': None,
                'url': None,
            }

        latest_commit = self.get_latest_commit(repo_name)

        return {
            'exists': True,
            'has_commits': latest_commit is not None,
            'last_commit': latest_commit,
            'updated_at': repo.updated_at,
            'url': repo.html_url,
        }

    def get_latest_workflow_run(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest workflow run for a repository."""
        url = f"{self.base_url}/repos/{repo_full_name}/actions/runs"
        try:
            resp = requests.get(url, headers=self.headers, params={"per_page": 1})
        except Exception as e:
            print(f"Error requesting workflow runs for {repo_full_name}: {e}")
            return None

        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            print(f"Unexpected status when fetching workflow runs for {repo_full_name}: {resp.status_code} - {resp.text}")
            return None

        data = resp.json() or {}
        runs = data.get("workflow_runs") or []
        if not runs:
            return None

        run = runs[0]
        run_id = run.get("id")
        failure_summary = None
        if run.get("conclusion") == "failure" and run_id:
            failure_summary = self._get_run_failure_summary(repo_full_name, run_id)

        return {
            "id": run_id,
            "name": run.get("name") or run.get("display_title"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "updated_at": run.get("updated_at"),
            "run_number": run.get("run_number"),
            "html_url": run.get("html_url"),
            "failure_summary": failure_summary,
        }

    def _get_run_failure_summary(self, repo_full_name: str, run_id: int) -> Optional[str]:
        """Collect failure details for a workflow run."""
        url = f"{self.base_url}/repos/{repo_full_name}/actions/runs/{run_id}/jobs"
        try:
            resp = requests.get(url, headers=self.headers, params={"per_page": 100})
        except Exception as e:
            print(f"Error requesting workflow jobs for {repo_full_name}#{run_id}: {e}")
            return None

        if resp.status_code != 200:
            print(f"Unexpected status when fetching jobs for {repo_full_name}#{run_id}: {resp.status_code} - {resp.text}")
            return None

        data = resp.json() or {}
        jobs = data.get("jobs") or []
        messages: List[str] = []

        for job in jobs:
            if job.get("conclusion") != "failure":
                continue
            job_name = job.get("name") or "Unnamed job"
            job_url = job.get("html_url")
            prefix = f"Job '{job_name}' failed"
            if job_url:
                prefix += f" ({job_url})"
            failure_message = job.get("failure_message")
            if failure_message:
                messages.append(f"{prefix}: {failure_message}")
            else:
                messages.append(prefix)

            for step in job.get("steps") or []:
                if step.get("conclusion") == "failure":
                    step_name = step.get("name") or "Unnamed step"
                    details = (step.get("failure_message") or "").strip()
                    if details:
                        messages.append(f"  Step '{step_name}': {details}")
                    else:
                        messages.append(f"  Step '{step_name}' failed.")

        if not messages:
            return None
        return "\n".join(messages)

    def get_ci_status(self, repo_full_name: str) -> Dict[str, Any]:
        """
        Return GitHub Actions CI status for repository.

        Returns dict with keys:
            - found (bool)
            - status (str) raw run status
            - conclusion (str or None)
            - message (str) localized message for bot
            - html_url (str or None)
            - failure_summary (str or None)
        """
        run = self.get_latest_workflow_run(repo_full_name)
        if not run:
            return {
                "found": False,
                "status": None,
                "conclusion": None,
                "message": "Нет запусков GitHub Actions для репозитория.",
                "html_url": None,
                "failure_summary": None,
            }

        status = run.get("status") or ""
        conclusion = run.get("conclusion")
        html_url = run.get("html_url")
        failure_summary = run.get("failure_summary")

        if conclusion == "success":
            message = "Сборка удалась ✅"
        elif conclusion == "failure":
            message = "Сборка завершилась с ошибками ❌"
        elif status in {"queued", "in_progress", "waiting"}:
            message = "Сборка выполняется… ⏳"
        else:
            message = f"Состояние сборки: {conclusion or status or 'неизвестно'}"

        return {
            "found": True,
            "status": status,
            "conclusion": conclusion,
            "message": message,
            "html_url": html_url,
            "failure_summary": failure_summary,
        }


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = GitHubClient()

    # Get all classrooms with assignments
    classrooms_with_assignments = client.get_all_classrooms_with_assignments()

    # Print results
    for classroom in classrooms_with_assignments:
        print(f"\nClassroom: {classroom['name']} (ID: {classroom['id']})")
        print(f"Assignments: {classroom['assignments_count']}")

        for assignment in classroom['assignments']:
            print(f"  - {assignment['title']} (Deadline: {assignment['deadline']})")