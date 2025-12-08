import time
import os
import threading
import datetime
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from github import Github, Auth
from sync_script import sync_projects, load_config, load_state, save_state, has_uncommited_changes, push_updates, Repo


SYNC_DELAY = 5 

PARENTS_DIR = ["../Projects_test"]

IGNORE_PATTERNS = [
    '.git',
    '__pycache__',
    '.pyc',
    '.venv',
    'venv',
    '.env',
    'node_modules',
    '.DS_Store',
    'tracked_repos.json',
    '_local_'
]

class ChangeHandler(FileSystemEventHandler):

    def __init__(self):
        self.last_sync_time = {}
        self.sync_timer = None
        self.lock = threading.Lock()

    def to_ignore(self, path):
        for pattern in IGNORE_PATTERNS:
            if pattern in path:
                return True
        return False
    
    def schedule_sync(self, project_path):
        with self.lock:
            if self.sync_timer and self.sync_timer.is_alive():
                self.sync_timer.cancel()
            
        self.sync_timer = threading.Timer(
            SYNC_DELAY, 
            self.trigger_sync,
            args=[project_path]
        )
        self.sync_timer.start()
        print(f"Scheduled sync for {project_path} in {SYNC_DELAY} seconds.")

    def trigger_sync(self, project_path):
        project_name = os.path.basename(project_path)

        last_sync = self.last_sync_time.get(project_path, 0)
        current_time = time.time()

        if current_time - last_sync < SYNC_DELAY:
            print(f"⏭ Skipping sync for {project_name} (last sync was too recent).")
            return
        
        print(f"\n{'='*60}")
        print(f"🔄 Triggering sync for {project_name}...")
        print(f"{'='*60}")

        try:
            token, username, email = load_config()
            auth = Auth.Token(token)
            github_client = Github(auth=auth)
            state = load_state()

            # Vérifier si le projet est déjà tracké
            if project_path not in state:
                print(f"📦 New project detected: {project_name}")
                print(f"⚠ Running initial setup via sync_projects...")
                
                # Utiliser sync_projects pour initialiser le nouveau projet
                temp_projects = {project_path: None}
                
                # Créer le repo GitHub et initialiser
                from sync_script import create_github_repo, initialize_local_repo
                
                repo_name = project_name.replace(" ", "-").replace("_", "-").lower()
                repo_name = "".join(c for c in repo_name if c.isalnum() or c == "-")
                
                print(f"📝 Creating GitHub repository: {repo_name}")
                repo_url = create_github_repo(
                    repo_name=repo_name,
                    is_private=True,
                    description=f"Project: {project_name}",
                    github_client=github_client,
                    username=username
                )
                
                if not repo_url:
                    print(f"✗ Failed to create GitHub repo for {project_name}")
                    return
                
                print(f"🔧 Initializing local repository...")
                if initialize_local_repo(project_path, repo_url):
                    state[project_path] = {
                        "repo_name": repo_name,
                        "repo_url": repo_url,
                        "last_sync": datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                    }
                    save_state(state)
                    print(f"✅ {project_name} initialized and synced successfully!")
                else:
                    print(f"✗ Failed to initialize {project_name}")
                
                self.last_sync_time[project_path] = current_time
                return

            # Pour les projets existants
            try:
                repo = Repo(project_path)

                if has_uncommited_changes(repo):
                    print(f"📝 Uncommitted changes detected. Pushing updates...")
                    if push_updates(project_path, f"Auto-sync: {project_name}"): 
                        state[project_path]["last_sync"] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat() 
                        save_state(state)
                        print(f"✅ {project_name} synced successfully.")
                    else:
                        print(f"✗ Failed to push updates for {project_name}.")
                else:
                    print(f"ℹ️ No changes to sync for {project_name}.")
                    
            except Exception as e:
                print(f"✗ Error syncing {project_name}: {e}")
                traceback.print_exc()

            self.last_sync_time[project_path] = current_time

        except Exception as e:
            print(f"✗ Critical error during sync for {project_name}: {e}")
            traceback.print_exc()

    def on_modified(self, event):
        if event.is_directory or self.to_ignore(event.src_path):
            return
        
        project_path = self.get_project_path(event.src_path)
        if project_path:
            self.schedule_sync(project_path)

    def on_created(self, event):
        if event.is_directory or self.to_ignore(event.src_path):
            return
        
        project_path = self.get_project_path(event.src_path)
        if project_path:
            self.schedule_sync(project_path)

    def on_deleted(self, event):
        if event.is_directory or self.to_ignore(event.src_path):
            return
        
        project_path = self.get_project_path(event.src_path)
        if project_path:
            self.schedule_sync(project_path)

    def get_project_path(self, file_path):
        for parent in PARENTS_DIR:
            abs_parent = os.path.abspath(parent)
            abs_file = os.path.abspath(file_path)
            
            if abs_file.startswith(abs_parent):
                relative_path = os.path.relpath(file_path, abs_parent)
                project_name = relative_path.split(os.sep)[0]
                return os.path.join(abs_parent, project_name)
            
        return None
    
def start_watching():
    event_handler = ChangeHandler()
    observer = Observer()

    for parent in PARENTS_DIR:
        if os.path.exists(parent):
            observer.schedule(event_handler, parent, recursive=True)
            print(f"Started watching directory: {parent}")
        else:
            print(f"Directory does not exist: {parent}")
        
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    print("Stopped watching.")

if __name__ == "__main__":
    start_watching()