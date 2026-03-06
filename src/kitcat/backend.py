import itertools
import os
import sys
from base64 import b64encode
from functools import wraps
from io import BytesIO

from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

from .utils import num_required_cols, num_required_lines

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


# Diacritical marks for encoding row/column indices in Unicode placeholders.
# Source: kitty/gen/rowcolumn-diacritics.txt (Unicode 6.0.0, combining class 230)
DIACRITICS = [
    0x0305, 0x030D, 0x030E, 0x0310, 0x0312, 0x033D, 0x033E, 0x033F,
    0x0346, 0x034A, 0x034B, 0x034C, 0x0350, 0x0351, 0x0352, 0x0357,
    0x035B, 0x0363, 0x0364, 0x0365, 0x0366, 0x0367, 0x0368, 0x0369,
    0x036A, 0x036B, 0x036C, 0x036D, 0x036E, 0x036F, 0x0483, 0x0484,
    0x0485, 0x0486, 0x0592, 0x0593, 0x0594, 0x0595, 0x0597, 0x0598,
    0x0599, 0x059C, 0x059D, 0x059E, 0x059F, 0x05A0, 0x05A1, 0x05A8,
    0x05A9, 0x05AB, 0x05AC, 0x05AF, 0x05C4, 0x0610, 0x0611, 0x0612,
    0x0613, 0x0614, 0x0615, 0x0616, 0x0617, 0x0657, 0x0658, 0x0659,
    0x065A, 0x065B, 0x065D, 0x065E, 0x06D6, 0x06D7, 0x06D8, 0x06D9,
    0x06DA, 0x06DB, 0x06DC, 0x06DF, 0x06E0, 0x06E1, 0x06E2, 0x06E4,
    0x06E7, 0x06E8, 0x06EB, 0x06EC, 0x0730, 0x0731, 0x0732, 0x0733,
    0x0734, 0x0735, 0x0736, 0x0737, 0x0738, 0x0739, 0x073A, 0x073B,
    0x073C, 0x073D, 0x073E, 0x073F, 0x0740, 0x0741, 0x0742, 0x0743,
    0x0744, 0x0745, 0x0746, 0x0747, 0x0748, 0x0749, 0x074A, 0x07EB,
    0x07EC, 0x07ED, 0x07EE, 0x07EF, 0x07F0, 0x07F1, 0x07F2, 0x07F3,
    0x0816, 0x0817, 0x0818, 0x0819, 0x081B, 0x081C, 0x081D, 0x081E,
    0x081F, 0x0820, 0x0821, 0x0822, 0x0823, 0x0825, 0x0826, 0x0827,
    0x0829, 0x082A, 0x082B, 0x082C, 0x082D, 0x0951, 0x0953, 0x0954,
    0x0F82, 0x0F83, 0x0F86, 0x0F87, 0x135D, 0x135E, 0x135F, 0x17DD,
    0x193A, 0x1A17, 0x1A75, 0x1A76, 0x1A77, 0x1A78, 0x1A79, 0x1A7A,
    0x1A7B, 0x1A7C, 0x1AB0, 0x1AB1, 0x1AB2, 0x1AB3, 0x1AB4, 0x1AB5,
    0x1AB6, 0x1AB7, 0x1AB8, 0x1AB9, 0x1ABA, 0x1ABB, 0x1ABC, 0x1ABD,
    0x1B6B, 0x1B6C, 0x1B6D, 0x1B6E, 0x1B6F, 0x1B70, 0x1B71, 0x1B72,
    0x1B73, 0x1CD0, 0x1CD1, 0x1CD2, 0x1CDA, 0x1CDB, 0x1CE0, 0x1CF4,
    0x1CF8, 0x1CF9, 0x1DC0, 0x1DC1, 0x1DC2, 0x1DC3, 0x1DC4, 0x1DC5,
    0x1DC6, 0x1DC7, 0x1DC8, 0x1DC9, 0x1DCA, 0x1DCB, 0x1DCC, 0x1DCD,
    0x1DCE, 0x1DCF, 0x1DD1, 0x1DD2, 0x1DD3, 0x1DD4, 0x1DD5, 0x1DD6,
    0x1DD7, 0x1DD8, 0x1DD9, 0x1DDA, 0x1DDB, 0x1DDC, 0x1DDD, 0x1DDE,
    0x1DDF, 0x1DE0, 0x1DE1, 0x1DE2, 0x1DE3, 0x1DE4, 0x1DE5, 0x1DE6,
    0x1DFE, 0x20D0, 0x20D1, 0x20D4, 0x20D5, 0x20D6, 0x20D7, 0x20DB,
    0x20DC, 0x20E1, 0x20E7, 0x20E9, 0x20F0, 0x2CEF, 0x2CF0, 0x2CF1,
    0x2DE0, 0x2DE1, 0x2DE2, 0x2DE3, 0x2DE4, 0x2DE5, 0x2DE6, 0x2DE7,
    0x2DE8, 0x2DE9, 0x2DEA, 0x2DEB, 0x2DEC, 0x2DED, 0x2DEE, 0x2DEF,
    0x2DF0, 0x2DF1, 0x2DF2, 0x2DF3, 0x2DF4, 0x2DF5, 0x2DF6, 0x2DF7,
    0x2DF8, 0x2DF9, 0x2DFA, 0x2DFB, 0x2DFC, 0x2DFD, 0x2DFE, 0x2DFF,
    0xA66F, 0xA674, 0xA675, 0xA676, 0xA677, 0xA678, 0xA679, 0xA67A,
    0xA67B, 0xA67C, 0xA67D, 0xA69E, 0xA69F, 0xA6F0, 0xA6F1, 0xA8E0,
    0xA8E1, 0xA8E2, 0xA8E3, 0xA8E4, 0xA8E5, 0xA8E6, 0xA8E7, 0xA8E8,
    0xA8E9, 0xA8EA, 0xA8EB, 0xA8EC, 0xA8ED, 0xA8EE, 0xA8EF, 0xA8F0,
    0xA8F1, 0xAAB0, 0xAAB2, 0xAAB3, 0xAAB7, 0xAAB8, 0xAABE, 0xAABF,
    0xAAC1, 0xFE20, 0xFE21, 0xFE22, 0xFE23, 0xFE24, 0xFE25, 0xFE26,
    0xFE27, 0xFE28, 0xFE29, 0xFE2A, 0xFE2B, 0xFE2C, 0xFE2D, 0xFE2E,
    0xFE2F, 0x10A0F, 0x10A38, 0x10AE5, 0x10AE6, 0x10D24, 0x10D25,
    0x10D26, 0x10D27, 0x10F48, 0x10F49, 0x10F4A, 0x10F4B, 0x10F4C,
    0x11100, 0x11101, 0x11102, 0x11366, 0x11367, 0x11368, 0x11369,
    0x1136A, 0x1136B, 0x1136C, 0x11370, 0x11371, 0x11372, 0x11373,
    0x11374, 0x16AF0, 0x16AF1, 0x16AF2, 0x16AF3, 0x16AF4, 0x1D165,
    0x1D166, 0x1D167, 0x1D168, 0x1D169, 0x1D16D, 0x1D16E, 0x1D16F,
    0x1D170, 0x1D171, 0x1D172, 0x1D17B, 0x1D17C, 0x1D17D, 0x1D17E,
    0x1D17F, 0x1D180, 0x1D181, 0x1D182, 0x1D185, 0x1D186, 0x1D187,
    0x1D188, 0x1D189, 0x1D18A, 0x1D18B, 0x1D1AA, 0x1D1AB, 0x1D1AC,
    0x1D1AD, 0x1D242, 0x1D243, 0x1D244, 0x1E000, 0x1E001, 0x1E002,
    0x1E003, 0x1E004, 0x1E005, 0x1E006, 0x1E008, 0x1E009, 0x1E00A,
    0x1E00B, 0x1E00C, 0x1E00D, 0x1E00E, 0x1E00F, 0x1E010, 0x1E011,
    0x1E012, 0x1E013, 0x1E014, 0x1E015, 0x1E016, 0x1E017, 0x1E018,
    0x1E01B, 0x1E01C, 0x1E01D, 0x1E01E, 0x1E01F, 0x1E020, 0x1E021,
    0x1E023, 0x1E024, 0x1E026, 0x1E027, 0x1E028, 0x1E029, 0x1E02A,
    0x1E8D0, 0x1E8D1, 0x1E8D2, 0x1E8D3, 0x1E8D4, 0x1E8D5, 0x1E8D6,
]

