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

    def __init__(self, parent, pageSize, resolution):
        QDialog.__init__(self, parent)

        pixelWidthLabel, self.pixelWidthEditBox, pixelWidthComboBox = self.createLabelEditComboWidgets("&Width:")
        pixelHeightLabel, self.pixelHeightEditBox, pixelHeightComboBox = self.createLabelEditComboWidgets("&Height:")

        self.pixelWidthEditBox.setText(str(pageSize.width()))
        self.pixelWidthEditBox.setValidator(QIntValidator(1, 10000, self))
        self.connect(self.pixelWidthEditBox, SIGNAL("textEdited(const QString &)"), self.updatePixelWidth)
        
        self.pixelHeightEditBox.setText(str(pageSize.height()))
        self.pixelHeightEditBox.setValidator(QIntValidator(1, 10000, self))
        self.connect(self.pixelHeightEditBox, SIGNAL("textEdited(const QString &)"), self.updatePixelHeight)

        grid = QGridLayout()
        self.addWidgetsToGrid(grid, 0, pixelWidthLabel, self.pixelWidthEditBox, pixelWidthComboBox)
        self.addWidgetsToGrid(grid, 1, pixelHeightLabel, self.pixelHeightEditBox, pixelHeightComboBox)
        self.setGridSize(grid)
        
        pixelGroupBox = QGroupBox("Pixel Dimensions:", self)
        pixelGroupBox.setLayout(grid)

        docWidthLabel, docWidthEditBox, docWidthComboBox = self.createLabelEditComboWidgets("Wi&dth:", "inches")
        docHeightLabel, docHeightEditBox, docHeightComboBox = self.createLabelEditComboWidgets("Hei&ght:", "inches")
        resLabel, self.resEditBox, resComboBox = self.createLabelEditComboWidgets("&Resolution:", "pixels/inch", "pixels/cm")

        docWidthEditBox.setText("%.2f" % (pageSize.width() / resolution))
        docWidthEditBox.setValidator(QDoubleValidator(1.0, 10000.0, 4, self))

        docHeightEditBox.setText("%.2f" % (pageSize.height() / resolution))
        docHeightEditBox.setValidator(QDoubleValidator(1.0, 10000.0, 4, self))

        self.resEditBox.setText(str(resolution))
        self.resEditBox.setValidator(QDoubleValidator(1.0, 10000.0, 4, self))
        
        grid = QGridLayout()
        self.addWidgetsToGrid(grid, 0, docWidthLabel, docWidthEditBox, docWidthComboBox)
        self.addWidgetsToGrid(grid, 1, docHeightLabel, docHeightEditBox, docHeightComboBox)
        self.addWidgetsToGrid(grid, 2, resLabel, self.resEditBox, resComboBox)        
        self.setGridSize(grid)
        
        docGroupBox = QGroupBox("Document Size:")
        docGroupBox.setLayout(grid)
        
        self.constrainCheckBox = QCheckBox("&Constrain Page Proportions")
        resampleCheckBox = QCheckBox("Rescale all &Page Elements on Resize")
        
        layout = QVBoxLayout()
        layout.addWidget(pixelGroupBox)
        layout.addWidget(docGroupBox)
        layout.addWidget(self.constrainCheckBox)
        layout.addWidget(resampleCheckBox)
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Vertical)

        mainLayout = QHBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.setWindowTitle("Set Page Size")
        
    def updatePixelWidth(self, text):
        
        if not text or not self.pixelWidthEditBox.hasAcceptableInput():
            return
        
        newPageWidth = float(text)
        oldPageWidth = float(self.pixelWidthEditBox.text())
        pageHeight = float(self.pixelHeightEditBox.text())
        if self.constrainCheckBox.isChecked():
            aspect = pageHeight / oldPageWidth
            pageHeight = int(newPageWidth * aspect)
            self.pixelHeightEditBox.setText(str(pageHeight))

    def updatePixelHeight(self, text):
        
        if not text or not self.pixelHeightEditBox.hasAcceptableInput():
            return
        
        newPageHeight = float(text)
        oldPageHeight = float(self.pixelHeightEditBox.text())
        pageWidth = float(self.pixelWidthEditBox.text())
        if self.constrainCheckBox.isChecked():
            aspect = pageWidth / oldPageHeight
            pageWidth = int(newPageHeight * aspect)
            self.pixelWidthEditBox.setText(str(pageWidth))
            
    def isValid(self):
        if not self.pixelWidthEditBox.hasAcceptableInput():
            return False
        if not self.pixelHeightEditBox.hasAcceptableInput():
            return False
        if not self.resEditBox.hasAcceptableInput():
            return False
        return True
    
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

        if self.isValid():
            pageWidth = int(self.pixelWidthEditBox.text())
            pageHeight = int(self.pixelHeightEditBox.text())
            newPageSize = QSize(pageWidth, pageHeight)
            resolution = float(self.resEditBox.text())
            self.emit(SIGNAL("newPageSize"), newPageSize, resolution)        
            QDialog.accept(self)

