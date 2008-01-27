import math   # for sqrt
import os     # for output path creation

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

import GLHelpers
import l3p
import povray
import LDrawColors

from LDrawFileFormat import *

MagicNumber = 0x14768126
FileVersion = 1

UNINIT_OGL_DISPID = -1
partDictionary = {}      # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
submodelDictionary = {}  # {'filename': Submodel()}
currentModelFilename = ""

GlobalGLContext = None
AllFlags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable
NoMoveFlags = QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable

def genericMousePressEvent(className):
    def _tmp(self, event):
        className.mousePressEvent(self, event)
        self.oldPos = self.pos()
    return _tmp
    
def genericMouseReleaseEvent(className):
    
    def _tmp(self, event):        
        className.mouseReleaseEvent(self, event)
        
        if self.pos() != self.oldPos:
            self.scene().emit(SIGNAL("itemsMoved"), self.scene().selectedItems())
            if hasattr(self.parentItem(), "resetRect"):
                self.parentItem().resetRect()
    return _tmp
                
def genericItemParent(self):
    return self.parentItem()

def genericItemData(self, index):
    return self.dataText

def genericRow(self):
    if hasattr(self, '_row'):
        return self._row
    if hasattr(self, 'parentItem'):
        parent = self.parentItem()
        if hasattr(parent, 'getChildRow'):
            return parent.getChildRow(self)
    return 0

QGraphicsRectItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsRectItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsRectItem.parent = genericItemParent
QGraphicsRectItem.data = genericItemData
QGraphicsRectItem.row = genericRow

QGraphicsSimpleTextItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.parent = genericItemParent
QGraphicsSimpleTextItem.data = genericItemData
QGraphicsSimpleTextItem.row = genericRow

QGraphicsPixmapItem.mousePressEvent = genericMousePressEvent(QGraphicsItem)
QGraphicsPixmapItem.mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsItem)

QGraphicsPixmapItem.parent = genericItemParent
QGraphicsPixmapItem.data = genericItemData
QGraphicsPixmapItem.row = genericRow

def printRect(rect, text = ""):
    print text + ", l: %f, r: %f, t: %f, b: %f" % (rect.left(), rect.right(), rect.top(), rect.bottom())

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.connect(self, SIGNAL("clicked(QModelIndex)"), self.clicked)

    def keyReleaseEvent(self, event):
        key = event.key()
        moved = False
        if key == Qt.Key_Left:
            moved = True
        elif key == Qt.Key_Right:
            moved = True
        elif key == Qt.Key_Up:
            moved = True
        elif key == Qt.Key_Down:
            moved = True
        elif key == Qt.Key_PageUp:
            moved = True
        elif key == Qt.Key_PageDown:
            moved = True
        else:
            event.ignore()
            return

        if moved:
            QTreeView.keyReleaseEvent(self, event)
            self.clicked(self.currentIndex())
        
    def updateSelection(self):
        """ This is called whenever the graphics scene's selection changes """
        
        # Deselect everything in the tree
        model = self.model()
        selection = self.selectionModel()
        selection.clear()

        # Select everything in the tree that's currently selected in the graphics view
        for item in model.scene.selectedItems():
            index = model.createIndex(item.row(), 0, item)
            if index:
                self.setCurrentIndex(index)
                selection.select(index, QItemSelectionModel.Select)
                self.scrollTo(index)

    def clicked(self, index = None):
        if not index:
            return

        # Get a list of everything selected in the tree
        selList = self.selectionModel().selectedIndexes()

        # Clear any existing selection from the graphics view
        instructions = self.model()
        instructions.clearSelectedParts()
        instructions.scene.clearSelection()

        # Find the selected item's parent page, then flip to that page
        if isinstance(index.internalPointer(), Submodel):
            instructions.mainModel.selectPage(index.internalPointer().pages[0].number)
            self.scrollTo(index.child(0, 0))
        else:
            parent = QModelIndex(index)
            while not isinstance(parent.internalPointer(), Page):
                parent = parent.parent()
            instructions.mainModel.selectPage(parent.internalPointer().number)

        # Finally, select the things we actually clicked on
        for index in selList:
            item = index.internalPointer()
            item.setSelected(True)

