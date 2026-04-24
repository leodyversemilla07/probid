"""Legacy ANSI + Kitty key parsing and input splitting."""

from __future__ import annotations

LEGACY_KEYS: dict[bytes, str] = {
    b"\x1b[A": "up",
    b"\x1b[B": "down",
    b"\x1b[C": "right",
    b"\x1b[D": "left",
    b"\x1b[H": "home",
    b"\x1b[F": "end",
    b"\x1b[2~": "insert",
    b"\x1b[3~": "delete",
    b"\x1b[5~": "page_up",
    b"\x1b[6~": "page_down",
    b"\x7f": "backspace",
    b"\x08": "ctrl+h",
    b"\x1b": "escape",
    b"\r": "enter",
    b"\n": "enter",
    b"\t": "tab",
    b"\x1b[Z": "shift+tab",
    b"\x1bOP": "f1",
    b"\x1bOQ": "f2",
    b"\x1bOR": "f3",
    b"\x1bOS": "f4",
}

for i in range(1, 27):  # ctrl+a ... ctrl+z
    raw = bytes([i])
    if raw not in LEGACY_KEYS:
        LEGACY_KEYS[raw] = f"ctrl+{chr(i + 96)}"

KeyId = str
KeyEventType = str  # "press" | "repeat" | "release"
_kitty_protocol_active = False


def set_kitty_protocol_active(active: bool) -> None:
    global _kitty_protocol_active
    _kitty_protocol_active = bool(active)


def is_kitty_protocol_active() -> bool:
    return _kitty_protocol_active


class Key:
    escape = "escape"
    esc = "esc"
    enter = "enter"
    tab = "tab"
    space = "space"
    backspace = "backspace"
    delete = "delete"
    home = "home"
    end = "end"
    pageUp = "page_up"
    pageDown = "page_down"
    up = "up"
    down = "down"
    left = "left"
    right = "right"
    f1 = "f1"
    f2 = "f2"
    f3 = "f3"
    f4 = "f4"

    @staticmethod
    def ctrl(key: str) -> str:
        return f"ctrl+{key}"

    @staticmethod
    def shift(key: str) -> str:
        return f"shift+{key}"

    @staticmethod
    def alt(key: str) -> str:
        return f"alt+{key}"

    @staticmethod
    def super(key: str) -> str:
        return f"super+{key}"

    @staticmethod
    def ctrlShift(key: str) -> str:
        return f"ctrl+shift+{key}"

    @staticmethod
    def ctrlAlt(key: str) -> str:
        return f"ctrl+alt+{key}"


def is_key_release(data: bytes | str) -> bool:
    raw = _to_bytes(data)
    return b":3u" in raw or b":3~" in raw


def is_key_repeat(data: bytes | str) -> bool:
    raw = _to_bytes(data)
    return b":2u" in raw or b":2~" in raw


def _utf8_char_len(first_byte: int) -> int:
    if first_byte < 0x80:
        return 1
    if (first_byte & 0xE0) == 0xC0:
        return 2
    if (first_byte & 0xF0) == 0xE0:
        return 3
    if (first_byte & 0xF8) == 0xF0:
        return 4
    return 1


def split_input_sequences(data: bytes) -> list[bytes]:
    out: list[bytes] = []
    i = 0
    n = len(data)

    while i < n:
        if data.startswith(b"\x1b[200~", i):
            end = data.find(b"\x1b[201~", i + 6)
            if end == -1:
                out.append(data[i:])
                break
            out.append(data[i : end + 6])
            i = end + 6
            continue

        b0 = data[i]
        if b0 == 0x1B:
            if i + 1 < n and data[i + 1] == ord("["):
                j = i + 2
                while j < n and not (0x40 <= data[j] <= 0x7E):
                    j += 1
                if j < n:
                    out.append(data[i : j + 1])
                    i = j + 1
                    continue
                out.append(data[i:])
                break

            if i + 2 < n and data[i + 1] == ord("O"):
                out.append(data[i : i + 3])
                i += 3
                continue

            if i + 1 < n:
                out.append(data[i : i + 2])
                i += 2
                continue

            out.append(data[i : i + 1])
            i += 1
            continue

        clen = _utf8_char_len(b0)
        if i + clen <= n:
            out.append(data[i : i + clen])
            i += clen
        else:
            out.append(data[i:])
            break

    return out


def _to_bytes(data: bytes | str) -> bytes:
    return data.encode("utf-8", errors="replace") if isinstance(data, str) else data


def parse_key(data: bytes | str) -> str | None:
    raw = _to_bytes(data)
    if raw in LEGACY_KEYS:
        return LEGACY_KEYS[raw]

    if len(raw) == 2 and raw[0] == 0x1B and raw[1] >= 32:
        try:
            return f"alt+{bytes([raw[1]]).decode('utf-8', errors='replace')}"
        except Exception:
            return None

    # Kitty CSI-u: ESC[codepoint;mods(:event)?u
    if raw.startswith(b"\x1b[") and raw.endswith(b"u"):
        try:
            inner = raw[2:-1].decode("ascii", errors="replace")
            parts = inner.split(";")
            codepoint = int(parts[0].split(":")[0]) if parts and parts[0] else 0

            modifier_part = parts[1] if len(parts) > 1 else "1"
            modifier_base = modifier_part.split(":")[0]
            modifiers = int(modifier_base) - 1 if modifier_base.isdigit() else 0

            shift = bool(modifiers & 1)
            alt = bool(modifiers & 2)
            ctrl = bool(modifiers & 4)
            sup = bool(modifiers & 8)

            if 32 <= codepoint < 127:
                name = chr(codepoint).lower()
            elif codepoint == 13:
                name = "enter"
            elif codepoint == 9:
                name = "tab"
            elif codepoint == 27:
                name = "escape"
            else:
                name = str(codepoint)

            prefix = (
                ("ctrl+" if ctrl else "")
                + ("alt+" if alt else "")
                + ("shift+" if shift else "")
                + ("super+" if sup else "")
            )
            return prefix + name
        except Exception:
            return None

    if len(raw) >= 1 and all(ch >= 32 for ch in raw):
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None

    return None


def decode_kitty_printable(data: bytes | str) -> str | None:
    key = parse_key(data)
    if not key:
        return None
    # Strip modifiers; printable when resulting key is single char.
    base = key.split("+")[-1]
    return base if len(base) == 1 else None


def matches_key(data: bytes | str, key_id: str) -> bool:
    return parse_key(data) == key_id


# pi-tui style aliases
setKittyProtocolActive = set_kitty_protocol_active
isKittyProtocolActive = is_kitty_protocol_active
isKeyRelease = is_key_release
isKeyRepeat = is_key_repeat
parseKey = parse_key
decodeKittyPrintable = decode_kitty_printable
matchesKey = matches_key
