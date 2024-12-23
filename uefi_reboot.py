#!C:\Windows\py.exe -3
import ctypes
import sys

if __name__ == "__main__":
    if sys.platform != "win32":
        print("This script doesn't function outside of Windows.")

    if not ctypes.windll.shell32.IsUserAnAdmin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()

    ctypes.windll.shell32.ShellExecuteW(None, None, "shutdown", "/r /fw /t 0", None, 1)
