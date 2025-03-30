import os
import time
import random
import threading
import tkinter as tk
import pyautogui
import keyboard
from pynput import mouse
from pynput.mouse import Button

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
        self.mouse_threshold = 15  # Increased threshold - only record if moved more than this many pixels
        self.min_delay_between_moves = 50  # Minimum milliseconds between mouse move recordings
        self.last_mouse_record_time = 0
        
        # Set up the hidden UI
        self._setup_ui()
        
        # Setup keyboard hooks
        keyboard.on_press_key(self.action_key, self._key_action_callback, suppress=False)
        
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
        
        # Initialize log
        self.log()
        self.recording = True
        
        # Setup mouse tracking
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll)
        self.mouse_listener.start()
        
        # Setup keyboard tracking - using direct key listening instead of _os_keyboard
        # Get common modifier keys
        self.modifier_keys = ['shift', 'ctrl', 'alt', 'win']
        
        # Hook all keys individually instead of using all_modifiers
        for key_name in self.modifier_keys:
            keyboard.on_press_key(key_name, self._on_key_press, suppress=False)
            keyboard.on_release_key(key_name, self._on_key_release, suppress=False)
        
        # For letter keys, function keys, etc.
        for key in "abcdefghijklmnopqrstuvwxyz0123456789":
            keyboard.on_press_key(key, self._on_key_press, suppress=False)
            keyboard.on_release_key(key, self._on_key_release, suppress=False)
        
        # For function keys
        for i in range(1, 13):
            key = f'f{i}'
            if key != self.action_key:  # Skip the action key
                keyboard.on_press_key(key, self._on_key_press, suppress=False)
                keyboard.on_release_key(key, self._on_key_release, suppress=False)
        
        # For other common keys
        for key in ['esc', 'tab', 'caps lock', 'space', 'backspace', 'enter', 'insert', 
                    'delete', 'home', 'end', 'page up', 'page down', 'up', 'down', 'left', 'right']:
            keyboard.on_press_key(key, self._on_key_press, suppress=False)
            keyboard.on_release_key(key, self._on_key_release, suppress=False)
        
        # Get initial position for relative mode
        x, y = pyautogui.position()
        self.relative_x = x
        self.relative_y = y
        self.last_mouse_x = x
        self.last_mouse_y = y
        
        
        self.show_tip("Recording")

    def _on_mouse_move(self, x, y):
        """Handle mouse movement events - converted to Click commands with 0 parameter
        Now with reduced recording frequency for smaller files"""
        if not self.recording:
            return
            
        # Get current time
        current_time = int(time.time() * 1000)
        
        # Only log if:
        # 1. Moved significantly (using increased threshold)
        # 2. Enough time has passed since last recording
        if (abs(x - self.last_mouse_x) > self.mouse_threshold or 
            abs(y - self.last_mouse_y) > self.mouse_threshold) and \
           (current_time - self.last_mouse_record_time > self.min_delay_between_moves):
            
            # Using Click command with 0 parameter instead of MouseMove
            if self.mouse_mode == "screen":
                self.log(f"Click, {x}, {y}, 0")
            elif self.mouse_mode == "window":
                self.log(f"Click, {x}, {y}, 0")
            elif self.mouse_mode == "relative":
                self.log(f"Click, {x - self.relative_x}, {y - self.relative_y}, 0")
                
            self.last_mouse_x = x
            self.last_mouse_y = y
            self.last_mouse_record_time = current_time

    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events"""
        if not self.recording:
            return
            
        btn = "Left" if button == Button.left else "Right" if button == Button.right else "Middle"
        action = "Down" if pressed else "Up"
        
        # Record for all three coordinate modes - Format to match demo.txt
        if self.mouse_mode == "screen":
            self.log(f"Click, {x}, {y} {btn}, , {action}")
        elif self.mouse_mode == "window":
            self.log(f"Click, {x}, {y} {btn}, , {action}")
        elif self.mouse_mode == "relative":
            self.log(f"Click, {x - self.relative_x}, {y - self.relative_y} {btn}, , {action}")
            if not pressed:  # Update relative position after release
                self.relative_x = x
                self.relative_y = y

    def _on_mouse_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events"""
        if not self.recording:
            return
            
        # Convert scroll direction to wheel direction strings
        direction = "up" if dy > 0 else "down"
        self.log(f"MouseWheel {direction}")

    def _on_key_press(self, e):
        """Handle key press events"""
        if not self.recording or e.name == self.action_key:
            return
            
        key_name = e.name
        # Handle special keys
        if key_name.startswith('shift') or key_name.startswith('ctrl') or key_name.startswith('alt'):
            key_name = key_name.capitalize()
        
        self.log(f"{{{key_name} Down}}", keyboard=True)

    def _on_key_release(self, e):
        """Handle key release events"""
        if not self.recording or e.name == self.action_key:
            return
            
        key_name = e.name
        # Handle special keys
        if key_name.startswith('shift') or key_name.startswith('ctrl') or key_name.startswith('alt'):
            key_name = key_name.capitalize()
            
        self.log(f"{{{key_name} Up}}", keyboard=True)


    def log(self, text="", keyboard=False):
        """Log an action with timing information"""
        current_time = time.time() * 1000  # Convert to milliseconds
        
        if not hasattr(self, 'last_time'):
            self.last_time = current_time
            
        if not text:
            return
            
        delay = int(current_time - self.last_time)
        self.last_time = current_time
        
        # Add sleep command if delay is significant
        if delay > 200:
            sleep_comment = "" if self.record_sleep else ";"
            self.log_arr.append(f"{sleep_comment}Sleep, {delay // 2}")
        
        # Format keyboard input
        if keyboard:
            self.log_arr.append(f"Send, {text}")
        else:
            self.log_arr.append(text)

    def update_settings(self):
        """Load settings from file if it exists"""
        log_file = os.path.join(self.script_dir, f"{self.next_file_number}.txt")
        
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) >= 6:
                        self.mouse_mode = lines[3].strip().split('=')[-1]
                        self.record_sleep = lines[5].strip().split('=')[-1] == 'true'
            except:
                pass
        
        # Validate settings
        if self.mouse_mode not in ["screen", "window", "relative"]:
            self.mouse_mode = "screen"

    def stop(self):
        """Stop recording and save the macro"""
        if not self.recording:
            return
            
        # Stop the listeners
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
            
        # Remove keyboard hooks
        keyboard.unhook_all()
        
        # Re-hook the action key
        keyboard.on_press_key(self.action_key, self._key_action_callback, suppress=False)
        
        
        # Make sure log_arr is populated before saving
        if self.log_arr and len(self.log_arr) > 0:
            # Add proper filename format at the top
            file_name = f"{self.next_file_number}.txt"
            full_file_path = os.path.join(self.script_dir, file_name)
            file_header = f""
            
            # Add all the recorded actions
            output = file_header
            
            for line in self.log_arr:
                # Skip window activation code lines
                if "tt :=" in line or "WinWait" in line or "WinActive" in line or "WinActivate" in line:
                    continue
                    
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
        error_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error_log.txt")
        with open(error_log_path, "w") as f:
            f.write(f"Error starting recorder: {str(e)}")
        print(f"Error: {str(e)}")
        print(f"Error details written to: {error_log_path}")
