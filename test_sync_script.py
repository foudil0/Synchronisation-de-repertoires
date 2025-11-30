import datetime
import os
from git import Repo, InvalidGitRepositoryError
from github import Auth, Github
from sync_script import (
    load_config,
    load_state,
    save_state,
    get_commit_date,
    has_uncommited_changes,
    create_github_repo,
    ensure_gitignore,
    initialize_local_repo,
    push_updates,
    PARENT_DIRECTORIES
)


def test_all():
    print("=== Testing sync_script.py functions ===\n")
    
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
                print(f"✓ .gitignore ensured in {project_path}")
        except Exception as e:
            print(f"✗ Error with gitignore in {project_path}: {e}")
    print()
    
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

    # Test 9: Test push_updates 
    print("9. Testing push_updates()...")
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

    # Test 10: Save final state of all projects
    print("10. Testing save_state() with all projects...")
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
    
    print("\n=== Test Summary ===")
    print(f"Found {len(potential_projects)} potential projects")
    print("All tests completed!")


if __name__ == "__main__":
    test_all()