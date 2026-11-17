"""Customer-side Gmail/Stripe evidence collection for Arga Training."""

from .collector import Tracing, init
from .models import Episode
from .projection import CapturePolicy

__all__ = ["CapturePolicy", "Episode", "Tracing", "init"]
