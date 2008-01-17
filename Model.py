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

from LDrawFileFormat import *
from LDrawColors import *

UNINIT_OGL_DISPID = -1
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
GlobalGLContext = None
AllFlags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable

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

QGraphicsSimpleTextItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.parent = genericItemParent
QGraphicsSimpleTextItem.data = genericItemData
QGraphicsPixmapItem.parent = genericItemParent
QGraphicsPixmapItem.data = genericItemData

def printRect(rect, text = ""):
    print text + ", l: %f, r: %f, t: %f, b: %f" % (rect.left(), rect.right(), rect.top(), rect.bottom())

class MoveCommand(QUndoCommand):

    """
    MoveCommand stores a list of parts moved together:
    itemList[0] = (item, item.oldPos, item.newPos)
    """
    
    def __init__(self, itemList):
        QUndoCommand.__init__(self)
        
        self.itemList = []
        for item in itemList:
            self.itemList.append((item, item.oldPos, item.pos()))
    
    def id(self):
        return 123
    
    def undo(self):
        for i in self.itemList:
            item, oldPos, newPos = i
            item.setPos(oldPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()
    
    def redo(self):
        for i in self.itemList:
            item, oldPos, newPos = i
            item.setPos(newPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()
    
#    def mergeWith(self, command):
#        pass
    
class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.connect(self, SIGNAL("clicked(QModelIndex)"), self.clicked)
        
    def updateSelection(self):
        model = self.model()
        scene = model.scene
        selection = self.selectionModel()
        selection.clear()
        
        for item in scene.selectedItems():
            index = model.graphicsItemToModelIndex(item)
            if index:
                selection.select(index, QItemSelectionModel.Select)

    def clicked(self, index = None):
        if not index:
            return

        # Get a list of everything selected in the tree
        selList = self.selectionModel().selectedIndexes()

        # Clear any existing selection
        instructions = self.model()
        instructions.scene.clearSelection()
        
        # Find the selected item's parent page, then flip to that page
        parent = QModelIndex(index)
        while parent.parent().internalPointer():
            parent = parent.parent()
        instructions.selectPage(parent.internalPointer().number)

        # Finally, select the things we actually clicked on
        for item in selList:
            item.internalPointer().setSelected(True)

class Instructions(QAbstractItemModel):

    def __init__(self, parent, scene, glWidget, filename = None):
        QAbstractItemModel.__init__(self, parent)
        global GlobalGLContext

        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"

        # eg: c:\ldraw\lic\models\pyramid.lic 
        self.path = ""       # c:\ldraw\lic\models
        self.filename = ""   # pyramid.lic
        self.modelname = ""  # pyramid
        self.scene = scene
        GlobalGLContext = glWidget
        GlobalGLContext.makeCurrent()

        self.pages = []
        self.currentPage = None
        self.currentStep = None
        self.currentCSI = None

        if filename:
            self.loadModel(filename)

    def data(self, index, role = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()

        if not index.isValid():
            return QVariant(self.modelname)

        item = index.internalPointer()

        return QVariant(item.data(0))

    def rowCount(self, parent):

        if parent.column() > 0:
            return 0

        if not parent.isValid():
            return len(self.pages)

        item = parent.internalPointer()
        if hasattr(item, "childCount"):
            return item.childCount()
        return 0

    def columnCount(self, parentIndex):
        return 1  # Every single item in the tree has exactly 1 column

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index(self, row, column, parent):
        if row < 0 or column < 0:
            return QModelIndex()

        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self

        if not hasattr(parentItem, "child"):
            return QModelIndex()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def child(self, row):
        if row < 0 or row >= len(self.pages):
            return None
        return self.pages[row]

    def childCount(self):
        return len(self.pages)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is self:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def headerData(self, section, orientation, role = Qt.DisplayRole):
        return QVariant("Instruction Book")

    def graphicsItemToModelIndex(self, item):
        if item is self:
            return QModelIndex()
        if hasattr(item, "row"):
            return self.createIndex(item.row(), 0, item)
        else:
            return self.createIndex(0, 0, item)
    
    def loadModel(self, filename):
        self.emit(SIGNAL("layoutAboutToBeChanged"))
        self.path = os.path.dirname(filename)
        self.filename = os.path.basename(filename)
        self.modelname = os.path.splitext(self.filename)[0]
        self.importModel(filename)
        self.initDraw()  # generate all part GL display lists on the general glWidget
        self.pages[-1].hide()
        self.pages[0].show()
        self.emit(SIGNAL("layoutChanged()"))

    def clear(self):
        global partDictionary
        self.emit(SIGNAL("layoutAboutToBeChanged"))
        self.currentPage = self.currentStep = self.currentCSI = None
        self.filename = self.path = self.modelname = ""
        for page in self.pages:
            item = self.scene.removeItem(page)
            del(item)
        self.pages = []
        partDictionary = {}
        Page.NextNumber = 1
        Step.NextNumber = 1
        GlobalGLContext.makeCurrent()
        self.emit(SIGNAL("layoutChanged()"))

    def addPage(self, page):

        self.pages.append(page)
        self.selectPage(page.number)

    def selectPage(self, pageNumber):
        for page in self.pages:
            page.hide()
        self.currentPage = self.pages[pageNumber - 1]
        self.currentPage.show()
        self.scene.clearSelection()

    def importModel(self, filename):
        """ Reads in an LDraw model file and popluates this instruction book with the info. """

        ldrawFile = LDrawFile(filename)

        # Loop over the specified LDraw file array, skipping the first line
        for line in ldrawFile.fileArray[1:]:

            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return

            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):

        if isValidStepLine(line):
            self.addStep()
        elif isValidPartLine(line):
            self.addPart(lineToPart(line))

    def addStep(self):
        
        # For now, this implicitly adds a new page for each new step
        page = Page(self)
        self.addPage(page)
        self.currentStep = Step(page, -1, self.currentCSI)
        self.currentCSI = self.currentStep.csi
        page.steps.append(self.currentStep)

    def addPart(self, p):
        try:
            part = Part(p['filename'], p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return

        if not self.currentStep:
            self.addStep()
        self.currentStep.addPart(part)

    def initDraw(self):

        # First initialize all GL display lists
        for part in partDictionary.values():
            part.createOGLDisplayList()

        # Calculate the width and height of each partOGL in the part dictionary
        self.initPartDimensionsManually()

        # Calculate the width and height of each CSI in this instruction book
        self.initCSIDimensions()

        # Layout each step on each page.  
        # TODO: This should only happen if we're importing a new model.  Otherwise, layout should be pulled from load / save binary blob
        for page in self.pages:
            for step in page.steps:
                step.initLayout()

    def initPartDimensionsManually(self):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        global GlobalGLContext

        partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]

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
#        print ""
#        if lines:
#            f = open(self.partDimensionsFilename, 'a')
#            f.writelines(lines)
#            f.close()

    def initCSIDimensions(self):
        global GlobalGLContext

        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)

        if csiList == []:
            return  # All CSIs initialized - nothing to do here

        GlobalGLContext.makeCurrent()
        for csi in csiList:
            csi.createOGLDisplayList()

        csiList2 = []
        sizes = [512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels

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

        # Initialize each CSI's pixmap, for display in the gui
        for csi in csiList:
            pBuffer = QGLPixelBuffer(csi.width, csi.height, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()
            csi.initPixmap(pBuffer)
            
        GlobalGLContext.makeCurrent()

    def getPartDictionary(self):
        global partDictionary
        return partDictionary

class Page(QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """

    NextNumber = 1
    margin = QPointF(15, 15)

    def __init__(self, instructions, number = -1):
        QGraphicsRectItem.__init__(self, None, instructions.scene)

        # Position this rectangle inset from the containing scene
        self.setPos(0, 0)
        self.setRect(instructions.scene.sceneRect())

        self.instructions = instructions
        self.steps = []

        # Give this page a number
        if number == -1:
            self.number = Page.NextNumber
            Page.NextNumber += 1
        else:
            self.number = number
            Page.NextNumber = number + 1

        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.dataText = "Page Number Label"

        # Position page number in bottom right page corner
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.margin)
        self.numberItem.setPos(rect.topLeft())
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
        self.numberItem.setFlags(AllFlags)

    def parent(self):
        return self.instructions

    def child(self, row):
        if row < 0 or row > len(self.steps):
            return None
        if row == 0:
            return self.numberItem
        return self.steps[row - 1]

    def childCount(self):
        return len(self.steps) + 1 # + 1 for the page number label

    def row(self):
        return self.number - 1

    def data(self, index):
        return "Page %d" % self.number

    def getAllChildItems(self):
        items = [self]
        items.append(self.numberItem)
        
        for step in self.steps:
            items.append(step)
            items.append(step.numberItem)
            items.append(step.pli)
            for pliItem in step.pli.pliItems:
                items.append(pliItem)
                items.append(pliItem.numberItem)
                
        return items
    
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
                painter.drawImage(step.csi.pos(), step.csi.pngImage)
            else:
                print "Error: Trying to draw a csi that was not exported to png: page %d step %d" % step.csi.getPageStepNumberPair()
                
            for item in step.pli.pliItems:
                if hasattr(item, "pngImage"):
                    painter.drawImage(item.scenePos(), item.pngImage)
                else:
                    print "Error: Trying to draw a pliItem that was not exported to png: step %d, item %s" % (step.number, item.filename)
                
        painter.end()
        
        imgName = os.path.join(config.config['imgPath'], "Page_%d.png" % self.number)
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

        # Draw a (debug) rect around the page number label
        #rect = self.numberItem.boundingRect()
        #rect.translate(self.numberItem.pos())
        #painter.drawRect(rect)

class Step(QGraphicsRectItem):
    """ A single step in an instruction book.  Contains one optional PLI and exactly one CSI. """

    NextNumber = 1
    mousePressEvent = genericMousePressEvent(QGraphicsRectItem)
    mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsRectItem)

    def __init__(self, parentPage, number = -1, prevCSI = None):
        QGraphicsRectItem.__init__(self, parentPage)

        pen = self.pen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)

        self.page = parentPage  # TODO: remove this and use parentItem()
        self.setPos(parentPage.rect().topLeft() + parentPage.margin)

        # Give this page a number
        if number == -1:
            self.number = Step.NextNumber
            Step.NextNumber += 1
        else:
            self.number = number
            Step.NextNumber = number + 1

        # Initialize Step's number label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setPos(0, 0)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.setFlags(AllFlags)
        self.numberItem.dataText = "Step Number Label"
        self.setFlags(AllFlags)

        self.pli = PLI(self)
        self.csi = CSI(self, prevCSI)

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

    def childCount(self):
        return 3

    def row(self):
        page = self.parentItem()
        return page.steps.index(self) + 1  # + 1 for page number label

    def data(self, index):
        return "Step %d" % self.number

    def addPart(self, part):
        self.csi.parts.append(part)
        if self.pli:
            self.pli.addPart(part)

    def resetRect(self):
        self.setRect(self.childrenBoundingRect())
        
    def initLayout(self):

        print "initializing step: %d" % self.number
        self.pli.initLayout()
        self.csi.initLayout()

        # Position the Step number label beneath the PLI
        self.numberItem.setPos(0, 0)
        self.numberItem.moveBy(0, self.pli.rect().height() + Page.margin.y() + 0.5)

        self.resetRect()

class PLIItem(QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """

    mousePressEvent = genericMousePressEvent(QGraphicsRectItem)
    mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsRectItem)
    
    def __init__(self, parent, partOGL, color):
        QGraphicsRectItem.__init__(self, parent)

        self.partOGL = partOGL
        self.filename = partOGL.filename
        self.color = color
        self._count = 1
        pen = self.pen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)

        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem("x%d" % self._count, self)
        self.numberItem.setFont(QFont("Arial", 10))
        self.numberItem.dataText = "Qty. Label (x%d)" % self._count

        self.pixmapItem = QGraphicsPixmapItem(self)
        self.pixmapItem.dataText = "Image"

        self.setPos(parent.margin)
        self.setFlags(AllFlags)
        self.numberItem.setFlags(AllFlags)

    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row == 0:
            return self.numberItem
        return None

    def childCount(self):
        return 1

    def row(self):
        pli = self.parentItem()
        return pli.pliItems.index(self)

    def data(self, index):
        return "%s - %s" % (self.partOGL.name, getColorName(self.color))

    def resetRect(self):
        self.setRect(self.childrenBoundingRect())
        self.parentItem().resetRect()
        
    def initLayout(self):

        part = self.partOGL
        lblHeight = self.numberItem.boundingRect().height() / 2.0

        # Position quantity label based on part corner, empty corner triangle and label's size
        if part.leftInset == part.bottomInset == 0:
            dx = -3   # Bottom left triangle is full - shift just a little, for a touch more padding
        else:
            slope = part.leftInset / float(part.bottomInset)
            dx = ((part.leftInset - lblHeight) / slope) - 3  # 3 for a touch more padding

        self.numberItem.setPos(dx, part.height - lblHeight)

        pixmap = part.getPixmap(self.color)
        if pixmap:
            self.pixmapItem.setPixmap(pixmap)

        # Place qty label above the item image
        self.numberItem.setZValue(self.pixmapItem.zValue() + 1)

        # Set this item to the union of its image and qty label rects
        pixmapRect = self.pixmapItem.boundingRect().translated(self.pixmapItem.pos())
        numberRect = self.numberItem.boundingRect().translated(self.numberItem.pos())
        self.setRect(pixmapRect | numberRect)

    def _setCount(self, count):
        self._count = count
        self.numberItem.setText("x%d" % self._count)
        self.numberItem.dataText = "Qty. Label (x%d)" % self._count

    def _getCount(self):
        return self._count

    count = property(fget = _getCount, fset = _setCount)
    
    def createPng(self):
    
        datFile = os.path.join(config.LDrawPath, 'PARTS', self.filename)
        if not os.path.isfile(datFile):
            datFile = os.path.join(config.LDrawPath, 'P', self.filename)
            if not os.path.isfile(datFile):
                datFile = os.path.join(config.LDrawPath, 'MODELS', self.filename)
                if not os.path.isfile(datFile):
                    print "Error: could not find dat file for part %s" % self.filename
                    return

        povFile = l3p.createPovFromDat(datFile, self.color)
        self.pngFile = povray.createPngFromPov(povFile, self.partOGL.width, self.partOGL.height, self.partOGL.center, True)
        self.pngImage = QImage(self.pngFile)

class PLI(QGraphicsRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """

    margin = QPointF(15, 15)
    mousePressEvent = genericMousePressEvent(QGraphicsRectItem)
    mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsRectItem)

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

    def childCount(self):
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

        found = False
        for item in self.pliItems:
            if item.color == part.color and item.filename == part.partOGL.filename:
                item.count += 1
                found = True
                break
        if not found:
            item = PLIItem(self, part.partOGL, part.color)
            item.setParentItem(self)
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

        # Return the height of the part in the specified layout item
        def itemHeight(layoutItem):
            return layoutItem.partOGL.height

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
        tallestPart = max(partList, key=itemHeight)
        partList.remove(tallestPart)
        partList.sort(compareLayoutItemWidths)
        partList.insert(0, tallestPart)

        # This rect will be enlarged as needed
        b = self.rect()
        b.setSize(QSizeF(-1, -1))

        overallX = xMargin = PLI.margin.x()
        yMargin = PLI.margin.y()

        for i, item in enumerate(partList):

            # Move this PLIItem to its new position
            item.setPos(overallX, yMargin)

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
                    y = prevCorner.y + b.internalGap + item.rect().height()
                    item.setPos(x, y)

            # Increase overall x, box width and box height to make PLI box big enough for this part
            overallX += newWidth + xMargin
            b.setWidth(round(overallX))

            newHeight = item.rect().height() + yMargin + yMargin
            b.setHeight(round(max(b.height(), newHeight)))
            self.setRect(b)

class CSI(QGraphicsPixmapItem):
    """
    Construction Step Image.  Includes border and positional info.
    """

    mousePressEvent = genericMousePressEvent(QGraphicsPixmapItem)
    mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsPixmapItem)

    def __init__(self, step, prevCSI = None):
        QGraphicsPixmapItem.__init__(self, step)

        self.center = QPointF()
        self.width = self.height = UNINIT_OGL_DISPID
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

    def callPreviousOGLDisplayLists(self):

        # Call all previous step's CSI display list
        if self.prevCSI:
            self.prevCSI.callPreviousOGLDisplayLists()

        # Now call this CSI's display list
        glCallList(self.partialGLDispID)

    def createOGLDisplayList(self):

        # Create a display list for just the parts in this CSI
        self.partialGLDispID = glGenLists(1)
        glNewList(self.partialGLDispID, GL_COMPILE)

        for part in self.parts:
            part.callOGLDisplayList()

        glEndList()

        # Create a display list that includes all previous CSIs plus this one,
        # for a single display list giving a full model rendering up to this step.
        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)
        self.callPreviousOGLDisplayLists()
        glEndList()

    def initLayout(self):
        step = self.parentItem()
        x = (step.page.rect().width() / 2.0) - (self.width / 2.0)
        pliBottom = step.pli.rect().bottom() + step.pli.pos().y()
        y = pliBottom + ((step.page.rect().height() - pliBottom) / 2.0) - (self.height / 2.0)
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

        if self.oglDispID == UNINIT_OGL_DISPID:
            print "Trying to init a CSI size that has no display list"
            return

        rawFilename = self.parentItem().page.instructions.modelname
        filename = "%s_step_%d" % (rawFilename, self.parentItem().number)

        params = GLHelpers.initImgSize(size, size, self.oglDispID, True, filename, None, pBuffer)
        if params is None:
            return False

        # TODO: update some kind of load status bar her - this function is *slow*
        print "CSI %s step %d - size %d" % (filename, self.parentItem().number, size)
        self.width, self.height, self.center, x, y = params
        return True

    def initPixmap(self, pBuffer):

        GLHelpers.initFreshContext()
        GLHelpers.adjustGLViewport(0, 0, self.width, self.height)
        GLHelpers.rotateToDefaultView(self.center.x(), self.center.y(), 0.0)

        glCallList(self.oglDispID)

        image = pBuffer.toImage()
        self.setPixmap(QPixmap.fromImage(image))

    def createPng(self):
                
        csiName = "CSI_Page_%d_Step_%d.dat" % self.getPageStepNumberPair()
        datFile = os.path.join(config.config['datPath'], csiName)
        
        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            self.exportToLDrawFile(fh)
            fh.close()
            
        povFile = l3p.createPovFromDat(datFile)
        self.pngFile = povray.createPngFromPov(povFile, self.width, self.height, self.center, False)
        self.pngImage = QImage(self.pngFile)
        
    def exportToLDrawFile(self, fh):
        if self.prevCSI:
            self.prevCSI.exportToLDrawFile(fh)
            
        for part in self.parts:
            part.exportToLDrawFile(fh)

    def getPrevPageStepNumberPair(self):
        if self.prevCSI:
            prevStep = self.prevCSI.parentItem()
            prevStepNumber = prevStep.number
            prevPageNumber = prevStep.parentItem().number
        else:
            prevPageNumber = prevStepNumber = 0
        return (prevPageNumber, prevStepNumber)
    
    def getPageStepNumberPair(self):
        pn, sn = self.getPrevPageStepNumberPair()
        pn += 1
        sn += 1
        return (pn, sn)
        
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

    def addPart(self, p, line):
        try:
            part = Part(p['filename'], p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return

        self.parts.append(part)

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
        # TODO: Check how many pieces would be rendered successfully at 128 - if significant, test adding that to size list, see if it speeds part generation up
        if self.isPrimitive:
            return True  # Primitive parts need not be sized

        params = GLHelpers.initImgSize(size, size, self.oglDispID, False, self.filename, None, pBuffer)
        if params is None:
            return False

        # TODO: update some kind of load status bar here - this function is *slow*
        print self.filename + " - size: %d" % (size)

        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def getPixmap(self, color = 0):
        global GlobalGLContext

        if self.isPrimitive:
            return None  # Do not generate pixmaps for primitives

        pBuffer = QGLPixelBuffer(self.width, self.height, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()

        GLHelpers.initFreshContext()
        GLHelpers.adjustGLViewport(0, 0, self.width, self.height)
        GLHelpers.rotateToPLIView(self.center.x(), self.center.y(), 0.0)

        color = convertToRGBA(color)
        if len(color) == 3:
            glColor3fv(color)
        elif len(color) == 4:
            glColor4fv(color)

        self.draw()

        image = pBuffer.toImage()
        #if image:
        #    image.save("C:\\ldraw\\tmp\\buffer_%s.png" % self.filename, None)

        pixmap = QPixmap.fromImage(image)
        GlobalGLContext.makeCurrent()
        return pixmap

class Part:
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """

    def __init__(self, filename, color = 16, matrix = None, invert = False, setPartOGL = True):

        self.filename = filename
        self.color = color
        self.matrix = matrix
        self.inverted = invert

        if setPartOGL:
            if filename in partDictionary:
                self.partOGL = partDictionary[filename]
            else:
                self.partOGL = partDictionary[filename] = PartOGL(filename, loadFromFile = True)        
            self.name = self.partOGL.name

    def callOGLDisplayList(self):

        # must be called inside a glNewList/EndList pair
        color = convertToRGBA(self.color)

        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
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

        if color != CurrentColor:
            glPopAttrib()

    def draw(self):
        self.partOGL.draw()

    def exportToLDrawFile(self, fh):
        line = createPartLine(self.color, self.matrix, self.filename)
        fh.write(line + '\n')

class Primitive:
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
        color = convertToRGBA(self.color)

        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
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

        if color != CurrentColor:
            glPopAttrib()
