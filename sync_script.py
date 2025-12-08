import datetime 
import os
import json
from dotenv import load_dotenv
from git import Actor, InvalidGitRepositoryError, Repo, GitCommandError
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
    

def handle_conflict_rename_local(repo, folder_path):
    if not repo.index.unmerged_blobs():
        print("Aucun conflit détecté dans l'index.")
        return False

    print(f"⚠ Conflits détectés dans {folder_path}. Résolution en cours...")

    try:
        unmerged_blobs = repo.index.unmerged_blobs()

        for file_path in unmerged_blobs:
            base, ext = os.path.splitext(file_path)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            local_renamed_path = f"{base}_local_{timestamp}{ext}"

            try:
                content_local = repo.git.show(f":2:{file_path}")
                full_local_path = os.path.join(folder_path, local_renamed_path)
                with open(full_local_path, "w", encoding="utf-8") as f:
                    f.write(content_local)
                print(f"   -> Version locale sauvegardée sous : {local_renamed_path}")
            except Exception as e:
                print(f"   ! Erreur sauvegarde locale {file_path}: {e}")
                continue

            repo.git.checkout("--theirs", file_path)
            print(f"   -> Version distante acceptée pour : {file_path}")

            repo.git.add(file_path)
            repo.git.add(local_renamed_path)


        commit_msg = "Auto-resolve: Rename local conflicts and keep remote version"
        repo.git.commit("-m", commit_msg)
        
        print("✓ Conflits résolus et commités localement (Merge Commit créé).")
        return True

    except Exception as e:
        print(f"✗ Erreur critique résolution conflit : {e}")
        return False
    


def pull_updates(folder_path):
    try:
        repo = Repo(folder_path)
        
        if 'origin' not in repo.remotes:
            print(f"No remote 'origin' found for {folder_path}.")
            return False
            
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            print(f"couldn't determine current branch. cannot pull updates.")
            return False

        # Nettoyage d'un ancien état de merge incomplet
        git_dir = os.path.join(folder_path, '.git')
        if os.path.exists(os.path.join(git_dir, 'MERGE_HEAD')):
            print(f"⚠ Unfinished merge detected in {folder_path}. cleaning state...")
            try:
                repo.git.merge('--abort')
                print("   -> Old merge aborted. Repository is clean.")
            except GitCommandError:
                pass

        print(f"Pulling from {current_branch}...")
        repo.git.pull('origin', current_branch, '--no-rebase')

        print(f"Successfully pulled updates for {folder_path}.")
        return True
    
    except GitCommandError as e:
        err_msg = str(e)
        if "CONFLICT" in err_msg or "Merge conflict" in err_msg:
            print(f"⚠ Conflict detected during pull in {folder_path}.")
            return handle_conflict_rename_local(repo, folder_path)
        
        elif "MERGE_HEAD exists" in err_msg:
             print(f"⚠ Still stuck in merge state. Attempting force abort...")
             try:
                 repo.git.merge('--abort')
                 return pull_updates(folder_path) 
             except:
                 return False

        else:
            print(f"Git pull failed in {folder_path}: {e}")
            return False
            
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


def push_updates(folder_path, commit_message):
    repo = Repo(folder_path)

    # 1. Ajouter tout à l'index
    repo.git.add(A=True)

    if not repo.is_dirty() and not repo.untracked_files:
        print(f"No changes to commit in {folder_path}.")
        return True
    
    # 2. COMMITTER 
    commit_date = get_commit_date(folder_path)
    repo.index.commit(
        commit_message,
        author_date=commit_date,
        commit_date=commit_date
    )
    print(f"Changes committed locally in {folder_path}.")

    # 3. PULL 
    if not pull_updates(folder_path):
        print(f"Warning: Pull failed or processed conflicts in {folder_path}.")

    # 4. PUSH
    try:
        current_branch = repo.active_branch.name
    except TypeError:
        print(f"couldn't determine current branch. cannot push changes.")
        return False
    
    try:
        origin = repo.remote('origin')
        push_infos = origin.push(refspec=f"{current_branch}:{current_branch}")
        
        success = True
        for info in push_infos:
            if info.flags & info.ERROR:
                print(f"✗ Push failed for {info.remote_ref_string}: {info.summary}")
                success = False
        
        if success:
            print(f"Succesfully pushed changes to remote repository from {folder_path}.")
            return True
        else:
            return False

    except Exception as e:
        print(f"Failed to push changes: {e}")
        return False


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
        token, username, email = load_config()
        auth = Auth.Token(token)
        github_client = Github(auth=auth)
        
        state = load_state()
        updated_state = sync_projects(github_client, username, state)
        save_state(updated_state)
        
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

