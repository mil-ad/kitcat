import array
import fcntl
import math
import sys
import termios

from PIL import Image


def get_char_cell_height() -> int:
    """Source https://sw.kovidgoyal.net/kitty/graphics-protocol/#getting-the-window-size"""

    buf = array.array("H", [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    num_rows, _, _, screen_height = buf

    return int(screen_height // num_rows)


def num_required_lines(img_buf):
    with Image.open(img_buf) as img:
        _, img_height = img.size
        img_buf.seek(0)

    return math.ceil(img_height / get_char_cell_height())
