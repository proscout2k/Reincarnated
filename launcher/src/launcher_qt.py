import os
import sys
import json
import shutil
import tempfile
import zipfile
import subprocess
import urllib.request
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressBar, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QWidget, QTabWidget, QFormLayout, QDialog, QDialogButtonBox
import winreg
from PyQt6.QtCore import pyqtSignal, QThread
from pathlib import Path

CONFIG_DIR = os.path.join(str(Path.home()), 'Documents', 'Reincarnated Launcher')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'launcher_config.json')
GITHUB_ZIP_URL = 'https://github.com/proscout2k/Reincarnated/archive/refs/heads/main.zip'
GITHUB_MODINFO_URL = 'https://raw.githubusercontent.com/proscout2k/Reincarnated/main/Reincarnated/Reincarnated.mpq/modinfo.json'

# --- D2R path detection (as before) ---
def find_d2r_path_from_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Blizzard Entertainment\\Diablo II Resurrected") as key:
            val, _ = winreg.QueryValueEx(key, "InstallLocation")
            if os.path.exists(os.path.join(val, 'D2R.exe')):
                return val
    except Exception:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Blizzard Entertainment\\Diablo II Resurrected") as key:
            val, _ = winreg.QueryValueEx(key, "InstallLocation")
            if os.path.exists(os.path.join(val, 'D2R.exe')):
                return val
    except Exception:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\WOW6432Node\\Blizzard Entertainment\\Battle.net\\Client") as key:
            val, _ = winreg.QueryValueEx(key, "GamePath_D2R")
            if os.path.exists(os.path.join(val, 'D2R.exe')):
                return val
    except Exception:
        pass
    return None

def find_d2r_path_common():
    possible = [
        r"C:\\Program Files (x86)\\Diablo II Resurrected",
        r"C:\\Program Files\\Diablo II Resurrected",
        r"C:\\Program Files (x86)\\Battle.net\\Diablo II Resurrected",
        r"C:\\Program Files\\Battle.net\\Diablo II Resurrected",
        r"C:\\Gry\\Diablo II Resurrected",
        r"D:\\Gry\\Diablo II Resurrected"
    ]
    for path in possible:
        if os.path.exists(os.path.join(path, 'D2R.exe')):
            return path
    return None

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f)

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, url, dest):
        super().__init__()
        self.url = url
        self.dest = dest

    def run(self):
        try:
            with urllib.request.urlopen(self.url) as response, open(self.dest, 'wb') as out_file:
                total = int(response.getheader('Content-Length', 0))
                downloaded = 0
                blocksize = 8192
                while True:
                    buffer = response.read(blocksize)
                    if not buffer:
                        break
                    out_file.write(buffer)
                    downloaded += len(buffer)
                    percent = int(downloaded * 100 / total) if total > 0 else 0
                    self.progress.emit(min(percent, 100))
            self.progress.emit(100)
            self.finished.emit(self.url, self.dest)
        except Exception as e:
            self.error.emit(str(e))

class SettingsDialog(QDialog):
    def __init__(self, d2r_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia")
        self.setFixedSize(400, 180)
        tabs = QTabWidget()
        global_tab = QWidget()
        global_layout = QFormLayout()
        self.path_edit = QLineEdit(d2r_path)
        self.path_edit.setReadOnly(True)
        global_layout.addRow("Ścieżka do Diablo II Resurrected:", self.path_edit)
        global_tab.setLayout(global_layout)
        tabs.addTab(global_tab, "Global")
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)
        self.setLayout(layout)

