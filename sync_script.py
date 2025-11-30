import datetime 
import os
import json
from dotenv import load_dotenv
from git import Actor, InvalidGitRepositoryError, Repo
from github import Github, GithubException, Auth


STATE_FILE="tracked_repos.json"
BACKDATE_COMMITS_TO_FOLDER_DATE = False
PARENT_DIRECTORIES = ["../Projects_test"]


# Load configuration from .env file
def load_config():
    load_dotenv()
    token = os.getenv("GITHUB_API_TOKEN")
    username = os.getenv("GITHUB_USERNAME")
    email = os.getenv("GITHUB_EMAIL")

    if not token or not username or not email:
        raise ValueError("Missing required environment variables.")
    return token, username, email


# Load tracking state from JSON file
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


# Save tracking state to JSON file
def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)


# Get the commit date for a folder mtime or current date
def get_commit_date(folder_path):
    if BACKDATE_COMMITS_TO_FOLDER_DATE:
        timestamp = os.path.getmtime(folder_path)
        dt_object = datetime.datetime.fromtimestamp(timestamp)
        return dt_object
    
    return datetime.datetime.now(tz=datetime.timezone.utc)


# Check if there are uncommited changes in the repo
def has_uncommited_changes(repo):
    return repo.is_dirty(untracked_files=True)


# Create a GitHub repository or return existing one
def create_github_repo(repo_name, is_private, description, github_client, username):
    try:
        user = github_client.get_user()
        repo = user.create_repo(
            name=repo_name,
            private=is_private,
            description=description or f"Project: {repo_name}",
            auto_init=False 
        )
        token = os.getenv("GITHUB_API_TOKEN")
        auth_url = repo.clone_url.replace("https://", f"https://{token}@")
        return auth_url
    except GithubException as e:
        if e.status == 422:
            print(f"Repository {repo_name} already exists on GitHub.")
            try:
                repo = user.get_repo(repo_name)
                print(f"Using existing repository {repo.html_url}.")
                token = os.getenv("GITHUB_API_TOKEN")
                auth_url = repo.clone_url.replace("https://", f"https://{token}@")
                return auth_url 
            except GithubException:
                print(f"Failed to access existing repository {repo_name}.")
                return None
        else:
            print(f"Failed to create repository {repo_name}: {e}")
            return None
        

# Ensure a .gitignore file exists in the folder
def ensure_gitignore(folder_path):
    gitignore_path = os.path.join(folder_path, ".gitignore") 

    if not os.path.exists(gitignore_path):
        with open(gitignore_path, 'w') as f:
            f.write("# Auto-generated .gitignore")
        return True
    else:
        print(f".gitignore already exists in {folder_path}.")
        return True
    

# Pull updates from remote repository
def pull_updates(folder_path):
    try:
        repo = Repo(folder_path)
        try:
            origin = repo.remote('origin')
        except ValueError:
            print(f"No remote 'origin' found for {folder_path}.")
            return False
        
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            print(f"couldn't determine current branch. cannot pull updates.")
            return False
        
        origin.pull(current_branch, rebase=False)

        print(f"Successfully pulled updates for {folder_path}.")
        return True
    
    except Exception as e:
        print(f"Failed to pull updates for {folder_path}: {e}")
        return False
    

# Initialize local Git repository and set remote
def initialize_local_repo(folder_path, repo_url):
    try:
        repo = Repo(folder_path)
        print(f"Existing Git repository found in {folder_path}.")
    except InvalidGitRepositoryError:
        print(f"Initializing new Git repository in {folder_path}.")
        repo = Repo.init(folder_path)

    if not ensure_gitignore(folder_path):
        return False
        
    try:
        origin = repo.remote('origin') 
        current_url = next(origin.urls)

        if current_url == repo_url:
            print(f"Remote 'origin' already set to {repo_url}.")
        else:
            origin.set_url(repo_url)
            print(f"Updated remote 'origin' URL to {repo_url}.")
    except ValueError:
        origin = repo.create_remote('origin', repo_url)
        print(f"Set remote 'origin' to {repo_url}.")

    repo.git.add(A=True)

    if repo.is_dirty() or repo.untracked_files:
        commit_date = get_commit_date(folder_path)

        author_name = repo.config_reader().get_value("user", "name")
        author_email = repo.config_reader().get_value("user", "email")

        author = Actor(author_name, author_email)

        if commit_date:
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author,
                author_date=commit_date,
                commit_date=commit_date
            )
        else:
            repo.index.commit(
                "Initial commit",
                author=author,
                committer=author
            )

        try:
            current_branch = repo.active_branch.name
        except TypeError:
            current_branch = 'main'
            print(f"couldn't determine current branch. Setting to {current_branch}.")
            repo.git.checkout('-B', current_branch)

        print("Pushing initial commit to remote repository.")
        origin.push(refspec=f"{current_branch}:{current_branch}", set_upstream=True)
    else:
        print(f"No changes to commit in {folder_path}.")

    print(f"Successfully configured local repo {folder_path} for {repo_url}.")
    return True


