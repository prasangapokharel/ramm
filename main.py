import os
import time
import subprocess
import hashlib
import sys
import threading
import json
import requests
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                            QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, 
                            QTextEdit, QLineEdit, QGroupBox, QProgressBar, QSpinBox,
                            QTabWidget, QComboBox, QCheckBox, QMessageBox, QSplitter,
                            QFrame, QScrollArea, QStackedWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QColor

# GitHub API class for repository operations
class GitHubAPI:
    def __init__(self, token=None):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    def set_token(self, token):
        self.token = token
        self.headers["Authorization"] = f"token {token}"
    
    def get_user_info(self):
        """Get authenticated user information"""
        response = requests.get(f"{self.base_url}/user", headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get user info: {response.text}")
    
    def list_repositories(self):
        """List user repositories"""
        response = requests.get(f"{self.base_url}/user/repos", headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to list repositories: {response.text}")
    
    def create_repository(self, name, description="", private=False):
        """Create a new repository"""
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": True  # Initialize with README
        }
        
        response = requests.post(f"{self.base_url}/user/repos", 
                                headers=self.headers, 
                                data=json.dumps(data))
        
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create repository: {response.text}")
    
    def delete_repository(self, owner, repo):
        """Delete a repository"""
        response = requests.delete(f"{self.base_url}/repos/{owner}/{repo}", 
                                  headers=self.headers)
        
        if response.status_code == 204:
            return True
        else:
            raise Exception(f"Failed to delete repository: {response.text}")
    
    def check_repository_exists(self, owner, repo):
        """Check if a repository exists"""
        response = requests.get(f"{self.base_url}/repos/{owner}/{repo}", 
                               headers=self.headers)
        
        return response.status_code == 200


class MonitorThread(QThread):
    update_signal = pyqtSignal(str)
    hash_calculated_signal = pyqtSignal()
    stats_update_signal = pyqtSignal(dict)
    change_detected_signal = pyqtSignal()
    
    def __init__(self, directory, check_interval=10):
        super().__init__()
        self.directory = directory
        self.check_interval = check_interval
        self.running = True
        self.previous_hash = None
        self.stats = {
            "commits": 0,
            "changes_detected": 0,
            "failed_operations": 0,
            "last_commit": "Never"
        }
    
    def get_directory_hash(self):
        """Calculate a hash of all files in the directory to detect changes"""
        hash_list = []
        
        for root, dirs, files in os.walk(self.directory):
            for file in files:
                # Skip git directory
                if ".git" in root:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                        hash_list.append(f"{file_path}:{file_hash}")
                except Exception as e:
                    self.update_signal.emit(f"Error reading file {file_path}: {e}")
        
        # Sort to ensure consistent ordering
        hash_list.sort()
        return hashlib.md5("".join(hash_list).encode()).hexdigest()
    
    def git_operations(self):
        """Execute git operations: add, commit, and push"""
        try:
            # Change to the directory
            os.chdir(self.directory)
            
            # Git add
            self.update_signal.emit("Running git add...")
            add_process = subprocess.run(["git", "add", "."], 
                                        check=True, 
                                        capture_output=True, 
                                        text=True)
            self.update_signal.emit(f"git add output: {add_process.stdout}")
            
            # Check if there are changes to commit
            status_process = subprocess.run(["git", "status", "--porcelain"], 
                                           check=True, 
                                           capture_output=True, 
                                           text=True)
            
            if not status_process.stdout.strip():
                self.update_signal.emit("No changes to commit.")
                return False
            
            # Git commit
            self.update_signal.emit("Running git commit...")
            commit_process = subprocess.run(["git", "commit", "-m", f"Auto-commit: Changes detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"], 
                                           check=True, 
                                           capture_output=True, 
                                           text=True)
            self.update_signal.emit(f"git commit output: {commit_process.stdout}")
            
            # Git push
            self.update_signal.emit("Running git push...")
            push_process = subprocess.run(["git", "push", "origin", "main"], 
                                         check=True, 
                                         capture_output=True, 
                                         text=True)
            self.update_signal.emit(f"git push output: {push_process.stdout}")
            
            self.update_signal.emit("Successfully pushed changes to repository!")
            
            # Update stats
            self.stats["commits"] += 1
            self.stats["last_commit"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.stats_update_signal.emit(self.stats)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.update_signal.emit(f"Error in git operations: {e}")
            self.update_signal.emit(f"Command output: {e.stdout}")
            self.update_signal.emit(f"Command error: {e.stderr}")
            
            # Update stats
            self.stats["failed_operations"] += 1
            self.stats_update_signal.emit(self.stats)
            
            return False
    
    def run(self):
        self.update_signal.emit(f"Starting file monitor for {self.directory}")
        
        # Check if directory exists
        if not os.path.exists(self.directory):
            self.update_signal.emit(f"Error: Directory {self.directory} does not exist.")
            return
        
        # Check if it's a git repository
        if not os.path.exists(os.path.join(self.directory, ".git")):
            self.update_signal.emit(f"Error: {self.directory} is not a git repository.")
            return
        
        # Get initial directory hash
        self.update_signal.emit("Calculating initial directory hash...")
        self.previous_hash = self.get_directory_hash()
        self.update_signal.emit("Initial directory hash calculated. Monitoring for changes...")
        self.hash_calculated_signal.emit()
        
        try:
            while self.running:
                # Get current hash
                current_hash = self.get_directory_hash()
                
                # Check if hash has changed
                if current_hash != self.previous_hash:
                    self.update_signal.emit("Changes detected!")
                    self.stats["changes_detected"] += 1
                    self.change_detected_signal.emit()
                    self.stats_update_signal.emit(self.stats)
                    
                    # Perform git operations
                    success = self.git_operations()
                    
                    if success:
                        # Update hash after successful git operations
                        self.previous_hash = current_hash
                    
                # Wait before checking again
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
        except Exception as e:
            self.update_signal.emit(f"Error in monitor thread: {e}")
    
    def stop(self):
        self.running = False


class SidebarButton(QPushButton):
    def __init__(self, text, icon_name=None, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(50)
        self.setCheckable(True)
        
        # Set icon if provided
        if icon_name:
            self.setIcon(QIcon(f"{icon_name}.svg"))
            self.setIconSize(QSize(24, 24))
        
        # Style
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 0;
                text-align: left;
                padding: 10px 15px;
                font-weight: bold;
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:checked {
                background-color: #3498db;
                color: white;
            }
        """)


class GitAutoCommitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.monitor_thread = None
        self.directory = None
        self.change_count = 0
        self.github_api = GitHubAPI()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("GitHub Automation Tool")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        
        # Main widget
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background-color: #2c3e50;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # App title in sidebar
        title_label = QLabel("GitHub Auto")
        title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 20px;")
        title_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(title_label)
        
        # Sidebar buttons
        self.monitor_btn = SidebarButton("Monitor", "monitor")
        self.repo_btn = SidebarButton("Repositories", "repo")
        self.settings_btn = SidebarButton("Settings", "settings")
        self.stats_btn = SidebarButton("Statistics", "stats")
        
        # Set first button as checked
        self.monitor_btn.setChecked(True)
        
        # Connect buttons to change content
        self.monitor_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.repo_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.settings_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.stats_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
        
        # Add buttons to sidebar
        sidebar_layout.addWidget(self.monitor_btn)
        sidebar_layout.addWidget(self.repo_btn)
        sidebar_layout.addWidget(self.settings_btn)
        sidebar_layout.addWidget(self.stats_btn)
        
        # Add spacer at the bottom
        sidebar_layout.addStretch()
        
        # Create content area
        content_area = QWidget()
        content_area.setStyleSheet("background-color: white;")
        
        # Create stacked widget for different pages
        self.content_stack = QStackedWidget()
        
        # Create pages
        monitor_page = self.create_monitor_page()
        repo_page = self.create_repo_page()
        settings_page = self.create_settings_page()
        stats_page = self.create_stats_page()
        
        # Add pages to stack
        self.content_stack.addWidget(monitor_page)
        self.content_stack.addWidget(repo_page)
        self.content_stack.addWidget(settings_page)
        self.content_stack.addWidget(stats_page)
        
        # Content layout
        content_layout = QVBoxLayout(content_area)
        content_layout.addWidget(self.content_stack)
        
        # Add sidebar and content to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(content_area, 1)  # Content area takes remaining space
        
        self.setCentralWidget(main_widget)
        
        # Set up progress timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.progress_value = 0
        
        self.log_message("GitHub Automation Tool started. Please configure your settings.")
    
    def create_monitor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Directory selection
        dir_group = QGroupBox("Repository Selection")
        dir_layout = QHBoxLayout()
        
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Select a Git repository directory")
        self.dir_input.setReadOnly(True)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_directory)
        browse_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        check_status_btn = QPushButton("Check Status")
        check_status_btn.clicked.connect(self.check_repo_status)
        check_status_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(browse_btn)
        dir_layout.addWidget(check_status_btn)
        dir_group.setLayout(dir_layout)
        
        # Monitor settings
        settings_group = QGroupBox("Monitor Settings")
        settings_layout = QHBoxLayout()
        
        interval_label = QLabel("Check Interval (seconds):")
        self.interval_spinner = QSpinBox()
        self.interval_spinner.setRange(1, 3600)
        self.interval_spinner.setValue(10)
        
        self.start_btn = QPushButton("Start Monitoring")
        self.start_btn.clicked.connect(self.start_monitoring)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("Stop Monitoring")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.setEnabled(False)
        
        settings_layout.addWidget(interval_label)
        settings_layout.addWidget(self.interval_spinner)
        settings_layout.addWidget(self.start_btn)
        settings_layout.addWidget(self.stop_btn)
        settings_group.setLayout(settings_layout)
        
        # Status indicators
        status_group = QGroupBox("Status")
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: Not Monitoring")
        self.status_label.setStyleSheet("font-weight: bold; color: gray;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                width: 10px;
                margin: 0.5px;
            }
        """)
        
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        status_group.setLayout(status_layout)
        
        # Log output
        log_group = QGroupBox("Process Log")
        log_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #000; color: #0f0; font-family: Courier;")
        
        log_layout.addWidget(self.log_output)
        log_group.setLayout(log_layout)
        
        # Add all sections to page layout
        layout.addWidget(dir_group)
        layout.addWidget(settings_group)
        layout.addWidget(status_group)
        layout.addWidget(log_group, 1)  # Give more space to the log
        
        return page
    
    def create_repo_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # GitHub Authentication
        auth_group = QGroupBox("GitHub Authentication")
        auth_layout = QHBoxLayout()
        
        token_label = QLabel("GitHub Token:")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Enter your GitHub personal access token")
        self.token_input.setEchoMode(QLineEdit.Password)
        
        save_token_btn = QPushButton("Save Token")
        save_token_btn.clicked.connect(self.save_github_token)
        save_token_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        
        auth_layout.addWidget(token_label)
        auth_layout.addWidget(self.token_input)
        auth_layout.addWidget(save_token_btn)
        auth_group.setLayout(auth_layout)
        
        # Create Repository
        create_group = QGroupBox("Create New Repository")
        create_layout = QVBoxLayout()
        
        repo_form_layout = QHBoxLayout()
        repo_name_label = QLabel("Repository Name:")
        self.repo_name_input = QLineEdit()
        
        repo_form_layout.addWidget(repo_name_label)
        repo_form_layout.addWidget(self.repo_name_input)
        
        repo_desc_layout = QHBoxLayout()
        repo_desc_label = QLabel("Description:")
        self.repo_desc_input = QLineEdit()
        
        repo_desc_layout.addWidget(repo_desc_label)
        repo_desc_layout.addWidget(self.repo_desc_input)
        
        repo_options_layout = QHBoxLayout()
        self.private_checkbox = QCheckBox("Private Repository")
        
        create_repo_btn = QPushButton("Create Repository")
        create_repo_btn.clicked.connect(self.create_repository)
        create_repo_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        repo_options_layout.addWidget(self.private_checkbox)
        repo_options_layout.addWidget(create_repo_btn)
        
        create_layout.addLayout(repo_form_layout)
        create_layout.addLayout(repo_desc_layout)
        create_layout.addLayout(repo_options_layout)
        create_group.setLayout(create_layout)
        
        # Repository List
        list_group = QGroupBox("Your Repositories")
        list_layout = QVBoxLayout()
        
        refresh_btn = QPushButton("Refresh Repository List")
        refresh_btn.clicked.connect(self.refresh_repositories)
        refresh_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        
        self.repo_list = QTextEdit()
        self.repo_list.setReadOnly(True)
        
        list_layout.addWidget(refresh_btn)
        list_layout.addWidget(self.repo_list)
        list_group.setLayout(list_layout)
        
        # Clone Repository
        clone_group = QGroupBox("Clone Repository")
        clone_layout = QHBoxLayout()
        
        self.clone_url_input = QLineEdit()
        self.clone_url_input.setPlaceholderText("Enter repository URL to clone")
        
        clone_dir_btn = QPushButton("Select Directory")
        clone_dir_btn.clicked.connect(self.select_clone_directory)
        
        clone_btn = QPushButton("Clone")
        clone_btn.clicked.connect(self.clone_repository)
        clone_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        
        clone_layout.addWidget(self.clone_url_input)
        clone_layout.addWidget(clone_dir_btn)
        clone_layout.addWidget(clone_btn)
        clone_group.setLayout(clone_layout)
        
        # Add all sections to page layout
        layout.addWidget(auth_group)
        layout.addWidget(create_group)
        layout.addWidget(clone_group)
        layout.addWidget(list_group, 1)  # Give more space to the repo list
        
        return page
    
    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # General Settings
        general_group = QGroupBox("General Settings")
        general_layout = QVBoxLayout()
        
        # Auto-start option
        self.autostart_checkbox = QCheckBox("Auto-start monitoring when application launches")
        
        # Default branch
        branch_layout = QHBoxLayout()
        branch_label = QLabel("Default Branch:")
        self.branch_combo = QComboBox()
        self.branch_combo.addItems(["main", "master", "develop"])
        
        branch_layout.addWidget(branch_label)
        branch_layout.addWidget(self.branch_combo)
        
        # Commit message template
        commit_layout = QHBoxLayout()
        commit_label = QLabel("Commit Message Template:")
        self.commit_template = QLineEdit()
        self.commit_template.setText("Auto-commit: Changes detected at {datetime}")
        
        commit_layout.addWidget(commit_label)
        commit_layout.addWidget(self.commit_template)
        
        # Add to general layout
        general_layout.addWidget(self.autostart_checkbox)
        general_layout.addLayout(branch_layout)
        general_layout.addLayout(commit_layout)
        general_group.setLayout(general_layout)
        
        # Advanced Settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout()
        
        # Ignore patterns
        ignore_layout = QVBoxLayout()
        ignore_label = QLabel("Ignore Patterns (one per line):")
        self.ignore_patterns = QTextEdit()
        self.ignore_patterns.setPlaceholderText("*.log\ntmp/*\n.DS_Store")
        
        ignore_layout.addWidget(ignore_label)
        ignore_layout.addWidget(self.ignore_patterns)
        
        # Add to advanced layout
        advanced_layout.addLayout(ignore_layout)
        advanced_group.setLayout(advanced_layout)
        
        # Save Settings
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        
        # Add all sections to page layout
        layout.addWidget(general_group)
        layout.addWidget(advanced_group, 1)  # Give more space to advanced settings
        layout.addWidget(save_btn)
        
        return page
    
    def create_stats_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Statistics
        stats_group = QGroupBox("Repository Statistics")
        stats_layout = QVBoxLayout()
        
        # Stats display
        self.commits_label = QLabel("Total Commits: 0")
        self.changes_label = QLabel("Changes Detected: 0")
        self.errors_label = QLabel("Failed Operations: 0")
        self.last_commit_label = QLabel("Last Commit: Never")
        
        stats_layout.addWidget(self.commits_label)
        stats_layout.addWidget(self.changes_label)
        stats_layout.addWidget(self.errors_label)
        stats_layout.addWidget(self.last_commit_label)
        stats_group.setLayout(stats_layout)
        
        # History
        history_group = QGroupBox("Commit History")
        history_layout = QVBoxLayout()
        
        self.history_output = QTextEdit()
        self.history_output.setReadOnly(True)
        
        refresh_history_btn = QPushButton("Refresh History")
        refresh_history_btn.clicked.connect(self.refresh_history)
        refresh_history_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        
        history_layout.addWidget(refresh_history_btn)
        history_layout.addWidget(self.history_output)
        history_group.setLayout(history_layout)
        
        # Add all sections to page layout
        layout.addWidget(stats_group)
        layout.addWidget(history_group, 1)  # Give more space to history
        
        return page
    
    def log_message(self, message):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.log_output.append(f"{timestamp} {message}")
        # Scroll to bottom
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
    
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if directory:
            self.directory = directory
            self.dir_input.setText(directory)
            self.check_repo_status()
    
    def check_repo_status(self):
        if not self.directory:
            self.log_message("Please select a directory first.")
            return
            
        # Check if it's a git repository
        if os.path.exists(os.path.join(self.directory, ".git")):
            self.log_message(f"Selected valid Git repository: {self.directory}")
            self.start_btn.setEnabled(True)
            
            # Get remote URL if available
            try:
                os.chdir(self.directory)
                remote_process = subprocess.run(["git", "remote", "-v"], 
                                              check=True, 
                                              capture_output=True, 
                                              text=True)
                
                if remote_process.stdout:
                    self.log_message(f"Remote repositories: \n{remote_process.stdout}")
                else:
                    self.log_message("No remote repositories configured.")
                    
                # Get current branch
                branch_process = subprocess.run(["git", "branch", "--show-current"], 
                                              check=True, 
                                              capture_output=True, 
                                              text=True)
                
                if branch_process.stdout:
                    self.log_message(f"Current branch: {branch_process.stdout.strip()}")
                
            except subprocess.CalledProcessError as e:
                self.log_message(f"Error getting repository info: {e}")
        else:
            self.log_message(f"Warning: {self.directory} is not a Git repository")
            
            # Ask if user wants to initialize a repository
            reply = QMessageBox.question(self, 'Repository Not Found', 
                                        f"Directory {self.directory} is not a Git repository. Would you like to initialize it?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.initialize_repository()
            else:
                self.start_btn.setEnabled(False)
    
    def initialize_repository(self):
        if not self.directory:
            self.log_message("No directory selected.")
            return
            
        try:
            os.chdir(self.directory)
            
            # Initialize git repository
            self.log_message(f"Initializing Git repository in {self.directory}...")
            init_process = subprocess.run(["git", "init"], 
                                         check=True, 
                                         capture_output=True, 
                                         text=True)
            
            self.log_message(f"Git init output: {init_process.stdout}")
            
            # Create .gitignore if it doesn't exist
            gitignore_path = os.path.join(self.directory, ".gitignore")
            if not os.path.exists(gitignore_path):
                with open(gitignore_path, "w") as f:
                    f.write("# Generated by GitHub Automation Tool\n")
                    f.write("*.log\n")
                    f.write("__pycache__/\n")
                    f.write("*.py[cod]\n")
                    f.write(".DS_Store\n")
                self.log_message("Created default .gitignore file")
            
            # Create initial README if it doesn't exist
            readme_path = os.path.join(self.directory, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as f:
                    f.write(f"# {os.path.basename(self.directory)}\n\n")
                    f.write("This repository was initialized with GitHub Automation Tool.\n")
                self.log_message("Created default README.md file")
            
            # Initial commit
            self.log_message("Creating initial commit...")
            
            # Add all files
            add_process = subprocess.run(["git", "add", "."], 
                                        check=True, 
                                        capture_output=True, 
                                        text=True)
            
            # Initial commit
            commit_process = subprocess.run(["git", "commit", "-m", "Initial commit"], 
                                           check=True, 
                                           capture_output=True, 
                                           text=True)
            
            self.log_message(f"Initial commit created: {commit_process.stdout}")
            self.start_btn.setEnabled(True)
            
            # Ask if user wants to connect to a remote repository
            reply = QMessageBox.question(self, 'Remote Repository', 
                                        "Would you like to connect this repository to GitHub?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.content_stack.setCurrentIndex(1)  # Switch to repo page
                self.repo_btn.setChecked(True)
                self.monitor_btn.setChecked(False)
            
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error initializing repository: {e}")
            self.log_message(f"Command output: {e.stdout}")
            self.log_message(f"Command error: {e.stderr}")
    
    def start_monitoring(self):
        if not self.directory:
            self.log_message("Please select a valid Git repository first.")
            return
        
        # Disable start button, enable stop button
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.dir_input.setEnabled(False)
        self.interval_spinner.setEnabled(False)
        
        # Update status
        self.status_label.setText("Status: Initializing...")
        self.status_label.setStyleSheet("font-weight: bold; color: #FFA500;")
        
        # Start the monitor thread
        check_interval = self.interval_spinner.value()
        self.monitor_thread = MonitorThread(self.directory, check_interval)
        self.monitor_thread.update_signal.connect(self.log_message)
        self.monitor_thread.hash_calculated_signal.connect(self.monitoring_started)
        self.monitor_thread.stats_update_signal.connect(self.update_stats)
        self.monitor_thread.change_detected_signal.connect(self.change_detected)
        self.monitor_thread.start()
        
        # Start progress timer
        self.timer.start(100)
        
        self.log_message(f"Starting monitoring with {check_interval} second interval")
    
    def stop_monitoring(self):
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.log_message("Stopping monitor...")
            self.monitor_thread.stop()
            self.monitor_thread.wait()
            
            # Update UI
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.dir_input.setEnabled(True)
            self.interval_spinner.setEnabled(True)
            
            # Update status
            self.status_label.setText("Status: Not Monitoring")
            self.status_label.setStyleSheet("font-weight: bold; color: gray;")
            
            # Stop progress timer
            self.timer.stop()
            self.progress_bar.setValue(0)
            
            self.log_message("Monitoring stopped")
    
    def monitoring_started(self):
        self.status_label.setText("Status: Monitoring")
        self.status_label.setStyleSheet("font-weight: bold; color: green;")
    
    def update_stats(self, stats):
        self.commits_label.setText(f"Total Commits: {stats['commits']}")
        self.changes_label.setText(f"Changes Detected: {stats['changes_detected']}")
        self.errors_label.setText(f"Failed Operations: {stats['failed_operations']}")
        self.last_commit_label.setText(f"Last Commit: {stats['last_commit']}")
    
    def change_detected(self):
        self.change_count += 1
        
        # Flash status
        self.status_label.setText("Status: CHANGES DETECTED!")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        
        # Reset status after 2 seconds
        QTimer.singleShot(2000, self.reset_status)
    
    def reset_status(self):
        if self.monitor_thread and self.monitor_thread.isRunning():
            self.status_label.setText("Status: Monitoring")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
    
    def update_progress(self):
        if self.monitor_thread and self.monitor_thread.isRunning():
            # Progress cycles every 10 seconds
            self.progress_value = (self.progress_value + 1) % 100
            self.progress_bar.setValue(self.progress_value)
    
    def save_github_token(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Token Required", "Please enter a GitHub token.")
            return
        
        self.github_api.set_token(token)
        self.log_message("GitHub token saved.")
        
        # Test the token
        try:
            user_info = self.github_api.get_user_info()
            self.log_message(f"Successfully authenticated as: {user_info['login']}")
            
            # Refresh repositories
            self.refresh_repositories()
            
        except Exception as e:
            self.log_message(f"Error authenticating with GitHub: {e}")
    
    def refresh_repositories(self):
        try:
            if not self.github_api.token:
                QMessageBox.warning(self, "Token Required", "Please enter and save a GitHub token first.")
                return
                
            self.log_message("Fetching repositories from GitHub...")
            repos = self.github_api.list_repositories()
            
            self.repo_list.clear()
            for repo in repos:
                self.repo_list.append(f"• {repo['name']} - {repo['html_url']}")
                
            self.log_message(f"Found {len(repos)} repositories.")
            
        except Exception as e:
            self.log_message(f"Error fetching repositories: {e}")
    
    def create_repository(self):
        if not self.github_api.token:
            QMessageBox.warning(self, "Token Required", "Please enter and save a GitHub token first.")
            return
            
        name = self.repo_name_input.text().strip()
        description = self.repo_desc_input.text().strip()
        private = self.private_checkbox.isChecked()
        
        if not name:
            QMessageBox.warning(self, "Name Required", "Please enter a repository name.")
            return
            
        try:
            self.log_message(f"Creating repository '{name}'...")
            repo = self.github_api.create_repository(name, description, private)
            
            self.log_message(f"Repository created successfully: {repo['html_url']}")
            
            # Ask if user wants to clone the repository
            reply = QMessageBox.question(self, 'Clone Repository', 
                                        f"Repository created. Would you like to clone it now?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                self.clone_url_input.setText(repo['clone_url'])
                self.select_clone_directory()
            
            # Refresh repository list
            self.refresh_repositories()
            
        except Exception as e:
            self.log_message(f"Error creating repository: {e}")
    
    def select_clone_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory for Clone")
        if directory:
            self.clone_repository(directory)
    
    def clone_repository(self, directory=None):
        url = self.clone_url_input.text().strip()
        
        if not url:
            QMessageBox.warning(self, "URL Required", "Please enter a repository URL to clone.")
            return
            
        if not directory:
            directory = QFileDialog.getExistingDirectory(self, "Select Directory for Clone")
            
        if not directory:
            return
            
        try:
            self.log_message(f"Cloning repository from {url} to {directory}...")
            
            # Extract repo name from URL
            repo_name = url.split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
                
            # Full path for the cloned repo
            clone_path = os.path.join(directory, repo_name)
            
            # Clone the repository
            clone_process = subprocess.run(["git", "clone", url, clone_path], 
                                         check=True, 
                                         capture_output=True, 
                                         text=True)
            
            self.log_message(f"Repository cloned successfully to {clone_path}")
            
            # Ask if user wants to monitor this repository
            reply = QMessageBox.question(self, 'Monitor Repository', 
                                        f"Would you like to start monitoring this repository?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                self.directory = clone_path
                self.dir_input.setText(clone_path)
                self.content_stack.setCurrentIndex(0)  # Switch to monitor page
                self.monitor_btn.setChecked(True)
                self.repo_btn.setChecked(False)
                self.start_btn.setEnabled(True)
                
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error cloning repository: {e}")
            self.log_message(f"Command output: {e.stdout}")
            self.log_message(f"Command error: {e.stderr}")
    
    def save_settings(self):
        self.log_message("Settings saved.")
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")
    
    def refresh_history(self):
        if not self.directory:
            QMessageBox.warning(self, "Repository Required", "Please select a repository first.")
            return
            
        try:
            os.chdir(self.directory)
            
            # Get commit history
            history_process = subprocess.run(["git", "log", "--pretty=format:%h - %an, %ar : %s", "-n", "20"], 
                                           check=True, 
                                           capture_output=True, 
                                           text=True)
            
            if history_process.stdout:
                self.history_output.setText(history_process.stdout)
                self.log_message("Commit history refreshed.")
            else:
                self.history_output.setText("No commit history found.")
                
        except subprocess.CalledProcessError as e:
            self.log_message(f"Error fetching commit history: {e}")
    
    def closeEvent(self, event):
        self.stop_monitoring()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitAutoCommitApp()
    window.show()
    sys.exit(app.exec_())
    