# --- Main PyQt6 Launcher ---
class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diablo II Resurrected Mod Launcher")
        self.setFixedSize(420, 220)
        self.config = load_config()
        self.d2r_path = self.detect_d2r_path()
        self.init_ui()
        self.check_mod_state()
        self.check_for_mod_update()

    def detect_d2r_path(self):
        if 'd2r_path' in self.config and os.path.exists(os.path.join(self.config['d2r_path'], 'D2R.exe')):
            return self.config['d2r_path']
        path = find_d2r_path_from_registry()
        if path:
            self.config['d2r_path'] = path
            save_config(self.config)
            return path
        path = find_d2r_path_common()
        if path:
            self.config['d2r_path'] = path
            save_config(self.config)
            return path
        return ''

    def init_ui(self):
        layout = QVBoxLayout()
        # Górny pasek: po lewej tytuł, po prawej ikonki
        top_layout = QHBoxLayout()
        self.title_label = QLabel("<b>Reincarnated Mod for D2R</b>")
        self.title_label.setStyleSheet("font-size: 20px; color: #e0e6f0; margin: 0 0 0 0; letter-spacing: 1px;")
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft)
        top_layout.addWidget(self.title_label, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        top_layout.addStretch()
        # Przycisk Patch notes
        self.patchnotes_btn = QPushButton()
        self.patchnotes_btn.setFixedSize(36, 36)
        self.patchnotes_btn.setStyleSheet("background: #232a3a; border: 1px solid #3a4256; border-radius: 18px; color: #e0e6f0; font-size: 18px;")
        # Ikona: ta, która była na ustawieniach
        self.patchnotes_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.patchnotes_btn.setIconSize(QtCore.QSize(22, 22))
        self.patchnotes_btn.clicked.connect(self.show_patch_notes)
        top_layout.addWidget(self.patchnotes_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        # Przycisk ustawień z ikoną koła zębatego
        self.settings_btn = QPushButton()
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setStyleSheet("background: #232a3a; border: 1px solid #3a4256; border-radius: 18px; color: #e0e6f0; font-size: 18px;")
        self.settings_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.settings_btn.setIconSize(QtCore.QSize(22, 22))
        self.settings_btn.clicked.connect(self.open_settings)
        top_layout.addWidget(self.settings_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_layout)
        layout.addSpacing(30)
        # Usunięcie opisu o parametrach startowych
        # Przycisk uruchamiania/pobierania na dole
        layout.addStretch()
        self.launch_btn = QPushButton()
        self.launch_btn.setMinimumHeight(54)
        self.launch_btn.setStyleSheet("font-size: 22px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3a4256, stop:1 #7eb7ff); color: #fff; border: none; border-radius: 12px; padding: 18px 30px 18px 30px; font-weight: bold; letter-spacing: 1px;")
        self.launch_btn.clicked.connect(self.launch_or_download)
        layout.addWidget(self.launch_btn)
        # Progres i status
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.progress.setStyleSheet("QProgressBar { border: 1px solid #3a4256; border-radius: 8px; background: #232a3a; height: 22px; font-size: 13px; color: #fff; } QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7eb7ff, stop:1 #232a3a); border-radius: 8px; }")
        layout.addWidget(self.progress)
        self.statusbar = QLabel("")
        self.statusbar.setStyleSheet("color: #b0b6c6; font-size: 13px; margin-top: 8px; font-style: italic;")
        self.statusbar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.statusbar)
        self.setLayout(layout)
        # Ciemny styl dla całego okna
        self.setStyleSheet("QWidget { background: #181c24; } QPushButton { border-radius: 12px; padding: 12px 30px; } QDialog { background: #232a3a; color: #e0e6f0; }")

    def show_patch_notes(self):
        PATCH_NOTES_URL = "https://raw.githubusercontent.com/proscout2k/Reincarnated/refs/heads/main/Reincarnated/Reincarnated.mpq/data/patchnotes.md"
        try:
            with urllib.request.urlopen(PATCH_NOTES_URL) as response:
                notes = response.read().decode("utf-8")
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Patch notes")
            dlg.setMinimumSize(700, 540)
            layout = QtWidgets.QVBoxLayout()
            text = QtWidgets.QTextBrowser()
            text.setOpenExternalLinks(True)
            text.setMarkdown(notes)
            text.setStyleSheet("background: #181c24; color: #e0e6f0; font-size: 16px; padding: 18px; border-radius: 10px;")
            text.verticalScrollBar().setValue(0)  # przewiń na górę
            layout.addWidget(text)
            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
            btns.setStyleSheet("QDialogButtonBox QPushButton { font-size: 15px; padding: 8px 24px; border-radius: 8px; background: #232a3a; color: #e0e6f0; }")
            btns.accepted.connect(dlg.accept)
            layout.addWidget(btns)
            dlg.setLayout(layout)
            dlg.setStyleSheet("QDialog { background: #232a3a; color: #e0e6f0; }")
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Patch notes", f"Nie udało się pobrać patch notes z internetu.\n\n{e}")

    def open_settings(self):
        dlg = SettingsDialog(self.d2r_path, self)
        dlg.exec()

    def set_status(self, msg):
        self.statusbar.setText(msg)
        QtWidgets.QApplication.processEvents()

    def set_progress(self, val):
        self.progress.setValue(val)
        QtWidgets.QApplication.processEvents()

    def check_mod_state(self):
        mpq_path = os.path.join(self.d2r_path, 'mods', 'reincarnated', 'reincarnated.mpq', 'modinfo.json')
        self._mod_update_available = False
        self._mod_installed = False
        self._mod_versions = (None, None)
        if not self.d2r_path or not os.path.exists(self.d2r_path) or not os.path.exists(os.path.join(self.d2r_path, 'D2R.exe')):
            self.launch_btn.setText("Brak ścieżki do gry")
            self.launch_btn.setEnabled(False)
            self.set_status("Nie wykryto poprawnej ścieżki do Diablo II Resurrected!")
            return
        if os.path.exists(mpq_path):
            self._mod_installed = True
            local_ver = self.get_local_mod_version()
            github_ver = self.get_github_mod_version()
            self._mod_versions = (local_ver, github_ver)
            if local_ver is not None and github_ver is not None and local_ver != github_ver:
                self._mod_update_available = True
                self.launch_btn.setText("Uruchom grę (!)")
                self.launch_btn.setEnabled(True)
                self.set_status(f"Dostępna nowa wersja moda: {local_ver} → {github_ver}")
            else:
                self.launch_btn.setText("Uruchom grę")
                self.launch_btn.setEnabled(True)
                self.set_status("")
        else:
            self.launch_btn.setText("Pobierz moda")
            self.launch_btn.setEnabled(True)
            self.set_status("")

    def launch_game(self):
        exe = os.path.join(self.d2r_path, 'D2R.exe')
        if not os.path.exists(exe):
            QMessageBox.critical(self, "Błąd", "Nie znaleziono D2R.exe w podanej ścieżce!")
            return
        try:
            subprocess.Popen([exe, '-mod', 'Reincarnated', '-txt'])
            QtWidgets.QApplication.quit()
        except Exception as e:
            self.set_status(f"Błąd uruchamiania gry: {e}")
            QMessageBox.critical(self, "Błąd", f"Nie udało się uruchomić gry: {e}")

    def launch_or_download(self):
        mpq_path = os.path.join(self.d2r_path, 'mods', 'reincarnated', 'reincarnated.mpq', 'modinfo.json')
        # Jeśli mod zainstalowany i dostępny update
        if self._mod_installed & self._mod_update_available:
            local_ver, github_ver = self._mod_versions
            msg = f"Wykryto nową wersję moda: {local_ver} → {github_ver}.\nCzy chcesz pobrać i zainstalować aktualizację?"
            reply = QMessageBox.question(self, "Aktualizacja moda", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Po update uruchom grę
                self.install_mod_from_github(launch_after=True)
                return
            else:
                # Uruchom grę bez update
                self.set_status("Uruchamianie gry...")
                self.launch_game()
                return
        # Standardowe uruchamianie gry lub pobieranie moda
        if os.path.exists(mpq_path):
            self.set_status("Uruchamianie gry...")
            self.launch_game()
        else:
            self.progress.setVisible(True)
            self.set_status("Pobieranie moda z GitHuba...")
            self.set_progress(0)
            self._tmpdir = tempfile.TemporaryDirectory()
            zip_path = os.path.join(self._tmpdir.name, 'main.zip')
            self.download_thread = DownloadThread(GITHUB_ZIP_URL, zip_path)
            self.download_thread.progress.connect(self.set_progress)
            def on_finished(url, dest):
                self.set_progress(100)
                self.set_status("Rozpakowywanie archiwum...")
                try:
                    with zipfile.ZipFile(dest, 'r') as zip_ref:
                        zip_ref.extractall(self._tmpdir.name)
                    main_dir = [d for d in os.listdir(self._tmpdir.name) if os.path.isdir(os.path.join(self._tmpdir.name, d)) and d.startswith('Reincarnated')]
                    if not main_dir:
                        self.set_status("Błąd: nie znaleziono folderu reincarnated-main w archiwum!")
                        QMessageBox.critical(self, "Błąd", "Nie znaleziono folderu reincarnated-main w archiwum!")
                        self.progress.setVisible(False)
                        self.check_mod_state()
                        self._tmpdir.cleanup()
                        return
                    reincarnated_dir = os.path.join(self._tmpdir.name, main_dir[0], 'reincarnated')
                    mpq_src = os.path.join(reincarnated_dir, 'reincarnated.mpq')
                    if not os.path.exists(mpq_src):
                        self.set_status("Błąd: nie znaleziono reincarnated/reincarnated.mpq w archiwum!")
                        QMessageBox.critical(self, "Błąd", "Nie znaleziono reincarnated/reincarnated.mpq w archiwum!")
                        self.progress.setVisible(False)
                        self.check_mod_state()
                        self._tmpdir.cleanup()
                        return
                    mods_dir = os.path.join(self.d2r_path, 'mods', 'reincarnated')
                    mpq_dst = os.path.join(mods_dir, 'reincarnated.mpq')
                    os.makedirs(mods_dir, exist_ok=True)
                    if os.path.exists(mpq_dst):
                        shutil.rmtree(mpq_dst)
                    self.set_status("Kopiowanie plików moda...")
                    shutil.copytree(mpq_src, mpq_dst)
                    self.set_status("Mod zainstalowany.")
                    self.progress.setVisible(False)
                    self.check_mod_state()
                    QMessageBox.information(self, "Sukces", f"Mod został pobrany i zainstalowany/zaaktualizowany w: {mpq_dst}")
                    self._tmpdir.cleanup()
                except Exception as e:
                    self.set_status(f"Błąd: {e}")
                    self.progress.setVisible(False)
                    self.check_mod_state()
                    self._tmpdir.cleanup()
                    QMessageBox.critical(self, "Błąd", f"Wystąpił problem podczas pobierania/instalacji moda: {e}")
            self.download_thread.finished.connect(on_finished)
            self.download_thread.error.connect(lambda e: (self._tmpdir.cleanup(), QMessageBox.critical(self, "Błąd", f"Błąd pobierania: {e}")))
            self.download_thread.start()

    def get_local_mod_version(self):
        try:
            modinfo_path = os.path.join(self.d2r_path, 'mods', 'reincarnated', 'reincarnated.mpq', 'modinfo.json')
            with open(modinfo_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('version', None)
        except Exception:
            return None

    def get_github_mod_version(self):
        try:
            with urllib.request.urlopen(GITHUB_MODINFO_URL) as response:
                raw = response.read().decode('utf-8-sig')
                data = json.loads(raw)
            return data.get('version', None)
        except Exception as e:
            print(f"Błąd pobierania/parsingu modinfo.json z GitHuba: {e}")
            return None

    def check_for_mod_update(self):
        # Nie pokazuj komunikatu przy starcie, tylko logika przeniesiona do check_mod_state
        pass

    def install_mod_from_github(self, launch_after=False):
        if not self.d2r_path:
            QMessageBox.critical(self, "Błąd", "Najpierw ustaw ścieżkę do Diablo II Resurrected!")
            return
        self.progress.setVisible(True)
        self.set_status("Pobieranie moda z GitHuba...")
        self.set_progress(0)
        self._tmpdir = tempfile.TemporaryDirectory()
        zip_path = os.path.join(self._tmpdir.name, 'main.zip')
        self.download_thread = DownloadThread(GITHUB_ZIP_URL, zip_path)
        self.download_thread.progress.connect(self.set_progress)
        def on_finished(url, dest):
            self.set_progress(100)
            self.set_status("Rozpakowywanie archiwum...")
            try:
                with zipfile.ZipFile(dest, 'r') as zip_ref:
                    zip_ref.extractall(self._tmpdir.name)
                main_dir = [d for d in os.listdir(self._tmpdir.name) if os.path.isdir(os.path.join(self._tmpdir.name, d)) and d.startswith('Reincarnated')]
                if not main_dir:
                    self.set_status("Błąd: nie znaleziono folderu reincarnated-main w archiwum!")
                    QMessageBox.critical(self, "Błąd", "Nie znaleziono folderu reincarnated-main w archiwum!")
                    self.progress.setVisible(False)
                    self._tmpdir.cleanup()
                    return
                reincarnated_dir = os.path.join(self._tmpdir.name, main_dir[0], 'reincarnated')
                mpq_src = os.path.join(reincarnated_dir, 'reincarnated.mpq')
                if not os.path.exists(mpq_src):
                    self.set_status("Błąd: nie znaleziono reincarnated/reincarnated.mpq w archiwum!")
                    QMessageBox.critical(self, "Błąd", "Nie znaleziono reincarnated/reincarnated.mpq w archiwum!")
                    self.progress.setVisible(False)
                    self._tmpdir.cleanup()
                    return
                mods_dir = os.path.join(self.d2r_path, 'mods', 'reincarnated')
                mpq_dst = os.path.join(mods_dir, 'reincarnated.mpq')
                os.makedirs(mods_dir, exist_ok=True)
                if os.path.exists(mpq_dst):
                    shutil.rmtree(mpq_dst)
                self.set_status("Kopiowanie plików moda...")
                shutil.copytree(mpq_src, mpq_dst)
                self.set_status("Mod zainstalowany.")
                self.progress.setVisible(False)
                if launch_after:
                    self.set_status("Uruchamianie gry...")
                    self.launch_game()
                QMessageBox.information(self, "Sukces", f"Mod został pobrany i zainstalowany/zaaktualizowany w: {mpq_dst}")
                self._tmpdir.cleanup()
            except Exception as e:
                self.set_status(f"Błąd: {e}")
                self.progress.setVisible(False)
                self._tmpdir.cleanup()
                QMessageBox.critical(self, "Błąd", f"Wystąpił problem podczas pobierania/instalacji moda: {e}")
        self.download_thread.finished.connect(on_finished)
        self.download_thread.error.connect(lambda e: (self.progress.setVisible(False), self._tmpdir.cleanup(), QMessageBox.critical(self, "Błąd", f"Błąd pobierania: {e}")))
        self.download_thread.start()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    # Ustaw ikonę programu
    import os
    from PyQt6.QtGui import QIcon
    ico_path = os.path.join(os.path.dirname(__file__), 'd2r.ico')
    if os.path.exists(ico_path):
        app.setWindowIcon(QIcon(ico_path))
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec())