PLACEHOLDER = "\U0010EEEE"

_image_id_counter = 0


def _next_image_id():
    global _image_id_counter
    _image_id_counter = (_image_id_counter + 1) % 0xFFFFFF
    if _image_id_counter == 0:
        _image_id_counter = 1
    return _image_id_counter


def _transmit_image_via_passthrough(data, image_id, rows, cols):
    """Transmit image data to the terminal via tmux passthrough."""
    first_chunk, more_data = data[:CHUNK_SIZE_KITTY], data[CHUNK_SIZE_KITTY:]

    sys.stdout.write("\033Ptmux;")
    m = "1" if more_data else "0"
    sys.stdout.write(
        f"\033\033_Gm={m},a=T,U=1,q=2,i={image_id},f=100,c={cols},r={rows}"
        f";{first_chunk}\033\033\\"
    )
    while more_data:
        chunk, more_data = more_data[:CHUNK_SIZE_KITTY], more_data[CHUNK_SIZE_KITTY:]
        m = "1" if more_data else "0"
        sys.stdout.write(f"\033\033_Gm={m},i={image_id};{chunk}\033\033\\")
    sys.stdout.write("\033\\")


def _output_placeholders(image_id, rows, cols):
    """Output Unicode placeholder characters that tmux treats as normal text."""
    r = (image_id >> 16) & 0xFF
    g = (image_id >> 8) & 0xFF
    b = image_id & 0xFF
    fg = f"\033[38;2;{r};{g};{b}m"

    for row in range(rows):
        row_diac = chr(DIACRITICS[row])
        sys.stdout.write(fg)
        for col in range(cols):
            col_diac = chr(DIACRITICS[col])
            sys.stdout.write(f"{PLACEHOLDER}{row_diac}{col_diac}")
        sys.stdout.write("\033[39m\n")


