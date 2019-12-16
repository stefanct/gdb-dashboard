#!/usr/bin/env python

import subprocess, os, sys

def start_terminal():
    import psutil
    from time import sleep

    #  cmd = [
        #  "xterm",
        #  "-e",
        #  "stty -echo ; cat >/dev/null",
    #  ]
    cmd = [
        "mate-terminal",
        "--hide-menubar",
        "--disable-factory",
        "--",
        "sh",
        "-c",
        "stty -echo ; cat >/dev/null",
    ]

    #  print("cmd is %s" % ' '.join(cmd))

    proc_pipe = subprocess.Popen(cmd,
        # Running in a separate process group prevents delivery of SIGINT on ^c
        preexec_fn=os.setpgrp,
        close_fds=True,
    )
    pid = proc_pipe.pid

    parent = psutil.Process(pid)
    #  print("Waiting for children of %d" % parent.pid)
    children = parent.children()
    while (len(children) is 0):
        sleep(0.1)
        children = parent.children()

    pts_path = children[0].terminal()
    
    return proc_pipe, pts_path

def get_active_window_id():
    import Xlib
    import Xlib.display

    display = Xlib.display.Display()
    root = display.screen().root
    windowID = root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), Xlib.X.AnyPropertyType).value[0]
    return windowID

def get_current_monitor():
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk

    disp = Gdk.Display.get_default()
    scr = disp.get_default_screen()
    win = scr.get_active_window()
    win_pos=win.get_root_origin()
    #  print("caller win origin: %d x %d" % (win_pos.x, win_pos.y))
    mon = disp.get_monitor_at_point(win_pos.x, win_pos.y)
    mon_geom = mon.get_geometry()
    #  print("caller monitor geometry: %d x %d" % (mon_geom.width, mon_geom.height))
    workarea = mon.get_workarea()
    #  print("caller monitor workarea: %d x %d" % (workarea.x, workarea.y))
    return mon

def set_win_geometry(win_id, x, y, w):
    # Resize window (approximately) and move it to the right
    subprocess.check_call(["wmctrl",
                           "-i",
                           "-r",
                           "0x%x" % win_id,
                           "-e",
                           "3,{x:.0f},{y:.0f},{width:.0f},-1".format(x=x, y=y, width=w),
                          ])

    # Maximize it vertically
    subprocess.check_call(["wmctrl",
                           "-i",
                           "-r",
                           "0x%x" % win_id,
                           "-b",
                           "add,maximized_vert",
                          ])

def activate_win(win_id):
    subprocess.check_call(["wmctrl",
                           "-i",
                           "-a",
                           "0x%x" % win_id,
                          ])

def main():
    mon = get_current_monitor()
    mon_geom = mon.get_geometry()
    workarea = mon.get_workarea()

    caller_id = get_active_window_id()
    proc_pipe, pts_path = start_terminal()
    callee_id = get_active_window_id()

    # Make sure terminal gets killed again when we exit gdb/this process
    def exit_handler(proc):
        # While this creates a (harmless) race condition it is the best
        # thing we can do without changing the subprocess package.
        proc.poll()
        if proc.returncode == None:
            proc.kill()
    import atexit
    atexit.register(exit_handler, proc_pipe)

    # Calculate and set new window coordinates
    new_x=workarea.x + mon_geom.width/2
    new_y=workarea.y
    new_width=mon_geom.width/2
    set_win_geometry(callee_id, new_x, new_y, new_width)
    activate_win(caller_id)

    try:
        import gdb
        from packaging import version
        if version.parse(gdb.VERSION) >= version.parse('8.2.1'):
            gdb.set_convenience_variable("tty", pts_path)
        else:
            print("Could not use convenience variable to pass path to PTY")
            print("Please execute 'dashboard -output %s' manually." % pts_path)

    except ImportError:
        try:
            proc_pipe.wait()
        except KeyboardInterrupt:
            print("Interrupted")

if __name__== "__main__":
    if sys.platform != 'win32':
        main()
