"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicDialogs.py) is part of Lic.

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
from collections import OrderedDict

def makeLabelSpinBox(self, text, value, min, max, signal = None, double = False, percent = False):
    
    spinBox = self.makeSpinBox(value, min, max, signal, double, percent)
    
    lbl = QLabel(self.tr(text))
    lbl.setBuddy(spinBox)
    
    return lbl, spinBox

def makeSpinBox(self, value, min, max, signal = None, double = False, percent = False):
    if double:
        spinBox = QDoubleSpinBox()
    else:
        spinBox = QSpinBox()

    if percent:
        spinBox.setSuffix("%")
        
    spinBox.setRange(min, max)
    spinBox.setValue(value)
    
    if signal:
        self.connect(spinBox, SIGNAL("valueChanged(double)") if double else SIGNAL("valueChanged(int)"), signal)
        
    return spinBox

QWidget.makeLabelSpinBox = makeLabelSpinBox
QWidget.makeSpinBox = makeSpinBox

def addWidgetRow(self, row, widgetList):
    for i, widget in enumerate(widgetList):
        self.addWidget(widget, row, i)

QGridLayout.addWidgetRow = addWidgetRow

class LicProgressDialog(QProgressDialog):

    def __init__(self, parent, title):
        QProgressDialog.__init__(self, parent, Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        self.setWindowModality(Qt.WindowModal)
        self.setMinimumSize(300, 0)
        self.setWindowTitle(title)
        self.setMinimumDuration(0)
        self.setCancelButtonText("Cancel")
        self.setRange(0, 100000)
        self.setLabelText(title)
        self.setValue(1)  # Try and force dialog to show up right away
        self.count = 0

    def incr(self, label = None):
        self.count += 1
        if label:
            self.setLabelText(label)
        self.setValue(self.value() + 1)

class ColorButton(QToolButton):
    
    def __init__(self, parent, color):
        QToolButton.__init__(self, parent)

        self.brush = QBrush(QColor.fromRgbF(*color.rgba))
        self.colorCode = color
        self.setToolTip(color.name)

    def paintEvent(self, event):
        QToolButton.paintEvent(self, event)

        p = QPainter(self)
        p.setBrush(self.brush)
        p.drawRect(3, 3, self.width() - 9, self.height() - 9)
        p.end()

class LDrawColorDialog(QDialog):

    def __init__(self, parent, color, colorDict):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Color"))
        self.originalColor = color
        
        r, c = 0, 0
        grid = QGridLayout()
        grid.setSizeConstraint(QLayout.SetFixedSize)

        colorList = [i for i in colorDict.values() if i is not None]
        for color in sorted(colorList, key = lambda k: k.name):
            b = ColorButton(self, color)
            self.connect(b, SIGNAL('clicked(bool)'), lambda b, c = color: self.emit(SIGNAL('changeColor'), c))
            grid.addWidget(b, r, c)
            c += 1
            if c > 7:
                c = 0
                r += 1

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL('accepted()'), self, SLOT('accept()'))
        self.connect(buttonBox, SIGNAL('rejected()'), self, SLOT('reject()'))

        box = QBoxLayout(QBoxLayout.TopToBottom, self)
        box.insertLayout(0, grid)
        box.addWidget(buttonBox)

    def accept(self):
        self.emit(SIGNAL('acceptColor'), self.originalColor)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL('changeColor'), self.originalColor)
        QDialog.reject(self)

