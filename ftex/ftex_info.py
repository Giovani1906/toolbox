import argparse
import io
import os
import struct

# Pixel formats:
# (ftex format ID) -- (dds dxgiFormat)
#
#  0 -- D3DFMT_A8R8G8B8
#  1 -- DXGI_FORMAT_R8_UNORM
#  2 -- BC1U ["DXT1"]
#  3 -- BC2U ["DXT3"]
#  4 -- BC3U ["DXT5"]
#  8 -- BC4U [DXGI_FORMAT_BC4_UNORM]
#  9 -- BC5U [DXGI_FORMAT_BC5_UNORM]
# 10 -- BC6H_UF16 [DXGI_FORMAT_BC6H_UF16]
# 11 -- BC7U [DXGI_FORMAT_BC7_UNORM]
# 12 -- DXGI_FORMAT_R16G16B16A16_FLOAT
# 13 -- DXGI_FORMAT_R32G32B32A32_FLOAT
# 14 -- DXGI_FORMAT_R10G10B10A2_UNORM
# 15 -- DXGI_FORMAT_R11G11B10_FLOAT
#
# Format support:
#  PES18: 0-4
#  PES19: 0-4, 8-15

# For each ftex format, stores the height and width of encoded blocks,
# and the size in bytes of each encoded block.

ftex_fmt_str = {
    0: "D3DFMT_A8R8G8B8",
    1: "DXGI_FORMAT_R8_UNORM",
    2: "DXGI_FORMAT_BC1_UNORM aka DXT1",
    3: "DXGI_FORMAT_BC2_UNORM aka DXT3",
    4: "DXGI_FORMAT_BC3_UNORM aka DXT5",
    8: "DXGI_FORMAT_BC4_UNORM",
    9: "DXGI_FORMAT_BC5_UNORM",
    10: "DXGI_FORMAT_BC6H_UF16",
    11: "DXGI_FORMAT_BC7_UNORM",
    12: "DXGI_FORMAT_R16G16B16A16_FLOAT",
    13: "DXGI_FORMAT_R32G32B32A32_FLOAT",
    14: "DXGI_FORMAT_R10G10B10A2_UNORM",
    15: "DXGI_FORMAT_R11G11B10_FLOAT",
}


class DecodeError(Exception):
    pass


class FtexHeader:
    def __init__(self, data_buffer: bytes):
        input_stream = io.BytesIO(data_buffer)
        header = bytearray(64)

        if input_stream.readinto(header) != len(header):
            raise DecodeError("Incomplete ftex header")

        (
            self.magic,
            self.version,
            self.pixel_fmt,
            self.width,
            self.height,
            self.depth,
            self.mipmap_count,
            self.nrt,
            self.flags,
            self.unknown_1,
            self.unknown_2,
            self.texture_type,
            self.ftexs_count,
            self.unknown_3,
            self.hash_1,
            self.hash_2,
        ) = struct.unpack("< 4s f HHHH  BB HIII  BB 14x  8s 8s", header)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="FTEX Info Gatherer")
    parser.add_argument("dir_path", type=str)
    parser.add_argument("--check-folder", action="store_true")
    parser.add_argument("--check-version", choices=[2.03, 2.04], type=float)
    fmt_choices = [
        "DXT1",
        "DXT3",
        "DXT5",
        "BC1",
        "BC2",
        "BC3",
        "BC4",
        "BC5",
        "BC6",
        "BC7",
        "ARGB",
    ]
    parser.add_argument("--check-format", choices=fmt_choices, default=[], nargs="*")
    args = parser.parse_args()

    if args.check_folder:
        for root, dirs, files in os.walk(args.dir_path):
            for file in files:
                if file.split(".")[-1].lower() == "ftex":
                    path = os.path.join(root, file)
                    data = open(path, "rb")
                    ftex = FtexHeader(data.read())
                    data.close()

                    if args.check_version or args.check_format:
                        ver_pass = args.check_version == round(ftex.version, 2)
                        fmt_pass = any(
                            [
                                tex_fmt in ftex_fmt_str[ftex.pixel_fmt]
                                for tex_fmt in args.check_format
                            ]
                        )
                        if not (ver_pass or fmt_pass):
                            continue

                    print(
                        f"{path}\n"
                        f"FTEX VERSION {round(ftex.version, 2)} "
                        f"FORMAT {ftex_fmt_str[ftex.pixel_fmt]}"
                    )
    else:
        data = open(args.dir_path, "rb")
        ftex = FtexHeader(data.read())
        data.close()

        if args.check_version or args.check_format:
            ver_pass = args.check_version == round(ftex.version, 2)
            fmt_pass = any(
                [
                    tex_fmt in ftex_fmt_str[ftex.pixel_fmt]
                    for tex_fmt in args.check_format
                ]
            )
            if not (ver_pass or fmt_pass):
                exit(0)

        print(
            f"{args.dir_path}\n"
            f"FTEX VERSION {round(ftex.version, 2)} "
            f"FORMAT {ftex_fmt_str[ftex.pixel_fmt]}"
        )
