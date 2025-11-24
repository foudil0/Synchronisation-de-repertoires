import datetime 
import os
import json
from dotenv import load_dotenv
from git import InvalidGitRepositoryError, Repo
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

        if commit_date:
            repo.index.commit(
                "Initial commit",
                author=repo.config_reader().get_value("user", "name"),
                author_email=repo.config_reader().get_value("user", "email"),
                commit_date=commit_date.isoformat()
            )
        else:
            repo.index.commit("Initial commit")

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


# def main():
#     token, username, email = load_config()
#     github_client = Github(token)
#     state = load_state()

#     potential_projects = {}

#     for parent_folder in PARENT_DIRECTORIES:

#         if not os.path.isdir(parent_folder):
#             print(f"Parent folder not found: {parent_folder}")
#             continue
        
#         print(f"Scanning inside: {parent_folder}")
        
#         try:
#             for item_name in os.listdir(parent_folder):
#                 item_path = os.path.join(parent_folder, item_name)
                
#                 if not os.path.isdir(item_path) or item_name.startswith('.'):
#                     print(f"Skipping non-directory or hidden item: {item_name}")
#                     continue
                
#                 # Check one level deeper for single subdirectory
#                 try:
#                     level1_contents = os.listdir(item_path)
#                     subdirs = [d for d in level1_contents
#                             if os.path.isdir(os.path.join(item_path, d)) and not d.startswith('.')]
                    
#                     if len(subdirs) == 1:
#                         sub_item_path = os.path.join(item_path, subdirs[0])
#                         print(f"Adding single sub-directory: {sub_item_path}")
                        
#                         if sub_item_path not in potential_projects:
#                             potential_projects[sub_item_path] = None
#                 except PermissionError:
#                     print(f"Permission denied accessing contents of {item_path}.")
#                 except Exception as e:
#                     print(f"Error checking contents of {item_path}: {e}")
        
