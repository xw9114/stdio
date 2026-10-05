from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.models.settings import AppSettings
from app.ui.theme import application_style
from app.ui.wallpaper import (
    PRESETS,
    WallpaperCanvas,
    describe,
    load_wallpaper,
    minimum_veil,
    preset_value,
)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="uses real QWidgets on Windows")


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _photo(tmp_path: Path, color: str, name: str = "photo.png") -> Path:
    image = QImage(800, 500, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    path = tmp_path / name
    assert image.save(str(path))
    return path


def test_every_preset_renders_and_describes_itself() -> None:
    for preset in PRESETS:
        image = load_wallpaper(preset_value(preset.key), 2)
        assert image is not None and not image.isNull()
        assert describe(preset_value(preset.key)) == preset.label


def test_none_unknown_and_missing_wallpapers_load_as_nothing(tmp_path: Path) -> None:
    assert load_wallpaper("", 2) is None
    assert load_wallpaper("preset:nope", 2) is None
    assert load_wallpaper(str(tmp_path / "gone.jpg"), 2) is None
    broken = tmp_path / "broken.png"
    broken.write_text("not an image", encoding="utf-8")
    assert load_wallpaper(str(broken), 2) is None


def test_an_image_loads_at_working_size_for_every_blur_level(tmp_path: Path) -> None:
    path = _photo(tmp_path, "#336699")
    for level in range(4):
        image = load_wallpaper(str(path), level)
        assert image is not None
        assert image.size() == QSize(800, 500)
        # Blurring a flat colour keeps it flat, edges included (no dark rim
        # from transparent pixels pulled in; Qt's blur rounds by a level or two).
        edge, middle = QColor(image.pixel(1, 1)), QColor(image.pixel(400, 250))
        assert max(abs(edge.red() - middle.red()), abs(edge.green() - middle.green()), abs(edge.blue() - middle.blue())) <= 4
    assert describe(str(path)) == "photo.png"


def test_dark_images_get_a_veil_floor_and_pale_ones_none(tmp_path: Path) -> None:
    dark = load_wallpaper(str(_photo(tmp_path, "#20202a", "dark.png")), 0)
    light = load_wallpaper(preset_value("mist"), 0)
    assert dark is not None and light is not None
    assert minimum_veil(dark) > 0.6
    assert minimum_veil(light) == 0.0

    canvas = WallpaperCanvas()
    canvas.set_wallpaper(dark, 0)
    assert canvas._veil.alphaF() == pytest.approx(minimum_veil(dark), abs=0.01)
    canvas.set_wallpaper(dark, 50)
    assert canvas._veil.alphaF() > minimum_veil(dark), "the setting adds to the floor"
    canvas.set_wallpaper(None, 50)
    assert not canvas.has_wallpaper


def test_wallpaper_settings_are_bounded_and_kept() -> None:
    settings = AppSettings.from_dict({"wallpaper": "E:/a.jpg", "wallpaper_blur": 9, "wallpaper_veil": -4})
    assert (settings.wallpaper, settings.wallpaper_blur, settings.wallpaper_veil) == ("E:/a.jpg", 3, 0)
    assert AppSettings.from_dict({}).wallpaper == "preset:mist"
    assert AppSettings.from_dict(settings.to_dict()) == settings


def test_glass_style_only_layers_translucent_panels_over_the_base() -> None:
    plain, glass = application_style(False), application_style(True)
    assert glass.startswith(plain)
    assert "rgba(255, 255, 255, 0.50)" in glass and "rgba(255, 255, 255, 0.50)" not in plain
