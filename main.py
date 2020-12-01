import cmd2
import sys
import os
import platform
import subprocess
import inspect
import pyfiglet
import getpass
import socket
import time
import datetime
import tarfile
import pathlib
from colorama import Fore, Style
from cmd2 import bg, fg, style


class MyShell(cmd2.Cmd):
    version_name = '1.0'

    STARTUP_SCRIPT_NAME = '.zshellrc'
    STARTUP_SCRIPT = '{}'.format(pathlib.Path.home()) + os.sep + STARTUP_SCRIPT_NAME

    # Categories
    CUSTOM_CATEGORY = 'My custom commands'
    SHELL_CATEGORY = 'Shell commands'
    VARIABLE_MANAGEMENT_CATEGORY = 'Variable management commands'

    def __init__(self):
        super().__init__(persistent_history_file='cmd2_history.dat',
                         startup_script=self.STARTUP_SCRIPT, use_ipython=True)

        # self.intro = style('Welcome to my own shell', fg=fg.red, bg=bg.white, bold=True) + ' 😀'

        # Allow access to your application in py and ipy via self
        self.self_in_py = True

        # Set the default category name
        self.default_category = 'Built-in commands'

        # Set prompt and intro
        self._set_prompt()
        self.intro = pyfiglet.figlet_format('zShell') + self.version_name

        # Set some properties
        self.hidden_commands.append('py')
        self.hidden_commands.append('pyscript')
        self.default_to_shell = True

        # Set variable store
        self.store = dict()

    def _set_prompt(self):
        """Set prompt so it displays the current working directory."""
        self.cwd = os.getcwd()
        homedir = os.environ['HOME']

        if self.cwd.startswith(homedir):
            self.cwd = '~' + self.cwd[len(homedir):]

        self.username = getpass.getuser()
        self.hostname = socket.gethostname()

        self.prompt = Style.BRIGHT + Fore.GREEN + '{}@{}'.format(self.username, self.hostname) + \
                        Fore.RED + ' {}'.format(time.strftime("%H:%M:%S")) + \
                        Fore.CYAN + ' {} $ '.format(self.cwd) + \
                        Fore.RESET + Style.RESET_ALL

    @cmd2.with_category(SHELL_CATEGORY)
    @cmd2.with_argument_list
    def do_cd(self, arglist):
        """Change directory.
    Usage:
        cd <new_dir>
        """
        # Expect 1 argument, the directory to change to
        if not arglist or len(arglist) != 1:
            self.perror("cd requires exactly 1 argument")
            self.do_help('cd')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        # Convert relative paths to absolute paths
        path = os.path.abspath(os.path.expanduser(arglist[0]))

        # Make sure the directory exists, is a directory, and we have read access
        out = ''
        err = None
        data = None
        if not os.path.isdir(path):
            err = '{!r} is not a directory'.format(path)
        elif not os.access(path, os.R_OK):
            err = 'You do not have read access to {!r}'.format(path)
        else:
            try:
                os.chdir(path)
            except Exception as ex:
                err = '{}'.format(ex)
            else:
                out = 'Successfully changed directory to {!r}\n'.format(path)
                self.stdout.write(out)
                data = path

        if err:
            self.perror(err)

        self._last_result = cmd2.CommandResult(out, err, data)

    # Enable tab completion for cd command
    def complete_cd(self, text, line, begidx, endidx):
        return self.path_complete(text, line, begidx, endidx, path_filter=os.path.isdir)

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_timestamp(self, args):
        """Generate timestamp.
    Usage:
        timestamp
        """

        self.poutput(self.get_timestamp())

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_intro(self, _):
        """Display the intro banner"""
        self.poutput(self.intro)

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_echo(self, arg):
        """Example of a multiline command"""
        self.poutput(arg)

    def get_timestamp(self):
        return '{:%Y%m%d%H%M%S}'.format(datetime.datetime.now())

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_targz(self, args):
        """Create tar gz file creating directory too if not exists.
    Usage:
        targz source_dir output_filename
        """

        arglist = args.split()

        # Expect 2 argument
        if len(arglist) != 2:
            self.perror('targz requires 2 argument')
            self.do_help('targz')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        source_file_or_dir = os.path.expanduser(arglist[0])
        output_filename = os.path.expanduser(arglist[1])

        # Create output directory if not exists
        complete_path = pathlib.Path(output_filename)
        path = pathlib.Path(os.sep.join(complete_path.parts[0:-1])[1:])
        path.mkdir(parents=True, exist_ok=True)

        # Create path for origin
        origin_path = pathlib.Path(source_file_or_dir)

        # Make tar gz
        with tarfile.open(output_filename, "w:gz") as tar:
            if origin_path.is_dir():
                tar.add(source_file_or_dir, arcname=os.path.basename(source_file_or_dir))
            else:
                files = self.list_files(source_file_or_dir)
                for f in files:
                    tar.add(f)

    @cmd2.with_category(CUSTOM_CATEGORY)
    def do_untargz(self, args):
        """Create tar gz file creating directory too if not exists.
    Usage:
        untargz input_filename
        untargz input_filename destination_dir
        """

        arglist = args.split()

        # Expect 1 or 2 argument
        if len(arglist) > 2:
            self.perror('untargz requires 1 or 2 argument')
            self.do_help('untargz')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        input_file = os.path.expanduser(arglist[0])
        destination = '.'

        if len(arglist) == 2:
            destination = os.path.expanduser(arglist[1])

            # Create output directory if not exists
            complete_path = pathlib.Path(destination)
            path = pathlib.Path(os.sep.join(complete_path.parts[0:-1])[1:])
            path.mkdir(parents=True, exist_ok=True)

        # Decompress tar gz file
        with tarfile.open(input_file, "r:gz") as tar:
            tar.extractall(path=destination)

    @cmd2.with_category(VARIABLE_MANAGEMENT_CATEGORY)
    def do_zset(self, args):
        """Set variable in Z server.
    Usage:
        zset varname value
        zset varname value store -> With the keyword store it saves the variable in startup script
        """

        arglist = args.split()

        # Expect 2 argument
        if not arglist or len(arglist) < 2 or len(arglist) > 3:
            self.perror('zset requires 2 or 3 argument')
            self.do_help('zset')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        # Recover arguments
        key = arglist[0]
        value = arglist[1]
        save = False
        if len(arglist) == 3:
            save = True if arglist[2].lower() == 'store' else False

        # Update dictionary
        self.store.update({key: value})

        # Update startup script is save is set
        if save:
            self.create_startup_file_if_not_exists()
            lines = self.get_startup_script_as_list()

            # Open startup script and add at the beginning this variable
            # Be careful because it is possible that already exists the variable in startup script: delete before write
            with open(self.STARTUP_SCRIPT, 'w') as f:
                new_command = ['zset {} {}\n'.format(key, value)]

                # Delete variable from lines if it exists
                lines_modified = [line for line in lines if not line.lower().startswith('zset {}'.format(key.lower()))]

                lines_with_new_command = new_command + lines_modified
                f.writelines(lines_with_new_command)
                self.poutput('Variable stored {} = {}'.format(key, value))

    @cmd2.with_category(VARIABLE_MANAGEMENT_CATEGORY)
    def do_zget(self, args):
        """Get variable value in Z server. Return 'NOT SET string if not exists.
    Usage:
        zget
        zget varname
        """

        arglist = args.split()

        # Expect 0 or 1 argument
        if len(arglist) > 1:
            self.perror('zget requires 0 or 1 argument')
            self.do_help('zget')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        if len(arglist) == 0:
            for (key, value) in self.store.items():
                self.poutput('{}: {}'.format(key, value))
        elif len(arglist) == 1:
            key = arglist[0]
            value = self.store.get(key, 'NOT SET')
            self.poutput(value)

    @cmd2.with_category(VARIABLE_MANAGEMENT_CATEGORY)
    def do_zdel(self, args):
        """Delete variable value in Z server.
    Usage:
        zdel varname
        """

        arglist = args.split()

        # Expect 1 argument
        if not arglist or len(arglist) != 1:
            self.perror('zdel requires exactly 1 argument')
            self.do_help('zdel')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        key = arglist[0]

        del self.store[key]
        return

    @cmd2.with_category(VARIABLE_MANAGEMENT_CATEGORY)
    def do_zstorevar(self, args):
        """Store all variables in init script.
    Usage:
        zstorevar
        """

        arglist = args.split()

        # Expect 0 argument
        if len(arglist) != 0:
            self.perror('zstorevar requires exactly 0 argument')
            self.do_help('zstorevar')
            self._last_result = cmd2.CommandResult('', 'Bad arguments')
            return

        #  Create empty startup script sfile
        self.create_startup_file_if_not_exists()

        # Open init script, delete all zset commands and insert the new zset commands at the beginning
        lines = self.get_startup_script_as_list()

        with open(self.STARTUP_SCRIPT, 'w') as f:
            lines_without_set = [line for line in lines if not line.lower().startswith('zset')]
            new_set = ['zset {} {}\n'.format(key, value) for key, value in self.store.items()]
            lines_with_new_set = new_set + lines_without_set
            f.writelines(lines_with_new_set)

        return

    def execute_generic_shell_command(self, *args):
        system = platform.system()
        shell_command = args[0]
        if system == 'Linux':
            command = self.SHELL_COMMANDS[shell_command][self.LINUX] + args[1]
        elif system == 'Windows':
            command = self.SHELL_COMMANDS[shell_command][self.WINDOWS] + args[1]
        else:
            return self.OS_NOT_SUPPORTED

        output_without_encoding = subprocess.check_output(command, shell=True)
        return output_without_encoding.decode('utf-8').strip()

    def create_startup_file_if_not_exists(self):
        # If startup_script does not exist, then create it empty
        if not os.path.exists(self.STARTUP_SCRIPT):
            pathlib.Path(self.STARTUP_SCRIPT).touch()

    def get_startup_script_as_list(self):
        # Recover all lines of startup script
        lines = list()
        with open(self.STARTUP_SCRIPT, 'r') as f:
            lines = f.readlines()
        return lines

if __name__ == '__main__':
    shell = MyShell()
    shell.cmdloop()