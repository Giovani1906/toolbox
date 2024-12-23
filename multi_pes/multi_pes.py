#!C:\Windows\py.exe -3
import ctypes
import re
import subprocess
import sys
import time
from os.path import exists

if __name__ == "__main__":
    try:
        if sys.platform != "win32":
            print(
                "This script doesn't function outside of Windows.\n"
                "For a similar effect on GNU/Linux (and probably macOS) "
                "use a Wine prefix for each instance of PES you want to launch."
            )

        if not ctypes.windll.shell32.IsUserAnAdmin():
            print(
                "This script needs administrator permissions in order to function.\n"
                "The script will restart in ten seconds in order to run as administrator.",
                end="",
            )
            for _ in range(10):
                sys.stdout.write(".")
                sys.stdout.flush()
                time.sleep(1)
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
            sys.exit()

        if exists("handle.exe"):
            h_path = "handle.exe"
        elif exists("handle/handle.exe"):
            h_path = "handle/handle.exe"
        elif exists("multi_pes/handle/handle.exe"):
            h_path = "multi_pes/handle/handle.exe"
        else:
            print(
                "Handle could not be found. Please install it next to the Python script.\n"
                "You can get it from here: https://learn.microsoft.com/en-us/sysinternals/downloads/handle"
            )
            sys.exit()

        c = "\033[47m\033[30m"
        r = "\33[0m"
        print(
            f"{c}{'=' * 35}\033[41m\033[37m MultiPES {c}{'=' * 35}{r}\n"
            f"{c}|{r}    A Python script that allows a version of PES to be ran multiple times.    {c}|{r}\n"
            f'{c}|{r}You\'ll never see that "Pro Evolution Soccer is already running" message again.{c}|{r}\n'
            f"{c}|{r}{' ' * 78}{c}|{r}\n"
            f"{c}|{r}        PES can be launched again after a new line appears down bellow.       {c}|{r}\n"
            f"{c}{'=' * 80}{r}"
        )

        procs_modded = []

        while True:
            p_cmd = 'Get-Process -Name "PES*" | Format-Table Id,Name,mainWindowTitle -HideTableHeaders'
            p_out = subprocess.check_output(f"powershell -Command {p_cmd}")
            if not p_out:
                continue

            proc_re = re.compile(r"^\s*(\d*) (PES20\d{2}) ?\b(.*)\b\s*$", re.MULTILINE)
            if procs := proc_re.findall(p_out.decode("utf8")):
                for proc in procs:
                    title_check = (
                        "Pro Evolution Soccer" in proc[2] or "eFootball PES" in proc[2]
                    )
                    if (proc[0] not in procs_modded) and title_check:
                        h_cmd = f'{h_path} -p {proc[0]} -a -nobanner "boot"'
                        h_out = subprocess.check_output(h_cmd)

                        if "No matching handles found." not in h_out.decode("utf-8"):
                            m_re = re.compile(r".*Mutant\s*(\w{2,}): \\.*\sBoot")
                            mutex = m_re.search(h_out.decode("utf8")).group(1)
                            m_cmd = f"{h_path} -p {proc[0]} -nobanner -c {mutex} -y"
                            m_out = subprocess.check_output(m_cmd)

                            if "Handle closed." in m_out.decode("utf-8"):
                                print(
                                    f'"{proc[1]}.exe (PID: {proc[0]})" '
                                    "has been modified to allow another window to be launched."
                                )
                                procs_modded.append(proc[0])
                            else:
                                print(
                                    f"Something happened.\n\nError:\n{m_out.decode('utf8')}"
                                )
                                break

            time.sleep(5)
    except KeyboardInterrupt:
        print("Exiting...")
        time.sleep(1)
        sys.exit()