def display_kitty_unicode_placeholder(img_buf):
    """Display image using kitty graphics protocol with Unicode placeholders.
    Works correctly inside tmux - images stay within pane boundaries."""
    data = b64encode(img_buf.read()).decode("ascii")
    img_buf.seek(0)
    rows = num_required_lines(img_buf)
    cols = num_required_cols(img_buf)
    image_id = _next_image_id()

    _transmit_image_via_passthrough(data, image_id, rows, cols)
    _output_placeholders(image_id, rows, cols)

    sys.stdout.flush()


def _is_tmux():
    """Detect if running inside tmux, including over SSH where TMUX isn't set."""
    if "TMUX" in os.environ:
        return True
    if os.environ.get("KITCAT_TMUX") == "1":
        return True
    term = os.environ.get("TERM", "")
    return term.startswith("tmux") or term.startswith("screen")


class KitcatFigureManager(FigureManagerBase):
    def show(self):
        with BytesIO() as buf:
            self.canvas.print_png(buf)
            buf.seek(0)

            if os.environ.get("TERM_PROGRAM") in ["iTerm.app", "vscode"]:
                display_iterm2(img_buf=buf)
            elif _is_tmux():
                display_kitty_unicode_placeholder(img_buf=buf)
            else:
                display_kitty(img_buf=buf)

        sys.stdout.write("\n")
        sys.stdout.flush()


class KitcatFigureCanvas(FigureCanvasAgg):
    manager_class = KitcatFigureManager


# provide the standard names that matplotlib is expecting
FigureCanvas = KitcatFigureCanvas
FigureManager = KitcatFigureManager
