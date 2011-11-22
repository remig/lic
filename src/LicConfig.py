"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicConfig.py) is part of Lic.

    Lic is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Lic is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/
"""

from LicCommonImports import *

# Path to LDraw library.  These are set by user through PathsDialog below.
# Contents below are just some brain-dead default settings for a very first run of Lic. 

if sys.platform.startswith('win'):
    LDrawPath = "C:\\LDraw"
else:
    root = os.path.expanduser('~')
    LDrawPath = os.path.join(root, 'LDraw')

class PathsDialog(QDialog):

    def __init__(self, parent, hideCancelButton = False):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Set paths to files and applications"))

        ldrawLabel, self.ldrawEdit, ldrawButton = self.makeLabelEditButton("L&Draw:", LDrawPath, self.browseForLDraw)

        buttons = QDialogButtonBox.Ok if hideCancelButton else QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(buttons, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), lambda: QDialog.reject(self))

        grid = QGridLayout()
        grid.addWidget(ldrawLabel, 0, 0)
        grid.addWidget(self.ldrawEdit, 0, 1)
        grid.addWidget(ldrawButton, 0, 2)
        grid.addWidget(buttonBox, 3, 1, 1, 2)
        self.setLayout(grid)

    def makeLabelEditButton(self, text, path, slot):
        edit = QLineEdit(path)
        button = QPushButton(self.tr("Browse..."))
        label = QLabel(self.tr(text))
        label.setBuddy(button)
        self.connect(button, SIGNAL("clicked()"), slot)
        return label, edit, button

    def browseForLDraw(self):
        title = "Path to LDraw (must contain 'PARTS' and 'P' folders)"
        self.browse(title, LDrawPath, self.ldrawEdit, self.validateLDrawPath)

    def validateLDrawPath(self, path):
        if not (os.path.isdir(os.path.join(path, "PARTS")) and os.path.isdir(os.path.join(path, "P"))):
            return "LDraw path must contain 'PARTS' and 'P' folders"
        return ""

    def browse(self, title, defaultPath, target, validator):
        path = str(QFileDialog.getExistingDirectory(self, title, defaultPath, QFileDialog.ShowDirsOnly))
        if path != "":
            valid = validator(path)
            if valid != "":
                QMessageBox.warning(self, "Invalid path", valid)
            else:
                target.setText(path)

    def accept(self):
        res = self.validateLDrawPath(str(self.ldrawEdit.text()))
        if res:
            QMessageBox.warning(self, "Invalid path", res)
        else:
            global LDrawPath
            LDrawPath = str(self.ldrawEdit.text())
            QDialog.accept(self)

filename = ""  # Set when a file is loaded

def checkPath(pathName, root = None):
    root = root if root else modelCachePath()
    path = os.path.join(root, pathName)
    if not os.path.isdir(path):
        os.mkdir(path)
    return path

def rootCachePath():
    return checkPath('cache', os.getcwd())

def modelCachePath():
    return checkPath(os.path.basename(filename), rootCachePath())

def datCachePath():
    return checkPath('DATs')

def pngCachePath():
    return checkPath('PNGs')

def finalImageCachePath():
    return checkPath('Final_Images')

def glImageCachePath():
    return checkPath('GL_Images')

def pdfCachePath():
    return checkPath('PDFs')
