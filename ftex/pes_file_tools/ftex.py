import io
import struct
import zlib

from ._zlib import try_decompress


class DecodeError(Exception):
    pass


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
fmt_blk_cfg = {
    0: (1, 4),  # D3DFMT_A8R8G8B8
    1: (1, 1),  # DXGI_FORMAT_R8_UNORM
    2: (4, 8),  # DXGI_FORMAT_BC1_UNORM ["DXT1"]
    3: (4, 16),  # DXGI_FORMAT_BC2_UNORM ["DXT3"]
    4: (4, 16),  # DXGI_FORMAT_BC3_UNORM ["DXT5"]
    8: (4, 8),  # DXGI_FORMAT_BC4_UNORM
    9: (4, 16),  # DXGI_FORMAT_BC5_UNORM
    10: (4, 16),  # DXGI_FORMAT_BC6H_UF16
    11: (4, 16),  # DXGI_FORMAT_BC7_UNORM
    12: (1, 8),  # DXGI_FORMAT_R16G16B16A16_FLOAT
    13: (1, 16),  # DXGI_FORMAT_R32G32B32A32_FLOAT
    14: (1, 4),  # DXGI_FORMAT_R10G10B10A2_UNORM
    15: (1, 4),  # DXGI_FORMAT_R11G11B10_FLOAT
}