class LicColorConfigDialog(QDialog):

    def __init__(self, parent, colorDict):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Configure Brick Colors"))
        
        colorList = [i for i in colorDict.values() if i is not None]
        cols = OrderedDict([['Color', 40], ['Name', 110], ['Internal r,g,b,a' if colorDict.licColors else 'LDConfig r,g,b,a', 120], ['Custom r,g,b,a:', 120], ['Edge r,g,b,a:', 120]])

        table = self.table = QTableWidget(len(colorList), len(cols))
        table.verticalHeader().hide()
        table.setHorizontalHeaderLabels(cols.keys())
        table.setMinimumWidth(sum(cols.values()) + 20)  # 20 for vertical scroll bar

        for i, v in enumerate(cols.values()):
            table.setColumnWidth(i, v)

        def buildRowItem(flags = Qt.ItemIsEnabled, text = "", color = None, align = Qt.AlignLeft | Qt.AlignVCenter):
            item = QTableWidgetItem(text)
            item.setTextAlignment(align)
            item.setFlags(flags)
            if color:
                item.setBackgroundColor(QColor.fromRgbF(*color.rgba))
                item.licColor = color
            return item;

        def rgbaToStr(rgba):
            return ', '.join([str(int(x * 255)) for x in rgba])
        
        editFlags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        for r, color in enumerate(sorted(colorList, key = lambda k: k.name)):
            table.setItem(r, 0, buildRowItem(color = color, align = Qt.AlignCenter))
            table.setItem(r, 1, buildRowItem(text = color.name, align = Qt.AlignCenter))
            table.setItem(r, 2, buildRowItem(text = rgbaToStr(color.originalRGBA)))
            table.setItem(r, 3, buildRowItem(flags = editFlags, text = rgbaToStr(color.rgba) if color.rgba != color.originalRGBA else ''))
            table.setItem(r, 4, buildRowItem(flags = editFlags, text = rgbaToStr(color.edgeColor.rgba)))

        self.connect(table, SIGNAL('cellChanged(int, int)'), self.cellEdited)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL('accepted()'), self, SLOT('accept()'))
        self.connect(buttonBox, SIGNAL('rejected()'), self, SLOT('reject()'))

        if (LicConfig.filename):  # If there's an open instruction book, add an apply button to see new colors immediately.
            btn = buttonBox.addButton(QDialogButtonBox.Apply)
            self.connect(btn, SIGNAL('clicked()'), self.apply)

        if (colorDict.licColors):
            text = "Could not find LDConfig.ldr. Color information loaded from Lic's internal color table."
        else:
            text = "Color information loaded from: %s\\LDConfig.ldr" % LicConfig.LDrawPath
        
        text += "\nTo have Lic use different colors, edit the 'Custom' and 'Edge' columns."

        box = QBoxLayout(QBoxLayout.TopToBottom, self)
        box.addWidget(QLabel(text))
        box.addWidget(table)
        box.addWidget(buttonBox)
        
    def cellRGBA(self, row, col):
        text = str(self.table.item(row, col).text())
        if text:
            rgba = text.split(',')
            rgba = (rgba + ['255']) if len(rgba) == 3 else rgba
            rgba = [min(max(int(x.strip()), 0), 255) / 255.0 for x in rgba]
            if len(rgba) < 4:
                raise ValueError
            return rgba
        return []

    def cellEdited(self, row, col):
        if col < 3:
            return
        colorCell = self.table.item(row, 0)
        colorCell.setIcon(QIcon())
        try:
            rgba = self.cellRGBA(row, col)
            if col == 3:
                colorCell.setBackgroundColor(QColor.fromRgbF(*(rgba if rgba else colorCell.licColor.originalRGBA)))
            elif col == 4 and not rgba:
                self.table.item(row, 4).setText('0, 0, 0, 255')
        except ValueError:
            w, h = self.table.columnWidth(0), self.table.rowHeight(row)
            pixmap = QPixmap(w, h)
            pixmap.fill(Qt.white)
            painter = QPainter(pixmap)
            painter.setPen(QPen(QBrush(Qt.black), 2))
            painter.drawLine(0, 0, w, h)
            painter.drawLine(0, h, w, 0)
            painter.end()
            colorCell.setBackgroundColor(Qt.white)
            colorCell.setIcon(QIcon(pixmap))

    def apply(self):
        # Build & return list of changed colors & edges
        change = False
        for row in range(self.table.rowCount()):
            color = self.table.item(row, 0).licColor
            try:
                licRGBA = self.cellRGBA(row, 3)
                edgeRGBA = self.cellRGBA(row, 4)
            except ValueError as e:
                # Hit an error parsing user's input: warn user & abort the apply
                col = 4 if licRGBA == [] else 3
                text = str(self.table.item(row, col).text())
                QMessageBox.warning(self, "Lic - Color Error", "Cannot convert \"%s\" into red, green, blue and alpha values." % text)
                self.table.setCurrentCell(row, col)
                return False
            
            if licRGBA and licRGBA != color.rgba:
                color.rgba = licRGBA
                change = True
            elif not licRGBA and color.rgba != color.originalRGBA:
                color.rgba = color.originalRGBA
                change = True

            if edgeRGBA and edgeRGBA != color.edgeColor.rgba:
                color.edgeColor.rgba = edgeRGBA
                change = True
            elif not edgeRGBA and color.edgeColor.rgba != [0, 0, 0, 1]:
                color.edgeColor.rgba = [0, 0, 0, 1]
                change = True

        if change:
            self.emit(SIGNAL('acceptColor'))

        return True

    def accept(self):
        if self.apply():
            QDialog.accept(self)
        
    def reject(self):
        QDialog.reject(self)

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
        self.originalBrush = QBrush(self.fillColor) if self.fillColor else None

        self.penWidthSpinBox = QSpinBox()
        self.penWidthSpinBox.setRange(0, 50)
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
        color, ok = QColorDialog.getRgba(self.penColorButton.color.rgba(), self)
        if not ok:
            return
        color = QColor.fromRgba(color)
        if color.isValid(): 
            self.penColorButton.color = color
            self.penChanged()

    def getFillColor(self):
        color, ok = QColorDialog.getRgba(self.fillColorButton.color.rgba(), self)
        if not ok:
            return
        color = QColor.fromRgba(color)
        if color.isValid():
            self.fillColorButton.color = color
            self.penChanged()

    def penChanged(self):
        width = self.penWidthSpinBox.value()
        style = Qt.PenStyle(self.penStyleComboBox.itemData(self.penStyleComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        cap = Qt.PenCapStyle(self.penCapComboBox.itemData(self.penCapComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        join = Qt.PenJoinStyle(self.penJoinComboBox.itemData(self.penJoinComboBox.currentIndex(), Qt.UserRole).toInt()[0])
        color = self.penColorButton.color
        pen = QPen(color, width, style, cap, join)
        pen.cornerRadius = self.cornerRadiusSpinBox.value() if self.hasRadius else 0
        brush = QBrush(self.fillColorButton.color) if self.fillColor else None
        
        # Pen cap & join do nothing on rounded rects, so disable those combo box options if we have a corner radius
        self.penCapComboBox.setEnabled(pen.cornerRadius == 0)
        self.penJoinComboBox.setEnabled(pen.cornerRadius == 0)
        
        self.emit(SIGNAL("changePen"), pen, brush)

    def accept(self):
        self.emit(SIGNAL("acceptPen"), self.originalPen, self.originalBrush)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changePen"), self.originalPen, self.originalBrush)
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

class XYZWidget(QWidget):
    
    def __init__(self, changeSignal, min, max, x, y, z, double = False):
        QWidget.__init__(self)

        self.xSpinBox = self.makeSpinBox(x, min, max, changeSignal, double)
        self.ySpinBox = self.makeSpinBox(y, min, max, changeSignal, double)
        self.zSpinBox = self.makeSpinBox(z, min, max, changeSignal, double)
        
        layout = QFormLayout(self)
        layout.addRow("X:", self.xSpinBox)
        layout.addRow("Y:", self.ySpinBox)
        layout.addRow("Z:", self.zSpinBox)
        
    def setLabels(self, x, y, z):
        self.layout().labelForField(self.xSpinBox).setText(x)
        self.layout().labelForField(self.ySpinBox).setText(y)
        self.layout().labelForField(self.zSpinBox).setText(z)
    
    def xyz(self):
        return [self.xSpinBox.value(), self.ySpinBox.value(), self.zSpinBox.value()]
    
    def selectFirst(self):
        self.xSpinBox.selectAll()

class RowColDialog(QDialog):

    def __init__(self, parent, rows, cols, max):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Row & Column Page Layout"))

        self.originalValues = (rows, cols)

        rowLabel, self.rowSpinBox = self.makeLabelSpinBox("&Rows:", rows, 1, max, self.valueChanged)
        colLabel, self.colSpinBox = self.makeLabelSpinBox("&Cols:", cols, 1, max, self.valueChanged)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)

        grid = QGridLayout()
        grid.addWidget(rowLabel, 0, 0)
        grid.addWidget(self.rowSpinBox, 0, 1)
        grid.addWidget(colLabel, 1, 0)
        grid.addWidget(self.colSpinBox, 1, 1)
        grid.addWidget(buttonBox, 2, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.rowSpinBox.selectAll()
        
    def valueChanged(self):
        rows = self.rowSpinBox.value()
        cols = self.colSpinBox.value()
        self.emit(SIGNAL("changeValue"), (rows, cols))
    
    def accept(self):
        self.emit(SIGNAL("acceptValue"), self.originalValues)
        QDialog.accept(self)
        
    def reject(self):
        self.emit(SIGNAL("changeValue"), self.originalValues)
        QDialog.reject(self)
    
class RotationDialog(QDialog):
    
    def __init__(self, parent, rotation):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Rotation"))

        self.originalRotation = list(rotation)

        self.xyzWidget = XYZWidget(self.rotationChanged, -360, 360, *self.originalRotation)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        box = QBoxLayout(QBoxLayout.TopToBottom, self)
        box.addWidget(self.xyzWidget)
        box.addWidget(buttonBox)

        self.rotationChanged()
        self.xyzWidget.selectFirst()

    def rotationChanged(self):
        self.emit(SIGNAL("changeRotation"), self.xyzWidget.xyz())

    def accept(self):
        self.emit(SIGNAL("acceptRotation"), self.originalRotation)
        QDialog.accept(self)

    def reject(self):
        self.emit(SIGNAL("changeRotation"), self.originalRotation)
        QDialog.reject(self)

class DisplaceDlg(QDialog):

    def __init__(self, parent, displacement, direction):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Displacement"))
        self.originalDisplacement, self.direction = displacement, direction

        distance = LicHelpers.displacementToDistance(displacement, direction)
        sizeLabel, self.sizeSpinBox = self.makeLabelSpinBox(self.tr("&Distance:"), distance, -5000, 5000, self.sizeChanged)

        self.arrowCheckBox = QCheckBox(self.tr("&Adjust Arrow Length"))
        self.arrowCheckBox.setChecked(True)

        self.xyzWidget = XYZWidget(self.displacementChanged, -5000, 5000, *displacement)

        self.moreButton = QPushButton(self.tr("X - Y - Z"))
        self.moreButton.setCheckable(True)
        self.moreButton.setAutoDefault(False)
        self.connect(self.moreButton, SIGNAL("toggled(bool)"), self.xyzWidget, SLOT("setVisible(bool)"))

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        mainLayout = QGridLayout(self)
        mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        mainLayout.addWidgetRow(0, (sizeLabel, self.sizeSpinBox))
        mainLayout.addWidget(self.arrowCheckBox, 1, 0, 1, 2)
        mainLayout.addWidget(self.moreButton, 2, 0, 1, 2)
        mainLayout.addWidget(self.xyzWidget, 3, 0, 1, 2)
        mainLayout.addWidget(buttonBox, 4, 0, 1, 2)

        self.xyzWidget.hide()
        self.sizeSpinBox.selectAll()

    def sizeChanged(self):
        newSize = self.sizeSpinBox.value()
        displacement = LicHelpers.distanceToDisplacement(newSize, self.direction)
        self.emit(SIGNAL("changeDisplacement"), displacement, self.arrowCheckBox.isChecked())

    def displacementChanged(self):
        self.emit(SIGNAL("changeDisplacement"), self.xyzWidget.xyz(), self.arrowCheckBox.isChecked())

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
        self.originalDisplacement, self.originalLength, self.originalRotation = arrow.displacement, arrow.getLength(), arrow.axisRotation

        displacement = arrow.displacement
        distance = LicHelpers.displacementToDistance(displacement, arrow.displaceDirection)
        sizeLabel, self.sizeSpinBox = self.makeLabelSpinBox(self.tr("&Distance:"), distance, -5000, 5000, self.sizeChanged)
        lengthLabel, self.lengthSpinBox = self.makeLabelSpinBox(self.tr("&Length:"), arrow.getLength(), -5000, 5000, self.lengthChanged)
        rotationLabel, self.rotationSpinBox = self.makeLabelSpinBox(self.tr("&Rotation:"), arrow.axisRotation, -360, 360, self.rotationChanged)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        self.tipXYZWidget = XYZWidget(self.displacementChanged, -5000, 5000, *displacement)
        self.endXYZWidget = XYZWidget(self.displacementChanged, -5000, 5000, *displacement)
        self.tipXYZWidget.setLabels("tip X:", "tip Y:", "tip Z:")
        self.endXYZWidget.setLabels("end X (NYI):", "end Y (NYI):", "end Z (NYI):")

        extension = QWidget()
        box = QBoxLayout(QBoxLayout.TopToBottom, extension)
        box.addWidget(self.tipXYZWidget)
        #box.addWidget(self.endXYZWidget)  # TODO: Either implement arbitrary arrow end point positions or remove this

        self.moreButton = QPushButton(self.tr("X - Y - Z"))
        self.moreButton.setCheckable(True)
        self.moreButton.setAutoDefault(False)
        self.connect(self.moreButton, SIGNAL("toggled(bool)"), extension, SLOT("setVisible(bool)"))

        mainLayout = QGridLayout(self)
        mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        mainLayout.addWidgetRow(0, (sizeLabel, self.sizeSpinBox))
        mainLayout.addWidgetRow(1, (lengthLabel, self.lengthSpinBox))
        mainLayout.addWidgetRow(2, (rotationLabel, self.rotationSpinBox))

        mainLayout.addWidget(self.moreButton, 3, 0, 1, 2)
        mainLayout.addWidget(extension, 4, 0, 1, 2)
        mainLayout.addWidget(buttonBox, 5, 0, 1, 2)

        extension.hide()
        self.sizeSpinBox.selectAll()

    def sizeChanged(self):
        newSize = self.sizeSpinBox.value()
        displacement = LicHelpers.distanceToDisplacement(newSize, self.arrow.displaceDirection)
        self.emit(SIGNAL("changeDisplacement"), displacement)

    def lengthChanged(self):
        newLength = self.lengthSpinBox.value()
        self.emit(SIGNAL("changeLength"), newLength)

    def rotationChanged(self):
        newRotation = self.rotationSpinBox.value()
        self.emit(SIGNAL("changeRotation"), newRotation)

    def displacementChanged(self):
        self.emit(SIGNAL("changeDisplacement"), self.tipXYZWidget.xyz())

    def accept(self):
        self.emit(SIGNAL("accept"), self.originalDisplacement, self.originalLength, self.originalRotation)
        QDialog.accept(self)

    def reject(self):
        self.emit(SIGNAL("changeDisplacement"), self.originalDisplacement)
        self.emit(SIGNAL("changeLength"), self.originalLength)
        self.emit(SIGNAL("changeRotation"), self.originalRotation)
        QDialog.reject(self)

class PositionRotationDlg(QDialog):

    def __init__(self, parent, position, rotation):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change Position & Rotation"))
        self.originalPosition, self.originalRotation = position, rotation

        self.xyzWidget = XYZWidget(self.valueChanged, -5000, 5000, *position)
        posLabel = QLabel(self.tr("Position:"))
        posLabel.setBuddy(self.xyzWidget)

        r = rotation
        self.rotationWidget = XYZWidget(self.valueChanged, -360, 360, r[0], r[1], r[2], True)
        rotLabel = QLabel(self.tr("Rotation:"))
        rotLabel.setBuddy(self.rotationWidget)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))

        mainLayout = QGridLayout(self)
        mainLayout.setSizeConstraint(QLayout.SetFixedSize)
        mainLayout.addWidget(posLabel, 0, 0)
        mainLayout.addWidget(self.xyzWidget, 1, 0)
        mainLayout.addWidget(rotLabel, 2, 0)
        mainLayout.addWidget(self.rotationWidget, 3, 0)
        mainLayout.addWidget(buttonBox, 4, 0)

        self.xyzWidget.selectFirst()

    def valueChanged(self):
        self.emit(SIGNAL("change"), self.xyzWidget.xyz(), self.rotationWidget.xyz())

    def accept(self):
        self.emit(SIGNAL("accept"), self.originalPosition, self.originalRotation)
        QDialog.accept(self)

    def reject(self):
        self.emit(SIGNAL("change"), self.originalPosition, self.originalRotation)
        QDialog.reject(self)

class LightingDialog(QDialog):

    def __init__(self, parent, ambient, shine, lineWidth, disableLight):
        QDialog.__init__(self, parent,  Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.tr("Change 3D Lighting"))

        self.values = [ambient, shine, lineWidth, disableLight]

        self.disableLightCheckbox = QCheckBox("&Disable Lighting")
        self.disableLightCheckbox.setChecked(disableLight)
        self.connect(self.disableLightCheckbox, SIGNAL("stateChanged(int)"), self.valueChanged)

        ambientLabel, self.ambientSpinBox = self.makeLabelSpinBox("&Ambient:", ambient * 100.0, 0.0, 100.0, self.valueChanged)
        shineLabel, self.shineSpinBox = self.makeLabelSpinBox("&Shininess:", shine, 0.0, 100.0, self.valueChanged)
        lwLabel, self.lwSpinBox = self.makeLabelSpinBox("&Line Width:", (lineWidth - 1) * 10.0, 0.0, 100.0, self.valueChanged)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)

        grid = QGridLayout()
        grid.addWidget(self.disableLightCheckbox, 0, 0, 1, 2)
        grid.addWidgetRow(1, (ambientLabel, self.ambientSpinBox))
        #grid.addWidgetRow(1, (shineLabel, self.shineSpinBox))
        grid.addWidgetRow(2, (lwLabel, self.lwSpinBox))
        grid.addWidget(buttonBox, 3, 0, 1, 2)
        self.setLayout(grid)

        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        self.ambientSpinBox.selectAll()

    def valueChanged(self):
        newValues = [self.ambientSpinBox.value() / 100.0, self.shineSpinBox.value(), (self.lwSpinBox.value() / 10.0) + 1, self.disableLightCheckbox.isChecked()]
        self.emit(SIGNAL("changeValues"), newValues)

    def accept(self):
        self.emit(SIGNAL("acceptValues"), self.values)
        QDialog.accept(self)

    def reject(self):
        self.emit(SIGNAL("changeValues"), self.values)
        QDialog.reject(self)
