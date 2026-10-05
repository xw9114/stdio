"""Soft drop shadows painted by a container under chosen child widgets.

QGraphicsDropShadowEffect renders its whole widget into an offscreen buffer
on every update - for the composer that is every keystroke and cursor blink
- so the container paints the shadows instead, from one small blurred image
per (corner radius, softness) stretched as a nine-slice.
"""

from __future__ import annotations

from functools import lru_cache

import shiboken6
from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPaintEvent, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene, QWidget


@lru_cache(maxsize=16)
def _shadow_tile(radius: int, softness: int) -> tuple[QPixmap, int]:
    """A blurred rounded square and the width of its corner slices."""
    corner = radius + softness
    margin = softness * 2
    inner = corner * 2 + 2  # a 2px straight run between the corners
    size = inner + margin * 2
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(margin, margin, inner, inner), radius, radius)
    painter.fillPath(path, QColor(0, 0, 0))
    painter.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(softness * 2)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    blurred = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    blurred.fill(Qt.GlobalColor.transparent)
    painter = QPainter(blurred)
    scene.render(painter, QRectF(blurred.rect()), QRectF(image.rect()))
    painter.end()
    return QPixmap.fromImage(blurred), margin + corner


def paint_shadow(painter: QPainter, rect: QRect, radius: int, softness: int, opacity: float, offset_y: int) -> None:
    """Paints a soft shadow for a rounded `rect` (in the painter's coordinates)."""
    tile, slice_size = _shadow_tile(radius, softness)
    margin = softness * 2
    target = rect.adjusted(-margin, -margin + offset_y, margin, margin + offset_y)
    if target.width() < 2 * slice_size or target.height() < 2 * slice_size:
        return
    side = tile.width()
    middle = side - 2 * slice_size
    painter.save()
    painter.setOpacity(opacity)
    xs = (
        (target.left(), slice_size, 0, slice_size),
        (target.left() + slice_size, target.width() - 2 * slice_size, slice_size, middle),
        (target.right() + 1 - slice_size, slice_size, side - slice_size, slice_size),
    )
    ys = (
        (target.top(), slice_size, 0, slice_size),
        (target.top() + slice_size, target.height() - 2 * slice_size, slice_size, middle),
        (target.bottom() + 1 - slice_size, slice_size, side - slice_size, slice_size),
    )
    for x, width, source_x, source_width in xs:
        for y, height, source_y, source_height in ys:
            painter.drawPixmap(QRect(x, y, width, height), tile, QRect(source_x, source_y, source_width, source_height))
    painter.restore()


class ShadowSurface(QWidget):
    """A container that paints soft shadows under registered descendants."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shadowed: list[tuple[QWidget, int]] = []

    def add_shadow(self, widget: QWidget, radius: int) -> None:
        self._shadowed.append((widget, radius))
        widget.installEventFilter(self)
        self.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide}:
            self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        # Deleted widgets (a cleared chat) drop out here.
        self._shadowed = [(widget, radius) for widget, radius in self._shadowed if shiboken6.isValid(widget)]
        if not self._shadowed:
            return
        painter = QPainter(self)
        for widget, radius in self._shadowed:
            if not widget.isVisible():
                continue
            top_left = widget.mapTo(self, widget.rect().topLeft())
            rect = QRect(top_left, widget.size())
            if not rect.intersects(event.rect().adjusted(-40, -40, 40, 40)):
                continue
            # A wide faint shadow for depth plus a tight one for the edge.
            paint_shadow(painter, rect, radius, 14, 0.07, 6)
            paint_shadow(painter, rect, radius, 3, 0.05, 1)