# Commit and push updates to remote repository
def push_updates(folder_path, commit_message):
    repo = Repo(folder_path)

    repo.git.add(A=True)

    if not repo.is_dirty() and not repo.untracked_files:
        print(f"No changes to commit in {folder_path}.")
        return True
    
    pull_updates(folder_path)

    commit_date = get_commit_date(folder_path)

    repo.index.commit(
        commit_message,
        author_date=commit_date,
        commit_date=commit_date
    )

    try:
        current_branch = repo.active_branch.name
    except TypeError:
        print(f"couldn't determine current branch. cannot push changes.")
        return False
    
    origin = repo.remote('origin')
    origin.push(refspec=f"{current_branch}:{current_branch}")
    print(f"Succesfully pushed changes to remote repository from {folder_path}.")
    return True


def sync_projects(github_client, username, state):
    potential_projects = {}

    # Scan des répertoires parents
    for parent_folder in PARENT_DIRECTORIES:
        if not os.path.isdir(parent_folder):
            print(f"Parent folder not found: {parent_folder}")
            continue
        
        print(f"\nScanning inside: {parent_folder}")
        
        try:
            for item_name in os.listdir(parent_folder):
                item_path = os.path.join(parent_folder, item_name)
                
                if not os.path.isdir(item_path) or item_name.startswith('.'):
                    continue
                
                print(f"Found directory: {item_name}")
                potential_projects[item_path] = None
                
        except PermissionError:
            print(f"Permission denied scanning directory {parent_folder}. Skipping.")
        except Exception as e:
            print(f"Error scanning directory {parent_folder}: {e}")
    
    print(f"\nFound {len(potential_projects)} potential projects to sync")
    
    # Traiter chaque projet
    synced_count = 0
    failed_count = 0
    
    for project_path in potential_projects.keys():
        project_name = os.path.basename(project_path)
        
        # Nettoyer le nom du repo
        repo_name = project_name.replace(" ", "-").replace("_", "-").lower()
        repo_name = "".join(c for c in repo_name if c.isalnum() or c == "-")
        
        print(f"\n{'='*60}")
        print(f"Processing project: {project_name}")
        print(f"Repository name: {repo_name}")
        print(f"{'='*60}")
        
        # Vérifier si déjà synchronisé
        if project_path in state:
            print(f"Project already tracked. Checking for updates...")
            
            try:
                repo = Repo(project_path)
                
                if has_uncommited_changes(repo):
                    print(f"Changes detected. Pushing updates...")
                    if push_updates(project_path, f"Update {project_name}"):
                        state[project_path]["last_sync"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                        synced_count += 1
                        print(f"✓ Successfully updated {project_name}")
                    else:
                        failed_count += 1
                        print(f"✗ Failed to update {project_name}")
                else:
                    print(f"✓ No changes detected in {project_name}")
                    synced_count += 1
                    
            except InvalidGitRepositoryError:
                print(f"Not a valid git repository. Re-initializing...")
            except Exception as e:
                print(f"✗ Error checking {project_name}: {e}")
                failed_count += 1
                continue
        
        # Si pas encore synchronisé ou erreur détectée
        if project_path not in state or not isinstance(state.get(project_path), dict):
            # Créer le repo GitHub
            repo_url = create_github_repo(
                repo_name=repo_name,
                is_private=True,
                description=f"Project: {project_name}",
                github_client=github_client,
                username=username
            )
            
            if not repo_url:
                print(f"✗ Skipping {project_name} - failed to create/access repo")
                failed_count += 1
                continue
            
            # Initialiser le repo local et pousser
            if initialize_local_repo(project_path, repo_url):
                state[project_path] = {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "last_sync": datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                }
                synced_count += 1
                print(f"✓ Successfully synced {project_name}")
            else:
                failed_count += 1
                print(f"✗ Failed to initialize {project_name}")
    return state


def main():
    try:
        # Charger la configuration
        print("Loading configuration...")
        token, username, email = load_config()
        print(f"✓ Loaded config for user: {username}")
        
        # Créer le client GitHub
        auth = Auth.Token(token)
        github_client = Github(auth=auth)
        print("✓ GitHub client created\n")
        
        # Charger l'état actuel
        state = load_state()
        print(f"✓ Loaded state ({len(state)} tracked projects)\n")
        
        # Synchroniser les projets
        updated_state = sync_projects(github_client, username, state)
        
        # Sauvegarder l'état mis à jour
        save_state(updated_state)
        print("✓ State saved successfully")
        
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