def dds_mipmap_size(ftex_fmt, width, height, depth, mipmap_idx):
    block_size_pixels, block_size_bytes = fmt_blk_cfg[ftex_fmt]
    scale_factor = 2**mipmap_idx

    mipmap_width = max(width // scale_factor, 1)
    mipmap_height = max(height // scale_factor, 1)
    mipmap_depth = max(depth // scale_factor, 1)

    width_blocks = (mipmap_width + block_size_pixels - 1) // block_size_pixels
    height_blocks = (mipmap_height + block_size_pixels - 1) // block_size_pixels
    return width_blocks * height_blocks * mipmap_depth * block_size_bytes


def read_image_buffer(
    stream, image_offset, chunk_count, size_uncompressed, size_compressed
):
    stream.seek(image_offset, 0)

    if chunk_count == 0:
        if size_compressed == 0:
            uncompressed_buffer = bytearray(size_uncompressed)
            if stream.readinto(uncompressed_buffer) != len(uncompressed_buffer):
                raise DecodeError("Unexpected end of stream")
            return uncompressed_buffer
        else:
            compressed_buffer = bytearray(size_compressed)
            if stream.readinto(compressed_buffer) != len(compressed_buffer):
                raise DecodeError("Unexpected end of stream")
            return zlib.decompress(compressed_buffer)

    chunks = []
    for i in range(chunk_count):
        header = bytearray(8)
        if stream.readinto(header) != len(header):
            raise DecodeError("Incomplete chunk header")
        (
            size_compressed,
            size_uncompressed,
            offset,
        ) = struct.unpack("< HH I", header)
        is_compressed = size_compressed != size_uncompressed
        offset &= ~(1 << 31)

        chunks.append((offset, size_compressed, is_compressed))

    image_buffers = []
    for offset, size_compressed, is_compressed in chunks:
        stream.seek(image_offset + offset, 0)
        compressed_buffer = bytearray(size_compressed)
        if stream.readinto(compressed_buffer) != len(compressed_buffer):
            raise DecodeError("Unexpected end of stream")
        if is_compressed:
            try:
                decompressed_buffer = zlib.decompress(compressed_buffer)
            except zlib.error:
                raise DecodeError("Decompression error")
        else:
            decompressed_buffer = compressed_buffer
        image_buffers.append(decompressed_buffer)
    return b"".join(image_buffers)


def ftex_to_dds_buffer(ftex_buffer):
    input_stream = io.BytesIO(ftex_buffer)

    header = bytearray(64)
    if input_stream.readinto(header) != len(header):
        raise DecodeError("Incomplete ftex header")

    (
        ftex_magic,
        ftex_version,
        ftex_pixel_fmt,
        ftex_width,
        ftex_height,
        ftex_depth,
        ftex_mipmap_count,
        ftex_nrt,
        ftex_flags,
        ftex_unknown1,
        ftex_unknown2,
        ftex_texture_type,
        ftex_ftexs_count,
        ftex_unknown3,
        ftex_hash1,
        ftex_hash2,
    ) = struct.unpack("< 4s f HHHH  BB HIII  BB 14x  8s 8s", header)

    if ftex_magic != b"FTEX":
        raise DecodeError("Incorrect ftex signature")

    if ftex_version < 2.025:
        raise DecodeError("Unsupported ftex version")
    if ftex_version > 2.045:
        raise DecodeError("Unsupported ftex version")
    if ftex_ftexs_count > 0:
        raise DecodeError("Unsupported ftex variant")
    if ftex_mipmap_count == 0:
        raise DecodeError("Unsupported ftex variant")

    dds_flags = (
        0x1  # capabilities
        | 0x2  # height
        | 0x4  # width
        | 0x1000  # pixel format
    )
    dds_capabilities1 = 0x1000  # texture
    dds_capabilities2 = 0

    if (ftex_texture_type & 4) != 0:
        # Cube map, with six faces
        if ftex_depth > 1:
            raise DecodeError("Unsupported ftex variant")
        image_count = 6
        dds_depth = 1
        dds_capabilities1 |= 0x8  # complex
        dds_capabilities2 |= 0xFE00  # cube map with six faces

        dds_extension_dimension = 3  # 2D
        dds_extension_flags = 0x4  # cube map
    elif ftex_depth > 1:
        # Volume texture
        image_count = 1
        dds_depth = ftex_depth
        dds_flags |= 0x800000  # depth
        dds_capabilities2 |= 0x200000  # volume texture

        dds_extension_dimension = 4  # 3D
        dds_extension_flags = 0
    else:
        # Regular 2D texture
        image_count = 1
        dds_depth = 1

        dds_extension_dimension = 3  # 2D
        dds_extension_flags = 0

    dds_mipmap_count = ftex_mipmap_count
    mipmap_count = ftex_mipmap_count
    dds_flags |= 0x20000  # mipmapCount
    dds_capabilities1 |= 0x8  # complex
    dds_capabilities1 |= 0x400000  # mipmap

    # A frame is a byte array containing a single mipmap element of a single image.
    # Cube maps have six images with mipmaps, and so 6 * $mipmapCount frames.
    # Other textures just have $mipmapCount frames.
    frame_specifications = []
    for i in range(image_count):
        for j in range(mipmap_count):
            mipmap_header = bytearray(16)
            if input_stream.readinto(mipmap_header) != len(mipmap_header):
                raise DecodeError("Incomplete mipmap header")
            (
                offset,
                size_uncompressed,
                size_compressed,
                index,
                ftexs_number,
                chunk_count,
            ) = struct.unpack("< I I I BB H", mipmap_header)
            if index != j:
                raise DecodeError("Unexpected mipmap")

            frame_expected_size = dds_mipmap_size(
                ftex_pixel_fmt, ftex_width, ftex_height, dds_depth, j
            )
            frame_specifications.append(
                (
                    offset,
                    chunk_count,
                    size_uncompressed,
                    size_compressed,
                    frame_expected_size,
                )
            )

    frames = []
    for (
        offset,
        chunk_count,
        size_uncompressed,
        size_compressed,
        size_expected,
    ) in frame_specifications:
        frame = read_image_buffer(
            input_stream, offset, chunk_count, size_uncompressed, size_compressed
        )
        if len(frame) < size_expected:
            frame += bytes(size_expected - len(frame))
        elif len(frame) > size_expected:
            frame = frame[0:size_expected]
        frames.append(frame)

    if ftex_pixel_fmt == 0:
        dds_pitch_or_linear_size = 4 * ftex_width
        dds_flags |= 0x8  # pitch
        use_extension_header = False

        dds_format_flags = 0x41  # uncompressed rgba
        dds_four_cc = b"\0\0\0\0"
        dds_extension_format = None
        dds_rgb_bit_count = 32
        dds_r_bit_mask = 0x00FF0000
        dds_g_bit_mask = 0x0000FF00
        dds_b_bit_mask = 0x000000FF
        dds_a_bit_mask = 0xFF000000
    else:
        dds_pitch_or_linear_size = len(frames[0])
        dds_flags |= 0x80000  # linear size

        dds_format_flags = 0x4  # compressed
        dds_rgb_bit_count = 0
        dds_r_bit_mask = 0
        dds_g_bit_mask = 0
        dds_b_bit_mask = 0
        dds_a_bit_mask = 0

        dds_four_cc = None
        dds_extension_format = None

        match ftex_pixel_fmt:
            case 1:
                dds_extension_format = 61  # DXGI_FORMAT_R8_UNORM
            case 2:
                dds_four_cc = b"DXT1"
            case 3:
                dds_four_cc = b"DXT3"
            case 4:
                dds_four_cc = b"DXT5"
            case 8:
                dds_extension_format = 80  # DXGI_FORMAT_BC4_UNORM
            case 9:
                dds_extension_format = 83  # DXGI_FORMAT_BC5_UNORM
            case 10:
                dds_extension_format = 95  # DXGI_FORMAT_BC6H_UF16
            case 11:
                dds_extension_format = 98  # DXGI_FORMAT_BC7_UNORM
            case 12:
                dds_extension_format = 10  # DXGI_FORMAT_R16G16B16A16_FLOAT
            case 13:
                dds_extension_format = 2  # DXGI_FORMAT_R32G32B32A32_FLOAT
            case 14:
                dds_extension_format = 24  # DXGI_FORMAT_R10G10B10A2_UNORM
            case 15:
                dds_extension_format = 26  # DXGI_FORMAT_R11G11B10_FLOAT
            case _:
                raise DecodeError("Unsupported ftex codec")

        if dds_extension_format is not None:
            dds_four_cc = b"DX10"
            use_extension_header = True
        else:
            use_extension_header = False

    output_stream = io.BytesIO()
    output_stream.write(
        struct.pack(
            "< 4s 7I 44x 2I 4s 5I 2I 12x",
            b"DDS ",
            124,  # header size
            dds_flags,
            ftex_height,
            ftex_width,
            dds_pitch_or_linear_size,
            dds_depth,
            dds_mipmap_count,
            32,  # substructure size
            dds_format_flags,
            dds_four_cc,
            dds_rgb_bit_count,
            dds_r_bit_mask,
            dds_g_bit_mask,
            dds_b_bit_mask,
            dds_a_bit_mask,
            dds_capabilities1,
            dds_capabilities2,
        )
    )

    if use_extension_header:
        output_stream.write(
            struct.pack(
                "< 5I",
                dds_extension_format,
                dds_extension_dimension,
                dds_extension_flags,
                1,  # array size
                0,  # flags
            )
        )

    for frame in frames:
        output_stream.write(frame)

    return output_stream.getvalue()


def ftex_to_dds(ftex_filename, dds_filename):
    with open(ftex_filename, "rb") as input_stream:
        input_buffer = input_stream.read()

    output_buffer = ftex_to_dds_buffer(input_buffer)

    with open(dds_filename, "wb") as outputStream:
        outputStream.write(output_buffer)


def encode_image(data):
    chunk_size = 1 << 14  # Value known not to crash PES
    chunk_count = (len(data) + chunk_size - 1) // chunk_size

    header_buffer = bytearray()
    chunk_buffer = bytearray()
    chunk_buffer_offset = chunk_count * 8

    for i in range(chunk_count):
        chunk = data[chunk_size * i : chunk_size * (i + 1)]
        compressed_chunk = zlib.compress(chunk, level=9)
        offset = len(chunk_buffer)
        chunk_buffer += compressed_chunk
        header_buffer += struct.pack(
            "< HHI",
            len(compressed_chunk),
            len(chunk),
            offset + chunk_buffer_offset,
        )

    output = header_buffer + chunk_buffer
    if len(output) % 8 > 0:
        output += bytearray(8 - len(output) % 8)

    return output, chunk_count


def dds_to_ftex_buffer(dds_buffer: bytes, color_space: str) -> bytes:
    input_stream = io.BytesIO(dds_buffer)

    header = bytearray(128)
    if input_stream.readinto(header) != len(header):
        raise DecodeError("Incomplete dds header")

    (
        dds_magic,
        dds_header_size,
        dds_flags,
        dds_height,
        dds_width,
        dds_pitch_or_linear_size,
        dds_depth,
        dds_mipmap_count,
        # ddsReserved,
        dds_pixel_format_size,
        dds_format_flags,
        dds_four_cc,
        dds_rgb_bit_count,
        dds_r_bit_mask,
        dds_g_bit_mask,
        dds_b_bit_mask,
        dds_a_bit_mask,
        dds_capabilities1,
        dds_capabilities2,
        # ddsReserved,
    ) = struct.unpack("< 4s 7I 44x 2I 4s 5I 2I 12x", header)

    if dds_magic != b"DDS ":
        raise DecodeError("Incorrect dds signature")
    if dds_header_size != 124:
        raise DecodeError("Incorrect dds header")

    if (
        (dds_capabilities1 & 0x400000) > 0  # mipmap
        and (dds_mipmap_count > 1)
    ):
        mipmap_count = dds_mipmap_count
    else:
        mipmap_count = 1

    if dds_capabilities2 & 0x200 > 0:  # cubemap
        if dds_capabilities2 & 0xFE00 != 0xFE00:
            raise DecodeError("Incomplete dds cube maps not supported")
        is_cube_map = True
        cube_entries = 6
    else:
        is_cube_map = False
        cube_entries = 1

    if dds_capabilities2 & 0x200000 > 0:  # volume texture
        depth = dds_depth
    else:
        depth = 1

    if is_cube_map and depth > 1:
        raise DecodeError("Invalid dds combination: cube map and volume map both set")

    match color_space:
        case "LINEAR":
            ftex_texture_type = 0x1
        case "SRGB":
            ftex_texture_type = 0x3
        case "NORMAL":
            ftex_texture_type = 0x9
        case _:
            ftex_texture_type = 0x9

    if is_cube_map:
        ftex_texture_type |= 0x4

    if dds_format_flags & 0x4 == 0:  # fourCC absent
        if all(
            [
                (dds_format_flags & 0x40) > 0,  # rgb
                (dds_format_flags & 0x1) > 0,  # alpha
                dds_r_bit_mask == 0x00FF0000,
                dds_g_bit_mask == 0x0000FF00,
                dds_b_bit_mask == 0x000000FF,
                dds_a_bit_mask == 0xFF000000,
            ]
        ):
            ftex_pixel_format = 0
        else:
            raise DecodeError("Unsupported dds codec")
    else:
        match dds_four_cc:
            case b"DX10":
                extension_header = bytearray(20)
                if input_stream.readinto(extension_header) != len(extension_header):
                    raise DecodeError("Incomplete dds extension header")

                (
                    dds_extension_format,
                    # ddsOther,
                ) = struct.unpack("< I 16x", extension_header)

                dds_to_ftex_format = {
                    61: 1,  # DXGI_FORMAT_R8_UNORM
                    71: 2,  # DXGI_FORMAT_BC1_UNORM ["DXT1"]
                    74: 3,  # DXGI_FORMAT_BC2_UNORM ["DXT3"]
                    77: 4,  # DXGI_FORMAT_BC3_UNORM ["DXT5"]
                    80: 8,  # DXGI_FORMAT_BC4_UNORM
                    83: 9,  # DXGI_FORMAT_BC5_UNORM
                    95: 10,  # DXGI_FORMAT_BC6H_UF16
                    98: 11,  # DXGI_FORMAT_BC7_UNORM
                    10: 12,  # DXGI_FORMAT_R16G16B16A16_FLOAT
                    1: 13,  # DXGI_FORMAT_R32G32B32A32_FLOAT
                    24: 14,  # DXGI_FORMAT_R10G10B10A2_UNORM
                    26: 15,  # DXGI_FORMAT_R11G11B10_FLOAT
                }

                if not (
                    ftex_pixel_format := dds_to_ftex_format.get(dds_extension_format)
                ):
                    raise DecodeError("Unsupported dds codec")
            case b"8888":
                ftex_pixel_format = 0
            case b"DXT1":
                ftex_pixel_format = 2
            case b"DXT3":
                ftex_pixel_format = 3
            case b"DXT5":
                ftex_pixel_format = 4
            case _:
                raise DecodeError("Unsupported dds codec")

    if ftex_pixel_format > 4:
        ftex_version = 2.04
    else:
        ftex_version = 2.03

    frame_buffer = bytearray()
    mipmap_entries = []
    for _ in range(cube_entries):
        for mipmap_index in range(mipmap_count):
            length = dds_mipmap_size(
                ftex_pixel_format, dds_width, dds_height, depth, mipmap_index
            )
            frame = input_stream.read(length)
            if len(frame) != length:
                raise DecodeError("Unexpected end of dds stream")

            frame_offset = len(frame_buffer)
            (compressed_frame, chunk_count) = encode_image(frame)
            frame_buffer += compressed_frame
            mipmap_entries.append(
                (
                    frame_offset,
                    len(frame),
                    len(compressed_frame),
                    mipmap_index,
                    chunk_count,
                )
            )

    mipmap_buffer = bytearray()
    mipmap_buffer_offset = 64
    frame_buffer_offset = mipmap_buffer_offset + len(mipmap_entries) * 16
    for (
        relative_frame_offset,
        size_uncompressed,
        size_compressed,
        mipmap_index,
        chunk_count,
    ) in mipmap_entries:
        mipmap_buffer += struct.pack(
            "< III BB H",
            relative_frame_offset + frame_buffer_offset,
            size_uncompressed,
            size_compressed,
            mipmap_index,
            0,  # ftexs number
            chunk_count,
        )

    header = struct.pack(
        "< 4s f HHHH  BB HIII  BB 14x  16x",
        b"FTEX",
        ftex_version,
        ftex_pixel_format,
        dds_width,
        dds_height,
        depth,
        mipmap_count,
        0x02,  # nrt flag, meaning unknown
        0x11,  # unknown flags
        1,  # unknown
        0,  # unknown
        ftex_texture_type,
        0,  # ftexs count
        0,  # unknown
        # 14 bytes padding
        # 16 bytes hashes
    )

    return header + mipmap_buffer + frame_buffer


def dds_to_ftex(dds_filename, ftex_filename, color_space):
    with open(dds_filename, "rb") as input_stream:
        input_buffer = input_stream.read()

    output_buffer = dds_to_ftex_buffer(try_decompress(input_buffer), color_space)

    with open(ftex_filename, "wb") as output_stream:
        output_stream.write(output_buffer)
