"""The stage: the selected app's artwork with the home and release-notes pages on top."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QLocale, QRectF, QSize, Qt, QTimer, QUrl, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPalette, QPixmap, QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QSizePolicy, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .. import sources
from ..i18n import language, tr
from . import art, icons, theme
from .images import is_url
from .widgets import label

CARDS_HEIGHT = 136


def format_date(dt) -> str:
    """Short, localised date ('21 Nov 2026' / '21 de nov. de 2026')."""
    if dt is None:
        return "—"
    from PyQt6.QtCore import QDate
    local = dt.astimezone() if dt.tzinfo else dt
    date = QDate(local.year, local.month, local.day)
    locale = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil) if language() == "pt-BR" \
        else QLocale(QLocale.Language.English, QLocale.Country.UnitedKingdom)
    return locale.toString(date, "d MMM yyyy")


# ---------------------------------------------------------------------------
# Backdrop
# ---------------------------------------------------------------------------

class Stage(QWidget):
    """Paints the app's artwork (banner or generated backdrop + framed screenshot)
    behind its children, with a cross-fade when the app changes."""

    def __init__(self, images, parent=None):
        super().__init__(parent)
        self._images = images
        self._spec = None                # (key, name, accent, banner, screenshot)
        self._cache: QPixmap | None = None
        self._previous: QPixmap | None = None
        self._fade = 1.0
        self._dim = 0.0
        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(420)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.valueChanged.connect(self._on_fade)
        self._fade_anim.finished.connect(self._drop_previous)
        self._dim_anim = QVariantAnimation(self)
        self._dim_anim.setDuration(260)
        self._dim_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._dim_anim.valueChanged.connect(self._on_dim)
        images.loaded.connect(self._on_image_loaded)

    def _on_fade(self, value):
        self._fade = float(value)
        self.update()

    def _drop_previous(self):
        self._previous = None
        self.update()

    def _on_dim(self, value):
        self._dim = float(value)
        self.update()

    def _on_image_loaded(self, ref: str):
        if self._spec and ref in (self._spec[3], self._spec[4]):
            self._cache = None
            self.update()

    def set_app(self, key: str, name: str, accent: str, banner: str = "", screenshot: str = "",
                animate: bool = True):
        spec = (key, name, accent, banner, screenshot)
        if spec == self._spec:
            return
        if animate and self._cache is not None:
            self._previous = self._cache
            self._fade_anim.stop()
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.start()
        else:
            self._fade = 1.0
        self._spec = spec
        self._cache = None
        self.update()

    def set_dimmed(self, dimmed: bool):
        self._dim_anim.stop()
        self._dim_anim.setStartValue(self._dim)
        self._dim_anim.setEndValue(0.86 if dimmed else 0.0)
        self._dim_anim.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._cache = None
        self._previous = None

    def screenshot_area(self) -> QRectF:
        w, h = self.width(), self.height()
        return QRectF(w * 0.53, 92, w * 0.47 - 56, max(80, h - CARDS_HEIGHT - 92 - 56))

    def _render(self) -> QPixmap:
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(theme.palette().bg))
        if self._spec is None:
            return pm
        _key, name, accent, banner_ref, shot_ref = self._spec
        rect = QRectF(0, 0, self.width(), self.height())
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        banner = self._images.get(banner_ref) if banner_ref else None
        if banner is not None:
            art.draw_cover(p, rect, banner)
        else:
            art.paint_backdrop(p, rect, accent, name)
            shot = self._images.get(shot_ref) if shot_ref else None
            if shot is not None:
                art.paint_screenshot(p, self.screenshot_area(), shot, accent)
        art.paint_legibility(p, rect)
        p.end()
        return pm

    def paintEvent(self, event):
        if self._cache is None or self._cache.size() != (self.size() * self.devicePixelRatioF()):
            self._cache = self._render()
        p = QPainter(self)
        if self._previous is not None and self._fade < 1.0:
            p.drawPixmap(0, 0, self._previous)
            p.setOpacity(self._fade)
        p.drawPixmap(0, 0, self._cache)
        p.setOpacity(1.0)
        if self._dim > 0:
            p.fillRect(self.rect(), art.with_alpha(QColor(theme.palette().bg), int(255 * self._dim)))
        p.end()


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

def chip(text: str, role: str = "chip", icon: str = "") -> QLabel:
    lbl = label(text, role)
    if icon:
        color = "#D5D9E2" if role == "chip" else theme.palette().warning
        lbl.setText(f"<img src='{_icon_resource(icon, color)}' width=11 height=11>&nbsp; {text}")
        lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


_ICON_CACHE: dict = {}


def _icon_resource(name: str, color: str) -> str:
    """Icon saved as a PNG data file so QLabel rich text can show it inline."""
    key = (name, color)
    if key not in _ICON_CACHE:
        import tempfile
        from pathlib import Path
        folder = Path(tempfile.gettempdir()) / "app-launcher-theme"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"inline-{name}-{color.strip('#')}.png"
        if not path.exists():
            icons.pixmap(name, color, 11, dpr=2.0).save(str(path), "PNG")
        _ICON_CACHE[key] = path.as_posix()
    return _ICON_CACHE[key]


class Card(QFrame):
    """Translucent card over the artwork; clickable when `clickable` is set."""

    clicked = pyqtSignal()

    def __init__(self, clickable: bool = True, parent=None):
        super().__init__(parent)
        self.setProperty("role", "glass")
        self.setProperty("clickable", "true" if clickable else "false")
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 14)
        self.lay.setSpacing(5)

    def mouseReleaseEvent(self, event):
        if self._clickable and event.button() == Qt.MouseButton.LeftButton \
                and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def overline(text: str, color: str) -> QLabel:
    lbl = label(text, "overline")
    lbl.setStyleSheet(f"color: {color};")
    return lbl


class HomePage(QWidget):
    open_notes = pyqtSignal(int)           # index in the history
    open_url = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._content = QWidget(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._content)
        lay = QVBoxLayout(self._content)
        lay.setContentsMargins(44, 22, 40, 28)
        lay.setSpacing(0)

        self.chips = QHBoxLayout()
        self.chips.setSpacing(6)
        lay.addLayout(self.chips)
        lay.addSpacing(14)
        self.title = label("", "hero-title")
        self.title.setMaximumWidth(560)
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        lay.addSpacing(4)
        self.tagline = label("", "hero-tagline", wrap=True)
        self.tagline.setMaximumWidth(470)
        lay.addWidget(self.tagline)
        lay.addSpacing(10)
        self.description = label("", "hero-text", wrap=True)
        self.description.setMaximumWidth(440)
        lay.addWidget(self.description)
        lay.addStretch(1)

        self.cards_holder = QWidget()
        self.cards_holder.setFixedHeight(CARDS_HEIGHT)
        self.cards = QHBoxLayout(self.cards_holder)
        self.cards.setContentsMargins(0, 0, 0, 0)
        self.cards.setSpacing(14)
        lay.addWidget(self.cards_holder)
        self._fx_anim = None

    # -- content ---------------------------------------------------------
    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def show_app(self, app, info: sources.AppInfo | None, accent: str, installed_key: str,
                 description: str, tagline: str, animate: bool = False):
        pal = theme.palette()
        self.title.setText(app.name.upper())
        self.tagline.setText(tagline)
        self.tagline.setVisible(bool(tagline))
        self.description.setText(description)
        self.description.setVisible(bool(description))

        self._clear(self.chips)
        repo = info.repository if info else None
        latest = info.latest if info else None
        if latest is not None:
            self.chips.addWidget(chip(latest.label, icon="tag"))
        if repo is not None:
            self.chips.addWidget(chip(str(repo.stars), icon="star"))
            if repo.language:
                self.chips.addWidget(chip(repo.language))
            if repo.license:
                self.chips.addWidget(chip(repo.license))
            if repo.archived:
                self.chips.addWidget(chip(tr("Archived"), "chip-warning", icon="alert"))
        if info is not None and info.offline:
            self.chips.addWidget(chip(tr("Offline"), "chip-warning", icon="alert"))
        self.chips.addStretch()

        self._clear(self.cards)
        history = [v for v in (info.history if info else ()) if v.title or v.notes]
        if latest is not None and (latest.notes or latest.title) and app.source == "github":
            news = Card()
            news.lay.addWidget(overline(tr("WHAT'S NEW · {version}", version=latest.label), QColor(accent).lighter(125).name()))
            title = label(latest.title, "card-title")
            news.lay.addWidget(title)
            notes = sources.localized_notes(latest.notes, language())
            text = label(sources.excerpt(notes, 150) or tr("No release notes."), "card-text", wrap=True)
            text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            news.lay.addWidget(text, 1)
            index = list(info.history).index(latest)
            news.clicked.connect(lambda i=index: self.open_notes.emit(i))
            self.cards.addWidget(news, 5)

        if history:
            releases = Card()
            releases.lay.addWidget(overline(tr("RELEASES · {count}", count=len(info.history)), pal.faint))
            for i, version in enumerate(list(info.history)[:3]):
                row = QHBoxLayout()
                name = label(version.label, "info-value")
                if version.key == installed_key:
                    name.setText(f"{version.label}  <span style='color:{pal.success}'>●</span>")
                    name.setTextFormat(Qt.TextFormat.RichText)
                row.addWidget(name)
                row.addStretch()
                row.addWidget(label(format_date(version.published), "card-text"))
                releases.lay.addLayout(row)
            releases.lay.addStretch()
            releases.clicked.connect(lambda: self.open_notes.emit(0))
            self.cards.addWidget(releases, 3)

        if repo is not None:
            card = Card()
            card.lay.addWidget(overline(tr("REPOSITORY"), pal.faint))
            name = label(repo.full_name, "card-title")
            card.lay.addWidget(name)
            stats = QLabel()
            stats.setTextFormat(Qt.TextFormat.RichText)
            stats.setProperty("role", "card-text")
            parts = [f"<img src='{_icon_resource('star', pal.muted)}' width=11 height=11> {repo.stars}",
                     f"<img src='{_icon_resource('fork', pal.muted)}' width=11 height=11> {repo.forks}"]
            if repo.has_issues:
                parts.append(f"<img src='{_icon_resource('alert', pal.muted)}' width=11 height=11> "
                             + tr("{count} open issues", count=repo.open_issues))
            stats.setText("&nbsp;&nbsp;&nbsp;".join(parts))
            card.lay.addWidget(stats)
            card.lay.addStretch()
            link = label(tr("Open on GitHub") + "  ↗", "card-text")
            link.setStyleSheet(f"color: {QColor(accent).lighter(125).name()};")
            card.lay.addWidget(link)
            card.clicked.connect(lambda url=repo.html_url: self.open_url.emit(url))
            self.cards.addWidget(card, 3)

        self.cards_holder.setVisible(self.cards.count() > 0)
        if animate:
            self._animate_in()

    def _animate_in(self):
        effect = QGraphicsOpacityEffect(self._content)
        self._content.setGraphicsEffect(effect)
        anim = QVariantAnimation(self)
        anim.setDuration(360)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: effect.setOpacity(float(v)))
        anim.finished.connect(lambda: self._content.setGraphicsEffect(None))
        self._fx_anim = anim
        anim.start()


# ---------------------------------------------------------------------------
# Release notes page
# ---------------------------------------------------------------------------

class NotesBrowser(QTextBrowser):
    """Markdown viewer that shows remote images (loaded by the ImageStore) scaled to fit."""

    def __init__(self, images, parent=None):
        super().__init__(parent)
        self._images = images
        self._wanted: set[str] = set()
        self.setProperty("role", "notes")
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(2)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Link, QColor(theme.palette().accent).lighter(130))
        self.setPalette(pal)
        images.loaded.connect(self._on_loaded)

    def _scaled(self, image: QImage) -> QImage:
        width = max(200, self.viewport().width() - 40)
        if image.width() > width:
            return image.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)
        return image

    def show_markdown(self, text: str):
        self._wanted = set(sources.markdown_images(text))
        self.setMarkdown(text or "")              # GitHub dialect: tables, task lists, autolinks
        self.moveCursor(QTextCursor.MoveOperation.Start)
        self._to_top()
        QTimer.singleShot(0, self._to_top)

    def _to_top(self):
        self.verticalScrollBar().setValue(0)
        self.horizontalScrollBar().setValue(0)

    def loadResource(self, kind, url: QUrl):
        if kind == QTextDocument.ResourceType.ImageResource.value or kind == QTextDocument.ResourceType.ImageResource:
            ref = url.toString()
            if is_url(ref):
                image = self._images.image(ref)
                if image is not None:
                    return self._scaled(image)
                return QImage()
        return None

    def _on_loaded(self, ref: str):
        if ref in self._wanted:
            image = self._images.image(ref)
            if image is not None:
                self.document().addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(ref),
                                            self._scaled(image))
                at_top = self.verticalScrollBar().value() == 0
                self.document().markContentsDirty(0, self.document().characterCount())
                self.horizontalScrollBar().setValue(0)
                if at_top:
                    self.verticalScrollBar().setValue(0)
                self.viewport().update()


class ReleaseItem(QWidget):
    def __init__(self, version: sources.Version, badges, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 9, 10, 9)
        lay.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(6)
        name = label(version.label, "card-title")
        top.addWidget(name)
        for text, color in badges:
            badge = QLabel(text)
            badge.setStyleSheet(f"color: {color}; border: 1px solid {color}; border-radius: 4px;"
                                "padding: 0 4px; font-size: 7pt; font-weight: 700;")
            top.addWidget(badge)
        top.addStretch()
        lay.addLayout(top)
        lay.addWidget(label(format_date(version.published), "card-text"))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class NotesPage(QWidget):
    open_url = pyqtSignal(str)

    def __init__(self, images, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 14, 32, 22)
        lay.setSpacing(0)

        self.list = QListWidget()
        self.list.setProperty("role", "releases")
        self.list.setFixedWidth(236)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._show)
        lay.addWidget(self.list)

        right = QVBoxLayout()
        right.setContentsMargins(30, 6, 0, 0)
        right.setSpacing(4)
        head = QHBoxLayout()
        self.heading = label("", "card-title")
        self.heading.setStyleSheet("font-size: 17pt;")
        head.addWidget(self.heading, 1)
        self.link = QPushButton(tr("View on GitHub"))
        self.link.setIcon(icons.icon("external", theme.palette().muted, 14))
        self.link.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link.clicked.connect(lambda: self._url and self.open_url.emit(self._url))
        head.addWidget(self.link, 0, Qt.AlignmentFlag.AlignTop)
        right.addLayout(head)
        self.meta = label("", "card-text")
        right.addWidget(self.meta)
        right.addSpacing(10)
        self.browser = NotesBrowser(images)
        right.addWidget(self.browser, 1)
        self.empty = label("", "muted", wrap=True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.empty, 1)
        lay.addLayout(right, 1)
        self._history: list = []
        self._url = ""

    def show_history(self, history, installed_key: str, latest_key: str, select: int = 0):
        pal = theme.palette()
        self._history = list(history)
        self.list.blockSignals(True)
        self.list.clear()
        for version in self._history:
            badges = []
            if version.key == latest_key:
                badges.append((tr("LATEST"), QColor(pal.accent).lighter(130).name()))
            if version.key == installed_key:
                badges.append((tr("INSTALLED"), pal.success))
            if version.prerelease:
                badges.append((tr("PRE-RELEASE"), pal.warning))
            item = QListWidgetItem()
            widget = ReleaseItem(version, badges)
            item.setSizeHint(QSize(220, 58))
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
        self.list.blockSignals(False)
        has = bool(self._history)
        for w in (self.list, self.heading, self.link, self.meta, self.browser):
            w.setVisible(has)
        self.empty.setVisible(not has)
        self.empty.setText(tr("No release notes for this application."))
        if has:
            self.list.setCurrentRow(max(0, min(select, len(self._history) - 1)))
            self._show(self.list.currentRow())

    def select(self, index: int):
        if 0 <= index < self.list.count():
            self.list.setCurrentRow(index)

    def _show(self, row: int):
        if not (0 <= row < len(self._history)):
            return
        version = self._history[row]
        self.heading.setText(version.title or version.label)
        parts = [version.label, format_date(version.published)]
        if version.size:
            from ..remote import format_size
            parts.append(f"{version.file_name} · {format_size(version.size)}")
        self.meta.setText("  ·  ".join(parts))
        self._url = version.url
        self.link.setVisible(bool(version.url))
        self.browser.show_markdown(sources.localized_notes(version.notes, language()) or tr("*No release notes.*"))


class Pages(QStackedWidget):
    """Transparent stack over the stage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
