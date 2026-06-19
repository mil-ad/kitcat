import array
import fcntl
import math
import os
import sys
import termios
from contextlib import contextmanager

from PIL import Image


def get_char_cell_height() -> int:
    """Source https://sw.kovidgoyal.net/kitty/graphics-protocol/#getting-the-window-size"""

    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    num_rows, _, _, screen_height = buf
    if num_rows and screen_height:
        return int(screen_height // num_rows)
    # ws_ypixel often 0 over SSH or in terminals that don't report pixel
    # sizes; fall back to a reasonable default rather than dividing by zero.
    return 16


def get_char_cell_width() -> int:
    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    _, num_cols, screen_width, _ = buf
    if num_cols and screen_width:
        return int(screen_width // num_cols)
    # ws_xpixel is often 0 (e.g. inside tmux or over SSH). Approximate from
    # cell height assuming a typical 2:1 monospace aspect ratio.
    return max(get_char_cell_height() // 2, 1)


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
    r"""Write escape codes to stdout.

    Inside tmux, wraps `payload` in a tmux passthrough DCS (`\ePtmux;…\e\\`)
    with internal ESC bytes doubled, so the bytes reach the outer terminal
    verbatim (requires `allow-passthrough on` in tmux config). Outside tmux,
    writes the payload as-is.
    """
    if "TMUX" in os.environ:
        inner = payload.replace("\033", "\033\033")
        sys.stdout.write(f"\033Ptmux;{inner}\033\\")
    else:
        sys.stdout.write(payload)


@contextmanager
def reserve_image_rows(n: int):
    """Inside tmux: reserve `n` rows below the cursor and advance past them
    on exit, so an image drawn at the cursor position isn't overwritten by
    later text. tmux can't see the image, so its own cursor model wouldn't
    naturally advance. No-op outside tmux."""
    if "TMUX" not in os.environ or n <= 0:
        yield
        return
    sys.stdout.write("\n" * n)
    sys.stdout.write(f"\033[{n}F")
    try:
        yield
    finally:
        sys.stdout.write(f"\033[{n}E")
