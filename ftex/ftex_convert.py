import argparse
import copy
import os
import sys
from subprocess import PIPE, Popen, check_output

from ftex_info import fmt_choices, ftex_check, ftex_fmt_str, FtexHeader
from lib.ftex import dds_to_ftex_buffer, ftex_to_dds_buffer


def check_and_convert(
    filename: str,
    chk_fmt: str,
    chk_ver: float,
    conv_fmt: str,
    conv_ver: float,
    dont_preserve_original: bool,
    keep_dds_file: bool,
    filedir: str = None,
) -> str | None:
    if filename.split(".")[-1].lower() != "ftex":
        return

    if filedir:
        path = os.path.join(filedir, filename)
    else:
        path = filename
        filedir = os.path.dirname(filename)

    with open(path, "rb") as input_buffer:
        buffer = input_buffer.read()

    chk_fmt = [chk_fmt] if chk_fmt else []
    if not (ftex := ftex_check(buffer, chk_fmt, chk_ver)):
        return

    if not conv_fmt and conv_ver != round(ftex.version, 2):
        ftex203 = b"\x85\xeb\x01@"
        ftex204 = b"\\\x8f\x02@"
        match conv_ver:
            case 2.03:
                buffer_conv = buffer.replace(ftex204, ftex203)
            case 2.04:
                buffer_conv = buffer.replace(ftex203, ftex204)
            case _:
                return

        if not dont_preserve_original:
            os.rename(path, path.replace(".ftex", "_old.ftex"))

        with open(path, "wb") as output_buffer:
            output_buffer.write(buffer_conv)
    else:
        dds_buffer = ftex_to_dds_buffer(buffer)
        match conv_fmt:
            case "BC1":
                conv_fmt = "DXT1"
            case "BC2":
                conv_fmt = "DXT3"
            case "BC3":
                conv_fmt = "DXT5"

        if sys.platform == "win32":
            dds_path = path.replace(".ftex", "_tmp.dds")
            with open(dds_path, "wb") as df:
                df.write(dds_buffer)

            cmd = [
                os.path.join("bin", "texconv.exe"),
                "-f",
                conv_fmt,
                "-y",
                "-o",
                filedir,
                dds_path,
            ]
            check_output(cmd)

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
                f"dds:compression={conv_fmt.lower()}",
                "-",
                "-",
            ]
            proc = Popen(
                cmd,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
            )
            dds_converted_buffer, p_err = proc.communicate(dds_buffer)

            if p_err:
                raise Exception(p_err.decode("utf-8"))

        if not dont_preserve_original:
            os.rename(path, path.replace(".ftex", "_old.ftex"))

        buffer_conv = dds_to_ftex_buffer(dds_converted_buffer)

        if conv_ver != round(ftex.version, 2):
            ftex203 = b"\x85\xeb\x01@"
            ftex204 = b"\\\x8f\x02@"
            match conv_ver:
                case 2.03:
                    buffer_conv = buffer_conv.replace(ftex204, ftex203)
                case 2.04:
                    buffer_conv = buffer_conv.replace(ftex203, ftex204)

        with open(path, "wb") as output_buffer:
            output_buffer.write(buffer_conv)

    ftex_conv = FtexHeader(buffer_conv)

    return (
        f"Converting: {filename}\n"
        f"FTEX VERSION {round(ftex.version, 2)} "
        f"FORMAT {ftex_fmt_str[ftex.pixel_fmt]} > "
        f"FTEX VERSION {round(ftex_conv.version, 2)} "
        f"FORMAT {ftex_fmt_str[ftex_conv.pixel_fmt]}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="FTEX Mass Converter")
    parser.add_argument("path")
    parser.add_argument("--check-for-format", dest="chk_fmt", choices=fmt_choices)
    parser.add_argument("--convert-to-format", dest="conv_fmt", choices=fmt_choices)
    parser.add_argument(
        "--check-for-version", dest="chk_ver", choices=[2.03, 2.04], type=float
    )
    parser.add_argument(
        "--convert-to-version", dest="conv_ver", choices=[2.03, 2.04], type=float
    )
    parser.add_argument("--dont-preserve-original", action="store_true")
    parser.add_argument("--keep-dds-file", action="store_true")
    args = parser.parse_args()

    if not (args.conv_fmt or args.conv_ver):
        print("No conversion flags specified.\nExiting...")
        exit(1)
    if args.conv_ver == 2.03 and args.conv_fmt in fmt_choices[6:-1]:
        print(f"{args.conv_fmt} is not compatible with FTEX {args.conv_ver}.")
        exit(1)
    if sys.platform != "win32":
        if args.conv_fmt and check_output(["whereis", "convert"]) == b"convert:\n":
            print("ImageMagick has not been found...")
            print("Please install it with your package manager.")
            exit(1)
        if args.conv_fmt in fmt_choices[6:-1]:
            print("Conversion to BC4, BC5, BC6 and BC7 is not supported on GNU/Linux.")
            exit(1)

    kwargs = copy.copy(vars(args))
    del kwargs["path"]

    if os.path.isdir(args.path):
        for root, dirs, files in os.walk(args.path):
            for file in files:
                if result := check_and_convert(file, filedir=root, **kwargs):
                    print(result)
    else:
        if result := check_and_convert(args.path, **kwargs):
            print(result)