class BackgroundImagePropertiesDlg(QDialog):

    def __init__(self, parent, image, backgroundColor, originalBrush, pageSize):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.image = image
        self.backgroundColor = backgroundColor
        self.originalBrush = originalBrush
        self.pageSize = pageSize

        self.imgCenter = QRadioButton("&Center")
        self.imgTile = QRadioButton("&Tile")
        self.imgStretch = QRadioButton("&Stretch")
        self.imgCenter.setChecked(True)

        radioGroup = QGroupBox("Image Fill options:", self)
        vbox = QVBoxLayout()
        vbox.addWidget(self.imgCenter)
        vbox.addWidget(self.imgTile)
        vbox.addWidget(self.imgStretch)
        radioGroup.setLayout(vbox)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Vertical)

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(radioGroup)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
        self.connect(self.imgCenter, SIGNAL("toggled(bool)"), self.changeImg)
        self.connect(self.imgTile, SIGNAL("toggled(bool)"), self.changeImg)
        self.connect(self.imgStretch, SIGNAL("toggled(bool)"), self.changeImg)
        self.setWindowTitle("Image Fill options")
        
    def exec_(self):
        self.changeImg(True)
        QDialog.exec_(self)

    def changeImg(self, toggled):
        if not toggled:
            return
        if self.imgCenter.isChecked():
            newImage = QImage(self.pageSize, QImage.Format_RGB32)
            newImage.fill(self.backgroundColor.rgb())
            painter = QPainter()
            painter.begin(newImage)
            painter.drawImage((self.pageSize.width() - self.image.width()) / 2.0, (self.pageSize.height() - self.image.height()) / 2.0, self.image)
            painter.end()
            self.emit(SIGNAL("changed"), newImage)
        elif self.imgTile.isChecked():
            self.emit(SIGNAL("changed"), self.image)
        elif self.imgStretch.isChecked():
            self.emit(SIGNAL("changed"), self.image.scaled(self.pageSize))

    def reject(self):
        self.emit(SIGNAL("changed"), self.originalBrush)
        QDialog.reject(self)

