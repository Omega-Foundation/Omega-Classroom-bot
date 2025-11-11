"""GitHub Classroom API integration."""
from github import Github
from datetime import datetime
from typing import List, Dict, Optional
from app.config import Config

class GitHubClient:
    """Client for interacting with GitHub API."""
    
    def __init__(self, token: str = None):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token. If None, uses Config.GITHUB_TOKEN (for backward compatibility)
        """
        self.token = token or Config.GITHUB_TOKEN
        
        if not self.token:
            raise ValueError("GitHub token is required")
        
        self.github = Github(self.token)
    
    def get_classroom_assignments(self) -> List[Dict]:
        """
        Get assignments from user's repositories.
        Returns all repositories accessible by the user.
        """
        assignments = []
        
        try:
            user = self.github.get_user()
#             repos = user.get_repos()
            
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
            print(f"Error getting classroom assignments: {e}")
        
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
