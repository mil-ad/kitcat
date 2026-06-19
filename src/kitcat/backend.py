import sys
from io import BytesIO

from matplotlib import _pylab_helpers
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

from kitcat.protocols import iterm, kitty_basic, kitty_unicode_placeholder
from kitcat.terminal_query import detect_terminal

__all__ = ["FigureCanvas", "FigureManager", "show"]


class KitcatFigureManager(FigureManagerBase):
    def show(self):
        with BytesIO() as buf:
            self.canvas.print_png(buf)
            buf.seek(0)

            terminal = detect_terminal()

            # Kitty and Ghostty implement unicode placeholders; the image
            # becomes part of the text buffer, so it scrolls and clips correctly
            # (notably, behaves right inside tmux).
            if terminal in {"kitty", "ghostty"}:
                kitty_unicode_placeholder.display(buf)
            # iTerm and VSCode speak the iTerm2 OSC 1337 image protocol and
            # don't implement kitty graphics at all.
            elif terminal in {"iterm.app", "iterm2", "vscode"}:
                iterm.display(buf)
            # Everything else: try basic kitty graphics. Well-behaved terminals
            # silently consume escapes they don't understand, so this is no
            # worse than no-op on incompatible terminals.
            else:
                kitty_basic.display(buf)

        sys.stdout.write("\n")
        sys.stdout.flush()


class KitcatFigureCanvas(FigureCanvasAgg):
    manager_class = KitcatFigureManager


# matplotlib looks these up by convention
FigureCanvas = KitcatFigureCanvas
FigureManager = KitcatFigureManager


def show(*, block=None):
    """
    Show all open figures and then close them.

    This matches the behavior of IPython's inline backend, where figures
    are closed after being displayed to prevent accumulating stale figures
    from previous plot() calls.

    Parameters
    ----------
    block : bool, optional
        This parameter is ignored for this non-GUI backend.
    """
    managers = _pylab_helpers.Gcf.get_all_fig_managers()
    for manager in managers:
        manager.show()
    if managers:
        _pylab_helpers.Gcf.destroy_all()
