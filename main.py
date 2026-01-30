import os
import subprocess
import json
import sys
import shutil
import shlex


class MyCMD:
    name = "-"  # default prompt

    def __init__(self):
        self.commands = {
            "help": self.help,
            "echo": self.echo,
            "clear": self.clear,
            "exit": self.exit,
            "cls": self.clear,
            "cat": self.cat,
            "ls": self.ls,
            "cd": self.cd,
            "q": self.exit,
            "name": self.set_name,
            "color": self.color,
            "rm": self.remove,
            "mkdir": self.make_dir,
            "touch": self.touch,
            "history": self.show_history,
            "pwd": self.print_working_directory,
            "cp": self.copy_file,
            "mv": self.move_file,
            "dir": self.ls,
            "init": self.init,
            "whatami": self.whatami,
            "alias": self.alias,
            "settings": self.settings,
            "filesearch": self.filesearch,
            "restart": self.restart,
            "run": self.run_cmd,
            "nano": self.nano,
            "version": self.version,
            "update": self.update,
        }
        self.running = True

        # Load config from data.json (if present)
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "data.json")
            with open(cfg_path, 'r') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

        # Apply settings
        settings = self.config.get("settings", {})
        self.name = settings.get("prompt_name", getattr(self, "name", "-"))
        self.welcome_message = settings.get("welcome_message")
        self.enable_history = settings.get("enable_history", False)
        history_file = settings.get("history_file")
        self.history_file = os.path.expanduser(history_file) if history_file else os.path.expanduser("~/.mycmd_history")
        self.max_history_size = settings.get("max_history_size", 100)
        self.aliases = self.config.get("aliases", {})
        # Load usage hints from config (data.json). If not present, use empty mapping.
        self.usages = self.config.get("usages", {})
        # store version metadata in a non-conflicting attribute name
        self.version_info = self.config.get("version", {})
        

        # Try to enable prompt_toolkit-based live completion & hinting if available and enabled.
        self.ptk_session = None
        try:
            if settings.get("enable_autocomplete", True):
                try:
                    from prompt_toolkit import PromptSession
                    from prompt_toolkit.completion import Completer, Completion
                    from prompt_toolkit.application import get_app
                    from prompt_toolkit.formatted_text import HTML
                    from prompt_toolkit.shortcuts import CompleteStyle

                    class PTCompleter(Completer):
                        def __init__(self, shell):
                            self.shell = shell

                        def get_completions(self, document, complete_event):
                            text_before = document.text_before_cursor
                            parts = text_before.split()
                            word = document.get_word_before_cursor(WORD=True) or ''
                            # first token: commands and aliases
                            if len(parts) <= 1:
                                seen = set()
                                for cmd in list(self.shell.commands.keys()) + list(self.shell.aliases.keys()):
                                    if cmd.startswith(word) and cmd not in seen:
                                        seen.add(cmd)
                                        display = cmd + (' ' if cmd in self.shell.usages else '')
                                        yield Completion(cmd, start_position=-len(word), display=display)
                            else:
                                cmd = parts[0]
                                filename_commands = {"mkdir", "touch", "rm", "cd", "ls", "cp", "mv", "cat"}
                                if cmd in filename_commands:
                                    base = word
                                    if os.path.sep in base:
                                        base_dir, base_name = os.path.split(base)
                                        base_dir = base_dir or '.'
                                    else:
                                        base_dir, base_name = '.', base
                                    try:
                                        for entry in os.listdir(base_dir):
                                            if entry.startswith(base_name):
                                                candidate = os.path.join(base_dir, entry)
                                                display = entry + (os.path.sep if os.path.isdir(candidate) else '')
                                                yield Completion(entry, start_position=-len(base_name), display=display)
                                    except Exception:
                                        return

                    def _pt_toolbar():
                        try:
                            app = get_app()
                            text = app.current_buffer.document.text_before_cursor
                            parts = text.split()
                            if parts:
                                cmd = parts[0]
                                hint = self.usages.get(cmd)
                                if hint:
                                    return HTML(f'<b>Hint:</b> {hint}')
                            return ''
                        except Exception:
                            return ''

                    self.ptk_completer = PTCompleter(self)
                    self.ptk_session = PromptSession()
                    self._pt_toolbar = _pt_toolbar
                    self._pt_complete_style = CompleteStyle.READLINE_LIKE
                except Exception:
                    self.ptk_session = None
            else:
                self.ptk_session = None
        except Exception:
            self.ptk_session = None

        # Inform user about completion availability
        if getattr(self, "ptk_session", None):
            try:
                print("Live completion & hints available (prompt_toolkit). Press Tab for completions; hints show while typing.")
            except Exception:
                pass
        elif getattr(self, "readline", None):
            try:
                print("Tab completion available. Press Tab for suggestions; enter a command without args to see usage hints.")
            except Exception:
                pass

        self.color_code = settings.get("color")
        if self.color_code:
            try:
                self.apply_color(self.color_code)
            except Exception:
                pass

        # Load ASCII art (ascii.txt) and display at top if present
        self.ascii_art = None
        try:
            ascii_path = os.path.join(os.path.dirname(__file__), "ascii.txt")
            if os.path.exists(ascii_path):
                with open(ascii_path, 'r', encoding='utf-8') as f:
                    self.ascii_art = f.read()
            if self.ascii_art:
                print(self.ascii_art)
        except Exception:
            self.ascii_art = None

        # Show welcome message if any
        if self.welcome_message:
            print(self.welcome_message)


    def update(self, args):
        """Update MyCMD shell to the latest version from GitHub."""
        print("Checking for updates...")
        try:
            import requests
            repo_api = "https://api.github.com/repos/Ovilli/own_cmd/releases/latest"
            response = requests.get(repo_api, timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("tag_name", "").lstrip("v")
                current_version = self.version_info.get("number", "0.0.0")
                if latest_version and latest_version != current_version:
                    print(f"New version available: {latest_version} (current: {current_version})")
                    download_url = None
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".zip"):
                            download_url = asset.get("browser_download_url")
                            break
                    if download_url:
                        print(f"Downloading update from {download_url}...")
                        zip_response = requests.get(download_url, timeout=30)
                        if zip_response.status_code == 200:
                            zip_path = os.path.join(os.path.dirname(__file__), "mycmd_update.zip")
                            with open(zip_path, 'wb') as f:
                                f.write(zip_response.content)
                            print(f"Update downloaded to {zip_path}. Please extract and replace existing files manually.")
                        else:
                            print("Failed to download the update package.")
                    else:
                        print("No downloadable assets found for the latest release.")
                else:
                    print("You are already using the latest version.")
            else:
                print("Failed to check for updates.")
        except Exception as e:
            print(f"Update failed: {e}")

    def version(self, args):
        """Display the version of MyCMD shell."""
        print("MyCMD Shell Version " + self.version_info.get("number", "unknown"))

    def nano(self, args):
        """Open a file with a visual editor (uses $EDITOR, falls back to nano/vi/notepad)."""
        if not args:
            print("Usage: nano [filename]")
            return
        editors = []
        env_editor = os.environ.get('EDITOR')
        if env_editor:
            editors.append(env_editor)
        if os.name == 'nt':
            editors += ['notepad', 'nano', 'vim']
        else:
            editors += ['nano', 'vi']

        for editor in editors:
            parts = shlex.split(editor)
            # check existence of executable
            if shutil.which(parts[0]) is None:
                continue
            try:
                subprocess.run(parts + args)
                return
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Editor '{editor}' failed: {e}")
                return

        print(f"nano: no editor found (tried: {', '.join(editors)}). Set EDITOR or install one of these.")

    def run_cmd(self, args):
        """Command wrapper: run the interactive shell. Usage: run"""
        # Ignore args, just start the REPL loop
        self.run()

    def restart(self, args):
        """Restart the shell. Usage: restart [now]"""
        # save current config and state before restarting
        try:
            self.config.setdefault("settings", {})["prompt_name"] = self.name
            self.config["aliases"] = self.aliases
            if getattr(self, "color_code", None):
                self.config.setdefault("settings", {})["color"] = self.color_code
            self.save_config()
        except Exception:
            pass

        # confirm unless user asked for immediate restart or stdin is not a tty
        if "now" not in args and sys.stdin.isatty():
            try:
                ans = input("Restart now? [Y/n] ").strip().lower()
                if ans and ans[0] == "n":
                    print("Restart cancelled.")
                    return
            except Exception:
                pass

        print("Restarting shell...")
        # restore terminal state to avoid broken input in the new process
        try:
            self.restore_terminal()
        except Exception:
            pass
        try:
            self.clear([])
        except Exception:
            pass

        # try to replace current process, fallback to spawn+exit
        python = os.sys.executable
        try:
            self.restore_terminal()
        except Exception:
            pass
        try:
            os.execv(python, [python] + os.sys.argv)
        except Exception:
            try:
                subprocess.Popen([python] + os.sys.argv)
            except Exception as e:
                print(f"Failed to respawn process: {e}")
                return
            os._exit(0)
    
    def filesearch(self, args):
        """Search for files containing a specific string in their names."""
        if not args:
            print("Usage: filesearch [search_string]")
            return
        search_string = args[0]
        for root, dirs, files in os.walk('.'):
            for file in files:
                if search_string in file:
                    print(os.path.join(root, file))

    def settings(self, args):
        """Display or modify shell settings."""
        if not args:
            print("Current settings:")
            print(f" - Shell name: {self.name}")
            return
        if args[0] == "name" and len(args) > 1:
            self.name = " ".join(args[1:])
            print(f"Shell name changed to: {self.name}")
            try:
                self.config.setdefault("settings", {})["prompt_name"] = self.name
                self.save_config()
            except Exception:
                pass
        else:
            print("Unknown setting or incorrect usage.")

    def alias(self, args):
        """Create a simple alias for a command."""
        if len(args) < 2:
            print("Usage: alias [name] [command]")
            return
        alias_name = args[0]
        command = " ".join(args[1:])

        def alias_command(alias_args):
            full_command = command + " " + " ".join(alias_args)
            try:
                result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            except Exception as e:
                print(f"alias: {e}")

        self.commands[alias_name] = alias_command
        self.aliases[alias_name] = command
        try:
            self.config["aliases"] = self.aliases
            self.save_config()
        except Exception:
            pass
        print(f"Alias '{alias_name}' created for command: {command}")

    def whatami(self, args):
        """Display the type of the current shell."""
        print("This is MyCMD, a custom command-line shell implemented in Python.")

    def init(self, args):
        """Initialize a new project directory with a README file."""
        project_name = args[0] if args else "NewProject"
        try:
            os.makedirs(project_name, exist_ok=True)
            readme_path = os.path.join(project_name, "README.md")
            with open(readme_path, 'w') as f:
                f.write(f"# {project_name}\n\nProject initialized.")
            print(f"Initialized empty project in ./{project_name}/")
        except Exception as e:
            print(f"init: {e}")

    def move_file(self, args):
        if len(args) != 2:
            print("Usage: mv [source] [destination]")
            return
        src, dst = args
        try:
            os.rename(src, dst)
        except FileNotFoundError:
            print(f"mv: cannot stat '{src}': No such file or directory")
        except Exception as e:
            print(f"mv: {e}")


    def show_history(self, args):

        if len(args) == 1 and args[0] == "clear":
            try:
                os.remove(self.history_file)
                print("History cleared.")
            except FileNotFoundError:
                print("No history to clear.")
            except Exception as e:
                print(f"Error clearing history: {e}")
            return
        try:
            with open(self.history_file, 'r') as f:
                history = f.readlines()
                for line in history:
                    print(line.strip())
        except FileNotFoundError:
            print("No history found.")


    def copy_file(self, args):
        if len(args) != 2:
            print("Usage: cp [source] [destination]")
            return
        src, dst = args
        try:
            with open(src, 'rb') as fsrc:
                with open(dst, 'wb') as fdst:
                    fdst.write(fsrc.read())
        except FileNotFoundError:
            print(f"cp: cannot stat '{src}': No such file or directory")
        except Exception as e:
            print(f"cp: {e}")

    def touch(self, args):
        for filename in args:
            try:
                with open(filename, 'a'):
                    os.utime(filename, None)
            except Exception as e:
                print(f"touch: cannot touch '{filename}': {e}")

    def print_working_directory(self, args):
        print(os.getcwd())

    def make_dir(self, args):
        for dirname in args:
            try:
                os.makedirs(dirname, exist_ok=True)
            except Exception as e:
                print(f"mkdir: cannot create directory '{dirname}': {e}")

    def remove(self, args):
        for filename in args:
            try:
                os.remove(filename)
            except FileNotFoundError:
                print(f"rm: cannot remove '{filename}': No such file or directory")
            except Exception as e:
                print(f"rm: {filename}: {e}")

    def help(self, args):
        print("Available commands:")
        cmd_desc = self.config.get("commands", {}) if hasattr(self, "config") else {}
        for cmd in sorted(self.commands):
            desc = cmd_desc.get(cmd)
            if desc:
                print(f" - {cmd}: {desc}")
            else:
                print(f" - {cmd}")
        print("You can also run system commands directly.")

    def echo(self, args):
        print(" ".join(args))

    def clear(self, args):
        """Clear the screen robustly and reset terminal state."""
        try:
            if os.name == 'nt':
                os.system('cls')
            else:
                # ANSI clear screen and move cursor home
                print("\033[2J\033[H", end='', flush=True)
            try:
                self.restore_terminal()
            except Exception:
                pass
            # reprint ascii art at top if available
            if getattr(self, 'ascii_art', None):
                try:
                    print(self.ascii_art)
                except Exception:
                    pass
        except Exception:
            pass

    def exit(self, args):
        print(f"Exiting {self.name}...")
        self.running = False

    def color(self, args):
        """Show or set terminal color. Use hex like 'f2' (bgfg) on Windows or mapped ANSI on Unix."""
        if not args:
            if getattr(self, "color_code", None):
                print(f"Current color: {self.color_code}")
                self.apply_color(self.color_code)
            else:
                print("Usage: color [color_code]")
            return
        color_code = args[0]
        self.color_code = color_code
        self.apply_color(color_code)
        try:
            self.config.setdefault("settings", {})["color"] = self.color_code
            self.save_config()
        except Exception:
            pass

    def apply_color(self, code):
        """Apply a color code. On Windows use 'color'; on others map hex to ANSI."""
        if not code:
            return
        # Windows 'color' expects two hex digits (bgfg)
        if os.name == 'nt':
            try:
                os.system(f'color {code}')
            except Exception:
                pass
            return

        def hex_to_fg(d):
            v = int(d, 16)
            if v < 8:
                return str(30 + v)
            return str(90 + (v - 8))

        def hex_to_bg(d):
            v = int(d, 16)
            if v < 8:
                return str(40 + v)
            return str(100 + (v - 8))

        seq = None
        cd = str(code)
        if len(cd) == 2 and all(c in "0123456789abcdefABCDEF" for c in cd):
            bg = hex_to_bg(cd[0])
            fg = hex_to_fg(cd[1])
            seq = f"\033[{fg};{bg}m"
        elif len(cd) == 1 and cd in "0123456789abcdefABCDEF":
            fg = hex_to_fg(cd)
            seq = f"\033[{fg}m"
        elif cd.startswith("\033["):
            seq = cd
        if seq:
            print(seq, end='')

    def save_config(self):
        """Write current config back to data.json."""
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "data.json")
            # ensure settings and aliases exist
            self.config.setdefault("settings", {})["color"] = self.color_code
            self.config.setdefault("settings", {})["prompt_name"] = self.name
            self.config["aliases"] = self.aliases
            # persist usage hints if present
            if getattr(self, 'usages', None) is not None:
                self.config["usages"] = self.usages
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception:
            pass

    def restore_terminal(self):
        """Reset terminal modes and ANSI state to avoid broken input after restart."""
        try:
            # reset ANSI colors
            print("\033[0m", end='', flush=True)
            # newline to ensure prompt starts on fresh line
            print("", flush=True)
            # try to make terminal sane on Unix
            if os.name != 'nt':
                try:
                    subprocess.run(['stty', 'sane'], check=False)
                except Exception:
                    pass
            else:
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    STD_INPUT_HANDLE = -10
                    handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
                    mode = ctypes.c_uint()
                    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                        ENABLE_ECHO_INPUT = 0x0004
                        ENABLE_LINE_INPUT = 0x0002
                        newmode = mode.value | ENABLE_ECHO_INPUT | ENABLE_LINE_INPUT
                        kernel32.SetConsoleMode(handle, newmode)
                except Exception:
                    pass
        except Exception:
            pass

    def _complete_filenames(self, text):
        """Return filename completions matching text in cwd."""
        try:
            base = text
            if os.path.sep in text:
                base_dir, base = os.path.split(text)
                base_dir = base_dir or "."
            else:
                base_dir = "."
            try:
                for entry in os.listdir(base_dir):
                    if entry.startswith(base):
                        candidate = os.path.join(base_dir, entry)
                        if os.path.isdir(candidate):
                            yield entry + os.path.sep
                        else:
                            yield entry
            except Exception:
                return
        except Exception:
            return

    def _completer(self, text, state):
        """Readline completer: completes commands, usage hints, and filenames."""
        # get current line buffer and split
        try:
            buf = self.readline.get_line_buffer()
            parts = buf.split()
            # completing first token: command names and aliases
            if len(parts) == 0 or (len(parts) == 1 and not buf.endswith(" ")):
                candidates = []
                for cmd in list(self.commands.keys()) + list(self.aliases.keys()):
                    if cmd.startswith(text):
                        candidates.append(cmd + (" " if cmd in self.usages else ""))
                candidates = sorted(set(candidates))
                return candidates[state] if state < len(candidates) else None
            # if completing after a command, and args empty, offer usage hint if matches command exactly
            cmd = parts[0]
            arg_fragment = text
            if len(parts) == 1 and not buf.endswith(" "):
                # still typing first token
                if cmd in self.usages:
                    # provide usage hint as a completion (non-destructive)
                    hint = self.usages[cmd]
                    if hint.startswith(cmd):
                        return hint + (" " if not hint.endswith(" ") else "") if state == 0 else None
            # for commands expecting filenames, offer filename completions
            filename_commands = {"mkdir", "touch", "rm", "cd", "ls", "cp", "mv", "cat"}
            if cmd in filename_commands:
                candidates = list(self._complete_filenames(text) or [])
                candidates = sorted(candidates)
                return candidates[state] if state < len(candidates) else None
        except Exception:
            pass
        return None

    def set_name(self, args):
        """Change the shell prompt name dynamically"""
        if args:
            self.name = " ".join(args)  # supports multi-word names
            print(f"Shell name changed to: {self.name}")
            try:
                self.config.setdefault("settings", {})["prompt_name"] = self.name
                self.save_config()
            except Exception:
                pass
        else:
            print(f"Current shell name: {self.name}")

    def cat(self, args):
        for filename in args:
            try:
                with open(filename, 'r') as f:
                    print(f.read())
            except FileNotFoundError:
                print(f"cat: {filename}: No such file or directory")
            except Exception as e:
                print(f"cat: {filename}: {e}")

    def ls(self, args):
        path = args[0] if args else "."
        try:
            for entry in os.listdir(path):
                print(entry)
        except FileNotFoundError:
            print(f"ls: cannot access '{path}': No such file or directory")
        except Exception as e:
            print(f"ls: {e}")

    def cd(self, args):
        if not args:
            print("cd: missing argument")
            return
        try:
            os.chdir(args[0])
        except FileNotFoundError:
            print(f"cd: {args[0]}: No such file or directory")
        except Exception as e:
            print(f"cd: {e}")

    def run(self):
        while self.running:
            try:
                if getattr(self, "ptk_session", None):
                    try:
                        user_input = self.ptk_session.prompt(f"{self.name}> ", completer=self.ptk_completer, bottom_toolbar=self._pt_toolbar, complete_while_typing=True, complete_style=self._pt_complete_style).strip()
                    except KeyboardInterrupt:
                        print(f"\nUse 'exit' to quit {self.name}.")
                        continue
                    except EOFError:
                        print()
                        break
                else:
                    user_input = input(f"{self.name}> ").strip()
                if not user_input:
                    continue
                parts = user_input.split()
                cmd = parts[0]
                args = parts[1:]

                # alias translation
                if cmd in getattr(self, "aliases", {}):
                    alias_parts = self.aliases[cmd].split()
                    cmd = alias_parts[0]
                    args = alias_parts[1:] + args

                if cmd in self.commands:
                    # Show usage hint when no args provided and a usage exists
                    if not args and cmd in getattr(self, "usages", {}):
                        print(f"Hint: {self.usages[cmd]}")
                    self.commands[cmd](args)
                else:
                    # Try to run system command
                    try:
                        result = subprocess.run([cmd] + args, capture_output=True, text=True)
                        print(result.stdout)
                        if result.stderr:
                            print(result.stderr)
                    except FileNotFoundError:
                        print(f"Command not found: {cmd}")

                # record history
                if getattr(self, "enable_history", False):
                    try:
                        with open(self.history_file, 'a+', encoding='utf-8') as hf:
                            hf.write(user_input + "\n")
                        with open(self.history_file, 'r', encoding='utf-8') as hf:
                            lines = hf.readlines()
                        if len(lines) > self.max_history_size:
                            with open(self.history_file, 'w', encoding='utf-8') as hf:
                                hf.writelines(lines[-self.max_history_size:])
                    except Exception:
                        pass
            except KeyboardInterrupt:
                print(f"\nUse 'exit' to quit {self.name}.")


if __name__ == "__main__":
    shell = MyCMD()
    shell.run()
