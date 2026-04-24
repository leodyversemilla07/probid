"""Terminal image helpers (Kitty/iTerm2 + fallback)."""

from __future__ import annotations

import base64
import os
import struct
from dataclasses import dataclass

ImageProtocol = str | None  # "kitty" | "iterm2" | None


@dataclass(frozen=True)
class TerminalCapabilities:
    protocol: ImageProtocol
    supports_images: bool


@dataclass(frozen=True)
class CellDimensions:
    width_px: int
    height_px: int


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class ImageRenderOptions:
    image_id: int | None = None
    width_cells: int | None = None
    height_cells: int | None = None
    filename: str | None = None


_cell_dimensions = CellDimensions(width_px=8, height_px=16)
_capabilities_cache: TerminalCapabilities | None = None
_next_image_id = 1


def get_cell_dimensions() -> CellDimensions:
    return _cell_dimensions


def set_cell_dimensions(dims: CellDimensions) -> None:
    global _cell_dimensions
    _cell_dimensions = dims


def detect_capabilities() -> TerminalCapabilities:
    term = (os.environ.get("TERM", "") or "").lower()
    term_program = (os.environ.get("TERM_PROGRAM", "") or "").lower()
    if "kitty" in term or "wezterm" in term or "ghostty" in term:
        return TerminalCapabilities(protocol="kitty", supports_images=True)
    if term_program == "iterm.app":
        return TerminalCapabilities(protocol="iterm2", supports_images=True)
    return TerminalCapabilities(protocol=None, supports_images=False)


def get_capabilities() -> TerminalCapabilities:
    global _capabilities_cache
    if _capabilities_cache is None:
        _capabilities_cache = detect_capabilities()
    return _capabilities_cache


def reset_capabilities_cache() -> None:
    global _capabilities_cache
    _capabilities_cache = None


def is_image_line(line: str) -> bool:
    return "\x1b_G" in line or "1337;File=" in line


def allocate_image_id() -> int:
    global _next_image_id
    image_id = _next_image_id
    _next_image_id += 1
    return image_id


def encode_kitty(
    base64_data: str,
    mime_type: str,
    image_id: int,
    width_cells: int | None = None,
    height_cells: int | None = None,
) -> str:
    width = f",c={width_cells}" if width_cells else ""
    height = f",r={height_cells}" if height_cells else ""
    _ = mime_type
    return f"\x1b_Ga=T,f=100,i={image_id}{width}{height};{base64_data}\x1b\\"


def delete_kitty_image(image_id: int) -> str:
    return f"\x1b_Ga=d,i={image_id}\x1b\\"


def delete_all_kitty_images() -> str:
    return "\x1b_Ga=d,d=A\x1b\\"


def encode_iterm2(base64_data: str, mime_type: str, filename: str | None = None) -> str:
    _ = mime_type
    name = base64.b64encode((filename or "image").encode("utf-8")).decode("ascii")
    return f"\x1b]1337;File=name={name};inline=1:{base64_data}\x07"


def calculate_image_rows(height_px: int, cell_height_px: int | None = None) -> int:
    cell_h = cell_height_px or _cell_dimensions.height_px
    return max(1, (height_px + max(1, cell_h) - 1) // max(1, cell_h))


def _safe_b64decode(base64_data: str) -> bytes | None:
    try:
        return base64.b64decode(base64_data, validate=False)
    except Exception:
        return None


def get_png_dimensions(base64_data: str) -> ImageDimensions | None:
    data = _safe_b64decode(base64_data)
    if not data or len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return ImageDimensions(width=width, height=height)


def get_jpeg_dimensions(base64_data: str) -> ImageDimensions | None:
    data = _safe_b64decode(base64_data)
    if not data or len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in {0xC0, 0xC2}:  # SOF0 / SOF2
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return ImageDimensions(width=w, height=h)
        if i + 4 > len(data):
            return None
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + seg_len
    return None


def get_gif_dimensions(base64_data: str) -> ImageDimensions | None:
    data = _safe_b64decode(base64_data)
    if not data or len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        return None
    width, height = struct.unpack("<HH", data[6:10])
    return ImageDimensions(width=width, height=height)


def get_webp_dimensions(base64_data: str) -> ImageDimensions | None:
    data = _safe_b64decode(base64_data)
    if not data or len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        w = 1 + int.from_bytes(data[24:27], "little") & 0x3FFF
        h = 1 + int.from_bytes(data[27:30], "little") & 0x3FFF
        return ImageDimensions(width=w, height=h)
    return None


def get_image_dimensions(base64_data: str, mime_type: str) -> ImageDimensions | None:
    mt = (mime_type or "").lower()
    if "png" in mt:
        return get_png_dimensions(base64_data)
    if "jpeg" in mt or "jpg" in mt:
        return get_jpeg_dimensions(base64_data)
    if "gif" in mt:
        return get_gif_dimensions(base64_data)
    if "webp" in mt:
        return get_webp_dimensions(base64_data)
    return None


def image_fallback(
    mime_type: str,
    dimensions: ImageDimensions | None = None,
    filename: str | None = None,
) -> str:
    dim = f" {dimensions.width}x{dimensions.height}" if dimensions else ""
    name = f" {filename}" if filename else ""
    return f"[image{dim}{name} {mime_type}]"


def render_image(
    base64_data: str,
    mime_type: str,
    options: ImageRenderOptions | None = None,
) -> str:
    options = options or ImageRenderOptions()
    caps = get_capabilities()
    image_id = options.image_id or allocate_image_id()
    if caps.protocol == "kitty":
        return encode_kitty(base64_data, mime_type, image_id, options.width_cells, options.height_cells)
    if caps.protocol == "iterm2":
        return encode_iterm2(base64_data, mime_type, options.filename)
    dims = get_image_dimensions(base64_data, mime_type)
    return image_fallback(mime_type, dims, options.filename)


# pi-tui style aliases
getCellDimensions = get_cell_dimensions
setCellDimensions = set_cell_dimensions
detectCapabilities = detect_capabilities
getCapabilities = get_capabilities
resetCapabilitiesCache = reset_capabilities_cache
isImageLine = is_image_line
allocateImageId = allocate_image_id
encodeKitty = encode_kitty
deleteKittyImage = delete_kitty_image
deleteAllKittyImages = delete_all_kitty_images
encodeITerm2 = encode_iterm2
calculateImageRows = calculate_image_rows
getPngDimensions = get_png_dimensions
getJpegDimensions = get_jpeg_dimensions
getGifDimensions = get_gif_dimensions
getWebpDimensions = get_webp_dimensions
getImageDimensions = get_image_dimensions
renderImage = render_image
imageFallback = image_fallback
