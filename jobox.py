#!/usr/bin/env python3
import os
import traceback
import pickle
import types
import copy
import sys
import marshal

VERSION = "0.6.3-beta"
REVISION_NUMBER = 9 #Used for checking compatibility

JB_EXEC_NAMES = ["jobox", "./jobox", "/usr/bin/jobox", "/bin/jobox", "jobox.py"]

path = ["/usr/bin", "/bin", "/usr/sbin", "/sbin", "/usr/local/bin"] #PATH
jb_ext_path = "/usr/local/lib/jobox" #Path for JoBox extensions
jb_builtin_comms = {} #Builtin Commands
ext_comms = {} #Extension commands

debugmsg = False#if DEbug Messages are to be shown
jbsafety = True #If some of JoBox's dafety abilities, such as proteching globals from being written to via jbdebug --eval, should be enabled

#Failsafe try loop in case sudo is used
try:
    hostname = "PLACEHOLDER" #machine hostname
    home = os.environ["HOME"] #user's home directory
except:
    hostname = "PLACEHOLDER"
    home = '/root'

user = os.getlogin()#Current user
cwd = os.getcwd() #current working directory (real)
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
    olen = len(args)
    debug(f"commobj.optargs={commobj.optargs}")
    debug(f"commobj.posargs={commobj.posargs}")
    while i < len(args):
        debug("Began quote check in parse_args")
        if args[i].startswith("'") or args[i].startswith('"'):
            debug("Quotes found")
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
    debug(f"args={args}")
    parsed = [{}, {}]
    poscounter = 1
    nextopt = False
    argindex = 0
    debug(f"len(args)={len(args)}")
    while argindex < len(args):
        if args==['']:
            break
        debug(f"argindex={argindex}")
        arg = args[argindex]
        debug(f"arg={arg}")
        debug(f"args={args}")
        if (arg.startswith("-")) or (arg.startswith("--")):
            debug("Began opt check in parse_args")
            if arg in commobj.optargs.keys():
                if commobj.optargs[arg] == "bool":
                    debug("arg type is bool")
                    parsed[1][arg] = True
                    args.pop(argindex)
                elif commobj.optargs[arg] == "str":
                    debug("arg type is str")
                    parsed[1][arg] = args[argindex+1]
                    args.pop(argindex)
                    args.pop(argindex)
                else:
                    debug("No suitable type found for arg")
            else:
                raise Exception(f"\n\nYou used an unknown argument ({arg}) when calling the command.")
        else:
            for i in commobj.posargs:
                num = commobj.posargs.index(i)
                if args.index(arg) == num:
                    debug(f"Found posarg {i}: {arg}")
                    parsed[0][i] = arg
                    argindex += 1
                    break
            else:
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

    def __call__(self, comm, parsed=None):
        '''Used for when the command is called.'''
        tmpargs = " ".join(comm.split(" ")[1:])
        if parsed == None:
            parsed = parse_args(tmpargs, self)
        posargs = parsed[0]
        optargs = parsed[1]
        self.func(posargs, optargs)

class JoboxExtension(JoboxBuiltin):
    '''Class for extensions. See EXTENDING.md for more info.'''
    def __init__(self, codeobj):
        self.__virtglobals = {
            "JoboxBuiltin": JoboxBuiltin,
            "JoboxExtension": JoboxExtension,
            "EXT_OBJ_SELF": self,
            "jobox_install": _null
        }
        exec(codeobj, self.__virtglobals, self.__virtglobals)
        super().__init__(self.__virtglobals["jobox_call"], self.__virtglobals["jobox_posargs"], self.__virtglobals["jobox_optargs"])
        self.extshortname = self.__virtglobals["JB_NAME_SHORT"]
        self.extlongname = self.__virtglobals["JB_NAME_LONG"]
        self.extversion = self.__virtglobals["JB_VERSION"]
        self.extinstallf = self.__virtglobals["jobox_install"]
        self.extminrev = self.__virtglobals["JB_MIN_REV"]
        self.extmaxrev = self.__virtglobals["JB_MAX_REV"]

    def __str__(self):
        return f"JoBox extension\nNAME: {self.extlongname}\nSHORTENED NAME: {self.extshortname}\nVERSION: {self.extversion}"

def install_extension(path):
    debug(f"Beginning installation of extension at {path}")
    with open(path, "r") as f:
        code = compile(f.read(), path, "exec")
        tmpext = JoboxExtension(code)
        if (REVISION_NUMBER < tmpext.extminrev) or (REVISION_NUMBER > tmpext.extmaxrev):
            print(f"You cannot install this extension because you don't have the right version of JoBox installed. It requires a revision between {tmpext.extminrev} and {tmpext.extmaxrev}.")
        ok = input(f"You are installing {tmpext.extshortname}-{tmpext.extversion}. Is this okay?(y/N)")
        if ok == "y":
            tmpext.extinstallf()
            with open(f"/usr/local/lib/jobox/{tmpext.extshortname}", "wb") as f2:
                marshal.dump(code, f2)
                print(f"Successfully installed.")
        else:
            return

def load_extension(name):
    with open(f"/usr/local/lib/jobox/{name}", "rb") as f:
        extensioncode = marshal.load(f)
        extension = JoboxExtension(extensioncode)
        ext_comms[name] = extension

def builtin_dec(*args, **kwargs):
    def _bd_wrapper(func):
        jb_builtin_comms[args[0]] = JoboxBuiltin(func, args[1], args[2])
    return _bd_wrapper

