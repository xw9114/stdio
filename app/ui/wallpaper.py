"""Window wallpapers: a local image or a built-in gradient, behind the UI.

A wallpaper is chosen by a string stored in the settings:

- ""                 no wallpaper (the plain light theme);
- "preset:<key>"     one of the gradients drawn below;
- any other value    a path to a local image.

Images are softened with a blur before use and a light veil is laid over
every wallpaper, so dark text stays readable whatever the picture is.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPaintEvent, QPixmap, QRadialGradient
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QWidget

from app.ui.theme import WINDOW_BG

PRESET_PREFIX = "preset:"
IMAGE_FILTER = "图片 (*.png *.jpg *.jpeg *.bmp *.webp *.gif)"

# Blur radius per level (0-3) at the working size below; 0 keeps the image sharp.
BLUR_LEVELS = ("不模糊", "轻微", "柔和", "强烈")
_BLUR_RADII = (0, 6, 16, 32)
# Images are worked on at this size: a background is soft anyway, and a
# smaller image keeps loading and blurring quick.
_WORKING_LONG_SIDE = 1600
_SHARP_LONG_SIDE = 2560


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    base: str
    # (red, green, blue, alpha 0-255, centre x 0-1, centre y 0-1, radius as a share of the width)
    glows: tuple[tuple[int, int, int, int, float, float, float], ...]


# Soft colour fields in the manner of mesh gradients: a pale base with a few
# large, heavily feathered glows. Pale enough that black text needs no veil.
PRESETS: tuple[Preset, ...] = (
    Preset(
        "mist",
        "晨雾",
        "#f5f2ee",
        (
            (255, 196, 168, 150, 0.12, 0.18, 0.62),
            (196, 186, 255, 130, 0.88, 0.22, 0.58),
            (172, 226, 208, 120, 0.62, 0.95, 0.66),
        ),
    ),
    Preset(
        "aurora",
        "极光",
        "#eef2f6",
        (
            (126, 214, 204, 150, 0.10, 0.85, 0.66),
            (146, 172, 255, 140, 0.55, 0.10, 0.62),
            (206, 168, 250, 120, 0.95, 0.70, 0.56),
        ),
    ),
    Preset(
        "dusk",
        "暮色",
        "#f7efea",
        (
            (247, 172, 170, 140, 0.85, 0.15, 0.60),
            (255, 208, 146, 140, 0.15, 0.30, 0.58),
            (196, 156, 210, 120, 0.50, 1.00, 0.70),
        ),
    ),
    Preset(
        "sage",
        "青苔",
        "#f1f3ee",
        (
            (176, 214, 170, 150, 0.20, 0.20, 0.62),
            (214, 226, 168, 120, 0.90, 0.40, 0.56),
            (160, 206, 214, 120, 0.40, 1.00, 0.66),
        ),
    ),
)
PRESET_BY_KEY = {preset.key: preset for preset in PRESETS}


def preset_value(key: str) -> str:
    return f"{PRESET_PREFIX}{key}"


def is_preset(value: str) -> bool:
    return value.startswith(PRESET_PREFIX)


def describe(value: str) -> str:
    """A short label for a wallpaper setting, for menus and tooltips."""
    if not value:
        return "无"
    if is_preset(value):
        preset = PRESET_BY_KEY.get(value[len(PRESET_PREFIX):])
        return preset.label if preset else "无"
    return Path(value).name


def load_wallpaper(value: str, blur_level: int) -> QImage | None:
    """The wallpaper image for a setting, or None for none (including an
    unknown preset or an image that no longer loads)."""
    if not value:
        return None
    if is_preset(value):
        preset = PRESET_BY_KEY.get(value[len(PRESET_PREFIX):])
        return _render_preset(preset.key) if preset else None
    path = Path(value)
    if not path.is_file():
        return None
    return _load_image(str(path), path.stat().st_mtime_ns, max(0, min(3, blur_level)))


@lru_cache(maxsize=8)
def _render_preset(key: str) -> QImage:
    preset = PRESET_BY_KEY[key]
    # Drawn at a size close to the window: a small image scaled up showed
    # blocky bands in the gradients.
    width, height = 1600, 1000
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(preset.base))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for red, green, blue, alpha, x, y, radius in preset.glows:
        centre = QPointF(x * width, y * height)
        gradient = QRadialGradient(centre, radius * width)
        gradient.setColorAt(0.0, QColor(red, green, blue, alpha))
        gradient.setColorAt(0.55, QColor(red, green, blue, alpha // 3))
        gradient.setColorAt(1.0, QColor(red, green, blue, 0))
        painter.fillRect(image.rect(), gradient)
    # A faint grain breaks up the 8-bit banding of wide soft gradients.
    painter.setOpacity(0.045)
    painter.drawTiledPixmap(image.rect(), _grain())
    painter.end()
    return image


@lru_cache(maxsize=1)
def _grain() -> QPixmap:
    size = 128
    tile = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    noise = random.Random(7)
    for y in range(size):
        for x in range(size):
            value = noise.randint(0, 255)
            tile.setPixel(x, y, QColor(value, value, value).rgb())
    return QPixmap.fromImage(tile)


# Darkest share of the wallpaper that must end up light enough for the
# theme's dark text, after the veil.
_LEGIBLE_LUMINANCE = 0.68
_VEIL_LUMINANCE = 0.955  # relative luminance of the page colour


def minimum_veil(image: QImage) -> float:
    """The veil opacity (0-1) that lifts the darker parts of `image` to a
    luminance where dark text stays readable: 0 for a pale gradient, about
    0.7 for a dark photo. The user's veil setting is added on top."""
    sample = image.scaled(48, 30, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    values = sorted(
        _luminance(QColor(sample.pixel(x, y))) for y in range(sample.height()) for x in range(sample.width())
    )
    dark = values[len(values) // 5]  # the 20th percentile: dark areas, not one black pixel
    if dark >= _LEGIBLE_LUMINANCE:
        return 0.0
    return min(0.9, (_LEGIBLE_LUMINANCE - dark) / (_VEIL_LUMINANCE - dark))


def _luminance(color: QColor) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(color.redF()) + 0.7152 * linear(color.greenF()) + 0.0722 * linear(color.blueF())


@lru_cache(maxsize=4)
def _load_image(path: str, _modified: int, blur_level: int) -> QImage | None:
    reader = QImageReader(path)
    reader.setAutoTransform(True)  # honour EXIF rotation of phone photos
    image = reader.read()
    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    long_side = _SHARP_LONG_SIDE if blur_level == 0 else _WORKING_LONG_SIDE
    if max(image.width(), image.height()) > long_side:
        image = image.scaled(
            long_side,
            long_side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return _blur(image, _BLUR_RADII[blur_level])


def _blur(image: QImage, radius: int) -> QImage:
    if radius <= 0:
        return image
    # Blurring pulls transparent pixels in at the edges and darkens them;
    # blur an enlarged copy with a margin, then crop the middle back out.
    margin = radius * 3  # the blur kernel reaches well past `radius`
    padded = QImage(image.width() + 2 * margin, image.height() + 2 * margin, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(padded)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(QRectF(padded.rect()), image)
    painter.drawImage(margin, margin, image)
    painter.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(padded))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    blurred = QImage(padded.size(), QImage.Format.Format_ARGB32_Premultiplied)
    blurred.fill(Qt.GlobalColor.transparent)
    painter = QPainter(blurred)
    scene.render(painter, QRectF(blurred.rect()), QRectF(padded.rect()))
    painter.end()
    return blurred.copy(margin, margin, image.width(), image.height())


class WallpaperCanvas(QWidget):
    """The window's backdrop: the wallpaper scaled to cover, under a light
    veil, or the plain window colour when there is none."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("appCanvas")
        self._image: QImage | None = None
        self._veil = QColor(WINDOW_BG)
        self._scaled: QPixmap | None = None
        self._scaled_for = QSize()

    @property
    def has_wallpaper(self) -> bool:
        return self._image is not None

    def set_wallpaper(self, image: QImage | None, veil_percent: int) -> None:
        """`veil_percent` is added on top of the veil `image` needs for
        legible text, so even 0 keeps a dark photo readable."""
        self._image = image
        floor = minimum_veil(image) if image is not None else 0.0
        extra = max(0, min(100, veil_percent)) / 100
        veil = QColor(WINDOW_BG)
        veil.setAlphaF(floor + (1 - floor) * extra)
        self._veil = veil
        self._scaled = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self._image is None:
            painter.fillRect(self.rect(), QColor(WINDOW_BG))
            return
        if self._scaled is None or self._scaled_for != self.size():
            self._scaled = _cover(self._image, self.size())
            self._scaled_for = self.size()
        painter.drawPixmap(0, 0, self._scaled)
        painter.fillRect(self.rect(), self._veil)


def _cover(image: QImage, size: QSize) -> QPixmap:
    """`image` scaled to fill `size`, cropped around its centre."""
    if size.isEmpty():
        return QPixmap()
    scaled = image.scaled(
        size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
    )
    x = (scaled.width() - size.width()) // 2
    y = (scaled.height() - size.height()) // 2
    return QPixmap.fromImage(scaled.copy(x, y, size.width(), size.height()))
