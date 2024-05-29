import argparse
import copy
import os
import subprocess
import sys
from functools import partial
from multiprocessing import Pool

from ftex_info import fmt_choices, ftex_check
from pes_file_tools.ftex import dds_to_ftex_buffer, ftex_to_dds_buffer


def check_and_convert(
    filename: str,
    check_for_format: str,
    check_for_version: float,
    convert_to_format: str,
    convert_to_version: float,
    dont_preserve_original: bool,
    keep_dds_file: bool,
    filedir: str = None,
):
    if filename.split(".")[-1].lower() != "ftex":
        return

    if filedir:
        path = os.path.join(filedir, filename)
    else:
        path = filename
        filedir = os.path.dirname(filename)

    with open(path, "rb") as input_buffer:
        buffer = input_buffer.read()

    chk_fmt = [check_for_format] if check_for_format else []
    if not (ftex := ftex_check(buffer, chk_fmt, check_for_version)):
        return

    if not convert_to_format and convert_to_version != round(ftex.version, 2):
        ftex203 = b"\x85\xeb\x01@"
        ftex204 = b"\\\x8f\x02@"
        match convert_to_version:
            case 2.03:
                buffer = buffer.replace(ftex204, ftex203)
            case 2.04:
                buffer = buffer.replace(ftex203, ftex204)

        if not dont_preserve_original:
            os.rename(path, path.replace(".ftex", "_old.ftex"))

        with open(path, "wb") as output_buffer:
            output_buffer.write(buffer)
    else:
        dds_buffer = ftex_to_dds_buffer(buffer)
        match convert_to_format:
            case "BC1":
                convert_to_format = "DXT1"
            case "BC2":
                convert_to_format = "DXT3"
            case "BC3":
                convert_to_format = "DXT5"

        if sys.platform == "win32":
            dds_path = path.replace(".ftex", "_tmp.dds")
            with open(dds_path, "wb") as df:
                df.write(dds_buffer)

            cmd = [
                os.path.join("bin", "texconv.exe"),
                "-f",
                convert_to_format,
                "-y",
                "-o",
                filedir,
                dds_path,
            ]
            p_out = subprocess.check_output(cmd)

            with open(dds_path, "rb") as dcf:
                dds_converted_buffer = dcf.read()

            if not keep_dds_file:
                os.remove(dds_path)
        else:
            cmd = [
                "convert",
                "-format",
                "dds",
                "-define",
                f"dds:compression={convert_to_format.lower()}",
                "-",
                "-",
            ]
            # cmd = ["identify", "-format", "%m %[compression]", "-"]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            p_out, p_err = proc.communicate(dds_buffer)

            if p_err:
                raise Exception(p_err.decode("utf-8"))
            print(p_out.decode("utf-8"))
            return

        if not dont_preserve_original:
            os.rename(path, path.replace(".ftex", "_old.ftex"))

        buffer = dds_to_ftex_buffer(dds_converted_buffer)

        if convert_to_version != round(ftex.version, 2):
            ftex203 = b"\x85\xeb\x01@"
            ftex204 = b"\\\x8f\x02@"
            match convert_to_version:
                case 2.03:
                    buffer = buffer.replace(ftex204, ftex203)
                case 2.04:
                    buffer = buffer.replace(ftex203, ftex204)

        with open(path, "wb") as output_buffer:
            output_buffer.write(buffer)


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
                p.map(partial(check_and_convert, filedir=root, **kwargs), files)
            """
            for file in files:
                check_and_convert(file, file_root=root, **kwargs)
            """
    else:
        check_and_convert(args.path, **kwargs)
