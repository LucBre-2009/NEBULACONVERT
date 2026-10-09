from __future__ import annotations
import os, sys, shutil, subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QIcon, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QFileDialog, QComboBox, QLineEdit, QProgressBar,
    QMessageBox, QGroupBox, QFormLayout, QCheckBox, QFrame, QStackedWidget,
    QButtonGroup, QRadioButton, QAbstractItemView, QSizePolicy, QScrollArea, QTextBrowser, QDialog
)

APP_NAME = "NEBULACONVERT"

# ---- Conversion engines -----------------------------------------------------
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".ico"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".mpeg", ".mpg", ".wmv", ".flv", ".m4v"}
TEXT_EXTS = {".txt", ".md", ".csv", ".html", ".htm", ".rtf"}
DOC_EXTS = {".docx", ".odt", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".ods", ".odp"}
PDF_EXTS = {".pdf"}

TARGETS = {
    "Images": ["PNG", "JPG", "WEBP", "BMP", "TIFF", "ICO", "PDF"],
    "Audio": ["MP3", "WAV", "FLAC", "AAC", "OGG", "M4A"],
    "Video": ["MP4", "MKV", "MOV", "WEBM", "AVI", "GIF", "MP3"],
    "Documents": ["PDF", "TXT", "PNG", "JPG", "DOCX", "ODT", "HTML", "RTF"],
}

def engine_path(name: str) -> str | None:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for candidate in (root / "bin" / name, root / "bin" / f"{name}.exe"):
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name) or shutil.which(f"{name}.exe")

