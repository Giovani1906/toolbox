import argparse
import copy
import os
import subprocess
import sys
from functools import partial
from multiprocessing import Pool

from ftex_info import fmt_choices, ftex_check
from pes_file_tools.ftex import dds_to_ftex_buffer, ftex_to_dds_buffer


def convert(data: bytes, ftex_format: str = None, ftex_version: float = None):
    if sys.platform == "win32":
        return
    else:
        dds_buffer = ftex_to_dds_buffer(data)
        proc = subprocess.Popen(
            ["identify", "-format", "%m %[compression]", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        p_out, p_err = proc.communicate(dds_buffer)
        if p_err:
            raise Exception(p_err.decode("utf-8"))
        print(p_out.decode("utf-8"))


def check_and_convert(
    file_name: str,
    check_for_format: str,
    check_for_version: float,
    convert_to_format: str,
    convert_to_version: float,
    dont_preserve_original: bool,
    keep_dds_file: bool,
    file_root: str = None,
):
    if file_name.split(".")[-1].lower() == "ftex":
        if file_root:
            path = os.path.join(file_root, file_name)
        else:
            path = file_name

        with open(path, "rb") as fd:
            buffer = fd.read()

            chk_fmt = [check_for_format] if check_for_format else []
            if not ftex_check(buffer, chk_fmt, check_for_version):
                return
            convert(buffer, convert_to_format, convert_to_version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="FTEX Mass Converter")
    parser.add_argument("path")
    parser.add_argument("--check-for-format", choices=fmt_choices)
    parser.add_argument("--convert-to-format", choices=fmt_choices)
    parser.add_argument("--check-for-version", choices=[2.03, 2.04], type=float)
    parser.add_argument("--convert-to-version", choices=[2.03, 2.04], type=float)
    parser.add_argument("--dont-preserve-original", action="store_true")
    parser.add_argument("--keep-dds-file", action="store_true")
    args = parser.parse_args()

    if not (args.convert_to_format or args.convert_to_version):
        print("No conversion flags specified.\nExiting...")
        exit(0)
    if args.convert_to_version == 2.03 and args.convert_to_format in fmt_choices[6:-1]:
        print(
            f"{args.convert_to_format} is not compatible with FTEX {args.convert_to_version}."
        )
        exit(0)
    if args.convert_to_format:
        if (
            sys.platform != "win32"
            and subprocess.check_output(["whereis", "convert"]) == b"convert:\n"
        ):
            print(
                "ImageMagick has not been found...\nPlease install it with your package manager."
            )
            exit(0)

    kwargs = copy.copy(vars(args))
    del kwargs["path"]

    if os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            with Pool() as p:
                p.map(partial(check_and_convert, file_root=root, **kwargs), files)
            """
            for file in files:
                check_and_convert(file, file_root=root, **kwargs)
            """
    else:
        check_and_convert(args.path, **kwargs)
