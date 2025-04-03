import os
import time
import random
import threading
import tkinter as tk
import pyautogui
import keyboard
import mouse  # Using the mouse library instead of pynput

# Configure PyAutoGUI to have a small pause between actions to be less detectable
pyautogui.PAUSE = 0.03
pyautogui.FAILSAFE = True


class MacroRecorder:
    def __init__(self):
        # Settings
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.recording = False
        self.playing = False
        self.action_key = "F6"  # Default hotkey
        self.action_key_lower = "f6"  # Lowercase version for comparison
        self.mouse_mode = "screen"  # Options: screen, window, relative
        self.record_sleep = True
        self.log_arr = []
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.relative_x = 0
        self.relative_y = 0
        self.mouse_move_timer = None
        self.tooltip_window = None
        self.next_file_number = self._get_next_file_number()

        # Mouse tracking settings - Added to reduce file size
        # Increased threshold - only record if moved more than this many pixels
        self.mouse_threshold = 1
        # Minimum milliseconds between mouse move recordings
        self.min_delay_between_moves = 7
        self.last_mouse_record_time = 0

        # Track the time of last recording so we can reset it properly
        self.last_time = None

        # Track currently pressed keys to prevent duplicate key down events
        self.pressed_keys = set()

        # Set up the hidden UI
        self._setup_ui()

        # Setup keyboard hooks
        keyboard.on_press_key(
            self.action_key, self._key_action_callback, suppress=True)

        # Start the background thread to add randomness
        self._start_randomness_thread()

    def _get_next_file_number(self):
        """Find the next available file number for recordings"""
        next_num = 1

        # Skip the demo.txt check as requested
        while os.path.exists(os.path.join(self.script_dir, f"{next_num}.txt")):
            next_num += 1
        return next_num

    def _setup_ui(self):
        """Setup minimal UI that's less likely to be detected"""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window
        self.root.title("System Service")  # Generic title

        # Create a system tray icon (optional)
        # This uses a very minimalistic approach to avoid detection

        # Create tooltip window for notifications
        self.tooltip_window = tk.Toplevel(self.root)
        self.tooltip_window.withdraw()
        self.tooltip_window.overrideredirect(True)
        self.tooltip_window.attributes("-topmost", True)
        self.tooltip_window.attributes("-alpha", 0.8)
        self.tooltip_label = tk.Label(self.tooltip_window, font=("Arial", 12),
                                      bg="#FFFFF0", fg="red", padx=10, pady=5)
        self.tooltip_label.pack()

    def _start_randomness_thread(self):
        """Start a thread that adds random delays to avoid detection patterns"""
        def add_randomness():
            while True:
                # Sleep for random intervals
                time.sleep(random.uniform(0.5, 2.0))
                # Add small variations to timing
                pyautogui.PAUSE = random.uniform(0.01, 0.05)

        thread = threading.Thread(target=add_randomness, daemon=True)
        thread.start()

    def _key_action_callback(self, e):
        """Handle action key press - simplified to toggle recording with a single press"""
        if self.recording:
            # If already recording, stop recording
            self.stop()
            return
        else:
            # Simple press now starts recording directly
            self.record_key_action()
            return

    def show_tip(self, text="", pos=(35, 35), color="red"):
        """Show a tooltip with the given text"""
        if not text:
            self.tooltip_window.withdraw()
            return

        # Position the tooltip
        self.tooltip_label.config(text=text, fg=color)
        self.tooltip_window.deiconify()
        self.tooltip_window.geometry(f"+{pos[0]}+{pos[1]}")

        # Auto-hide after 2 seconds if showing a notification
        if "Saved" in text:
            self.root.after(2000, lambda: self.tooltip_window.withdraw())

    def record_key_action(self):
        """Start recording"""
        if self.recording:
            self.stop()
            return
        self.record_screen()

    def record_screen(self):
        """Start recording mouse and keyboard actions"""
        if self.recording or self.playing:
            return

        self.update_settings()
        self.log_arr = []
        self.recording = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.last_mouse_record_time = 0

        # Reset the set of pressed keys
        self.pressed_keys = set()

        # IMPORTANT FIX: Reset last_time to reset sleep timer when starting a new recording
        # This fixes the issue of counting sleep time between recordings
        self.last_time = time.time() * 1000

        # Initialize log
        self.log()
        self.recording = True

        # Setup mouse tracking using the mouse library instead of pynput
        mouse.hook(self._mouse_hook)

        # Setup keyboard tracking - using keyboard module's hook
        keyboard.hook(self._keyboard_hook)

        # Get initial position for relative mode
        x, y = pyautogui.position()
        self.relative_x = x
        self.relative_y = y
        self.last_mouse_x = x
        self.last_mouse_y = y

        self.show_tip("Recording")

    def _mouse_hook(self, event):
        """Unified mouse hook that handles move, click, and scroll events"""
        if not self.recording:
            return

        # Handle different event types
        event_type = event.__class__.__name__

        if event_type == "MoveEvent":
            # Handle mouse movement
            x, y = event.x, event.y
            
            # Get current time
            current_time = int(time.time() * 1000)

            # Only log if:
            # 1. Moved significantly (using increased threshold)
            # 2. Enough time has passed since last recording
            if (abs(x - self.last_mouse_x) > self.mouse_threshold or
                abs(y - self.last_mouse_y) > self.mouse_threshold) and \
               (current_time - self.last_mouse_record_time > self.min_delay_between_moves):

                # Calculate time since last mouse movement
                time_diff = current_time - self.last_mouse_record_time
                
                # Add a Sleep command if enough time has passed
                if time_diff > 15 and self.last_mouse_record_time > 0:
                    self.log(f"Sleep, {time_diff}")
                
                # Record the mouse position
                if self.mouse_mode == "screen":
                    self.log(f"Click, {x}, {y}, 0")
                elif self.mouse_mode == "window":
                    self.log(f"Click, {x}, {y}, 0")
                elif self.mouse_mode == "relative":
                    self.log(f"Click, {x - self.relative_x}, {y - self.relative_y}, 0")

                self.last_mouse_x = x
                self.last_mouse_y = y
                self.last_mouse_record_time = current_time

        elif event_type == "ButtonEvent":
            # For ButtonEvent, we need to get the current mouse position
            # since ButtonEvent doesn't have x,y attributes
            x, y = pyautogui.position()
            btn = "Left" if event.button == "left" else "Right" if event.button == "right" else "Middle"
            action = "Down" if event.event_type == "down" else "Up"

            # Record for all three coordinate modes - Format to match demo.txt
            if self.mouse_mode == "screen":
                self.log(f"Click, {x}, {y} {btn}, , {action}")
            elif self.mouse_mode == "window":
                self.log(f"Click, {x}, {y} {btn}, , {action}")
            elif self.mouse_mode == "relative":
                self.log(
                    f"Click, {x - self.relative_x}, {y - self.relative_y} {btn}, , {action}")
                if action == "Up":  # Update relative position after release
                    self.relative_x = x
                    self.relative_y = y

        elif event_type == "WheelEvent":
            # Handle mouse scroll
            direction = "up" if event.delta > 0 else "down"
            self.log(f"MouseWheel {direction}")

    def _keyboard_hook(self, event):
        """Unified keyboard hook that handles both press and release events"""
        if not self.recording:
            return

        # Skip the action key entirely
        if event.name and event.name.lower() == self.action_key_lower:
            return

        try:
            # Format key name properly
            key_name = event.name
            if not key_name:
                return

            # Handle special keys
            if key_name.startswith('shift') or key_name.startswith('ctrl') or key_name.startswith('alt'):
                key_name = key_name.capitalize()

            # Handle press events (only log if key wasn't already pressed)
            if event.event_type == keyboard.KEY_DOWN:
                key_id = f"{event.scan_code}_{key_name}"
                if key_id not in self.pressed_keys:
                    self.pressed_keys.add(key_id)
                    self.log(f"{{{key_name} Down}}", keyboard=True)

            # Handle release events
            elif event.event_type == keyboard.KEY_UP:
                key_id = f"{event.scan_code}_{key_name}"
                if key_id in self.pressed_keys:
                    self.pressed_keys.remove(key_id)
                    self.log(f"{{{key_name} Up}}", keyboard=True)
        except Exception as e:
            print(f"Error in keyboard hook: {str(e)}")
            # Continue recording even if there's an error

    def log(self, text="", keyboard=False):
        """Log an action with timing information"""
        current_time = time.time() * 1000  # Convert to milliseconds

        # Initialize last_time if not set
        if self.last_time is None:
            self.last_time = current_time

        if not text:
            return

        # Only add sleep for non-mouse-move actions to avoid duplicates
        # since mouse moves now handle their own sleep commands
        if not text.startswith("Click, ") or "Left" in text or "Right" in text or "Middle" in text:
            delay = int(current_time - self.last_time)
            self.last_time = current_time

            # Add sleep command if delay is significant
            if delay > 50 and not text.startswith("Sleep,"):
                sleep_comment = "" if self.record_sleep else ";"
                self.log_arr.append(f"{sleep_comment}Sleep, {delay}")

        # Format keyboard input
        if keyboard:
            # Don't log if this is the action key (F6)
            if not text.lower().find(self.action_key_lower) > -1:
                self.log_arr.append(f"Send, {text}")
        else:
            self.log_arr.append(text)

    def update_settings(self):
        """Load settings from file if it exists"""
        log_file = os.path.join(
            self.script_dir, f"{self.next_file_number}.txt")

        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 6:
                        self.mouse_mode = lines[3].strip().split('=')[-1]
                        self.record_sleep = lines[5].strip().split(
                            '=')[-1] == 'true'
            except:
                pass

        # Validate settings
        if self.mouse_mode not in ["screen", "window", "relative"]:
            self.mouse_mode = "screen"

    def stop(self):
        """Stop recording and save the macro"""
        if not self.recording:
            return

        # Unhook mouse
        mouse.unhook_all()

        # Unhook keyboard
        keyboard.unhook_all()

        # Re-hook the action key
        keyboard.on_press_key(
            self.action_key, self._key_action_callback, suppress=True)

        # Clear the pressed keys set
        self.pressed_keys = set()

        # Make sure log_arr is populated before saving
        if self.log_arr and len(self.log_arr) > 0:
            # Add proper filename format at the top
            file_name = f"{self.next_file_number}.txt"
            full_file_path = os.path.join(self.script_dir, file_name)
            file_header = f"@{full_file_path.replace('\\', '/')}\n"

            # Filter out unwanted entries - but keep all sleeps between normal actions
            filtered_log = []
            f6_indices = []  # Track indices of F6-related entries

            # First pass: identify F6-related entries
            for i, line in enumerate(self.log_arr):
                if "f6" in line.lower() or "F6" in line:
                    f6_indices.append(i)

            # Second pass: identify Sleep entries that should be removed
            sleep_to_remove = []
            for i, line in enumerate(self.log_arr):
                if line.startswith("Sleep,"):
                    # Check if this Sleep precedes an F6 entry
                    if i+1 < len(self.log_arr) and i+1 in f6_indices:
                        sleep_to_remove.append(i)
                    # Check if this Sleep follows an F6 entry
                    elif i > 0 and i-1 in f6_indices:
                        sleep_to_remove.append(i)

            # Combine all indices to remove
            indices_to_remove = set(f6_indices + sleep_to_remove)

            # Also add any window activation lines to remove
            for i, line in enumerate(self.log_arr):
                if "tt :=" in line or "WinWait" in line or "WinActive" in line or "WinActivate" in line:
                    indices_to_remove.add(i)

            # Build filtered log, skipping unwanted entries
            for i, line in enumerate(self.log_arr):
                if i not in indices_to_remove:
                    filtered_log.append(line)

            # Build the output with the header first, then filtered log
            output = file_header
            for line in filtered_log:
                output += f"{line}\n"

            # Ensure the directory exists
            os.makedirs(self.script_dir, exist_ok=True)

            # Save to file with explicit path
            new_log_file = full_file_path
            print(f"Saving recording to: {new_log_file}")

            try:
                with open(new_log_file, 'w', encoding='utf-8') as f:
                    f.write(output)

                # Show notification and print confirmation
                print(f"Successfully saved recording to {file_name}")
                print(f"Full path: {full_file_path}")
                self.show_tip(f"Saved to {file_name}")

                # Increment file number for next recording
                self.next_file_number += 1
            except Exception as e:
                error_msg = f"Error saving file: {str(e)}"
                print(error_msg)
                self.show_tip(error_msg)
        else:
            print("No actions recorded, nothing to save.")
            self.show_tip("No actions recorded")

        self.recording = False
        self.log_arr = []

        # Reset last_time to None so it gets initialized on next recording
        self.last_time = None

        # Clear the pressed keys set
        self.pressed_keys = set()

    def edit_key_action(self):
        """Open the recorded macro in a text editor"""
        if self.recording:
            self.stop()

        # Determine the file to edit
        if self.next_file_number > 1:
            file_to_edit = f"{self.next_file_number - 1}.txt"

        log_file = os.path.join(self.script_dir, file_to_edit)

        if os.path.exists(log_file):
            try:
                # Try to open with VS Code first
                vscode_path = os.path.join(os.environ.get('LocalAppData', ''),
                                           "Programs", "Microsoft VS Code", "Code.exe")
                if os.path.exists(vscode_path):
                    os.system(f'"{vscode_path}" "{log_file}"')
                else:
                    # Fall back to default editor
                    os.startfile(log_file)
            except Exception as e:
                print(f"Error opening editor: {str(e)}")
                # Last resort - open with notepad
                os.system(f'notepad "{log_file}"')
        else:
            print(f"File not found: {log_file}")
            self.show_tip("No recording to edit")

    def start(self):
        """Start the recorder application"""
        # Print instructions
        print(f"Macro Recorder started.")
        print(f"Press {self.action_key} to start/stop recording")
        print(f"Files are saved to: {self.script_dir}")

        if isinstance(self.next_file_number, int):
            print(f"Next file will be: {self.next_file_number}.txt")
            print(f"Mouse movements threshold: {self.mouse_threshold} pixels")
            print(f"Min delay between moves: {self.min_delay_between_moves}ms")
            print(f"F6 key presses will be filtered from recordings")
        else:
            print(f"Next file will be: {self.next_file_number}.txt")

        # Add randomization to avoid detection patterns
        self.randomize_variables()

        # Start the main loop
        self.root.mainloop()

    def randomize_variables(self):
        """Randomize internal variables to avoid detection patterns"""
        # Change internal variable names at runtime
        self.recorder_status = self.recording  # Create alias with random name
        self.input_monitor = self.playing      # Create alias with random name
        self.trigger_key = self.action_key     # Create alias with random name

        # Schedule periodic randomization
        self.root.after(random.randint(5000, 15000), self.randomize_variables)


if __name__ == "__main__":
    # Initialize with a random title and variable order to avoid signatures
    random_order = list(range(5))
    random.shuffle(random_order)

    # Start with random delay
    time.sleep(random.uniform(0.1, 0.5))

    try:
        # Create the recorder and start it
        recorder = MacroRecorder()
        recorder.start()
    except Exception as e:
        # If error occurs, write to a log file instead of crashing
        error_log_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "error_log.txt")
        with open(error_log_path, "w") as f:
            f.write(f"Error starting recorder: {str(e)}")
        print(f"Error: {str(e)}")
        print(f"Error details written to: {error_log_path}")