#         except PermissionError:
#             print(f"Permission denied scanning directory {parent_folder}. Skipping.")
#         except Exception as e:
#             print(f"Error scanning directory {parent_folder}: {e}")
                        
                
def main():

    # Test 1: Load configuration
    print("1. Testing load_config()...")
    try:
        token, username, email = load_config()
        print(f"✓ Config loaded: username={username}, email={email}")
        
        auth = Auth.Token(token)
        github_client = Github(auth=auth)
        
        print("✓ GitHub client created successfully\n")
    except Exception as e:
        print(f"✗ Error loading config: {e}\n")
        return
    
    # Test 2: Load/Save state
    print("2. Testing load_state() and save_state()...")
    try:
        state = load_state()
        print(f"✓ Current state: {state}")
        
        test_state = {"test_path": {"repo_name": "test_repo", "repo_url": "https://github.com/test/test.git"}}
        save_state(test_state)
        print("✓ Test state saved")
        
        # Restore original state
        save_state(state)
        print("✓ Original state restored\n")
    except Exception as e:
        print(f"✗ Error with state: {e}\n")
    
    # Test 3: Scan directories
    print("3. Testing directory scanning...")
    potential_projects = {}
    
    for parent_folder in PARENT_DIRECTORIES:
        if not os.path.isdir(parent_folder):
            print(f"✗ Parent folder not found: {parent_folder}")
            continue
        
        print(f"✓ Scanning: {parent_folder}")
        
        try:
            for item_name in os.listdir(parent_folder):
                item_path = os.path.join(parent_folder, item_name)
                
                if not os.path.isdir(item_path) or item_name.startswith('.'):
                    continue
                
                print(f"  Found directory: {item_name}")
                potential_projects[item_path] = None
                
        except Exception as e:
            print(f"✗ Error scanning: {e}")
    
    print(f"✓ Found {len(potential_projects)} potential projects\n")
    
    # Test 4: Test get_commit_date
    print("4. Testing get_commit_date()...")
    if potential_projects:
        test_path = list(potential_projects.keys())[0]
        try:
            commit_date = get_commit_date(test_path)
            print(f"✓ Commit date for {test_path}: {commit_date}\n")
        except Exception as e:
            print(f"✗ Error getting commit date: {e}\n")
    
    # Test 5: Test GitHub repo creation
    print("5. Testing create_github_repo()...")
    repo_urls = {}
    
    for project_path in potential_projects.keys():
        try:
            project_name = os.path.basename(project_path)
            
            repo_name = project_name.replace(" ", "-").replace("_", "-").lower()
            repo_name = "".join(c for c in repo_name if c.isalnum() or c == "-") 
            
            print(f"Creating repo for project: {project_name} -> {repo_name}")
            
            repo_url = create_github_repo(
                repo_name=repo_name,
                is_private=True,  
                description=f"project: {project_name}",
                github_client=github_client,
                username=username
            )
            
            if repo_url:
                print(f"✓ Repository created/found: {repo_url}")
                repo_urls[project_path] = repo_url
                potential_projects[project_path] = {"repo_name": repo_name, "repo_url": repo_url}
            else:
                print(f"✗ Failed to create repository for {project_name}")
                
        except Exception as e:
            print(f"✗ Error creating repo for {project_path}: {e}")
    
    print(f"\n✓ Created/found {len(repo_urls)} repositories\n")
    
    # Test 6: Test gitignore creation
    print("6. Testing ensure_gitignore()...")
    for project_path in potential_projects.keys():
        try:
            result = ensure_gitignore(project_path)
            if result:
                print(f"✓ .gitignore ensured in {project_path}\n")
        except Exception as e:
            print(f"✗ Error with gitignore in {project_path}: {e}\n")
    
    # Test 7: Test initialize_local_repo 
    print("7. Testing initialize_local_repo()...")
    if potential_projects and repo_urls:
        for project_path in potential_projects.keys():
            repo_url = repo_urls.get(project_path)
            if not repo_url:
                print(f"✗ No repo URL found for {project_path}")
                continue
                
            try:
                result = initialize_local_repo(project_path, repo_url)
                if result:
                    print(f"✓ Successfully initialized local repo: {project_path}\n")
                else:
                    print(f"✗ Failed to initialize local repo: {project_path}\n")
            except Exception as e:
                print(f"✗ Error initializing {project_path}: {e}\n")
    else:
        print("✗ No projects or repo URLs available\n")

    # Test 8: Check for uncommitted changes
    print("8. Testing has_uncommited_changes()...")
    for project_path in potential_projects.keys():  
        try:
            repo = Repo(project_path)
            has_changes = has_uncommited_changes(repo)
            print(f"  {project_path}: {'Has changes' if has_changes else 'Clean'}")
        except InvalidGitRepositoryError:
            print(f"  {project_path}: Not a git repo")
        except Exception as e:
            print(f"  {project_path}: Error - {e}")
    print()

        # Test 10: Test push_updates 
    print("10. Testing push_updates()...")
    if potential_projects and repo_urls:
        for project_path in potential_projects.keys():
            try:
                test_file_path = os.path.join(project_path, "test_push.txt")
                with open(test_file_path, 'w') as f:
                    f.write(f"Test content - {datetime.datetime.now()}\n")
                print(f"✓ Created test file in {project_path}")
                
                repo = Repo(project_path)
                if has_uncommited_changes(repo):
                    print(f"✓ Repository has uncommitted changes")
                    
                    project_name = os.path.basename(project_path)
                    commit_msg = f"Test commit from Project - {project_name}"
                    result = push_updates(project_path, commit_msg)
                    
                    if result:
                        print(f"✓ Successfully pushed updates from {project_path}\n")
                    else:
                        print(f"✗ Failed to push updates from {project_path}\n")
                else:
                    print(f"✗ No changes detected in {project_path}\n")
                    
            except Exception as e:
                print(f"✗ Error testing push_updates for {project_path}: {e}\n")
    else:
        print("✗ No projects or repo URLs available for testing\n")

        # Test 11: Save final state of all projects
    print("11. Testing save_state() with all projects...")
    try:
        final_state = {}
        
        for project_path in potential_projects.keys():
            project_info = potential_projects[project_path]
            
            if project_info and isinstance(project_info, dict):
                final_state[project_path] = {
                    "repo_name": project_info.get("repo_name"),
                    "repo_url": project_info.get("repo_url"),
                    "last_sync": datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                }
                print(f"  Added to state: {project_path}")
            else:
                print(f"  Skipped (no repo info): {project_path}")
        
        if final_state:
            save_state(final_state)
            print(f"✓ Successfully saved state for {len(final_state)} projects")
            
            # Verify the saved state
            loaded_state = load_state()
            if loaded_state == final_state:
                print("✓ State verification successful (saved == loaded)")
            else:
                print("✗ State verification failed (mismatch)")
            
            # Display saved state
            print("\nSaved state:")
            for path, info in final_state.items():
                print(f"  {path}:")
                print(f"    - repo_name: {info['repo_name']}")
                print(f"    - repo_url: {info['repo_url']}")
                print(f"    - last_sync: {info['last_sync']}")
        else:
            print("✗ No project state to save\n")
            
    except Exception as e:
        print(f"✗ Error saving final state: {e}\n")
    

if __name__ == "__main__":
    main()

    
