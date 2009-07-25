from PyQt4.QtCore import *
from PyQt4.QtGui import *

import Helpers

def makeLabelSpinBox(self, text, value, min, max, signal = None, double = False, percent = False):
    if double:
        spinBox = QDoubleSpinBox()
    else:
        spinBox = QSpinBox()

    if percent:
        spinBox.setSuffix("%")
        
    spinBox.setRange(min, max)
    spinBox.setValue(value)
    lbl = QLabel(self.tr(text))
    lbl.setBuddy(spinBox)
    
    if signal:
        self.connect(spinBox, SIGNAL("valueChanged(double)") if double else SIGNAL("valueChanged(int)"), signal)
        
    return lbl, spinBox

QDialog.makeLabelSpinBox = makeLabelSpinBox

class PageSizeDlg(QDialog):

    def __init__(self, parent, pageSize, resolution):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setWindowTitle("Page Size")
        self.originalPageSize = pageSize
        self.notifySizeChange = True

        pixelWidthLabel, self.pixelWidthSpinBox, = self.makeLabelSpinBox("&Width:", pageSize.width(), 1, 50000, self.pixelWidthChanged)
        pixelHeightLabel, self.pixelHeightSpinBox  = self.makeLabelSpinBox("&Height:", pageSize.height(), 1, 50000, self.pixelHeightChanged)
        self.pixelFormatComboBox = QComboBox()
        self.pixelFormatComboBox.addItems(["pixels", "percent"])

        grid = QGridLayout()
        grid.addWidget(pixelWidthLabel, 0, 0, Qt.AlignRight)
        grid.addWidget(self.pixelWidthSpinBox, 0, 1)
        grid.addWidget(pixelHeightLabel, 1, 0, Qt.AlignRight)
        grid.addWidget(self.pixelHeightSpinBox, 1, 1)
        grid.addWidget(self.pixelFormatComboBox, 0, 2, 2, 1, Qt.AlignVCenter)
        self.setGridSize(grid)
        
        self.pixelGroupBox = QGroupBox("Image Size (pixels):", self)
        self.pixelGroupBox.setCheckable(True)
        self.pixelGroupBox.setChecked(True)
        self.pixelGroupBox.setLayout(grid)

        docWidthLabel, self.docWidthSpinBox = self.makeLabelSpinBox("Wi&dth:", pageSize.width() / float(resolution), 0.1, 1000.0, self.docWidthChanged, True)
        docHeightLabel, self.docHeightSpinBox = self.makeLabelSpinBox("Hei&ght:", pageSize.height() / float(resolution), 0.1, 1000.0, self.docHeightChanged, True)
        self.docFormatComboBox = QComboBox()
        self.docFormatComboBox.addItems(["inches", "cm"])
        
        resLabel, self.resSpinBox = self.makeLabelSpinBox("&Resolution:", resolution, 1, 50000, self.resolutionChanged)
        self.resFormatLabel = QLabel(self.tr("pixels/inch"))

        grid = QGridLayout()
        grid.addWidget(docWidthLabel, 0, 0, Qt.AlignRight)
        grid.addWidget(self.docWidthSpinBox, 0, 1)
        grid.addWidget(docHeightLabel, 1, 0, Qt.AlignRight)
        grid.addWidget(self.docHeightSpinBox, 1, 1)        
        grid.addWidget(self.docFormatComboBox, 0, 2, 2, 1, Qt.AlignVCenter)
        grid.addWidget(resLabel, 2, 0, Qt.AlignRight)
        grid.addWidget(self.resSpinBox, 2, 1)
        grid.addWidget(self.resFormatLabel, 2, 2, Qt.AlignLeft)
        self.setGridSize(grid)
        
        self.docGroupBox = QGroupBox("Printed Document Size:")
        self.docGroupBox.setCheckable(True)
        self.docGroupBox.setChecked(False)
        self.docGroupBox.setLayout(grid)
        
        self.rescaleCheckBox = QCheckBox("Rescale all &Page Elements (slow)")
        self.aspectRatioCheckBox = QCheckBox("&Keep Page Aspect Ratio")
        self.aspectRatioCheckBox.setChecked(True)
        
        layout = QVBoxLayout()
        layout.addWidget(self.pixelGroupBox)
        layout.addWidget(self.docGroupBox)
        layout.addWidget(self.aspectRatioCheckBox)
        layout.addWidget(self.rescaleCheckBox)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Vertical)
        
        mainLayout = QHBoxLayout()
        mainLayout.addLayout(layout)
        mainLayout.addWidget(buttonBox)
        self.setLayout(mainLayout)

        self.connect(self.pixelFormatComboBox, SIGNAL("currentIndexChanged(int)"), lambda index: self.pixelComboChange(index))
        self.connect(self.docFormatComboBox, SIGNAL("currentIndexChanged(int)"), lambda index: self.docComboChange(index))
        self.connect(self.pixelGroupBox, SIGNAL("clicked(bool)"), lambda checked: self.docGroupBox.setChecked(not checked))
        self.connect(self.docGroupBox, SIGNAL("clicked(bool)"), lambda checked: self.pixelGroupBox.setChecked(not checked))
        self.connect(self.aspectRatioCheckBox, SIGNAL("stateChanged(int)"), self.aspectRatioClick)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
    def setGridSize(self, grid):
        
        grid.setColumnMinimumWidth(0, 55)
        grid.setColumnMinimumWidth(1, 50)
        grid.setColumnMinimumWidth(2, 80)
        grid.setHorizontalSpacing(10)        

    def getPageSize(self):
        if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
            width = self.pixelWidthSpinBox.value()
            height = self.pixelHeightSpinBox.value()
        else:  # percent
            width = int(self.originalPageSize.width() * self.pixelWidthSpinBox.value() / 100.0)
            height = int(self.originalPageSize.height() * self.pixelHeightSpinBox.value() / 100.0)

        return QSize(width, height)

    def getResolution(self):
        return self.resSpinBox.value()

    def getRescalePageItems(self):
        return self.rescaleCheckBox.isChecked()

    def setWidth(self, width, isDocWidth):
        
        res = self.getResolution()
        oldWidth, oldHeight = self.originalPageSize.width(), self.originalPageSize.height()
        aspectRatio = float(oldHeight) / float(oldWidth)
        newPixelWidth, newDocWidth = width, width
        
        if isDocWidth:
            if self.docFormatComboBox.currentIndex() == 0:  # inch
                newPixelWidth = int(width * res)
            else:  # cm
                newPixelWidth = int(width * res / 2.54)
            if self.pixelFormatComboBox.currentIndex() == 1:  # percent
                newPixelWidth = int(100.0 * newPixelWidth / oldWidth)
        else:
            if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
                newDocWidth = float(width) / res
            else:  # percent
                newDocWidth = oldWidth * width / 100.0 / res
        
        self.notifySizeChange = False

        self.pixelWidthSpinBox.setValue(newPixelWidth)
        self.docWidthSpinBox.setValue(newDocWidth)
        
        if self.aspectRatioCheckBox.isChecked():  # Need to update height boxes too
            
            # Update height box
            if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
                self.pixelHeightSpinBox.setValue(int(newPixelWidth * aspectRatio))
            else:  # percent
                self.pixelHeightSpinBox.setValue(newPixelWidth)
                
            # Update doc height box
            self.docHeightSpinBox.setValue(newDocWidth * aspectRatio)
    
        self.notifySizeChange = True
    
    def setHeight(self, height, isDocHeight):

        res = self.getResolution()
        oldWidth, oldHeight = self.originalPageSize.width(), self.originalPageSize.height()
        aspectRatio = float(oldWidth) / float(oldHeight)
        newPixelHeight, newDocHeight = height, height
        
        if isDocHeight:
            if self.docFormatComboBox.currentIndex() == 0:  # inch
                newPixelHeight = int(height * res)
            else:  # cm
                newPixelHeight = int(height * res / 2.54)
            if self.pixelFormatComboBox.currentIndex() == 1:  # percent
                newPixelHeight = int(100.0 * newPixelHeight / oldHeight)
        else:
            if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
                newDocHeight = float(height) / res
            else:  # percent
                newDocHeight = oldHeight * height / 100.0 / res
        
        self.notifySizeChange = False

        self.pixelHeightSpinBox.setValue(newPixelHeight)
        self.docHeightSpinBox.setValue(newDocHeight)
        
        if self.aspectRatioCheckBox.isChecked():  # Need to update width boxes too
            
            # Update width box
            if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
                self.pixelWidthSpinBox.setValue(int(newPixelHeight * aspectRatio))
            else:  # percent
                self.pixelWidthSpinBox.setValue(newPixelHeight)
                
            # Update doc width box
            self.docWidthSpinBox.setValue(newDocHeight * aspectRatio)
    
        self.notifySizeChange = True

    def pixelComboChange(self, index):
        
        self.notifySizeChange = False
        oldWidth, oldHeight = float(self.originalPageSize.width()), float(self.originalPageSize.height())
        newWidth, newHeight = float(self.pixelWidthSpinBox.value()), float(self.pixelHeightSpinBox.value())
        
        if index == 0:  # to pixel
            self.pixelWidthSpinBox.setValue(int(oldWidth * newWidth / 100.0))
            self.pixelHeightSpinBox.setValue(int(oldHeight * newHeight / 100.0))
            self.pixelWidthSpinBox.setSuffix("")
            self.pixelHeightSpinBox.setSuffix("")
        else:  # to percent
            self.pixelWidthSpinBox.setValue(int(newWidth / oldWidth * 100.0))
            self.pixelHeightSpinBox.setValue(int(newHeight / oldHeight * 100.0))
            self.pixelWidthSpinBox.setSuffix("%")
            self.pixelHeightSpinBox.setSuffix("%")
        self.notifySizeChange = True
    
    def pixelWidthChanged(self, newValue):
        if self.notifySizeChange:
            self.setWidth(newValue, False)
            
    def pixelHeightChanged(self, newValue):
        if self.notifySizeChange:
            self.setHeight(newValue, False)

    def docComboChange(self, index):

        res = self.resSpinBox.value()
        
        if index == 0:  # to inches
            res *= 2.54
            self.resFormatLabel.setText("pixels/inch")
        else:  # to cm
            res /= 2.54
            self.resFormatLabel.setText("pixels/cm")
            
        self.resSpinBox.setValue(int(round(res)))

    def docWidthChanged(self, newValue):
        if self.notifySizeChange:
            self.setWidth(newValue, True)

    def docHeightChanged(self, newValue):
        if self.notifySizeChange:
            self.setHeight(newValue, True)

    def resolutionChanged(self, newValue):
        self.setWidth(self.pixelWidthSpinBox.value(), False)
        self.setHeight(self.pixelHeightSpinBox.value(), False)
    
    def aspectRatioClick(self, state):
        
        if self.aspectRatioCheckBox.isChecked():
            # Setting just width will trigger rest of everything else
            if self.pixelFormatComboBox.currentIndex() == 0:  # pixel
                self.setWidth(self.originalPageSize.width(), False)
            else:
                self.setWidth(100, False)
            self.rescaleCheckBox.setEnabled(True)
        else:
            self.rescaleCheckBox.setEnabled(False)
    
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

