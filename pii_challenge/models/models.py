from dataclasses import dataclass


@dataclass(order=True)
class TextBoundingBox:
    """Pillow-type Bounding Box.
    Co-ordinates start in (0,0) in the Top Left Corner."""

    text: str
    left: int
    right: int
    top: int
    bottom: int
