#!/usr/bin/env python3
import os
import traceback

VERSION = "0.1"

path = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin"] #PATH
debugmsg = False#if DEbug Messages are to be shown
jb_builtin_comms = {} #Builtin Commands
ext_comms = {} #Extension commands
user = os.environ["USER"]#Current user
hostname = "PLACEHOLDER" #machine hostname
home = os.environ["HOME"] #user's home directory
cwd = os.environ["PWD"] #current working directory (real)
fake_cwd = cwd#displayed current working directory, used for ~ mainly
envvars = {} #Virtual environment variables

def debug(msg):
    if debugmsg:
        print(f"[JOBOX:DEBUG]{msg}")

def parse_args(args, commobj):
    '''Parses the commands arguments, and returns them in the form [posargs: dict, optargs: dict]. args should be the args string
    and commobj should be the object that represents the command.'''
    args = args.split(" ")
    i = 0
    while i < len(args):
        debug("Began quote check in parse_args")
        if args[i].startswith("'") or args[i].startswith('"'):
            quotet = list(args[i])[0]
            debug(f"quotet={quotet}")
            for j in args[i:]:
                if j.endswith(quotet):
                    newarg = " ".join(args[i:args.index(j)+1])
                    del args[i:args.index(j)+1]
                    if len(args) == i:
                        args.append(None)
                    newarg = newarg.strip(quotet)
                    args[i] = newarg
                    break
        debug("Completed one cycle")
        i += 1
    parsed = [{}, {}]
    poscounter = 1
    nextopt = False
    argindex = 0
    debug(f"len(args)={len(args)}")
    while argindex < len(args):
        debug(f"argindex={argindex}")
        arg = args[argindex]
        debug(f"arg={arg}")
        if (arg.startswith("-")) or (arg.startswith("--")):
            debug("Began opt check in parse_args")
            if arg in commobj.optargs:
                if commobj.optargs[arg] == "bool":
                    parsed[1][arg] = True
                    args.pop(argindex)
                elif commobj.optargs[arg] == "str":
                    parsed[1][arg] = args[argindex+1]
                    args.pop(argindex)
                    args.pop(argindex)
        else:
            for i in commobj.posargs:
                num = commobj.posargs.index(i)
                if args.index(arg) == num:
                    parsed[0][i] = arg
                    argindex += 1
    for i in commobj.posargs:
        if not (i in parsed[0]):
            parsed[0][i] = None
    for i in commobj.optargs:
        if not (i in parsed[1]):
            parsed[1][i] = None
    debug(f"parse_args returned {parsed}")
    return parsed

def eval_stmt_vars(comm):
    """Evaluates variables in command comm and replaces them with their values in the string. Returns the new string."""
    commarr = list(comm)
    while "$" in commarr:
        vstart = commarr.index("$")
        if commarr[vstart+1] == "[":
            vcount = vstart
            vend = None
            for i in commarr[vstart:]:
                if i == "]":
                    vend = vcount
                    break
                vcount += 1
            if vend == None:
                continue
            else:
                varstring = "".join(commarr[vstart:vend+1])
                varname = varstring.strip("$").strip("[").strip("]")
                comm = comm.replace(varstring, envvars[varname])
                commarr = list(comm)
    return comm

class JoboxBuiltin:
    '''Class for special commands. func should be the commands function, 
    posargs should be a list of positional arguments, and optargs should be a dict of each option arg with its type (bool or str)'''
    def __init__(self, func, posargs, optargs):
        self.func = func
        self.posargs = posargs
        self.optargs = optargs

    def __call__(self, comm):
        '''Used for when the command is called.'''
        tmpargs = " ".join(comm.split(" ")[1:])
        parsed = parse_args(tmpargs, self)
        posargs = parsed[0]
        optargs = parsed[1]
        self.func(posargs, optargs)

def builtin_dec(*args, **kwargs):
    def _bd_wrapper(func):
        jb_builtin_comms[args[0]] = JoboxBuiltin(func, args[1], args[2])
    return _bd_wrapper

def exec_command(comm):
    '''Executes a command. comm should be a string.'''
    try:
        comm = eval_stmt_vars(comm)
        commname = comm.split(" ")[0]
        if ";" in list(comm):
            for i in comm.split(";"):
                exec_command(i)
            return
        for i in path:
            for j in os.listdir(i):
                if j == comm.split(" ")[0]:
                    os.system(f"{i}/{j} {' '.join(comm.split(' ')[1:])}")
        for i in jb_builtin_comms:
            if i == commname:
                jb_builtin_comms[i](comm)
                return
        print("Command not found")
    except:
        print(f"[{commname}:ERROR]{traceback.format_exc()}")

def main_cli():
    '''Starts the interactive shell.'''
    global user, hostname, home, cwd, fake_cwd
    print(f"JoBox shell version {VERSION}")
    while True:
        exec_command(input(f"{user}@{hostname}:{fake_cwd} J>"))

@builtin_dec("cd", ["dir"], {})
def _cd_builtin(posargs, optargs):
    global cwd, fake_cwd
    cwd = posargs["dir"]
    fake_cwd = cwd
    os.chdir(posargs["dir"])

@builtin_dec("jbdebug", ["action", "arg"], {"--pretty":"bool", "--say":"str"})
def _jbdebug_builtin(posargs, optargs):
    global debugmsg
    if posargs["action"] == "msgs":
        if posargs["arg"] == "on":
            debugmsg = True
        elif posargs["arg"] == "off":
            debugmsg = False
    if optargs["--pretty"]:
        print("JOBOX IS PRETTY")
    print(optargs["--say"])

@builtin_dec("jbdef", ["name", "value"], {})
def _jbdef_builtin(posargs, optargs):
    envvars[posargs["name"]] = posargs["value"]

if __name__ == "__main__":
    main_cli()