def category(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS: return "Images"
    if ext in AUDIO_EXTS: return "Audio"
    if ext in VIDEO_EXTS: return "Video"
    if ext in PDF_EXTS or ext in TEXT_EXTS or ext in DOC_EXTS: return "Documents"
    return "Unknown"

def available_targets(path: Path) -> list[str]:
    """Return formats with a plausible local implementation for this source type."""
    ext = path.suffix.lower()
    cat = category(path)
    if cat == "Images":
        targets = ["PNG", "JPG", "JPEG", "WEBP", "BMP", "TIFF", "ICO", "PDF"]
    elif cat == "Audio":
        targets = ["MP3", "WAV", "FLAC", "AAC", "OGG", "M4A"] if engine_path("ffmpeg") else []
    elif cat == "Video":
        targets = ["MP4", "MKV", "MOV", "WEBM", "AVI", "GIF", "MP3"] if engine_path("ffmpeg") else []
    elif ext == ".pdf":
        targets = ["TXT", "PNG", "JPG"]
        if engine_path("soffice") or engine_path("libreoffice"):
            targets += ["DOCX", "ODT", "HTML", "RTF"]
    elif ext in {".txt", ".md", ".csv", ".html", ".htm"}:
        targets = ["TXT", "PDF"]
    elif ext == ".rtf":
        targets = ["TXT", "PDF"] if engine_path("soffice") or engine_path("libreoffice") else ["TXT"]
    elif cat == "Documents" and (engine_path("soffice") or engine_path("libreoffice")):
        targets = ["PDF", "TXT", "HTML", "RTF", "DOCX", "ODT"]
    else:
        targets = []
    # Keep same-format choices visible. Selecting one copies the file into the
    # destination folder instead of trying to convert it onto itself.
    return targets

def convert_image(src: Path, dst: Path, target: str):
    from PIL import Image, ImageOps
    with Image.open(src) as original:
        im = ImageOps.exif_transpose(original)
        if target == "ICO":
            im = im.convert("RGBA")
            im.save(dst, format="ICO", sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
        elif target == "PDF":
            pages = []
            try:
                for frame in range(getattr(im, "n_frames", 1)):
                    im.seek(frame)
                    pages.append(im.convert("RGB").copy())
                if not pages: raise ValueError("No image data found.")
                pages[0].save(dst, "PDF", save_all=True, append_images=pages[1:])
            finally:
                for page in pages: page.close()
        else:
            fmt = "JPEG" if target in ("JPG", "JPEG") else target
            if fmt == "JPEG":
                if im.mode not in ("RGB", "L"):
                    rgba = im.convert("RGBA")
                    bg = Image.new("RGB", rgba.size, "white")
                    bg.paste(rgba, mask=rgba.getchannel("A"))
                    im = bg
                else: im = im.convert("RGB")
            elif fmt == "BMP" and im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(dst, format=fmt)

def run_ffmpeg(src: Path, dst: Path, target: str):
    ffmpeg = engine_path("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg fehlt. Lege ffmpeg.exe in den Ordner 'bin' neben der App.")
    args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    if target == "MP3" and category(src) == "Video":
        args += ["-vn", "-codec:a", "libmp3lame", "-q:a", "2"]
    elif target == "GIF":
        args += ["-vf", "fps=12,scale=720:-1:flags=lanczos"]
    elif target == "MP4":
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac"]
    elif target == "MP3": args += ["-codec:a", "libmp3lame", "-q:a", "2"]
    elif target == "WAV": args += ["-codec:a", "pcm_s16le"]
    elif target == "FLAC": args += ["-codec:a", "flac"]
    elif target == "AAC": args += ["-codec:a", "aac"]
    elif target == "OGG": args += ["-codec:a", "libvorbis"]
    elif target == "M4A": args += ["-codec:a", "aac"]
    proc = subprocess.run(args + [str(dst)], capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode:
        raise RuntimeError((proc.stderr or "FFmpeg-Konvertierung fehlgeschlagen.").strip()[-1500:])

def convert_document(src: Path, dst: Path, target: str):
    ext = src.suffix.lower()
    if ext in TEXT_EXTS and target == "PDF":
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase.pdfmetrics import stringWidth
        text = src.read_text(encoding="utf-8", errors="replace")
        c = canvas.Canvas(str(dst), pagesize=A4)
        width, height = A4
        margin, y = 48, height - 48
        c.setFont("Helvetica", 10)
        for raw in text.splitlines() or [""]:
            current, chunks = "", []
            for word in raw.split(" "):
                trial = (current + " " + word).strip()
                if stringWidth(trial, "Helvetica", 10) > width - 2*margin and current:
                    chunks.append(current); current = word
                else: current = trial
            chunks.append(current)
            for line in chunks:
                if y < margin:
                    c.showPage(); c.setFont("Helvetica", 10); y = height - margin
                c.drawString(margin, y, line); y -= 14
            y -= 2
        c.save()
        return
    if ext == ".pdf" and target in ("PNG", "JPG"):
        import fitz
        with fitz.open(src) as doc:
            if len(doc) != 1:
                raise RuntimeError("PDF → Bild unterstützt derzeit nur einseitige PDFs.")
            doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(dst))
        return
    if ext == ".pdf" and target == "TXT":
        import fitz
        with fitz.open(src) as doc:
            dst.write_text("\n\n".join(page.get_text() for page in doc), encoding="utf-8")
        return
    if ext in TEXT_EXTS and target == "TXT":
        dst.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        return
    soffice = engine_path("soffice") or engine_path("libreoffice")
    if soffice and (ext in DOC_EXTS or ext in {".pdf", ".html", ".htm", ".rtf"}):
        fmt = target.lower()
        proc = subprocess.run([soffice, "--headless", "--convert-to", fmt, "--outdir", str(dst.parent), str(src)],
                              capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        generated = dst.parent / f"{src.stem}.{fmt}"
        if proc.returncode == 0 and generated.exists():
            if generated != dst:
                if dst.exists(): dst.unlink()
                generated.rename(dst)
            return
        raise RuntimeError((proc.stderr or proc.stdout or "LibreOffice konnte nicht konvertieren.").strip()[-1500:])
    raise RuntimeError("Für diese Dateikombination ist kein passender lokaler Konverter verfügbar.")

def convert_one(src: Path, outdir: Path, target: str, overwrite: bool) -> Path:
    target = target.upper()
    ext = {"JPG": ".jpg", "JPEG": ".jpeg", "TIFF": ".tiff"}.get(target, "." + target.lower())
    dst = outdir / f"{src.stem}{ext}"
    same_format = {
        ".jpg": {"JPG", "JPEG"}, ".jpeg": {"JPG", "JPEG"},
        ".tif": {"TIFF"}, ".tiff": {"TIFF"},
    }
    source_ext = src.suffix.lower()
    source_as_format = source_ext.lstrip(".").upper()
    if target in same_format.get(source_ext, {source_as_format}):
        ext = src.suffix
        dst = outdir / f"{src.stem}{ext}"
        if src.resolve() == dst.resolve():
            # If source already is in the output folder, it is already done.
            return src
        if dst.exists() and not overwrite:
            n = 2
            while (outdir / f"{src.stem}_{n}{ext}").exists(): n += 1
            dst = outdir / f"{src.stem}_{n}{ext}"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        return dst
    if src.resolve() == dst.resolve():
        raise RuntimeError("Quelldatei und Zieldatei wären identisch.")
    if dst.exists() and not overwrite:
        n = 2
        while (outdir / f"{src.stem}_{n}{ext}").exists(): n += 1
        dst = outdir / f"{src.stem}_{n}{ext}"
    cat = category(src)
    if cat == "Images": convert_image(src, dst, target)
    elif cat in ("Audio", "Video"): run_ffmpeg(src, dst, target)
    elif cat == "Documents": convert_document(src, dst, target)
    else: raise RuntimeError("Nicht unterstütztes Eingabeformat.")
    return dst

class ConvertWorker(QThread):
    progress = Signal(int)
    log = Signal(str, bool)
    done = Signal(int, int)
    def __init__(self, paths, output, targets, overwrite):
        super().__init__()
        self.paths, self.output, self.targets, self.overwrite = paths, output, targets, overwrite
    def run(self):
        ok = fail = 0
        for i, path in enumerate(self.paths, 1):
            try:
                target = self.targets.get(str(path.resolve()), "")
                if not target: raise RuntimeError("Für diese Datei wurde kein Ausgabeformat gewählt.")
                if target not in available_targets(path): raise RuntimeError(f"{target} wird für {path.suffix} nicht unterstützt.")
                result = convert_one(path, self.output, target, self.overwrite)
                self.log.emit(f"{path.name}  →  {result.name}", True); ok += 1
            except Exception as e:
                self.log.emit(f"{path.name}  ·  {e}", False); fail += 1
            self.progress.emit(round(i * 100 / max(1, len(self.paths))))
        self.done.emit(ok, fail)

class DropList(QListWidget):
    files_dropped = Signal(list)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()
    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.files_dropped.emit(paths); event.acceptProposedAction()

class CompletionDialog(QDialog):
    """Large, non-blocking completion panel so the main app stays usable."""
    def __init__(self, parent, ok, failed, language="English"):
        super().__init__(parent)
        self.setWindowTitle("Conversion complete" if language == "English" else "Konvertierung abgeschlossen")
        self.setModal(False)
        self.setMinimumSize(540, 300)
        self.resize(600, 340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("Conversion complete" if language == "English" else "Konvertierung abgeschlossen")
        title.setStyleSheet("font-size:24px;font-weight:800;")
        title.setWordWrap(True)
        body = QLabel((f"Successfully converted: {ok}\nFailed: {failed}\n\nYour files were processed locally." if language == "English" else f"Erfolgreich: {ok}\nFehlgeschlagen: {failed}\n\nDeine Dateien wurden lokal verarbeitet."))
        body.setStyleSheet("font-size:15px;")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton("Close" if language == "English" else "Schließen")
        close.setMinimumWidth(120)
        close.clicked.connect(self.close)
        row.addWidget(close)
        layout.addLayout(row)


class NebulaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NEBULACONVERT")
        icon_path = Path(__file__).resolve().parent / "assets" / "nebulaconvert.ico"
        if icon_path.exists(): self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1120, 760)
        self.setMinimumSize(850, 600)
        self.paths: list[Path] = []
        self.worker = None
        self.prefs = QSettings("NebulaConvert", "NebulaConvert")
        self.dark = self.prefs.value("dark_mode", True, type=bool)
        self.language = self.prefs.value("language", "English", type=str)
        self.color_style = self.prefs.value("color_style", "Nebula Violet", type=str)
        self.default_output = self.prefs.value("destination", str(Path.home() / "Downloads"), type=str)
        self._use_borderless = True
        self._is_borderless_fullscreen = False
        self._normal_geometry = None
        self._activity_items: list[tuple[str, bool]] = []
        self._spinner_step = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(90)
        self._spinner_timer.timeout.connect(self._animate_conversion)
        self._build()
        self._shortcut_f11 = QShortcut(Qt.Key_F11, self); self._shortcut_f11.activated.connect(self.toggle_fullscreen_safe)
        self._shortcut_esc = QShortcut(Qt.Key_Escape, self); self._shortcut_esc.activated.connect(self.exit_fullscreen_safe)
        self._shortcut_quit = QShortcut(Qt.CTRL | Qt.Key_Q, self); self._shortcut_quit.activated.connect(self.close)
        # Use the settings checkbox as the single source of truth for overwrite behavior.
        # The old startup code referenced self.overwrite before it existed.
        self.overwrite = self.settings_overwrite
        self.output_summary.setText(self.default_output)
        self.settings_output.setText(self.default_output)
        self.overwrite.setChecked(self.prefs.value("overwrite", False, type=bool))
        self.settings_overwrite.setChecked(self.overwrite.isChecked())
        self.borderless_check.setChecked(self.prefs.value("borderless", True, type=bool))
        self._use_borderless = self.borderless_check.isChecked()
        self.settings_colors.setCurrentText(self.color_style)
        self.apply_theme()
        self.apply_language()

    def _build(self):
        shell = QWidget(); self.setCentralWidget(shell)
        outer = QHBoxLayout(shell); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(230)
        side = QVBoxLayout(self.sidebar); side.setContentsMargins(20,24,20,20); side.setSpacing(12)
        brandrow = QHBoxLayout()
        logo = QLabel("✦"); logo.setObjectName("logo")
        brand = QLabel("NEBULA\nCONVERT"); brand.setObjectName("brand")
        brandrow.addWidget(logo); brandrow.addWidget(brand); brandrow.addStretch()
        side.addLayout(brandrow)
        sub = QLabel("LOCAL FILE STUDIO"); sub.setObjectName("eyebrow"); side.addWidget(sub)
        side.addSpacing(24)
        self.nav_convert = QPushButton("▦   Converter"); self.nav_convert.setObjectName("navActive")
        self.nav_history = QPushButton("◷   Aktivität")
        self.nav_settings = QPushButton("⚙   Einstellungen")
        self.nav_about = QPushButton("◈   Über")
        for b in (self.nav_convert, self.nav_history, self.nav_settings, self.nav_about):
            b.setCursor(Qt.PointingHandCursor); b.setMinimumHeight(42); b.setCheckable(False); side.addWidget(b)
        self.nav_convert.clicked.connect(self.show_converter)
        self.nav_history.clicked.connect(self.show_history)
        self.nav_settings.clicked.connect(self.show_settings)
        self.nav_about.clicked.connect(self.show_about)
        side.addStretch()
        self.offline_badge = QLabel("●  OFFLINE-FIRST"); self.offline_badge.setObjectName("offlineBadge")
        side.addWidget(self.offline_badge)
        version = QLabel("NEBULA CONVERT  ·  BETA"); version.setObjectName("muted")
        side.addWidget(version)
        outer.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.page = QWidget(); content = QVBoxLayout(self.page)
        content.setContentsMargins(30,26,30,26); content.setSpacing(18)
        top = QHBoxLayout()
        titlecol = QVBoxLayout()
        self.page_title = QLabel("File conversion, reimagined"); self.page_title.setObjectName("pageTitle")
        self.page_sub = QLabel("Convert files privately, right on your device."); self.page_sub.setObjectName("muted")
        titlecol.addWidget(self.page_title); titlecol.addWidget(self.page_sub)
        top.addLayout(titlecol); top.addStretch()
        self.add_btn = QPushButton("＋  Mehrere Dateien hinzufügen"); self.add_btn.setObjectName("primary")
        self.add_btn.setMinimumHeight(42); self.add_btn.clicked.connect(self.pick_files)
        top.addWidget(self.add_btn); content.addLayout(top)

        self.drop = DropList(); self.drop.files_dropped.connect(self.add_paths)
        # Keep the queue viewport bounded: long batches scroll inside the list
        # instead of stretching the entire page beyond the available height.
        self.drop.setMinimumHeight(180); self.drop.setMaximumHeight(290); self.drop.setObjectName("dropZone")
        self.drop.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drop.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        content.addWidget(self.drop, 1)
        drop_hint = QLabel("DROP FILES HERE  ·  MULTIPLE FILES SUPPORTED"); drop_hint.setObjectName("dropHint")
        drop_hint.setAlignment(Qt.AlignCenter); content.addWidget(drop_hint)

        settingsrow = QHBoxLayout(); settingsrow.setSpacing(14)
        targetbox = QGroupBox("AUSGABEFORMAT · FÜR ALLE"); targetlayout = QVBoxLayout(targetbox)
        self.target = QComboBox(); self.target.addItem("Add files first")
        self.target.setEnabled(False); self.target.setMinimumHeight(42); targetlayout.addWidget(self.target)
        self.apply_all_btn = QPushButton("Format auf alle anwenden")
        self.apply_all_btn.clicked.connect(self.apply_format_to_all); targetlayout.addWidget(self.apply_all_btn)
        targetnote = QLabel("The list updates to show compatible formats for your files."); targetnote.setObjectName("muted")
        targetnote.setWordWrap(True); targetlayout.addWidget(targetnote)
        self.target_note = targetnote
        destbox = QGroupBox("ZIELORDNER"); destlayout = QVBoxLayout(destbox)
        self.output_summary = QLabel(self.default_output); self.output_summary.setObjectName("muted")
        self.output_summary.setWordWrap(True); destlayout.addWidget(self.output_summary)
        destnote = QLabel("Change the default destination in Settings."); destnote.setObjectName("muted")
        destnote.setWordWrap(True); destlayout.addWidget(destnote)
        settingsrow.addWidget(targetbox, 1); settingsrow.addWidget(destbox, 1)
        content.addLayout(settingsrow)

        actionrow = QHBoxLayout()
        self.convert_btn = QPushButton("✦   Konvertierung starten"); self.convert_btn.setObjectName("primary")
        self.convert_btn.setMinimumHeight(48); self.convert_btn.clicked.connect(self.start)
        self.clear_btn = QPushButton("Liste leeren"); self.clear_btn.setMinimumHeight(48); self.clear_btn.clicked.connect(self.clear_queue)
        actionrow.addWidget(self.convert_btn, 2); actionrow.addWidget(self.clear_btn, 1)
        content.addLayout(actionrow)
        self.progress = QProgressBar(); self.progress.setValue(0); self.progress.setFormat("READY  ·  %p%")
        content.addWidget(self.progress)
        self.status_label = QLabel("Ready · your files stay on this device."); self.status_label.setObjectName("muted")
        content.addWidget(self.status_label)
        self.log_title = QLabel("RECENT ACTIVITY"); self.log_title.setObjectName("eyebrow"); content.addWidget(self.log_title)
        self.log = QListWidget(); self.log.setMaximumHeight(82); content.addWidget(self.log)
        # The main workspace scrolls on compact / windowed displays, avoiding
        # clipped controls when the app is not in fullscreen.
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.page_scroll.setWidget(self.page)
        self.stack.addWidget(self.page_scroll)

        self.info_page = QWidget(); il = QVBoxLayout(self.info_page); il.setContentsMargins(34,34,34,34); il.setSpacing(16)
        self.info_title = QLabel("Activity"); self.info_title.setObjectName("pageTitle")
        self.info_text = QTextBrowser()
        self.info_text.setObjectName("muted"); self.info_text.setOpenExternalLinks(False); self.info_text.setMinimumHeight(110); self.info_text.setMaximumHeight(150)
        self.activity_summary = QLabel("No conversions yet."); self.activity_summary.setObjectName("muted")
        self.activity_list = QListWidget(); self.activity_list.setMinimumHeight(300)
        clear_history = QPushButton("Clear activity history"); clear_history.clicked.connect(self.clear_history)
        back = QPushButton("←  Back to converter"); back.clicked.connect(self.show_converter)
        il.addWidget(self.info_title); il.addWidget(self.info_text); il.addWidget(self.activity_summary)
        il.addWidget(self.activity_list, 1); il.addWidget(clear_history); il.addWidget(back, 0, Qt.AlignLeft)
        self.info_scroll = QScrollArea(); self.info_scroll.setWidgetResizable(True); self.info_scroll.setFrameShape(QFrame.NoFrame)
        self.info_scroll.setWidget(self.info_page)
        self.stack.addWidget(self.info_scroll)

        self.settings_page = QWidget(); sl = QVBoxLayout(self.settings_page); sl.setContentsMargins(34,34,34,34); sl.setSpacing(18)
        st = QLabel("Settings"); st.setObjectName("pageTitle")
        ss = QLabel("Set the defaults NebulaConvert uses on this computer."); ss.setObjectName("muted")
        appearance_box = QGroupBox("APPEARANCE"); al = QVBoxLayout(appearance_box)
        self.settings_theme = QComboBox(); self.settings_theme.addItems(["Dark mode", "Light mode"])
        self.settings_theme.currentIndexChanged.connect(self._settings_theme_changed); al.addWidget(QLabel("Appearance")); al.addWidget(self.settings_theme)
        self.settings_language = QComboBox(); self.settings_language.addItems(["English", "Deutsch"])
        self.settings_language.setCurrentText(self.language)
        self.settings_language.currentTextChanged.connect(self._language_changed)
        al.addWidget(QLabel("Language / Sprache")); al.addWidget(self.settings_language)
        self.settings_colors = QComboBox(); self.settings_colors.addItems(["Nebula Violet", "Ocean Blue", "Emerald", "Rose", "Amber"])
        self.settings_colors.setCurrentText(self.color_style if self.color_style in ["Nebula Violet", "Ocean Blue", "Emerald", "Rose", "Amber"] else "Nebula Violet")
        self.settings_colors.currentTextChanged.connect(self._color_changed)
        al.addWidget(QLabel("Accent color style")); al.addWidget(self.settings_colors)
        destination_box = QGroupBox("DEFAULT DESTINATION"); dl = QVBoxLayout(destination_box)
        self.settings_output = QLineEdit(self.default_output); self.settings_output.setMinimumHeight(42)
        choose_dest = QPushButton("Browse for folder…"); choose_dest.clicked.connect(self.pick_settings_output)
        dl.addWidget(QLabel("Converted files are saved here by default:")); dl.addWidget(self.settings_output); dl.addWidget(choose_dest)
        behavior_box = QGroupBox("CONVERSION BEHAVIOR"); bl = QVBoxLayout(behavior_box)
        self.settings_overwrite = QCheckBox("Overwrite existing files (otherwise add a number to the filename)")
        bl.addWidget(self.settings_overwrite)
        self.borderless_check = QCheckBox("F11 uses borderless fullscreen")
        self.borderless_check.setChecked(True); bl.addWidget(self.borderless_check)
        self.settings_hint = QLabel("F11 toggles fullscreen. Press Esc to leave borderless fullscreen."); self.settings_hint.setObjectName("muted")
        bl.addWidget(self.settings_hint)
        save_settings = QPushButton("Save settings"); save_settings.setObjectName("primary"); save_settings.clicked.connect(self.save_settings)
        back2 = QPushButton("←  Back to converter"); back2.clicked.connect(self.show_converter)
        sl.addWidget(st); sl.addWidget(ss); sl.addWidget(appearance_box); sl.addWidget(destination_box); sl.addWidget(behavior_box); sl.addWidget(save_settings, 0, Qt.AlignLeft); sl.addWidget(back2, 0, Qt.AlignLeft); sl.addStretch()
        self.settings_scroll = QScrollArea(); self.settings_scroll.setWidgetResizable(True); self.settings_scroll.setFrameShape(QFrame.NoFrame)
        self.settings_scroll.setWidget(self.settings_page)
        self.stack.addWidget(self.settings_scroll)

    def apply_theme(self):
        accents = {
            "Nebula Violet": ("#6d5dfc", "#8175ff", "#5b4be8", "#a99fff"),
            "Ocean Blue": ("#1687ff", "#52a7ff", "#0969da", "#8fc7ff"),
            "Emerald": ("#10a878", "#35d6a2", "#087f5b", "#75e8bf"),
            "Rose": ("#e34f91", "#ff7db4", "#c92e70", "#ffadd0"),
            "Amber": ("#d98b13", "#ffbd4a", "#b86b00", "#ffd27a"),
        }
        accent, accent_border, accent_hover, accent_text = accents.get(self.color_style, accents["Nebula Violet"])
        if self.dark:
            bg, panel, side, fg, muted, border = "#0b1020", "#121a2c", "#080d19", "#eef2ff", "#94a3b8", "#27334b"
            field, hover, dropbg = "#0d1526", "#1b2941", "#0e1729"

        else:
            bg, panel, side, fg, muted, border = "#f4f7fc", "#ffffff", "#eaf0fb", "#14213d", "#65748b", "#d8e1ef"
            field, hover, dropbg = "#ffffff", "#e8eef8", "#f8fbff"

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background:{bg}; color:{fg}; font-size:13px; }}
            #sidebar {{ background:{side}; border-right:1px solid {border}; }}
            #logo {{ color:#8b7bff; font-size:32px; font-weight:900; }}
            #brand {{ color:{fg}; font-size:17px; font-weight:900; letter-spacing:1px; }}
            #eyebrow {{ color:#8b7bff; font-size:10px; font-weight:800; letter-spacing:2px; }}
            #muted {{ color:{muted}; font-size:12px; }}
            #pageTitle {{ color:{fg}; font-size:25px; font-weight:800; }}
            #offlineBadge {{ color:#4adea6; background:rgba(74,222,166,0.10); border:1px solid rgba(74,222,166,0.3); border-radius:8px; padding:9px; font-size:10px; font-weight:800; }}
            QPushButton {{ background:{panel}; color:{fg}; border:1px solid {border}; border-radius:9px; padding:10px 13px; font-weight:600; }}
            QPushButton:hover {{ background:{hover}; border-color:#7467f0; }}
            QPushButton#primary {{ background:{accent}; color:#ffffff; border:1px solid {accent_border}; font-size:14px; font-weight:800; }}
            QPushButton#primary:hover {{ background:{accent_hover}; }}
            QPushButton#navActive {{ background:{accent}22; border:1px solid {accent_border}66; color:{accent_text}; text-align:left; }}
            QLineEdit, QComboBox {{ background:{field}; color:{fg}; border:1px solid {border}; border-radius:8px; padding:9px; selection-background-color:{accent}; }}
            QComboBox QAbstractItemView {{ background:{panel}; color:{fg}; selection-background-color:{accent}; }}
            QGroupBox {{ background:{panel}; border:1px solid {border}; border-radius:12px; margin-top:8px; padding:12px; font-weight:800; color:{muted}; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:12px; padding:0 5px; }}
            QScrollArea {{ background:transparent; border:0; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
            QListWidget {{ background:{panel}; color:{fg}; border:1px solid {border}; border-radius:12px; padding:7px; outline:0; }}
            QListWidget::item {{ border-bottom:1px solid {border}; padding:2px; }}
            QListWidget::item:selected {{ background:{hover}; }}
            QListWidget#dropZone {{ background:{dropbg}; border:2px dashed #4e4b94; padding:12px; }}
            QProgressBar {{ background:{panel}; color:{fg}; border:1px solid {border}; border-radius:7px; text-align:center; min-height:20px; }}
            QProgressBar::chunk {{ background:{accent}; border-radius:6px; }}
            QCheckBox {{ color:{fg}; spacing:8px; }}
            QScrollBar:vertical {{ background:{field}; width:10px; margin:2px; }}
            QScrollBar::handle:vertical {{ background:{border}; border-radius:4px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)

    def toggle_theme(self):
        self.dark = not self.dark
        self.prefs.setValue("dark_mode", self.dark)
        if hasattr(self, "settings_theme"):
            self.settings_theme.blockSignals(True); self.settings_theme.setCurrentIndex(0 if self.dark else 1); self.settings_theme.blockSignals(False)
        self.apply_theme()

    def _settings_theme_changed(self, index):
        self.dark = (index == 0)
        self.prefs.setValue("dark_mode", self.dark)
        self.apply_theme()

    def _color_changed(self, style):
        self.color_style = style
        self.prefs.setValue("color_style", style)
        self.apply_theme()

    def _language_changed(self, language):
        self.language = language
        self.prefs.setValue("language", language)
        self.apply_language()

    def apply_language(self):
        de = self.language == "Deutsch"
        self.nav_convert.setText("▦   Konverter" if de else "▦   Converter")
        self.nav_history.setText("◷   Aktivität" if de else "◷   Activity")
        self.nav_settings.setText("⚙   Einstellungen" if de else "⚙   Settings")
        self.nav_about.setText("◈   Über" if de else "◈   About")
        self.add_btn.setText("＋  Mehrere Dateien hinzufügen" if de else "＋  Add multiple files")
        self.apply_all_btn.setText("Format auf alle anwenden" if de else "Apply format to all")
        self.convert_btn.setText("✦   Konvertierung starten" if de else "✦   Start conversion")
        self.clear_btn.setText("Liste leeren" if de else "Clear list")
        self.settings_output.setPlaceholderText("Zielordner" if de else "Destination folder")
        self.settings_overwrite.setText("Vorhandene Dateien überschreiben" if de else "Overwrite existing files (otherwise add a number to the filename)")
        self.borderless_check.setText("F11 verwendet rahmenlosen Vollbildmodus" if de else "F11 uses borderless fullscreen")
        self.settings_hint.setText("F11 schaltet Vollbild um. Esc beendet den rahmenlosen Vollbildmodus." if de else "F11 toggles fullscreen. Press Esc to leave borderless fullscreen.")
        self.page_title.setText("Dateien konvertieren" if de else "File conversion, reimagined")
        self.page_sub.setText("Wähle deine Dateien und das gewünschte Ausgabeformat." if de else "Convert files privately, right on your device.")

    def show_converter(self):
        self.stack.setCurrentIndex(0)
        self.page_title.setText("Dateien konvertieren")
        self.page_sub.setText("Wähle deine Dateien und das gewünschte Ausgabeformat.")

    def show_settings(self):
        self.settings_theme.blockSignals(True); self.settings_theme.setCurrentIndex(0 if self.dark else 1); self.settings_theme.blockSignals(False)
        self.settings_output.setText(self.output_summary.text())
        self.settings_overwrite.setChecked(self.overwrite.isChecked())
        self.stack.setCurrentWidget(self.settings_scroll)

    def pick_settings_output(self):
        current = self.settings_output.text().strip() or str(Path.home() / "Downloads")
        folder = QFileDialog.getExistingDirectory(self, "Choose default destination", current)
        if folder: self.settings_output.setText(folder)

    def save_settings(self):
        dest = Path(self.settings_output.text().strip()).expanduser()
        if not self.settings_output.text().strip():
            QMessageBox.warning(self, "Destination missing", "Choose a destination folder first."); return
        try: dest.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Destination error", str(e)); return
        self.output_summary.setText(str(dest))
        self.default_output = str(dest)
        self.overwrite.setChecked(self.settings_overwrite.isChecked())
        self._use_borderless = self.borderless_check.isChecked()
        self.prefs.setValue("destination", str(dest))
        self.prefs.setValue("dark_mode", self.dark)
        self.prefs.setValue("overwrite", self.overwrite.isChecked())
        self.prefs.setValue("borderless", self._use_borderless)
        self.language = self.settings_language.currentText()
        self.color_style = self.settings_colors.currentText()
        self.prefs.setValue("language", self.language)
        self.prefs.setValue("color_style", self.color_style)
        self.apply_language()
        QMessageBox.information(self, "Settings saved", "Settings saved for your Windows user and will be reused next time." if self.language == "English" else "Einstellungen wurden gespeichert und beim nächsten Start wiederverwendet.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self._use_borderless: self.toggle_borderless_fullscreen()
            else:
                if self.isFullScreen(): self.showNormal()
                else: self.showFullScreen()
            event.accept(); return
        if event.key() == Qt.Key_Escape and self._is_borderless_fullscreen:
            self.exit_borderless_fullscreen(); event.accept(); return
        super().keyPressEvent(event)

    def toggle_fullscreen_safe(self):
        try:
            if self._use_borderless:
                self.toggle_borderless_fullscreen()
            elif self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        except Exception as exc:
            QMessageBox.warning(self, "Fullscreen error", str(exc))

    def exit_fullscreen_safe(self):
        if self._is_borderless_fullscreen:
            self.exit_borderless_fullscreen()
        elif self.isFullScreen():
            self.showNormal()

    def toggle_borderless_fullscreen(self):
        if self._is_borderless_fullscreen:
            self.exit_borderless_fullscreen(); return
        self._normal_geometry = self.geometry()
        self._is_borderless_fullscreen = True
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.showFullScreen()

    def exit_borderless_fullscreen(self):
        self._is_borderless_fullscreen = False
        self.setWindowFlag(Qt.FramelessWindowHint, False)
        self.showNormal()
        if self._normal_geometry is not None: self.setGeometry(self._normal_geometry)

    def _animate_conversion(self):
        frames = ["◐", "◓", "◑", "◒"]
        self._spinner_step = (self._spinner_step + 1) % len(frames)
        self.status_label.setText(f"{frames[self._spinner_step]}  Converting locally…")

    def add_paths(self, paths):
        known = {str(p.resolve()) for p in self.paths}
        for raw in paths:
            p = Path(raw)
            if p.is_file() and str(p.resolve()) not in known:
                self.paths.append(p); known.add(str(p.resolve()))
        self.refresh_file_rows()
        self.update_targets()

    def refresh_file_rows(self):
        self.drop.clear()
        for path in self.paths:
            item = __import__("PySide6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem(self.drop)
            item.setSizeHint(__import__("PySide6.QtCore", fromlist=["QSize"]).QSize(10, 56))
            row = QWidget(); lay = QHBoxLayout(row); lay.setContentsMargins(8, 3, 8, 3); lay.setSpacing(10)
            icon = QLabel("▣"); icon.setStyleSheet("color:#8b7bff;font-size:20px;font-weight:800;"); icon.setFixedWidth(26)
            details = QVBoxLayout(); details.setSpacing(2); name = QLabel(path.name); name.setToolTip(str(path)); name.setStyleSheet("font-weight:700;")
            name.setMinimumWidth(0); name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            try: size = f"{path.stat().st_size / 1024:.0f} KB · {category(path)}"
            except OSError: size = category(path)
            sub = QLabel(size); sub.setObjectName("muted"); details.addWidget(name); details.addWidget(sub)
            combo = QComboBox(); combo.setMinimumWidth(95); combo.setMaximumWidth(180)
            combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            options = available_targets(path)
            if options: combo.addItems(options)
            else: combo.addItem("No formats available")
            combo.setProperty("source_path", str(path.resolve()))
            combo.currentTextChanged.connect(self.sync_global_target)
            remove = QPushButton("×"); remove.setFixedWidth(34); remove.setToolTip("Remove file")
            remove.clicked.connect(lambda checked=False, p=path: self.remove_path(p))
            output_label = QLabel("Output:"); output_label.setObjectName("muted")
            lay.addWidget(icon); lay.addLayout(details, 1); lay.addWidget(output_label); lay.addWidget(combo); lay.addWidget(remove)
            row.setMinimumWidth(0)
            self.drop.setItemWidget(item, row)
        # Do not grow the queue widget with each added file; keep a stable
        # viewport and let QListWidget handle overflow with its own scrollbar.
        self.drop.setMinimumHeight(180)
        self.drop.setMaximumHeight(290)
        self.drop.setToolTip(f"{len(self.paths)} file(s) queued")

    def remove_path(self, path):
        if self.worker and self.worker.isRunning(): return
        self.paths = [p for p in self.paths if p != path]
        self.refresh_file_rows(); self.update_targets()

    def sync_global_target(self, *_):
        # Refresh the global menu whenever per-file choices change.
        self.update_targets()

    def update_targets(self):
        current = self.target.currentText()
        self.target.blockSignals(True); self.target.clear()
        if not self.paths:
            self.target.addItem("Add files first"); self.target.setEnabled(False)
        else:
            # Show every format supported by at least one selected file.
            # Applying a global format updates only files that support it.
            options = set()
            for p in self.paths: options.update(available_targets(p))
            ordered = [t for t in ["PNG","JPG","JPEG","WEBP","ICO","BMP","TIFF","PDF","TXT","HTML","RTF","DOCX","ODT","MP4","MKV","MOV","WEBM","AVI","GIF","MP3","WAV","FLAC","AAC","OGG","M4A"] if t in options]
            self.target.addItems(ordered)
            self.target.setEnabled(bool(ordered))
            if current in ordered: self.target.setCurrentText(current)
            if not ordered: self.target.addItem("No formats available")
        self.target.blockSignals(False)

    def apply_format_to_all(self):
        target = self.target.currentText()
        if not self.paths or not self.target.isEnabled() or target in ("Add files first", "No formats available"):
            QMessageBox.information(self, "No format available", "Add files and choose an available format first."); return
        applied = skipped = 0
        for i in range(self.drop.count()):
            widget = self.drop.itemWidget(self.drop.item(i))
            combo = widget.findChildren(QComboBox)[0] if widget else None
            if combo and combo.findText(target) >= 0:
                combo.setCurrentText(target); applied += 1
            else:
                skipped += 1
        if skipped:
            QMessageBox.information(self, "Format applied", f"{target} selected for {applied} compatible file(s). {skipped} file(s) were skipped because that format is not supported for their type.")

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add files to NebulaConvert")
        self.add_paths(files)
    def pick_output(self):
        self.pick_settings_output()
    def clear_queue(self):
        if self.worker and self.worker.isRunning(): return
        self.paths.clear(); self.drop.clear(); self.update_targets(); self.progress.setValue(0); self.progress.setFormat("READY  ·  %p%"); self.status_label.setText("Ready · your files stay on this device.")
    def start(self):
        if not self.paths:
            QMessageBox.information(self, "Queue is empty", "Add files or drag them into the drop zone first."); return
        targets = {}
        for i, path in enumerate(self.paths):
            item = self.drop.item(i); row = self.drop.itemWidget(item)
            combo = row.findChildren(QComboBox)[0] if row else None
            target_for_file = combo.currentText() if combo else ""
            if target_for_file not in available_targets(path):
                QMessageBox.warning(self, "Output format missing", f"Choose a valid output format for {path.name}."); return
            targets[str(path.resolve())] = target_for_file
        output = Path(self.output_summary.text()).expanduser()
        try: output.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Destination error", str(e)); return
        self.convert_btn.setEnabled(False); self.add_btn.setEnabled(False)
        self.progress.setValue(0); self.progress.setFormat("CONVERTING  ·  %p%")
        self.status_label.setText("◐  Preparing local conversion…"); self._spinner_timer.start()
        self.worker = ConvertWorker(self.paths.copy(), output, targets, self.overwrite.isChecked())
        self.worker.progress.connect(self.progress.setValue)
        self.worker.log.connect(self.add_log)
        self.worker.done.connect(self.finished)
        self.worker.start()
    def add_log(self, message, success):
        self.log.addItem(("✓  " if success else "✕  ") + message)
        self.log.scrollToBottom()
        self._activity_items.append((message, success))
        self.activity_list.addItem(("✓  " if success else "✕  ") + message)
        self.activity_summary.setText(f"{len(self._activity_items)} conversion result(s) this session. Nothing is uploaded.")
    def finished(self, ok, failed):
        self._spinner_timer.stop()
        self.convert_btn.setEnabled(True); self.add_btn.setEnabled(True)
        self.progress.setFormat("DONE  ·  %p%")
        self.status_label.setText(f"Finished · {ok} successful, {failed} failed.")
        self.log.addItem(f"SESSION COMPLETE  —  {ok} successful · {failed} failed")
        QApplication.beep()
        self.completion_dialog = CompletionDialog(self, ok, failed, self.language)
        self.completion_dialog.show()
        self.completion_dialog.raise_()
        self.completion_dialog.activateWindow()
    def clear_history(self):
        self._activity_items.clear(); self.activity_list.clear(); self.log.clear()
        self.activity_summary.setText("No conversions yet.")

    def show_history(self):
        self.info_title.setText("Activity")
        self.info_text.setText("A session-only history of conversion results. Files and logs remain on this computer; this prototype does not upload activity.")
        self.stack.setCurrentWidget(self.info_scroll)

    def show_about(self):
        self.info_title.setText("About NebulaConvert")
        self.info_text.setMinimumHeight(350)
        self.info_text.setMaximumHeight(16777215)
        self.info_text.setVisible(True)
        self.info_text.setText(
            "NEBULACONVERT · Local File Studio\n\n"
            "A Windows desktop converter designed around privacy and batch workflows. It runs conversion tasks on this computer and the app code does not send files to a cloud service.\n\n"
            "CURRENT CAPABILITIES\n"
            "• Multiple file selection and drag-and-drop\n"
            "• Batch conversion with progress and a local activity log\n"
            "• Image conversions powered by Pillow, including WebP → ICO\n"
            "• Basic text/PDF operations via ReportLab and PyMuPDF\n"
            "• Audio/video conversions when a local FFmpeg executable is installed\n"
            "• Many Office formats when LibreOffice is installed locally\n\n"
            "DEPENDENCIES\n"
            "Python · PySide6 · Pillow · ReportLab · PyMuPDF · optional FFmpeg / LibreOffice\n\n"
            "IMPORTANT LIMITATIONS\n"
            "This is still a prototype, not a signed standalone installer. Not every format pair is implemented, and FFmpeg/LibreOffice are not bundled. The app does not yet automatically chain intermediate formats.\n\n"
            "Keyboard shortcuts: F11 fullscreen, Esc exits borderless fullscreen."
        )
        self.info_text.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.stack.setCurrentWidget(self.info_scroll)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    win = NebulaWindow()
    win.show()
    sys.exit(app.exec())
