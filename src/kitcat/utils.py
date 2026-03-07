import array
import fcntl
import math
import os
import sys
import termios

from PIL import Image


def get_char_cell_height() -> int:
    """Source https://sw.kovidgoyal.net/kitty/graphics-protocol/#getting-the-window-size"""

    env_val = os.environ.get("KITCAT_CELL_HEIGHT")
    if env_val:
        return int(env_val)

    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    num_rows, _, _, screen_height = buf

    if num_rows == 0 or screen_height == 0:
        return 24  # fallback when pixel dimensions unavailable (e.g. SSH)
    return int(screen_height // num_rows)


def get_char_cell_width() -> int:
    env_val = os.environ.get("KITCAT_CELL_WIDTH")
    if env_val:
        return int(env_val)

    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    _, num_cols, screen_width, _ = buf
    if num_cols == 0 or screen_width == 0:
        return 12  # fallback when pixel dimensions unavailable (e.g. SSH)
    return int(screen_width // num_cols)


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