class ScaleDlg(QDialog):

    def __init__(self, parent, originalSize):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Set Size")
        self.originalSize = originalSize

        sizeLabel, self.sizeSpinBox = self.makeLabelSpinBox("&Size:", originalSize * 100.0, 0.1, 1000.0, self.sizeChanged, True, True)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)

        grid = QGridLayout()
        grid.addWidget(sizeLabel, 0, 0)
        grid.addWidget(self.sizeSpinBox, 0, 1)
        grid.addWidget(buttonBox, 2, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.sizeSpinBox.selectAll()
        
    def sizeChanged(self):
        newSize = self.sizeSpinBox.value() / 100.0
        self.emit(SIGNAL("changeScale"), newSize)
    
    def accept(self):
        self.emit(SIGNAL("acceptScale"), self.originalSize)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changeScale"), self.originalSize)
        QDialog.reject(self)

class RotationDialog(QDialog):
    
    def __init__(self, parent, rotation):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Rotation"))
        #self.setWindowOpacity(0.8)
        
        self.rotation = list(rotation)

        xLabel, self.xSpinBox = self.makeLabelSpinBox("X:", self.rotation[0], -360, 360, self.rotationChanged)
        yLabel, self.ySpinBox = self.makeLabelSpinBox("Y:", self.rotation[1], -360, 360, self.rotationChanged)
        zLabel, self.zSpinBox = self.makeLabelSpinBox("Z:", self.rotation[2], -360, 360, self.rotationChanged)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        
        grid = QGridLayout()
        grid.addWidget(xLabel, 0, 0, Qt.AlignRight)
        grid.addWidget(self.xSpinBox, 0, 1)
        grid.addWidget(yLabel, 1, 0, Qt.AlignRight)
        grid.addWidget(self.ySpinBox, 1, 1)
        grid.addWidget(zLabel, 2, 0, Qt.AlignRight)
        grid.addWidget(self.zSpinBox, 2, 1)
        grid.addWidget(buttonBox, 3, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
        self.rotationChanged()
        self.xSpinBox.selectAll()

    def rotationChanged(self):
        rotation = [self.xSpinBox.value(), self.ySpinBox.value(), self.zSpinBox.value()]
        self.emit(SIGNAL("changeRotation"), rotation)
        
    def accept(self):
        self.emit(SIGNAL("acceptRotation"), self.rotation)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changeRotation"), self.rotation)
        QDialog.reject(self)

class DisplaceDlg(QDialog):

    def __init__(self, parent, displacement, direction):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Displacement"))
        self.originalDisplacement, self.direction = displacement, direction

        distance = Helpers.displacementToDistance(displacement, direction)
        sizeLabel, self.sizeSpinBox = self.makeLabelSpinBox(self.tr("&Distance:"), distance, 0, 500, self.sizeChanged)
        
        self.arrowCheckBox = QCheckBox(self.tr("&Adjust Arrow (NYI)"))
        self.arrowCheckBox.setChecked(False)
        self.arrowCheckBox.setCheckable(False)

        self.moreButton = QPushButton(self.tr("X - Y - Z"))
        self.moreButton.setCheckable(True)
        self.moreButton.setAutoDefault(False)
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)

        self.extension = QWidget()

        xLabel, self.xSpinBox = self.makeLabelSpinBox("X:", displacement[0], -500, 500, self.displacementChanged)
        yLabel, self.ySpinBox = self.makeLabelSpinBox("Y:", displacement[1], -500, 500, self.displacementChanged)
        zLabel, self.zSpinBox = self.makeLabelSpinBox("Z:", displacement[2], -500, 500, self.displacementChanged)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        self.connect(self.moreButton, SIGNAL("toggled(bool)"), self.extension, SLOT("setVisible(bool)"))

        grid = QGridLayout()
        grid.setMargin(0)
        grid.addWidget(xLabel, 0, 0, Qt.AlignRight)
        grid.addWidget(self.xSpinBox, 0, 1)
        grid.addWidget(yLabel, 1, 0, Qt.AlignRight)
        grid.addWidget(self.ySpinBox, 1, 1)
        grid.addWidget(zLabel, 2, 0, Qt.AlignRight)
        grid.addWidget(self.zSpinBox, 2, 1)
        self.extension.setLayout(grid)

        mainLayout = QGridLayout()
        mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        mainLayout.addWidget(sizeLabel, 0, 0)
        mainLayout.addWidget(self.sizeSpinBox, 0, 1)
        mainLayout.addWidget(self.arrowCheckBox, 1, 0, 1, 2)
        mainLayout.addWidget(self.moreButton, 2, 0, 1, 2)
        mainLayout.addWidget(self.extension, 3, 0, 1, 2)
        mainLayout.addWidget(buttonBox, 4, 0, 1, 2)
        self.setLayout(mainLayout)

        self.extension.hide()
        self.sizeSpinBox.selectAll()
        
    def sizeChanged(self):
        newSize = self.sizeSpinBox.value()
        displacement = Helpers.distanceToDisplacement(newSize, self.direction)
        self.emit(SIGNAL("changeDisplacement"), displacement, self.arrowCheckBox.isChecked())
        
    def displacementChanged(self):
        displacement = [self.xSpinBox.value(), self.ySpinBox.value(), self.zSpinBox.value()]
        self.emit(SIGNAL("changeDisplacement"), displacement, self.arrowCheckBox.isChecked())
    
    def accept(self):
        self.emit(SIGNAL("acceptDisplacement"), self.originalDisplacement, self.arrowCheckBox.isChecked())
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changeDisplacement"), self.originalDisplacement, self.arrowCheckBox.isChecked())
        QDialog.reject(self)

class ArrowDisplaceDlg(QDialog):

    def __init__(self, parent, arrow):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Arrow"))
        self.arrow = arrow
        self.originalDisplacement, self.originalLength = arrow.displacement, arrow.getLength()

        displacement = arrow.displacement
        distance = Helpers.displacementToDistance(displacement, arrow.displaceDirection)
        sizeLabel, self.sizeSpinBox = self.makeLabelSpinBox(self.tr("&Distance:"), distance, -500, 500, self.sizeChanged)
        lengthLabel, self.lengthSpinBox = self.makeLabelSpinBox(self.tr("&Length:"), arrow.getLength(), -500, 500, self.lengthChanged)
        
        self.moreButton = QPushButton(self.tr("X - Y - Z (NYI)"))
        self.moreButton.setCheckable(True)
        self.moreButton.setAutoDefault(False)
        
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)

        self.extension = QWidget()

        xLabel, self.xSpinBox = self.makeLabelSpinBox("tip X:", displacement[0], -500, 500, self.displacementChanged)
        yLabel, self.ySpinBox = self.makeLabelSpinBox("tip Y:", displacement[1], -500, 500, self.displacementChanged)
        zLabel, self.zSpinBox = self.makeLabelSpinBox("tip Z:", displacement[2], -500, 500, self.displacementChanged)

        xEndLabel, self.xEndSpinBox = self.makeLabelSpinBox("end X:", displacement[0], -500, 500, self.displacementChanged)
        yEndLabel, self.yEndSpinBox = self.makeLabelSpinBox("end Y:", displacement[1], -500, 500, self.displacementChanged)
        zEndLabel, self.zEndSpinBox = self.makeLabelSpinBox("end Z:", displacement[2], -500, 500, self.displacementChanged)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        self.connect(self.moreButton, SIGNAL("toggled(bool)"), self.extension, SLOT("setVisible(bool)"))

        grid = QGridLayout()
        grid.setMargin(0)
        grid.addWidget(xLabel, 0, 0, Qt.AlignRight)
        grid.addWidget(self.xSpinBox, 0, 1)
        grid.addWidget(yLabel, 1, 0, Qt.AlignRight)
        grid.addWidget(self.ySpinBox, 1, 1)
        grid.addWidget(zLabel, 2, 0, Qt.AlignRight)
        grid.addWidget(self.zSpinBox, 2, 1)

        grid.addWidget(xEndLabel, 3, 0, Qt.AlignRight)
        grid.addWidget(self.xEndSpinBox, 3, 1)
        grid.addWidget(yEndLabel, 4, 0, Qt.AlignRight)
        grid.addWidget(self.yEndSpinBox, 4, 1)
        grid.addWidget(zEndLabel, 5, 0, Qt.AlignRight)
        grid.addWidget(self.zEndSpinBox, 5, 1)
        
        self.extension.setLayout(grid)

        mainLayout = QGridLayout()
        mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        mainLayout.addWidget(sizeLabel, 0, 0)
        mainLayout.addWidget(self.sizeSpinBox, 0, 1)
        mainLayout.addWidget(lengthLabel, 1, 0)
        mainLayout.addWidget(self.lengthSpinBox, 1, 1)
        mainLayout.addWidget(self.moreButton, 2, 0, 1, 2)
        mainLayout.addWidget(self.extension, 3, 0, 1, 2)
        mainLayout.addWidget(buttonBox, 4, 0, 1, 2)
        self.setLayout(mainLayout)

        self.extension.hide()
        self.sizeSpinBox.selectAll()
        
    def sizeChanged(self):
        newSize = self.sizeSpinBox.value()
        displacement = Helpers.distanceToDisplacement(newSize, self.arrow.displaceDirection)
        self.emit(SIGNAL("changeDisplacement"), displacement)
        
    def lengthChanged(self):
        newLength = self.lengthSpinBox.value()
        self.emit(SIGNAL("changeLength"), newLength)
    
    def displacementChanged(self):
        displacement = [self.xSpinBox.value(), self.ySpinBox.value(), self.zSpinBox.value()]
        self.emit(SIGNAL("changeDisplacement"), displacement, self.arrowCheckBox.isChecked())
    
    def accept(self):
        self.emit(SIGNAL("accept"), self.originalDisplacement, self.originalLength)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changeDisplacement"), self.originalDisplacement)
        self.emit(SIGNAL("changeLength"), self.originalLength)
        QDialog.reject(self)
