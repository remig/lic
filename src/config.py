"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (config.py) is part of Lic.

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

import os
from PyQt4.QtCore import *
from PyQt4.QtGui import *

# Path to LDraw, L3P and PovRay.  These are set by user through PathsDialog below.
# Contents below are just default settings for a very first run of Lic. 
# TODO: Provide better OS independent defaults for necessary paths.
LDrawPath = "C:\\LDraw"
L3PPath = "C:\\LDraw\\Apps\\L3p"
POVRayPath = "C:\\Program Files\\POV-Ray\\bin"

class PathsDialog(QDialog):

    def __init__(self, parent, hideCancelButton = False):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Set paths to files and applications"))

        ldrawLabel, self.ldrawEdit, ldrawButton = self.makeLabelEditButton("L&Draw:", LDrawPath, self.browseForLDraw)
        l3pLabel, self.l3pEdit, l3pButton = self.makeLabelEditButton("&L3P:", L3PPath, self.browseForL3P)
        povLabel, self.povEdit, povButton = self.makeLabelEditButton("&POVRay:", POVRayPath, self.browseForPOV)

        buttons = QDialogButtonBox.Ok if hideCancelButton else QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(buttons, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), lambda: QDialog.reject(self))

        grid = QGridLayout()
        grid.addWidget(ldrawLabel, 0, 0)
        grid.addWidget(self.ldrawEdit, 0, 1)
        grid.addWidget(ldrawButton, 0, 2)
        #grid.addWidget(l3pLabel, 1, 0)
        #grid.addWidget(self.l3pEdit, 1, 1)
        #grid.addWidget(l3pButton, 1, 2)
        #grid.addWidget(povLabel, 2, 0)
        #grid.addWidget(self.povEdit, 2, 1)
        #grid.addWidget(povButton, 2, 2)
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

    def browseForL3P(self):
        title = "Path to L3P (must contain 'l3p.exe')"
        self.browse(title, L3PPath, self.l3pEdit, self.validateL3PPath)

    def validateL3PPath(self, path):
        if not os.path.isfile(os.path.join(path, "l3p.exe")):
            return "L3P path must contain l3p.exe"
        return ""

    def browseForPOV(self):
        title = "Path to POVRay (must contain 'pvengine.exe')"
        self.browse(title, POVRayPath, self.povEdit, self.validatePOVPath)

    def validatePOVPath(self, path):
        if not os.path.isfile(os.path.join(path, "pvengine.exe")):
            return "POVRay path must contain pvengine.exe"
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
        #if res == "":
        #    res = self.validateL3PPath(str(self.l3pEdit.text()))
        #if res == "":
        #    res = self.validatePOVPath(str(self.povEdit.text()))
        if res:
            QMessageBox.warning(self, "Invalid path", res)
        else:
            global LDrawPath, L3PPath, POVRayPath
            LDrawPath = str(self.ldrawEdit.text())
            L3PPath = str(self.l3pEdit.text())
            POVRayPath = str(self.povEdit.text())
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

def povCachePath():
    return checkPath('POVs')

def pngCachePath():
    return checkPath('PNGs')

def finalImageCachePath():
    return checkPath('Final_Images')

def glImageCachePath():
    return checkPath('GL_Images')

def pdfCachePath():
    return checkPath('PDFs')
