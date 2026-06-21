import array
import fcntl
import math
import os
import sys
import termios
from contextlib import contextmanager

from PIL import Image

from kitcat.terminal_query import get_dpi_scale

# Fallback cell size (in pixels) used when the terminal doesn't report its
# pixel dimensions — e.g. inside tmux or over SSH, where ws_xpixel/ws_ypixel
# come back 0. A non-HiDPI cell at a typical 2:1 monospace aspect ratio.
_FALLBACK_CELL_HEIGHT = 16
_FALLBACK_CELL_WIDTH = 8


def _in_tmux() -> bool:
    """Whether we're running inside a tmux session."""
    return "TMUX" in os.environ


def get_char_cell_height() -> int:
    """Height of a single terminal cell in pixels.

    Read from the terminal via TIOCGWINSZ when it reports pixel sizes;
    otherwise a DPI-scaled fallback (see the fallback branch below).
    https://sw.kovidgoyal.net/kitty/graphics-protocol/#getting-the-window-size
    """
    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    num_rows, _, _, screen_height = buf
    if num_rows and screen_height:
        return int(screen_height // num_rows)
    # ws_ypixel often 0 over SSH or in terminals that don't report pixel
    # sizes; fall back to a reasonable default rather than dividing by zero.
    # The image is rendered at the terminal's device-pixel ratio, so scale the
    # fallback cell by the same factor — otherwise the placeholder grid
    # (image_px / cell_px) is inflated by the DPI scale and overflows the pane.
    return round(_FALLBACK_CELL_HEIGHT * get_dpi_scale())


def get_char_cell_width() -> int:
    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    _, num_cols, screen_width, _ = buf
    if num_cols and screen_width:
        return int(screen_width // num_cols)
    # ws_xpixel is often 0 (e.g. inside tmux or over SSH). Approximate from the
    # fallback cell width, scaled by the device-pixel ratio (see the height
    # fallback above for why the scaling matters).
    return max(round(_FALLBACK_CELL_WIDTH * get_dpi_scale()), 1)


def num_required_lines(img_buf):
    with Image.open(img_buf) as img:
        _, img_height = img.size
        img_buf.seek(0)

    return math.ceil(img_height / get_char_cell_height())


def num_required_cols(img_buf):
    with Image.open(img_buf) as img:
        img_width, _ = img.size
        img_buf.seek(0)

    return math.ceil(img_width / get_char_cell_width())


def send_sequence(payload: str) -> None:
    r"""Write a single escape sequence to stdout.

    Inside tmux, wraps `payload` in one tmux passthrough DCS (`\ePtmux;…\e\\`)
    with internal ESC bytes doubled, so the bytes reach the outer terminal
    verbatim (requires `allow-passthrough on` in tmux config). Outside tmux,
    writes the payload as-is.

    Pass exactly one sequence. For a chunked image, use `send_sequences` —
    concatenating chunks into a single envelope fails to render in tmux once
    the image grows past a few chunks.
    """
    if _in_tmux():
        inner = payload.replace("\033", "\033\033")
        sys.stdout.write(f"\033Ptmux;{inner}\033\\")
    else:
        sys.stdout.write(payload)


def send_sequences(sequences) -> None:
    r"""Write several escape sequences, each through its own passthrough.

    Inside tmux, every sequence gets its OWN ``\ePtmux;…\e\\`` envelope.
    Wrapping a whole multi-chunk image in a single envelope fails once it
    grows past a few chunks (the image silently doesn't render); per-chunk
    envelopes are what kitty's own ``icat`` does and they work at any size.
    Outside tmux this is just back-to-back writes.
    """
    for sequence in sequences:
        send_sequence(sequence)


@contextmanager
def reserve_image_rows(n: int):
    """Inside tmux: reserve `n` rows below the cursor and advance past them
    on exit, so an image drawn at the cursor position isn't overwritten by
    later text. tmux can't see the image, so its own cursor model wouldn't
    naturally advance. No-op outside tmux."""
    if not _in_tmux() or n <= 0:
        yield
        return
    sys.stdout.write("\n" * n)
    sys.stdout.write(f"\033[{n}F")
    try:
        yield
    finally:
        sys.stdout.write(f"\033[{n}E")
