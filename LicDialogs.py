from PyQt4.QtCore import *
from PyQt4.QtGui import *

class CSIPLIImageSizeDlg(QDialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

        csiSizeLabel = QLabel("&CSI Size:")
        self.csiSizeSpinBox = self.createSpinBox(csiSizeLabel)

        pliSizeLabel = QLabel("&PLI Size:")
        self.pliSizeSpinBox = self.createSpinBox(pliSizeLabel)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Close)

        grid = QGridLayout()
        grid.addWidget(csiSizeLabel, 0, 0)
        grid.addWidget(self.csiSizeSpinBox, 0, 1)
        grid.addWidget(pliSizeLabel, 1, 0)
        grid.addWidget(self.pliSizeSpinBox, 1, 1)
        grid.addWidget(buttonBox, 2, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox.button(QDialogButtonBox.Apply), SIGNAL("clicked()"), self.apply)
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.setWindowTitle("Set CSI | PLI Image Size")
        
    def createSpinBox(self, label):
        spinBox = QDoubleSpinBox()
        label.setBuddy(spinBox)
        spinBox.setRange(0.1, 1000)
        spinBox.setValue(100)
        spinBox.setSuffix(" %")
        return spinBox
        
    def apply(self):

        csiSize = self.csiSizeSpinBox.value() / 100.0
        pliSize = self.pliSizeSpinBox.value() / 100.0
        self.emit(SIGNAL("newCSIPLISize"), csiSize, pliSize)

class PageSizeDlg(QDialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)

        csiSizeLabel = QLabel("&CSI Size:")
        self.csiSizeSpinBox = self.createSpinBox(csiSizeLabel)

        pliSizeLabel = QLabel("&PLI Size:")
        self.pliSizeSpinBox = self.createSpinBox(pliSizeLabel)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        grid = QGridLayout()
        grid.addWidget(csiSizeLabel, 0, 0)
        grid.addWidget(self.csiSizeSpinBox, 0, 1)
        grid.addWidget(pliSizeLabel, 1, 0)
        grid.addWidget(self.pliSizeSpinBox, 1, 1)
        grid.addWidget(buttonBox, 2, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.setWindowTitle("Set Page Size")
        
    def createSpinBox(self, label):
        spinBox = QDoubleSpinBox()
        label.setBuddy(spinBox)
        spinBox.setRange(0.1, 1000)
        spinBox.setValue(100)
        spinBox.setSuffix(" %")
        return spinBox
        
    def accept(self):

        csiSize = self.csiSizeSpinBox.value() / 100.0
        pliSize = self.pliSizeSpinBox.value() / 100.0
        self.emit(SIGNAL("newCSIPLISize"), csiSize, pliSize)
        
        isValid = False
        
        if isValid:
            QDialog.accept(self)

    def getPageSize(self):
        return (0, 0)
