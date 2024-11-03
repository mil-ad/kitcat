import sys
from base64 import b64encode
from io import BytesIO

from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

__all__ = ["FigureCanvas", "FigureManager"]

CHUNK_SIZE = 4096


def display_png(pixel_data):
    """
    Encodes pixel data to the terminal using Kitty graphics protocol. All escape codes
    are of the form: <ESC>_G<control data>;<payload><ESC>\

    For more information on the protocol see:
    https://sw.kovidgoyal.net/kitty/graphics-protocol/#control-data-reference
    """
    data = b64encode(pixel_data).decode("ascii")

    first_chunk, more_data = data[:CHUNK_SIZE], data[CHUNK_SIZE:]

    # a=T simultaneously transmits and displays the image
    # f=100 indicates PNG data
    # m=1 indicates there's going to be more data chunks
    sys.stdout.write(
        f"\033_Gm={"1" if more_data else "0"},a=T,f=100;{first_chunk}\033\\"
    )

    while more_data:
        chunk, more_data = more_data[:CHUNK_SIZE], more_data[CHUNK_SIZE:]
        sys.stdout.write(f"\033_Gm={"1" if more_data else "0"};{chunk}\033\\")

    sys.stdout.write("\n")
    sys.stdout.flush()


class KitcatFigureManager(FigureManagerBase):
    def show(self):
        with BytesIO() as buf:
            self.canvas.print_png(buf)
            buf.seek(0)
            display_png(pixel_data=buf.read())


class KitcatFigureCanvas(FigureCanvasAgg):
    manager_class = KitcatFigureManager


# provide the standard names that matplotlib is expecting
FigureCanvas = KitcatFigureCanvas
FigureManager = KitcatFigureManager
