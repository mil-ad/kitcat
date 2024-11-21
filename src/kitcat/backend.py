import itertools
import os
import sys
from base64 import b64encode
from functools import wraps
from io import BytesIO

from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

from .utils import num_required_lines

__all__ = ["FigureCanvas", "FigureManager"]

CHUNK_SIZE_KITTY = 4096
CHUNK_SIZE_IT2 = 1_048_576


def make_tmux_compatible(func):
    if "TMUX" not in os.environ:
        return func

    old_write_fn = sys.stdout.write

    def new_write_fn(s):
        s = s.replace("\033", "\033\033")
        old_write_fn(s)

    @wraps(func)
    def wrapper(img_buf):
        try:
            height_lines = num_required_lines(img_buf)
            sys.stdout.write("\n" * height_lines)
            # sys.stdout.write("\033[?25l")
            sys.stdout.write(f"\033[{height_lines}F")
            sys.stdout.write("\033Ptmux;")

            sys.stdout.write = new_write_fn
            func(img_buf)
            sys.stdout.write = old_write_fn

            sys.stdout.write("\033\\")
            sys.stdout.write(f"\033[{height_lines}E")
        finally:
            # Ensure stdout is always restored
            sys.stdout.write = old_write_fn

    return wrapper


@make_tmux_compatible
def display_kitty(img_buf):
    """
    Encodes pixel data to the terminal using Kitty graphics protocol. All escape codes
    are of the form: <ESC>_G<control data>;<payload><ESC>\

    For more information on the protocol see:
    https://sw.kovidgoyal.net/kitty/graphics-protocol/#control-data-reference
    """
    data = b64encode(img_buf.read()).decode("ascii")

    first_chunk, more_data = data[:CHUNK_SIZE_KITTY], data[CHUNK_SIZE_KITTY:]

    # a=T simultaneously transmits and displays the image
    # f=100 indicates PNG data
    # m=1 indicates there's going to be more data chunks
    sys.stdout.write(
        f"\033_Gm={'1' if more_data else '0'},a=T,f=100;{first_chunk}\033\\"
    )

    while more_data:
        chunk, more_data = more_data[:CHUNK_SIZE_KITTY], more_data[CHUNK_SIZE_KITTY:]
        sys.stdout.write(f"\033_Gm={'1' if more_data else '0'};{chunk}\033\\")


def display_iterm2_new(pixel_data):
    data = b64encode(pixel_data).decode("ascii")

    sys.stdout.write(f"\033]1337;MultipartFile=inline=1;size={len(pixel_data)}\a")
    for chunk in itertools.batched(data, CHUNK_SIZE_IT2):
        sys.stdout.write(f"\033]1337;FilePart={''.join(chunk)}\a")
    sys.stdout.write("\033]1337;FileEnd\a")
    sys.stdout.write("\n")
    sys.stdout.flush()


@make_tmux_compatible
def display_iterm2(img_buf):
    pixel_data = img_buf.read()
    data = b64encode(pixel_data).decode("ascii")

    # size is optional in iTerm2 but is required in vscode terminal
    sys.stdout.write(f"\033]1337;File=inline=1;size={len(pixel_data)}:{data}\a")


class KitcatFigureManager(FigureManagerBase):
    def show(self):
        with BytesIO() as buf:
            self.canvas.print_png(buf)
            buf.seek(0)

            if os.environ.get("TERM_PROGRAM") in ["iTerm.app", "vscode"]:
                display_iterm2(img_buf=buf)
            else:
                display_kitty(img_buf=buf)

        sys.stdout.write("\n")
        sys.stdout.flush()


class KitcatFigureCanvas(FigureCanvasAgg):
    manager_class = KitcatFigureManager


# provide the standard names that matplotlib is expecting
FigureCanvas = KitcatFigureCanvas
FigureManager = KitcatFigureManager
