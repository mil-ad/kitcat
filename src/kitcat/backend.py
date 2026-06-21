import sys
from contextlib import contextmanager
from io import BytesIO

from matplotlib import _pylab_helpers
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg

from kitcat.protocols import iterm, kitty_basic, kitty_unicode_placeholder
from kitcat.terminal_query import detect_terminal, get_dpi_scale

__all__ = ["FigureCanvas", "FigureManager", "show"]


@contextmanager
def scaled_figure_dpi(fig, scale):
    """Temporarily multiply a figure's DPI by `scale` while rendering, then
    restore it (a no-op when scale == 1.0).

    DPI scaling is resolution-only — figsize is in inches and fonts in points,
    so the layout is unchanged, just rasterized at more pixels. Doing it here
    rather than mutating global rcParams keeps the user's own DPI (from
    rcParams, code, or a per-figure ``dpi=``) intact and merely multiplied for
    the render.
    """
    if scale == 1.0:
        yield
        return

    original = fig.dpi
    fig.set_dpi(original * scale)
    try:
        yield
    finally:
        fig.set_dpi(original)


class KitcatFigureManager(FigureManagerBase):
    def show(self):
        with BytesIO() as buf:
            # Render at the terminal's device-pixel ratio so the plot is the
            # right physical size and crisp on HiDPI displays. Restored after.
            with scaled_figure_dpi(self.canvas.figure, get_dpi_scale()):
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
