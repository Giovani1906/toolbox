#!C:\Windows\py.exe -3
import ctypes
import sys
import os

if __name__ == "__main__":
    match sys.platform:
        case "win32":
            if not ctypes.windll.shell32.IsUserAnAdmin():
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit()

            ctypes.windll.shell32.ShellExecuteW(None, None, "shutdown", "/r /fw /t 0", None, 1)
        case "linux":
            # This is for an OpenRC Gentoo system, so it won't work on SystemD distros.
            os.system("loginctl reboot --firmware-setup")
        case _:
            print("This script doesn't function outside of Windows and GNU/Linux.")
