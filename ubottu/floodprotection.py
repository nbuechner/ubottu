from collections import defaultdict
from time import time

class FloodProtection:
    def __init__(self):
        self.user_commands = defaultdict(list)  # Stores timestamps of commands for each user
        self.bug_ids = defaultdict(list)  # Stores timestamps of commands for each user
        self.max_commands = 3
        self.time_window = 60  # 60 seconds
        self.time_window_bug = 180  # 3 minutes
        self.max_commands_bugs = 1

    def flood_check(self, user_id):
        """Check if a user can send a command based on flood protection limits."""
        current_time = time()
        if user_id not in self.user_commands:
            self.user_commands[user_id] = [current_time]
            return True  # Allow the command if the user has no recorded commands

        # Remove commands outside the time window
        self.user_commands[user_id] = [timestamp for timestamp in self.user_commands[user_id] if current_time - timestamp < self.time_window]

        if len(self.user_commands[user_id]) < self.max_commands:
            self.user_commands[user_id].append(current_time)
            return True  # Allow the command if under the limit
        
        # Otherwise, do not allow the command
        return False
    def flood_check_bug(self, bug_id):
        """Check if a user can send a command based on flood protection limits."""
        current_time = time()
        if bug_id not in self.bug_ids:
            self.bug_ids[bug_id] = [current_time]
            return True 

        # Remove bugs outside the time window
        self.bug_ids[bug_id] = [timestamp for timestamp in self.bug_ids[bug_id] if current_time - timestamp < self.time_window_bug]

        if len(self.bug_ids[bug_id]) < self.max_commands_bugs:
            self.bug_ids[bug_id].append(current_time)
            return True  # Allow the bug if under the limit
        
        # Otherwise, do not allow the bug
        return False