class PenDlg(QDialog):
    
    def __init__(self, parent, originalPen, hasRadius, fillColor):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.originalPen, self.hasRadius, self.fillColor = originalPen, hasRadius, fillColor

        self.penWidthSpinBox = QSpinBox()
        self.penWidthSpinBox.setRange(0, 20)
        self.penWidthSpinBox.setValue(originalPen.width())

        self.penWidthLabel = QLabel(self.tr("Pen &Width:"))
        self.penWidthLabel.setBuddy(self.penWidthSpinBox)

        self.penStyleComboBox = QComboBox()
        self.penStyleComboBox.addItem(self.tr("None"), QVariant(Qt.NoPen))
        self.penStyleComboBox.addItem(self.tr("Solid"), QVariant(Qt.SolidLine))
        self.penStyleComboBox.addItem(self.tr("Dash"), QVariant(Qt.DashLine))
        self.penStyleComboBox.addItem(self.tr("Dot"), QVariant(Qt.DotLine))
        self.penStyleComboBox.addItem(self.tr("Dash Dot"), QVariant(Qt.DashDotLine))
        self.penStyleComboBox.addItem(self.tr("Dash Dot Dot"), QVariant(Qt.DashDotDotLine))
        self.penStyleComboBox.setCurrentIndex(originalPen.style())  # This works because combobox indexes match style numbers

        self.penStyleLabel = QLabel(self.tr("&Pen Style:"))
        self.penStyleLabel.setBuddy(self.penStyleComboBox)

        self.penCapComboBox = QComboBox()
        self.penCapComboBox.addItem(self.tr("Flat"), QVariant(Qt.FlatCap))
        self.penCapComboBox.addItem(self.tr("Square"), QVariant(Qt.SquareCap))
        self.penCapComboBox.addItem(self.tr("Round"), QVariant(Qt.RoundCap))
        if originalPen.capStyle() == Qt.FlatCap:
            self.penCapComboBox.setCurrentIndex(0)
        elif originalPen.capStyle() == Qt.SquareCap:
            self.penCapComboBox.setCurrentIndex(1)
        else:
            self.penCapComboBox.setCurrentIndex(2)

        self.penCapLabel = QLabel(self.tr("Pen &Cap:"))
        self.penCapLabel.setBuddy(self.penCapComboBox)

        self.penJoinComboBox = QComboBox()
        self.penJoinComboBox.addItem(self.tr("Miter"), QVariant(Qt.MiterJoin))
        self.penJoinComboBox.addItem(self.tr("Bevel"), QVariant(Qt.BevelJoin))
        self.penJoinComboBox.addItem(self.tr("Round"), QVariant(Qt.RoundJoin))
        if originalPen.joinStyle() == Qt.MiterJoin:
            self.penJoinComboBox.setCurrentIndex(0)
        elif originalPen.joinStyle() == Qt.BevelJoin:
            self.penJoinComboBox.setCurrentIndex(1)
        else:
            self.penJoinComboBox.setCurrentIndex(2)

        self.penJoinLabel = QLabel(self.tr("Pen &Join:"))
        self.penJoinLabel.setBuddy(self.penJoinComboBox)

        if self.hasRadius:
            self.cornerRadiusSpinBox = QSpinBox()
            self.cornerRadiusSpinBox.setRange(0, 50)
            self.cornerRadiusSpinBox.setValue(originalPen.cornerRadius)
    
            self.cornerRadiusLabel = QLabel(self.tr("Corner &Radius:"))
            self.cornerRadiusLabel.setBuddy(self.cornerRadiusSpinBox)
            
        self.penColorButton = QPushButton(self.tr("Border C&olor"))
        self.penColorButton.color = originalPen.color()

        if self.fillColor:
            self.fillColorButton = QPushButton(self.tr("Fill C&olor"))
            self.fillColorButton.color = self.fillColor

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.penWidthLabel, 0, 0)
        mainLayout.addWidget(self.penWidthSpinBox, 0, 1)
        mainLayout.addWidget(self.penStyleLabel, 1, 0)
        mainLayout.addWidget(self.penStyleComboBox, 1, 1)
        mainLayout.addWidget(self.penCapLabel, 2, 0)
        mainLayout.addWidget(self.penCapComboBox, 2, 1)
        mainLayout.addWidget(self.penJoinLabel, 3, 0)
        mainLayout.addWidget(self.penJoinComboBox, 3, 1)
        
        offset = 5
        if self.hasRadius:
            offset += 1
            mainLayout.addWidget(self.cornerRadiusLabel, 4, 0)
            mainLayout.addWidget(self.cornerRadiusSpinBox, 4, 1)
            
        mainLayout.addWidget(self.penColorButton, 5 if self.hasRadius else 4, 0, 1, 2)
        
        if self.fillColor:
            offset += 1
            mainLayout.addWidget(self.fillColorButton, 6 if self.hasRadius else 5, 0, 1, 2)

        mainLayout.addWidget(buttonBox, offset, 0, 1, 2)
        self.setLayout(mainLayout)

        self.connect(self.penWidthSpinBox, SIGNAL("valueChanged(int)"), self.penChanged)
        self.connect(self.penStyleComboBox, SIGNAL("activated(int)"), self.penChanged)
        self.connect(self.penCapComboBox, SIGNAL("activated(int)"), self.penChanged)
        self.connect(self.penJoinComboBox, SIGNAL("activated(int)"), self.penChanged)
        if self.hasRadius:
            self.connect(self.cornerRadiusSpinBox, SIGNAL("valueChanged(int)"), self.penChanged)
        self.connect(self.penColorButton, SIGNAL("clicked()"), self.getColor)
        if self.fillColor:
            self.connect(self.fillColorButton, SIGNAL("clicked()"), self.getFillColor)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
        self.penChanged()
        self.setWindowTitle(self.tr("Border Properties"))

    def getColor(self):
        color, value = QColorDialog.getRgba(self.penColorButton.color.rgba(), self)
        color = QColor.fromRgba(color)
        if color.isValid(): 
            self.penColorButton.color = color
            self.penChanged()

    def getFillColor(self):
        color, value = QColorDialog.getRgba(self.fillColorButton.color.rgba(), self)
        color = QColor.fromRgba(color)
        if color.isValid(): 
            self.fillColorButton.color = color
            self.brushChanged()
        
    def brushChanged(self):
        brush = QBrush(self.fillColorButton.color)
        self.emit(SIGNAL("brushChanged"), brush)
        
    def penChanged(self):
        width = self.penWidthSpinBox.value()
        style = Qt.PenStyle(self.penStyleComboBox.itemData(self.penStyleComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        cap = Qt.PenCapStyle(self.penCapComboBox.itemData(self.penCapComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        join = Qt.PenJoinStyle(self.penJoinComboBox.itemData(self.penJoinComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        color = self.penColorButton.color
        pen = QPen(color, width, style, cap, join)
        pen.cornerRadius = self.cornerRadiusSpinBox.value() if self.hasRadius else 0
        self.emit(SIGNAL("changed"), pen)
        
    def reject(self):
        self.emit(SIGNAL("changed"), self.originalPen)
        QDialog.reject(self)

class RotateCSIDialog(QDialog):
    
    def __init__(self, parent, rotation):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        
        self.rotation = list(rotation) if rotation else [0.0, 0.0, 0.0]

        self.xLabel, self.xSpinBox = self.makeLabelSpinBox("X:", self.rotation[0])
        self.yLabel, self.ySpinBox = self.makeLabelSpinBox("Y:", self.rotation[1])
        self.zLabel, self.zSpinBox = self.makeLabelSpinBox("Z:", self.rotation[2])

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.xLabel, 0, 0, Qt.AlignRight)
        mainLayout.addWidget(self.xSpinBox, 0, 1)
        mainLayout.addWidget(self.yLabel, 1, 0, Qt.AlignRight)
        mainLayout.addWidget(self.ySpinBox, 1, 1)
        mainLayout.addWidget(self.zLabel, 2, 0, Qt.AlignRight)
        mainLayout.addWidget(self.zSpinBox, 2, 1)
        mainLayout.addWidget(buttonBox, 3, 0, 1, 2)
        self.setLayout(mainLayout)

        self.connect(self.xSpinBox, SIGNAL("valueChanged(int)"), self.rotationChanged)
        self.connect(self.ySpinBox, SIGNAL("valueChanged(int)"), self.rotationChanged)
        self.connect(self.zSpinBox, SIGNAL("valueChanged(int)"), self.rotationChanged)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
        self.rotationChanged()
        self.setWindowTitle(self.tr("Rotate CSI"))

    def makeLabelSpinBox(self, text, value):
        spinBox = QSpinBox()
        spinBox.setRange(0, 360)
        spinBox.setValue(value)
        lbl = QLabel(self.tr(text))
        lbl.setBuddy(spinBox)
        return lbl, spinBox
        
    def rotationChanged(self):
        x = self.xSpinBox.value()
        y = self.ySpinBox.value()
        z = self.zSpinBox.value()
        self.emit(SIGNAL("changed"), [x, y, z])
        
    def accept(self):
        self.emit(SIGNAL("accept"), self.rotation)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changed"), self.rotation)
        QDialog.reject(self)