class Instructions(QAbstractItemModel):

    def __init__(self, parent, scene, glWidget, filename = None):
        QAbstractItemModel.__init__(self, parent)
        global GlobalGLContext

        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"

        self.scene = scene
        GlobalGLContext = glWidget
        GlobalGLContext.makeCurrent()
        
        self.mainModel = None

        if filename:
            self.loadModel(filename)

    def data(self, index, role = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if not index.isValid():
            global currentModelFilename
            return QVariant(currentModelFilename)

        item = index.internalPointer()

        return QVariant(item.data(0))

    def rowCount(self, parent):

        if parent.column() > 0:
            return 0

        if not parent.isValid():
            return self.mainModel.rowCount() if self.mainModel else 0

        item = parent.internalPointer()
        if hasattr(item, "rowCount"):
            return item.rowCount()
        return 0

    def columnCount(self, parentIndex):
        return 1  # Every single item in the tree has exactly 1 column

    def flags(self, index):
        if index.isValid():
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return Qt.ItemIsEnabled

    def index(self, row, column, parent):
        if row < 0 or column < 0:
            return QModelIndex()

        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self.mainModel

        if not hasattr(parentItem, "child"):
            return QModelIndex()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is self.mainModel:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def headerData(self, section, orientation, role = Qt.DisplayRole):
        return QVariant("Instruction Book")

    def clear(self):
        global partDictionary, submodelDictionary, currentModelFilename
        self.emit(SIGNAL("layoutAboutToBeChanged"))

        # Remove everything from the graphics scene
        if self.mainModel:
            self.mainModel.deleteAllPages(self.scene)

        self.mainModel = None
        partDictionary = {}
        submodelDictionary = {}
        currentModelFilename = ""
        Page.NextNumber = Step.NextNumber = 1
        CSI.scale = PLI.scale = 1.0
        GlobalGLContext.makeCurrent()
        self.emit(SIGNAL("layoutChanged()"))

    def clearSelectedParts(self):
        for item in self.scene.selectedItems():
            if isinstance(item, Part):
                item.setSelected(False)

    def loadModel(self, filename):
        global currentModelFilename        
        currentModelFilename = filename
        self.emit(SIGNAL("layoutAboutToBeChanged"))
        self.mainModel = Submodel(self, self, filename)
        self.mainModel.importModel()

        self.initGLDisplayLists()  # generate all part GL display lists on the general glWidget
        self.initPartDimensions()  # Calculate width and height of each partOGL in the part dictionary
        self.initCSIDimensions()   # Calculate width and height of each CSI in this instruction book
        self.initCSIPixmaps()       # Generate a pixmap for each CSI

        self.mainModel.initLayout()
        self.mainModel.selectPage(1)
        self.emit(SIGNAL("layoutChanged()"))

    def initGLDisplayLists(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()
        
        # First initialize all partOGL display lists
        for part in partDictionary.values():
            part.createOGLDisplayList()
            
        # Initialize all submodel display lists
        for submodel in submodelDictionary.values():
            submodel.createOGLDisplayList()
            
        # Initialize the main model display list (TODO: consider just storing this in submodelDictionary?)
        self.mainModel.createOGLDisplayList()

        # Initialize all CSI display lists
        csiList = self.mainModel.getCSIList()
        for csi in csiList:
            csi.createOGLDisplayList()

    def initPartDimensions(self):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        global GlobalGLContext

        partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        submodelList = [submodel for submodel in submodelDictionary.values() if submodel.used]
        partList += submodelList
        partList.append(self.mainModel)

        if not partList:
            return    # If there's no parts to initialize, we're done here

        partList2 = []
        lines = []
        sizes = [128, 256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render each image and calculate their sizes
            for partOGL in partList:

                if partOGL.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    lines.append(partOGL.dimensionsToString())
                else:
                    partList2.append(partOGL)

            if len(partList2) < 1:
                break  # All images initialized successfully
            else:
                partList = partList2  # Some images rendered out of frame - loop and try bigger frame
                partList2 = []

        # Append any newly calculated part dimensions to cache file
        # TODO: fix this
        """
        print ""
        if lines:
            f = open(self.partDimensionsFilename, 'a')
            f.writelines(lines)
            f.close()
        """

    def initCSIDimensions(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()

        csiList = self.mainModel.getCSIList()
        if not csiList:
            return  # All CSIs initialized - nothing to do here

        csiList2 = []
        sizes = [512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels or steps

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render each CSI and calculate its size
            for csi in csiList:
                if not csi.initSize(size, pBuffer):
                    csiList2.append(csi)

            if len(csiList2) < 1:
                break  # All images initialized successfully
            else:
                csiList = csiList2  # Some images rendered out of frame - loop and try bigger frame
                csiList2 = []

        GlobalGLContext.makeCurrent()
        
    def initCSIPixmaps(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()
        
        csiList = self.mainModel.getCSIList()
        format = QGLFormat()
        
        for csi in csiList:
            if csi.width < 1 or csi.height < 1:
                continue
            pBuffer = QGLPixelBuffer(csi.width * CSI.scale, csi.height * CSI.scale, format, GlobalGLContext)
            pBuffer.makeCurrent()
            csi.initPixmap(pBuffer)
            
        GlobalGLContext.makeCurrent()
        
    def initPLIPixmaps(self):
        for page in self.mainModel.pages:
            page.scaleImages()
        
        for submodel in submodelDictionary.values():
            for page in submodel.pages:
                page.scaleImages()
    
    def exportImages(self):

        global submodelDictionary
        for model in submodelDictionary.values():
            if model.used:
                model.createPng()
        self.mainModel.createPng()

        self.mainModel.exportImages()

    def getPartDictionary(self):
        global partDictionary
        return partDictionary

    def getSubmodelDictionary(self):
        global submodelDictionary
        return submodelDictionary
    
    def pageUp(self):
        if self.mainModel:
            self.mainModel.selectPage(self.mainModel.currentPage._number - 1)
            self.mainModel.currentPage.setSelected(True)

    def pageDown(self):
        if self.mainModel:
            m = self.mainModel
            lastPage = m.pages[-1]._number
            nextPage = min(m.currentPage._number + 1, lastPage)
            m.selectPage(nextPage)
            m.currentPage.setSelected(True)

    def selectFirstPage(self):
        if self.mainModel:
            self.mainModel.selectPage(0)
            self.mainModel.currentPage.setSelected(True)

    def selectLastPage(self):
        if self.mainModel:
            self.mainModel.selectPage(self.mainModel.pages[-1]._number)
            self.mainModel.currentPage.setSelected(True)

    def setCSIPLISize(self, newCSISize, newPLISize):

        print "Setting size to: %d, %d" % (newCSISize, newPLISize)
        oldCSISize = CSI.scale
        oldPLISize = PLI.scale
        
        if newCSISize != CSI.scale:
            CSI.scale = newCSISize
            self.initCSIPixmaps()

        if newPLISize != PLI.scale:
            PLI.scale = newPLISize
            self.initPLIPixmaps()
            
        if newCSISize != oldCSISize or newPLISize != oldPLISize:
            return ((oldCSISize, newCSISize), (oldPLISize, newPLISize))
        return None

    def enlargePixmaps(self):
        CSI.scale += 0.5
        PLI.scale += 0.5
        self.initCSIPixmaps()
        self.initPLIPixmaps()
    
    def shrinkPixmaps(self):
        CSI.scale -= 0.5
        PLI.scale -= 0.5
        self.initCSIPixmaps()
        self.initPLIPixmaps()

class Page(QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """

    NextNumber = 1
    margin = QPointF(15, 15)

    def __init__(self, parent, instructions, number = -1):
        QGraphicsRectItem.__init__(self)
        instructions.scene.addItem(self)

        # Position this rectangle inset from the containing scene
        self.setPos(0, 0)
        self.setRect(instructions.scene.sceneRect())

        self.instructions = instructions
        self._parent = parent
        self.steps = []
        self._row = 0
        self.children = []
        self.borders = []

        # Give this page a number
        if number == -1:
            self._number = Page.NextNumber
            Page.NextNumber += 1
        else:
            self._number = number
            Page.NextNumber = number + 1

        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.dataText = "Page Number Label"
        self.children.append(self.numberItem)

        self.submodelItem = None
        
        # Position page number in bottom right page corner
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.margin)
        self.numberItem.setPos(rect.topLeft())
        self.setFlags(NoMoveFlags)
        self.numberItem.setFlags(AllFlags)

    def _setNumber(self, number):
        self._number = number
        self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(fget = _getNumber, fset = _setNumber)

    def parent(self):
        return self._parent

    def child(self, row):
        if row < 0 or row >= len(self.children):
            return None
        return self.children[row]

    def rowCount(self):
        return len(self.children)

    def setRow(self, row):
        self._row = row
        
    def row(self):
        return self._row

    def getChildRow(self, child):
        return self.children.index(child)
    
    def data(self, index):
        return "Page %d" % self._number

    def getAllChildItems(self):

        items = [self, self.numberItem]

        for step in self.steps:
            items.append(step)
            items.append(step.numberItem)
            items.append(step.pli)
            for pliItem in step.pli.pliItems:
                items.append(pliItem)
                items.append(pliItem.numberItem)

        for border in self.borders:
            items.append(border)

        if self.submodelItem:
            items.append(self.submodelItem)

        return items

    def prevPage(self):
        if self._row:
            return self._parent.pages[self._row - 1]
        return None

    def nextPage(self):
        if self._row == len(self._parent.pages) - 1:
            return None
        return self._parent.pages[self._row + 1]
        
    def addStep(self, step, relayout = False):

        self.steps.append(step)
        self.steps.sort(key = lambda x: x._number)
        step.setParentItem(self)

        i = 0
        for i in range(len(self.children) - 1, -1, -1):
            item = self.children[i]
            if isinstance(item, Step):
                if item._number < step._number:
                    break
        self.addChild(i + 1, step)

        if relayout:
            self.initLayout()

    def addChild(self, index, child):

        # Add the child to the child array
        self.children.insert(index, child)

        # Adjust the z-order of all children: first child has highest z value
        for i, item in enumerate(self.children):
            item.setZValue(len(self.children) - i)

    def addStepSeparator(self, index):

        border = QGraphicsRectItem(self)
        border.setRect(QRectF(0, 0, 1, 1))
        border.setFlags(AllFlags)
        border.dataText = "Step Separator"
        self.borders.append(border)
        self.addChild(index, border)
        return border
    
    def removeStepSeparator(self, sep):
        self.children.remove(sep)
        self.borders.remove(sep)
        self.scene().removeItem(sep)
        del sep

    def removeStep(self, step):
        self.steps.remove(step)
        self.children.remove(step)

    def addSubmodelImage(self, childRow = None):

        pixmap = self._parent.getPixmap()
        if not pixmap:
            print "Error: could not create a pixmap for page %d's submodel image" % self._number
            return

        self.submodelItem = QGraphicsRectItem(self)
        self.submodelItem.dataText = "Submodel Preview"
        self.submodelItem.setPos(Page.margin)
        self.submodelItem.setFlags(AllFlags)
        
        self.pixmapItem = QGraphicsPixmapItem(self.submodelItem)
        self.pixmapItem.setPixmap(pixmap)
        self.pixmapItem.setPos(PLI.margin)
        
        self.submodelItem.setRect(0, 0, pixmap.width() + PLI.margin.x() * 2, pixmap.height() + PLI.margin.y() * 2)

        if childRow:
            self.addChild(childRow, self.submodelItem)
        else:
            self.children.append(self.submodelItem)
        
    def resetSubmodelImage(self):
        
        pixmap = self._parent.getPixmap()
        if not pixmap:
            print "Error: could not create a pixmap for page %d's submodel image" % self._number
            return

        self.pixmapItem.setPixmap(pixmap)
        self.pixmapItem.setPos(PLI.margin)

        self.submodelItem.setRect(0, 0, pixmap.width() + PLI.margin.x() * 2, pixmap.height() + PLI.margin.y() * 2)

    def initLayout(self):

        print "Initializing page: %d" % self._number

        # Remove any borders, since we'll re-add them in the appropriate place later
        for border in list(self.borders):
            self.removeStepSeparator(border)
        self.boders = []

        pageRect = self.rect()
        mx = Page.margin.x()
        my = Page.margin.y()
        
        # Allocate space for the submodel image, if any
        if self.submodelItem:
            self.submodelItem.setPos(Page.margin)
            self.submodelItem.rect().setTopLeft(Page.margin)
            pageRect.setTop(self.submodelItem.rect().height() + my + my)

        if len(self.steps) <= 0:
            return  # No steps - nothing more to do here

        # Divide the remaining space into equal space for each step, depending on the number of steps.
        stepCount = len(self.steps)
        colCount = int(math.ceil(math.sqrt(stepCount)))
        rowCount = stepCount / colCount  # This needs to be integer division
        if stepCount % colCount:
            rowCount += 1
        
        stepWidth = pageRect.width() / colCount
        stepHeight = pageRect.height() / rowCount
        x = pageRect.x() - stepWidth
        y = pageRect.y()
        
        separatorIndices = []
        for i, step in enumerate(self.steps):
            
            if i % rowCount:
                y += stepHeight
            else:
                y = pageRect.y()
                x += stepWidth
                if i > 0:
                    separatorIndices.append(step.row())

            tmpRect = QRectF(x, y, stepWidth, stepHeight)
            tmpRect.adjust(mx, my, -mx, -my)
            step.initLayout(tmpRect)

        if len(self.steps) < 2:
            return  # if there's only one step, no step separators needed

        # Add a step separator between each column of steps
        for i in range(1, colCount):
            index = separatorIndices[i - 1]
            sep = self.addStepSeparator(index)
            sep.setPos(stepWidth * i, pageRect.top() + my)
            sep.setRect(QRectF(0, 0, 1, pageRect.height() - my - my))

    def scaleImages(self):
        for step in self.steps:
            step.pli.initLayout()
            
        if self.submodelItem:
            self.resetSubmodelImage()
        
    def renderFinalImage(self):

        for step in self.steps:
            step.csi.createPng()
            for item in step.pli.pliItems:
                item.createPng()

        image = QImage(self.rect().width(), self.rect().height(), QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(image)

        items = self.getAllChildItems()
        options = QStyleOptionGraphicsItem()
        optionList = [options] * len(items)
        self.scene().drawItems(painter, items, optionList)

        for step in self.steps:
            if hasattr(step.csi, "pngImage"):
                painter.drawImage(step.csi.scenePos(), step.csi.pngImage)
            else:
                print "Error: Trying to draw a csi that was not exported to png: page %d step %d" % step.csi.getPageStepNumberPair()
                
            for item in step.pli.pliItems:
                if hasattr(item, "pngImage"):
                    painter.drawImage(item.scenePos(), item.pngImage)
                else:
                    print "Error: Trying to draw a pliItem that was not exported to png: step %d, item %s" % (step._number, item.partOGL.filename)

        if self.submodelItem:
            painter.drawImage(self.submodelItem.pos() + PLI.margin, self._parent.pngImage)

        painter.end()
        
        imgName = os.path.join(config.config['imgPath'], "Page_%d.png" % self._number)
        image.save(imgName, None)
                
    def paint(self, painter, option, widget = None):

        # Draw a slightly down-right translated black rectangle, for the page shadow effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.rect().translated(3, 3))

        # Draw the page itself - white with a thin black border
        painter.setPen(QPen(Qt.black))
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(self.rect())

    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        delPage = menu.addAction("Delete this Page", self.one)
        menu.exec_(event.screenPos())
    
    def one(self):
        print "It's ALIVE"
    
class Step(QGraphicsRectItem):
    """ A single step in an instruction book.  Contains one optional PLI and exactly one CSI. """

    NextNumber = 1

    def __init__(self, parentPage, number = -1, prevCSI = None):
        QGraphicsRectItem.__init__(self, parentPage)

        pen = self.pen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)

        self.setPos(Page.margin)

        # Give this page a number
        if number == -1:
            self._number = Step.NextNumber
            Step.NextNumber += 1
        else:
            self._number = number
            Step.NextNumber = number + 1

        self.csi = CSI(self, prevCSI)
        self.pli = PLI(self)

        # Initialize Step's number label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setPos(0, 0)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.setFlags(AllFlags)
        self.numberItem.dataText = "Step Number Label"
        self.setFlags(AllFlags)

    def _setNumber(self, number):
        self._number = number
        self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(fget = _getNumber, fset = _setNumber)
    
    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row == 0:
            return self.numberItem
        if row == 1:
            return self.csi
        if row == 2:
            return self.pli
        return None

    def rowCount(self):
        return 3

    def row(self):
        return self.parentItem().getChildRow(self)

    def data(self, index):
        return "Step %d" % self._number

    def addPart(self, part):
        self.csi.addPart(part)
        if self.pli:
            self.pli.addPart(part)

    def resetRect(self):
        stepRect = self.rect()
        childrenRect = self.childrenBoundingRect()
        self.setRect(stepRect | childrenRect)
        
    def initLayout(self, destRect):

        print "   Initializing step: %d" % self._number
        self.setPos(destRect.topLeft())
        self.setRect(0, 0, destRect.width(), destRect.height())
        
        self.pli.initLayout()
        self.csi.initLayout()

        # Position the Step number label beneath the PLI
        self.numberItem.setPos(0, 0)
        self.numberItem.moveBy(0, self.pli.rect().height() + Page.margin.y() + 0.5)

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        prevPage = menu.addAction("Move Step to &Previous Page", self.moveToPrevPage)
        nextPage = menu.addAction("Move Step to &Next Page", self.moveToNextPage)
        prevMerge = menu.addAction("Merge Step with Previous Step", self.mergeWithPrevStep)
        nextMerge = menu.addAction("Merge Step with Next Step", self.mergeWithNextStep)
        doLayout = menu.addAction("Re-layout affected Pages")
        doLayout.setCheckable(True)
        doLayout.setChecked(True)

        page = self.parent()
        
        if not page.prevPage():
            prevPage.setEnabled(False)
            prevMerge.setEnabled(False)

        if not page.nextPage():
            nextPage.setEnabled(False)
            nextMerge.setEnabled(False)

        menu.exec_(event.screenPos())

    def moveToPrevPage(self):
        self.moveToPage(self.parent().prevPage())
        
    def moveToNextPage(self):
        self.moveToPage(self.parent().nextPage())
    
    def moveToPage(self, page, relayout = True):
        
        page.instructions.emit(SIGNAL("layoutAboutToBeChanged"))

        # Remove this step from its current page's step list
        self.parent().removeStep(self)
        if relayout:
            self.parent().initLayout()
        
        # Add this step to the new page's step list, and set its scene parent
        page.addStep(self, relayout)
        
        page.instructions.emit(SIGNAL("layoutChanged()"))
    
    def mergeWithPrevStep(self):
        print "Merging Step %d with previous Step" % self._number
    
    def mergeWithNextStep(self, args = None):
        print "Merging Step %d with next Step" % self._number

class PLIItem(QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """

    def __init__(self, parent, partOGL, color):
        QGraphicsRectItem.__init__(self, parent)

        self.partOGL = partOGL
        self.parts = []

        self.color = color
        pen = self.pen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)
        self.setFlags(AllFlags)

        # Stores a pixmap of the actual part
        self.pixmapItem = QGraphicsPixmapItem(self)
        self.pixmapItem.dataText = "Image"

        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem("0x", self)
        self.numberItem.setFont(QFont("Arial", 10))
        self.numberItem.dataText = "Qty. Label (0x)"
        self.numberItem.setFlags(AllFlags)

    def addPart(self, part):
        self.parts.append(part)
        part._parentPLI = self
        part.setParentItem(self)
        self.numberItem.setText("%dx" % len(self.parts))
        self.numberItem.dataText = "Qty. Label (%dx)" % len(self.parts)
        
    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row <= 0:
            return self.numberItem
        if row > len(self.parts):
            return None
        return self.parts[row - 1]

    def rowCount(self):
        return 1 + len(self.parts)

    def row(self):
        pli = self.parentItem()
        return pli.pliItems.index(self)

    def data(self, index):
        return "%s - %s" % (self.partOGL.name, LDrawColors.getColorName(self.color))

    def resetRect(self):
        self.setRect(self.childrenBoundingRect())
        self.parentItem().resetRect()
        
    def initPixmap(self):
        pixmap = self.partOGL.getPixmap(self.color)
        if pixmap:
            self.pixmapItem.setPixmap(pixmap)
            self.pixmapItem.setPos(0, 0)

    def initLayout(self):

        self.resetTransform()
        self.initPixmap()
        part = self.partOGL
        lblHeight = self.numberItem.boundingRect().height() / 2.0

        li = part.leftInset * PLI.scale
        bi = part.bottomInset * PLI.scale
        h = part.height * PLI.scale
        
        # Position quantity label based on part corner, empty corner triangle and label's size
        if part.leftInset == part.bottomInset == 0:
            dx = -3   # Bottom left triangle is full - shift just a little, for a touch more padding
        else:
            slope = li / float(bi)
            dx = ((li - lblHeight) / slope) - 3  # 3 for a touch more padding

        self.numberItem.setPos(dx, h - lblHeight)

        # Set this item to the union of its image and qty label rects
        pixmapRect = self.pixmapItem.boundingRect().translated(self.pixmapItem.pos())
        numberRect = self.numberItem.boundingRect().translated(self.numberItem.pos())
        self.setRect(pixmapRect | numberRect)
        self.translate(-self.rect().x(), -self.rect().y())

    def createPng(self):

        part = self.partOGL
        if part.isSubmodel:
            self.pngImage = part.pngImage
            return

        fn = part.filename
        datFile = os.path.join(config.LDrawPath, 'PARTS', fn)
        if not os.path.isfile(datFile):
            datFile = os.path.join(config.LDrawPath, 'P', fn)
            if not os.path.isfile(datFile):
                datFile = os.path.join(config.LDrawPath, 'MODELS', fn)
                if not os.path.isfile(datFile):
                    datFile = os.path.join(config.config['datPath'], fn)
                    if not os.path.isfile(datFile):
                        print " *** Error: could not find dat file for part %s" % fn
                        return

        povFile = l3p.createPovFromDat(datFile, self.color)
        pngFile = povray.createPngFromPov(povFile, part.width, part.height, part.center, PLI.scale, isPLIItem = True)
        self.pngImage = QImage(pngFile)

class PLI(QGraphicsRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """

    scale = 1.0
    margin = QPointF(15, 15)

    def __init__(self, parent):
        QGraphicsRectItem.__init__(self, parent)

        self.setPos(0, 0)
        self.setPen(QPen(Qt.black))
        self.pliItems = []  # {(part filename, color): PLIItem instance}
        self.setFlags(AllFlags)

    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row < 0 or row >= len(self.pliItems):
            return None
        return self.pliItems[row] 

    def rowCount(self):
        return len(self.pliItems)

    def row(self):
        return 2

    def data(self, index):
        return "PLI"

    def isEmpty(self):
        return True if len(self.pliItems) == 0 else False

    def resetRect(self):
        rect = self.childrenBoundingRect().adjusted(-PLI.margin.x(), -PLI.margin.y(), PLI.margin.x(), PLI.margin.y())
        self.setRect(rect)
        self.parentItem().resetRect()
        
    def addPart(self, part):

        for item in self.pliItems:
            if item.color == part.color and item.partOGL.filename == part.partOGL.filename:
                item.addPart(part)
                return

        # If we're here, did not find an existing PLI, so create a new one
        item = PLIItem(self, part.partOGL, part.color)
        item.setParentItem(self)  # TODO: needed?
        item.addPart(part)
        self.pliItems.append(item)
        
    def initLayout(self):
        """
        Allocate space for all parts in this PLI, and choose a decent layout.
        """

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            return

        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for item in self.pliItems:
            item.initLayout()

        # Compare the width of layout Items 1 and 2
        def compareLayoutItemWidths(item1, item2):
            """ Returns 1 if part 2 is wider than part 1, 0 if equal, -1 if narrower. """
            if item1.partOGL.width < item2.partOGL.width:
                return 1
            if item1.partOGL.width == item2.partOGL.width:
                return 0
            return -1

        # Sort the list of parts in this PLI from widest to narrowest, with the tallest one first
        partList = self.pliItems
        tallestPart = max(partList, key = lambda x: x.partOGL.height)
        partList.remove(tallestPart)
        partList.sort(compareLayoutItemWidths)
        partList.insert(0, tallestPart)

        # This rect will be enlarged as needed
        b = QRectF(0, 0, -1, -1)

        overallX = maxX = xMargin = PLI.margin.x()
        overallY = maxY = yMargin = PLI.margin.y()

        for i, item in enumerate(partList):

            # Move this PLIItem to its new position
            item.setPos(overallX, overallY)

            # Check if the current PLI box is big enough to fit this part *below* the previous part,
            # without making the box any bigger.  If so, position part there instead.
            newWidth = item.rect().width()
            if i > 0:
                prevItem = partList[i-1]
                remainingHeight = b.height() - yMargin - yMargin - prevItem.rect().height()
                if item.rect().height() < remainingHeight:
                    overallX = prevItem.pos().x()
                    newWidth = prevItem.rect().width()
                    x = overallX + (newWidth - item.rect().width())
                    y = prevItem.pos().y() + PLI.margin.y() + item.rect().height()
                    item.setPos(x, y)

            # Increase overall x, box width and box height to make PLI box big enough for this part
            overallX += newWidth + xMargin
            maxX = max(maxX, overallX)

            # If this part pushes this PLI beyond the steps right edge, wrap to new line
            if overallX > self.parentItem().rect().width():
                overallX = xMargin
                maxX -= newWidth + xMargin
                overallY += b.height() - yMargin
                maxY += overallY - yMargin
                item.setPos(overallX, overallY)
                overallX += newWidth + xMargin
            
            b.setWidth(maxX)

            maxY = max(maxY, item.rect().height() + yMargin + yMargin)
            b.setHeight(maxY)
            self.setRect(b)

class CSI(QGraphicsPixmapItem):
    """
    Construction Step Image.  Includes border and positional info.
    """

    scale = 1.0

    def __init__(self, step, prevCSI = None):
        QGraphicsPixmapItem.__init__(self, step)

        self.center = QPointF()
        self.width = self.height = 0
        self.oglDispID = UNINIT_OGL_DISPID
        self.partialGLDispID = UNINIT_OGL_DISPID
        self.setFlags(AllFlags)
        
        self.prevCSI = prevCSI
        self.parts = []

    def parent(self):
        return self.parentItem()

    def row(self):
        return 1
    
    def data(self, index = 0):
        return "CSI"

    def addPart(self, part):
        part._parentCSI = self
        self.parts.append(part)

    def __callPreviousOGLDisplayLists(self):

        # Call all previous step's CSI display list
        if self.prevCSI:
            self.prevCSI.__callPreviousOGLDisplayLists()

        # Now call this CSI's display list
        glCallList(self.partialGLDispID)

    def createOGLDisplayList(self):

        # Create a display list for just the parts in this CSI
        self.partialGLDispID = glGenLists(1)
        glNewList(self.partialGLDispID, GL_COMPILE)

        # Draw all the parts in this CSI
        for part in self.parts:
            part.callOGLDisplayList()

        glEndList()

        # Create a display list that includes all previous CSIs plus this one,
        # for a single display list giving a full model rendering up to this step.
        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)
        self.__callPreviousOGLDisplayLists()
        glEndList()

    def updatePixmap(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()
        
        self.createOGLDisplayList()

        pBuffer = QGLPixelBuffer(self.width * CSI.scale, self.height * CSI.scale, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()
        self.initPixmap(pBuffer)
    
    def initLayout(self):

        step = self.parentItem()
        pliHeight = step.pli.rect().height()

        width = self.width * CSI.scale / 2.0
        height = self.height * CSI.scale / 2.0
        x = (step.rect().width() / 2.0) - width

        y = ((step.rect().height() - pliHeight) / 2.0) - height + pliHeight        
        y = max(y, pliHeight + Page.margin.y())

        self.setPos(x, y)

    def initSize(self, size, pBuffer):
        """
        Initialize this CSI's display width, height and center point. To do
        this, draw this CSI to the already initialized GL Frame Buffer Object.
        These dimensions are required to properly lay out PLIs and CSIs.
        Note that an appropriate FBO *must* be initialized before calling initSize.

        Parameters:
            size: Width & height of FBO to render to, in pixels.  Note that FBO is assumed square.

        Returns:
            True if CSI rendered successfully.
            False if the CSI has been rendered partially or wholly out of frame.
        """
        global currentModelFilename

        if self.oglDispID == UNINIT_OGL_DISPID:
            print "Trying to init a CSI size that has no display list"
            return
        
        if len(self.parts) == 0:
            return True  # A CSI with no parts is already initialized

        rawFilename = os.path.splitext(os.path.basename(currentModelFilename))[0]
        pageNumber, stepNumber = self.getPageStepNumberPair()
        filename = "%s_page_%d_step_%d" % (rawFilename, pageNumber, stepNumber)

        params = GLHelpers.initImgSize(size, size, self.oglDispID, True, filename, None, pBuffer)
        if params is None:
            return False

        # TODO: update some kind of load status bar her - this function is *slow*
        print "CSI %s page %d step %d - size %d" % (rawFilename, pageNumber, stepNumber, size)
        self.width, self.height, self.center, x, y = params  # x & y are just ignored placeholders
        return True

    def initPixmap(self, pBuffer):
        """ Requires a current GL Context, either the global one or a local PixelBuffer """

        GLHelpers.initFreshContext()
        w = self.width * CSI.scale
        h = self.height * CSI.scale
        x = self.center.x() * CSI.scale
        y = self.center.y() * CSI.scale
        GLHelpers.adjustGLViewport(0, 0, w, h)
        GLHelpers.rotateToDefaultView(x, y, 0.0, CSI.scale)

        glCallList(self.oglDispID)

        image = pBuffer.toImage()
        self.setPixmap(QPixmap.fromImage(image))
        self.initLayout()

    def createPng(self):

        csiName = "CSI_Page_%d_Step_%d.dat" % self.getPageStepNumberPair()
        datFile = os.path.join(config.config['datPath'], csiName)
        
        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            self.exportToLDrawFile(fh)
            fh.close()
            
        povFile = l3p.createPovFromDat(datFile)
        pngFile = povray.createPngFromPov(povFile, self.width, self.height, self.center, CSI.scale, isPLIItem = False)
        self.pngImage = QImage(pngFile)
        
    def exportToLDrawFile(self, fh):
        if self.prevCSI:
            self.prevCSI.exportToLDrawFile(fh)
            
        for part in self.parts:
            part.exportToLDrawFile(fh)

    def getPrevPageStepNumberPair(self):
        if self.prevCSI:
            return self.prevCSI.getPageStepNumberPair()
        else:
            return (0, 0)
    
    def getPageStepNumberPair(self):
        step = self.parentItem()
        page = step.parentItem()
        return (page.number, step.number)

class PartOGL(object):
    """
    Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
    simple primitive, like stud.dat.  
    Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
    Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
    in common when present in a model, everything inside 3001.dat.
    """

    def __init__(self, filename = None, loadFromFile = False):

        self.name = self.filename = filename
        self.inverted = False  # TODO: Fix this! inverted = GL_CW
        self.invertNext = False
        self.parts = []
        self.primitives = []
        self.oglDispID = UNINIT_OGL_DISPID
        self.isPrimitive = False  # primitive here means any file in 'P'
        self.isSubmodel = False

        self.width = self.height = -1
        self.leftInset = self.bottomInset = -1
        self.center = QPointF()

        if filename and loadFromFile:
            self.loadFromFile()

    def loadFromFile(self):

        ldrawFile = LDrawFile(self.filename)
        self.isPrimitive = ldrawFile.isPrimitive
        self.name = ldrawFile.name

        # Loop over the specified LDraw file array, skipping the first line
        for line in ldrawFile.fileArray[1:]:

            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return

            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):

        if isValidPartLine(line):
            self.addPart(lineToPart(line), line)

        elif isValidTriangleLine(line):
            self.addPrimitive(lineToTriangle(line), GL_TRIANGLES)

        elif isValidQuadLine(line):
            self.addPrimitive(lineToQuad(line), GL_QUADS)

    def addPart(self, p, line, lastStep = None):
        try:
            part = Part(p['filename'], p['color'], p['matrix'], lastStep = lastStep)
        except IOError:
            print "Could not find file: %s - Ignoring." % p['filename']
            return

        self.parts.append(part)
        return part

    def addPrimitive(self, p, shape):
        primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
        self.primitives.append(primitive)

    def createOGLDisplayList(self):
        """ Initialize this part's display list.  Expensive call, but called only once. """
        if self.oglDispID != UNINIT_OGL_DISPID:
            return

        # Ensure any parts in this part have been initialized
        for part in self.parts:
            if part.partOGL.oglDispID == UNINIT_OGL_DISPID:
                part.partOGL.createOGLDisplayList()

        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)

        for part in self.parts:
            part.callOGLDisplayList()

        for primitive in self.primitives:
            primitive.callOGLDisplayList()

        glEndList()

    def draw(self):
        glCallList(self.oglDispID)

    def dimensionsToString(self):
        if self.isPrimitive:
            return ""
        return "%s %d %d %d %d %d %d\n" % (self.filename, self.width, self.height, self.center.x(), self.center.y(), self.leftInset, self.bottomInset)

    def initSize(self, size, pBuffer):
        """
        Initialize this part's display width, height, empty corner insets and center point.
        To do this, draw this part to the already initialized GL buffer.
        These dimensions are required to properly lay out PLIs and CSIs.

        Parameters:
            size: Width & height of GL buffer to render to, in pixels.  Note that buffer is assumed square

        Returns:
            True if part rendered successfully.
            False if the part has been rendered partially or wholly out of frame.
        """

        # TODO: If a part is rendered at a size > 256, draw it smaller in the PLI - this sounds like a great way to know when to shrink a PLI image...
        if self.isPrimitive:
            return True  # Primitive parts need not be sized

        params = GLHelpers.initImgSize(size, size, self.oglDispID, self.isSubmodel, self.filename, None, pBuffer)
        if params is None:
            return False

        # TODO: update some kind of load status bar here - this method is *slow*
        print "%s - size: %d" % (self.filename, size)

        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def getPixmap(self, color = None):
        global GlobalGLContext

        if self.isPrimitive:
            return None  # Do not generate pixmaps for primitives

        w = self.width * PLI.scale
        h = self.height * PLI.scale
        x = self.center.x() * PLI.scale
        y = self.center.y() * PLI.scale

        pBuffer = QGLPixelBuffer(w, h, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()

        GLHelpers.initFreshContext()
        GLHelpers.adjustGLViewport(0, 0, w, h)
        if self.isSubmodel:
            GLHelpers.rotateToDefaultView(x, y, 0.0, PLI.scale)
        else:
            GLHelpers.rotateToPLIView(x, y, 0.0, PLI.scale)

        if color is not None:
            color = LDrawColors.convertToRGBA(color)
            glColor4fv(color)

        self.draw()

        image = pBuffer.toImage()
        #if image:
        #    image.save("C:\\ldraw\\tmp\\buffer_%s.png" % self.filename, None)

        pixmap = QPixmap.fromImage(image)
        GlobalGLContext.makeCurrent()
        return pixmap

class Submodel(PartOGL):
    """ A Submodel is just a PartOGL that also has pages & steps, and can be inserted into a tree. """

    def __init__(self, parent = None, instructions = None, filename = "", lineArray = None):
        PartOGL.__init__(self, filename)
        self.instructions = instructions
        self.lineArray = lineArray
        self.used = False

        self.pages = []
        self.submodels = []
        self.currentStep = None
        self.currentCSI = None
        self.currentPage = None
        self._row = 0
        self._parent = parent
        self.isSubmodel = True
        
    def setSelected(self, selected):
        self.pages[0].setSelected(selected)
        
    def parent(self):
        return self._parent

    def child(self, row):
        for page in self.pages:
            if page._row == row:
                return page
        for submodel in self.submodels:
            if submodel._row == row:
                return submodel
        return None

    def setRow(self, row):
        self._row = row
        
    def row(self):
        return self._row

    def rowCount(self):
        return len(self.pages) + len(self.submodels)
    
    def data(self, index):
        return self.filename

    def importModel(self):
        """ Reads in an LDraw model file and popluates this submodel with the info. """

        global submodelDictionary
        ldrawFile = LDrawFile(self.filename)
        submodelList = ldrawFile.getSubmodels()

        # Add any submodels found in this LDraw file to the submodel dictionary, unused and uninitialized
        if submodelList:
            for submodelFilename, index in submodelList.items():
                lineArray = ldrawFile.fileArray[index[0]: index[1]]
                model = Submodel(self, self.instructions, submodelFilename, lineArray)
                submodelDictionary[submodelFilename] = model

        # Load the contents of this specific LDraw file into this submodel
        self.lineArray = ldrawFile.fileArray
        self.loadFromLineArray()

    def loadFromLineArray(self):
        for line in self.lineArray[1:]:
            if isValidFileLine(line):
                return
            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):
        if isValidStepLine(line):
            self.addStep()
        elif isValidPartLine(line):
            self.addPart(lineToPart(line), line)
        else:
            PartOGL._loadOneLDrawLineCommand(self, line)

    def pageCount(self):
        pageCount = len(self.pages)
        for submodel in self.submodels:
            pageCount += submodel.pageCount()
        return pageCount

    def addStep(self):
        page = self.addPage()
        self.currentStep = Step(page, -1, self.currentCSI)
        self.currentCSI = self.currentStep.csi
        page.addStep(self.currentStep)
        
    def addPage(self):
        page = Page(self, self.instructions)
        if not self.pages and not self.submodels:
            page._row = 0
        else:
            page._row = 1 + max(self.pages[-1]._row if self.pages else 0, self.submodels[-1]._row if self.submodels else 0)
        self.pages.append(page)
        return page
    
    def deleteAllPages(self, scene):
        for page in self.pages:
            scene.removeItem(page)
            del(page)
        for submodel in self.submodels:
            submodel.deleteAllPages(scene)

    def getPage(self, pageNumber):
        for page in self.pages:
            if page.number == pageNumber:
                return page
        for submodel in self.submodels:
            page = submodel.getPage(pageNumber)
            if page:
                return page
        return None

    def selectPage(self, pageNumber):

        pageNumber = max(pageNumber, 1)
        newPage = self.currentPage = None
        
        for page in self.pages:
            if page._number == pageNumber:
                page.show()
                self.currentPage = page
            else:
                page.hide()

        for submodel in self.submodels:
            newPage = submodel.selectPage(pageNumber)
            if newPage:
                self.currentPage = newPage
            
        return self.currentPage

    def addPart(self, p, line):
        lastStep = self.pages[-1].steps[-1].number if self.pages and self.pages[-1].steps else None
        part = PartOGL.addPart(self, p, line, lastStep)
        if self.currentStep is None:
            self.addStep()
        self.currentStep.addPart(part)
        if part.isSubmodel() and not part.partOGL.used:
            p = part.partOGL
            p._parent = self
            p._row = self.pages[-1]._row
            p.used = True
            self.pages[-1]._row += 1
            self.pages[-1].number += p.pageCount()
            self.submodels.append(p)

    def getCSIList(self):
        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)

        for submodel in self.submodels:
            csiList += submodel.getCSIList()

        return csiList

    def initLayout(self):

        if self.pages:
            self.pages[0].addSubmodelImage()

        for page in self.pages:
            page.initLayout()

        for submodel in self.submodels:
            submodel.initLayout()

    def exportImages(self):
        for page in self.pages:
            page.renderFinalImage()

        for submodel in self.submodels:
            submodel.exportImages()

    def createPng(self):

        datFile = os.path.join(config.config['datPath'], self.filename)

        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            for part in self.parts:
                part.exportToLDrawFile(fh)
            fh.close()

        povFile = l3p.createPovFromDat(datFile)
        pngFile = povray.createPngFromPov(povFile, self.width, self.height, self.center, PLI.scale, isPLIItem = False)
        self.pngImage = QImage(pngFile)

class Part(QGraphicsRectItem):
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """

    def __init__(self, filename, color = 16, matrix = None, invert = False, setPartOGL = True, lastStep = None):
        QGraphicsRectItem.__init__(self)
        global partDictionary, submodelDictionary

        self.color = color
        self.matrix = matrix
        self.inverted = invert
        self.filename = filename  # Needed for save / load
        self.partOGL = None
        self._parentPLI = None # Needed because now Parts live in the tree (inside specific PLIItems)
        self._parentCSI = None # Needed to be able to notify CSI to draw this part as selected
        self.setFlags(NoMoveFlags)

        if setPartOGL:
            if filename in submodelDictionary:
                self.partOGL = submodelDictionary[filename]
                if not self.partOGL.used:
                    Step.NextNumber = 1
                    Page.NextNumber -= 1
                    self.partOGL.loadFromLineArray()
                    Step.NextNumber = lastStep
                    Page.NextNumber += 1
            elif filename in partDictionary:
                self.partOGL = partDictionary[filename]
            else:
                self.partOGL = partDictionary[filename] = PartOGL(filename, loadFromFile = True)
            self.name = self.partOGL.name
     
    def parent(self):
        return self._parentPLI

    def row(self):
        return self._parentPLI.parts.index(self) + 1
    
    def data(self, index):
        x, y, z = OGLMatrixToXYZ(self.matrix)
        return "%s  (%.1f, %.1f, %.1f)" % (self.partOGL.filename, x, y, z)

    def setSelected(self, selected):
        if self.isSelected() != selected:
            QGraphicsRectItem.setSelected(self, selected)
            self._parentCSI.updatePixmap()

    def isSubmodel(self):
        return isinstance(self.partOGL, Submodel)

    def callOGLDisplayList(self):

        # must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            if self.isSelected():
                color[3] = 0.5
            glPushAttrib(GL_CURRENT_BIT)
            glColor4fv(color)

        if self.inverted:
            glPushAttrib(GL_POLYGON_BIT)
            glFrontFace(GL_CW)

        if self.matrix:
            glPushMatrix()
            glMultMatrixf(self.matrix)

        glCallList(self.partOGL.oglDispID)

        if self.matrix:
            glPopMatrix()

        if self.inverted:
            glPopAttrib()

        if color != LDrawColors.CurrentColor:
            glPopAttrib()

    def exportToLDrawFile(self, fh):
        line = createPartLine(self.color, self.matrix, self.partOGL.filename)
        fh.write(line + '\n')

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        prevPage = menu.addAction("Move Step to &Previous Page", self.displace)
        menu.exec_(event.globalPos())
        
    def displace(self):
        print "displacing"

class Primitive(object):
    """
    Not a primitive in the LDraw sense, just a single line/triangle/quad.
    Used mainly to construct an OGL display list for a set of points.
    """

    def __init__(self, color, points, type, invert = True):
        self.color = color
        self.type = type
        self.points = points
        self.inverted = invert

    # TODO: using numpy for all this would probably work a lot better
    def addNormal(self, p1, p2, p3):
        Bx = p2[0] - p1[0]
        By = p2[1] - p1[1]
        Bz = p2[2] - p1[2]

        Cx = p3[0] - p1[0]
        Cy = p3[1] - p1[1]
        Cz = p3[2] - p1[2]

        Ax = (By * Cz) - (Bz * Cy)
        Ay = (Bz * Cx) - (Bx * Cz)
        Az = (Bx * Cy) - (By * Cx)
        l = math.sqrt((Ax*Ax)+(Ay*Ay)+(Az*Az))
        if l != 0:
            Ax /= l
            Ay /= l
            Az /= l
        return [Ax, Ay, Az]

    def callOGLDisplayList(self):

        # must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            glColor4fv(color)

        p = self.points

        if self.inverted:
            normal = self.addNormal(p[6:9], p[3:6], p[0:3])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()

            glBegin( self.type )
            glNormal3fv(normal)
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glVertex3f( p[6], p[7], p[8] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[0], p[1], p[2] )
            glEnd()
        else:
            normal = self.addNormal(p[0:3], p[3:6], p[6:9])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()

            glBegin( self.type )
            glNormal3fv(normal)
            glVertex3f( p[0], p[1], p[2] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[6], p[7], p[8] )
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glEnd()

        if color != LDrawColors.CurrentColor:
            glPopAttrib()