def exec_command(comm):
    '''Executes a command. comm should be a string.'''
    try:
        comm = comm.strip()
        comm = eval_stmt_vars(comm)
        commname = comm.split(" ")[0]
        if ";" in list(comm):
            for i in comm.split(";"):
                exec_command(i)
                return
            return
        for i in jb_builtin_comms:
            if i == commname:
                jb_builtin_comms[i](comm)
                return
        for i in ext_comms:
            if i == commname:
                ext_comms[i](comm)
                return
        for i in path:
            for j in os.listdir(i):
                if j == comm.split(" ")[0]:
                    os.system(f"{i}/{j} {' '.join(comm.split(' ')[1:])}")
                    return
        if comm == "":
            return
        print("Command not found")
    except SystemExit:
        debug("Caught SystemExit")
        sys.exit()
    except Exception:
        print(f"[{commname}:ERROR]{traceback.format_exc()}")

def exec_script(path):
    '''Executes a script at path. Self explanatory.'''
    with open(path, "r") as f:
        local_script_scope = copy.copy(globals())
        src = f.read()
        for i in src.split("\n"):
            i = i.strip()
            local_script_scope["_JOBOX_SCRIPT_COMMAND"] = i
            if i.startswith("#"):
                continue
            else:
                eval("exec_command(_JOBOX_SCRIPT_COMMAND)", local_script_scope)

def main_cli():
    '''Starts the interactive shell.'''
    global user, hostname, home, cwd, fake_cwd
    print(f"JoBox shell version {VERSION} (revision {REVISION_NUMBER})")
    while True:
        exec_command(input(f"{user}@{hostname}:{fake_cwd} J>"))

def main():
    '''When called, will take sys.argv[0] and use that to call the command based on sys.argv[0]. Checks both builtins and 
    extensions.'''
    has_spaces=[]
    pname = sys.argv[0]
    if pname in JB_EXEC_NAMES:
        pname = "jobox"
        sys.argv[0] = "jobox"
    for i in sys.argv:
        if " " in list(i):
            has_spaces.append(sys.argv.index(i))
    for j in has_spaces:
        sys.argv[j] = f"'{sys.argv[j]}'"
    #debug("processed command="+str("' '".join(sys.argv)+"'"))
    debug(f"sys.argv={sys.argv}")
    for i in os.listdir(jb_ext_path):
        if i == pname:
            exec_command(" ".join(sys.argv))
            break
    for i in jb_builtin_comms:
        if i == pname:
            exec_command(" ".join(sys.argv))
            break
    else:
        print("[JOBOX:WARN]The program name you used to start JoBox is unrecognized; Starting interactive CLI.")
        main_cli()

@builtin_dec("jobox", ["fname"], {"-c":"str", "--no-safety":"bool"})
def _jobox_init_builtin(posargs, optargs):
    '''This is a special builtin command; it is called when JoBox initializes without a command.'''
    global jbsafety
    if optargs["--no-safety"] != None:
        jbsafety = False
    if optargs["-c"] != None:
        exec_command(optargs["-c"])
        sys.exit()
    elif posargs["fname"] == None:
        main_cli()
    else:
        exec_script(posargs["fname"])

@builtin_dec("cd", ["dir"], {})
def _cd_builtin(posargs, optargs):
    global cwd, fake_cwd
    cwd = posargs["dir"]
    fake_cwd = cwd
    os.chdir(posargs["dir"])

@builtin_dec("jbdebug", ["action", "arg"], {"--pretty":"bool", "--say":"str", "--eval":"str"})
def _jbdebug_builtin(posargs, optargs):
    global debugmsg
    if posargs["action"] == "msgs":
        if posargs["arg"] == "on":
            debugmsg = True
        elif posargs["arg"] == "off":
            debugmsg = False
    if optargs["--pretty"]:
        print("JOBOX IS PRETTY")
    elif optargs["--eval"] != None:
        if jbsafety:
            virtglobals = copy.copy(globals())
            virtglobals["exec"] = _null
        else:
            virtglobals = globals()
        print(eval(optargs["--eval"], virtglobals))
    print(f"optargs['--say']={optargs['--say']}")

@builtin_dec("jbdef", ["name", "value"], {})
def _jbdef_builtin(posargs, optargs):
    envvars[posargs["name"]] = posargs["value"]

@builtin_dec("jbtools", ["command"], {"--install":"str", "--load":"str", "--bootstrap":"bool"})
def _jbtools_builtin(posargs, optargs):
    command = posargs["command"]
    if command == "extension":
        if optargs["--install"] != None:
            install_extension(optargs["--install"])
        elif optargs["--load"] != None:
            load_extension(optargs["--load"])
    elif command == "bootstrap":
        os.mkdir("/usr/local/lib/jobox")
        os.system("cp jobox.py /usr/bin/jobox")
        os.system("chmod a+x /usr/bin/jobox")
    elif command == "uninstall":
        os.rmtree(jb_ext_path)
        os.system("rm /usr/bin/jobox")

@builtin_dec("sudo", ["command"], {})
def _sudo_builtin(posargs, optargs):
    os.system(f"sudo {sys.argv[0]} -c '{posargs['command']}'")

@builtin_dec("su", ["user"], {})
def _su_builtin(posargs, optargs):
    debug("SU called")
    debug(f"sys.argv[0]={sys.argv[0]}")
    user = posargs["user"]
    if user == None:
        user = ""
    os.system(f"su {user} -c {sys.argv[0]}")

@builtin_dec("exit", [], {})
def _exit_builtin(posargs, optargs):
    sys.exit()

def _null(*args, **kwargs):
    """Placeholder function used if an extension doesnt define one."""
    pass

if __name__ == "__main__":
    main()