from PyQt4.QtCore import *
from PyQt4.QtGui import *

class CSIPLIImageSizeDlg(QDialog):

    def __init__(self, parent, currentCSISize, currentPLISize):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

        csiSizeLabel = QLabel("&CSI Size:")
        self.csiSizeSpinBox = self.createSpinBox(csiSizeLabel, currentCSISize)

        pliSizeLabel = QLabel("&PLI Size:")
        self.pliSizeSpinBox = self.createSpinBox(pliSizeLabel, currentPLISize)

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
        
    def createSpinBox(self, label, value):
        spinBox = QDoubleSpinBox()
        label.setBuddy(spinBox)
        spinBox.setRange(0.1, 1000)
        spinBox.setValue(value * 100)
        spinBox.setSuffix(" %")
        return spinBox
        
    def apply(self):

        csiSize = self.csiSizeSpinBox.value() / 100.0
        pliSize = self.pliSizeSpinBox.value() / 100.0
        self.emit(SIGNAL("newCSIPLISize"), csiSize, pliSize)

class PageSizeDlg(QDialog):

    def __init__(self, parent):
        QDialog.__init__(self, parent)

        pixelWidthLabel, pixelWidthEditBox, pixelWidthComboBox = self.createLabelEditComboWidgets("&Width:")
        pixelHeightLabel, pixelHeightEditBox, pixelHeightComboBox = self.createLabelEditComboWidgets("&Height:")

        grid = QGridLayout()
        self.addWidgetsToGrid(grid, 0, pixelWidthLabel, pixelWidthEditBox, pixelWidthComboBox)
        self.addWidgetsToGrid(grid, 1, pixelHeightLabel, pixelHeightEditBox, pixelHeightComboBox)
        self.setGridSize(grid)
        
        pixelGroupBox = QGroupBox("Pixel Dimensions:", self)
        pixelGroupBox.setLayout(grid)

        docWidthLabel, docWidthEditBox, docWidthComboBox = self.createLabelEditComboWidgets("Wi&dth:", "inches")
        docHeightLabel, docHeightEditBox, docHeightComboBox = self.createLabelEditComboWidgets("Hei&ght:", "inches")
        resLabel, resEditBox, resComboBox = self.createLabelEditComboWidgets("&Resolution:", "pixels/inch", "pixels/cm")

        grid = QGridLayout()
        self.addWidgetsToGrid(grid, 0, docWidthLabel, docWidthEditBox, docWidthComboBox)
        self.addWidgetsToGrid(grid, 1, docHeightLabel, docHeightEditBox, docHeightComboBox)
        self.addWidgetsToGrid(grid, 2, resLabel, resEditBox, resComboBox)        
        self.setGridSize(grid)
        
        docGroupBox = QGroupBox("Document Size:")
        docGroupBox.setLayout(grid)
        
        constrainCheckBox = QCheckBox("C&onstrain Proportions")
        resampleCheckBox = QCheckBox("Rescale all &Page Elements")
        
        layout = QVBoxLayout()
        layout.addWidget(pixelGroupBox)
        layout.addWidget(docGroupBox)
        layout.addWidget(constrainCheckBox)
        layout.addWidget(resampleCheckBox)
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Vertical)

        mainLayout = QHBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.setWindowTitle("Set Page Size")
        
    def createLabelEditComboWidgets(self, labelStr, comboStr1 = "pixels", comboStr2 = "percent"):
        
        label = QLabel(labelStr)
        editBox = QLineEdit()
        label.setBuddy(editBox)
        comboBox = QComboBox()
        comboBox.addItem(comboStr1)
        comboBox.addItem(comboStr2)
        return (label, editBox, comboBox)

    def setGridSize(self, grid):
        
        grid.setColumnMinimumWidth(0, 55)
        grid.setColumnMinimumWidth(1, 50)
        grid.setColumnMinimumWidth(2, 80)
        grid.setHorizontalSpacing(10)        

    def addWidgetsToGrid(self, grid, row, label, editBox, comboBox):
        
        grid.addWidget(label, row, 0, Qt.AlignRight)
        grid.addWidget(editBox, row, 1)
        grid.addWidget(comboBox, row, 2)
        
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
