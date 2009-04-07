import math   # for sqrt
import os     # for output path creation

from OpenGL import GL
from OpenGL import GLU

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from LicUndoActions import *
import GLHelpers
import l3p
import povray
import LDrawColors
import Helpers
import Layout

from LDrawFileFormat import *

MagicNumber = 0x14768126
FileVersion = 1

PageSize = QSize(800, 600)

UNINIT_GL_DISPID = -1
partDictionary = {}      # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
submodelDictionary = {}  # {'filename': Submodel()}
currentModelFilename = ""

GlobalGLContext = None
AllFlags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable
NoMoveFlags = QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.connect(self, SIGNAL("clicked(QModelIndex)"), self.clicked)

    """
    def keyReleaseEvent(self, event):
        #TODO: This is totally broken, and doesn't make sense: arrow keys in tree should move selection.
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
    """
        
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
        partList = []
        for index in selList:
            item = index.internalPointer()
            if isinstance(item, Part):
                partList.append(item)
            else:
                item.setSelected(True)
                
        # Optimization: don't just select each parts, because selecting a part forces it's CSI to redraw.
        # Instead, only redraw the CSI once, on the last part update
        if partList:
            for part in partList[:-1]:
                part.setSelected(True, False)
            partList[-1].setSelected(True, True)

class Instructions(QAbstractItemModel):

    def __init__(self, parent, scene, glWidget, filename = None):
        QAbstractItemModel.__init__(self, parent)
        global GlobalGLContext

        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"

        self.scene = scene
        self.mainModel = None

        GlobalGLContext = glWidget
        GlobalGLContext.makeCurrent()

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
        self.emit(SIGNAL("layoutAboutToBeChanged()"))

        # Remove everything from the graphics scene
        if self.mainModel:
            self.mainModel.deleteAllPages(self.scene)

        self.reset()
        self.scene.clear()
        self.mainModel = None
        partDictionary = {}
        submodelDictionary = {}
        currentModelFilename = ""
        CSI.scale = PLI.scale = 1.0
        GlobalGLContext.makeCurrent()
        self.emit(SIGNAL("layoutChanged()"))

    def clearSelectedParts(self):
        partList = []
        for item in self.scene.selectedItems():
            if isinstance(item, Part):
                partList.append(item)
        if partList:
            for part in partList[:-1]:
                part.setSelected(False, False)
            partList[-1].setSelected(False, True)

    def loadModel(self, filename):
        
        global currentModelFilename        
        currentModelFilename = filename
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.mainModel = Submodel(self, self, filename)
        self.mainModel.importModel()
        
        self.mainModel.syncPageNumbers()
        self.mainModel.addInitialPagesAndSteps()
        
        pageCount = self.mainModel.pageCount()
        totalCount = (pageCount * 2) + 2
        currentCount = 1
        yield (totalCount, "Initializing GL display lists")

        self.initGLDisplayLists()  # generate all part GL display lists on the general glWidget
        yield (currentCount, "Initializing Part Dimensions")
        
        for step, label in self.initPartDimensions(currentCount):  # Calculate width and height of each partOGL in the part dictionary
            currentCount = step
            yield (step, label)

        for step, label in self.initCSIDimensions(currentCount):   # Calculate width and height of each CSI in this instruction book
            currentCount = step
            yield (step, label)
            
        self.initCSIPixmaps()       # Generate a pixmap for each CSI

        for step, label in self.mainModel.initLayout(currentCount):
            yield (step, label)
            
        self.mainModel.selectPage(1)
        self.emit(SIGNAL("layoutChanged()"))
        yield (totalCount, "Import Complete!")

    def initGLDisplayLists(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()
        
        # First initialize all partOGL display lists
        for part in partDictionary.values():
            if part.oglDispID == UNINIT_GL_DISPID:
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

    def initPartDimensions(self, currentCount):
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

        partDivCount = 50
        partCount = int(len(partList) / partDivCount)
        currentPartCount = 0

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render each image and calculate their sizes
            for partOGL in partList:

                if partOGL.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    lines.append(partOGL.dimensionsToString())
                    currentPartCount += 1
                    if not currentPartCount % partDivCount:
                        currentPartCount = 0
                        currentCount += 1
                        yield (currentCount, "Initializing more Part Dimensions")
                else:
                    partList2.append(partOGL)

            if len(partList2) < 1:
                break  # All images initialized successfully
            else:
                partList = partList2  # Some images rendered out of frame - loop and try bigger frame
                partList2 = []

        # Append any newly calculated part dimensions to cache file
        # TODO: fix part cache file
        """
        print ""
        if lines:
            f = open(self.partDimensionsFilename, 'a')
            f.writelines(lines)
            f.close()
        """

    def initCSIDimensions(self, currentCount):
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

            # Render each CSI and calculate its size
            for csi in csiList:
                pBuffer.makeCurrent()
                result = csi.initSize(size, pBuffer)
                if not result:
                        csiList2.append(csi)
                else:
                    currentCount += 1
                    yield (currentCount, result)

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
        
        for csi in csiList:
            if csi.width < 1 or csi.height < 1:
                continue
            pBuffer = QGLPixelBuffer(csi.width * CSI.scale, csi.height * CSI.scale, QGLFormat(), GlobalGLContext)
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
        self.selectPage(0)

    def selectLastPage(self):
        self.selectPage(self.mainModel.pages[-1]._number)

    def selectPage(self, pageNumber):
        if self.mainModel:
            self.mainModel.selectPage(pageNumber)
            self.mainModel.currentPage.setSelected(True)
        
    def updatePageNumbers(self, newNumber, increment = 1):
        if self.mainModel:
            self.mainModel.updatePageNumbers(newNumber, increment)

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
    """ A single page in an instruction book.  Contains one or more Steps. _parent is a Submodel. """

    margin = QPointF(15, 15)

    def __init__(self, parent, instructions, number, row):
        QGraphicsRectItem.__init__(self)
        instructions.scene.addItem(self)

        # Position this rectangle inset from the containing scene
        self.setPos(0, 0)
        self.setRect(instructions.scene.sceneRect())

        self.instructions = instructions
        self._parent = parent
        self._number = number
        self._row = row
        self.steps = []
        self.separators = []
        self.children = []
        self.submodelItem = None
        self.layout = Layout.GridLayout(orientation = Layout.Horizontal)

        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.dataText = "Page Number Label"
        self.children.append(self.numberItem)

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
            if step.pli:
                items.append(step.pli)
                for pliItem in step.pli.pliItems:
                    items.append(pliItem)
                    items.append(pliItem.numberItem)

        for separator in self.separators:
            items.append(separator)

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
        
    def getStep(self, number):
        return self._parent.getStep(number)

    def addStep(self, step):

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

    def getNextStepNumber(self):

        if self.steps:
            return self.steps[-1].number + 1
        
        for page in self._parent.pages[self._row + 1 : ]:  # Look forward through pages
            if page.steps:
                return page.steps[0].number

        for page in reversed(self._parent.pages[ : self._row]):  # Look back
            if page.steps:
                return page.steps[-1].number + 1

        return 1
        
    def addBlankStep(self):
        self.insertStep(Step(self, self.getNextStepNumber()))
    
    def insertStep(self, step):
        self._parent.updateStepNumbers(step.number)
        self.addStep(step)

    def deleteStep(self, step):

        self.steps.remove(step)
        self.children.remove(step)
        self.scene().removeItem(step)
        self._parent.updateStepNumbers(step.number, -1)

    def addChild(self, index, child):

        self.children.insert(index, child)

        # Adjust the z-order of all children: first child has highest z value
        for i, item in enumerate(self.children):
            item.setZValue(len(self.children) - i)

    def addStepSeparator(self, index):

        border = QGraphicsRectItem(self)
        border.setRect(QRectF(0, 0, 1, 1))
        border.setFlags(AllFlags)
        border.dataText = "Step Separator"
        self.separators.append(border)
        self.addChild(index, border)
        return border

    def addAllSeparators(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        
        stepCount = len(self.steps)
        colCount = int(math.ceil(math.sqrt(stepCount)))
        rowCount = stepCount / colCount  # This needs to be integer division
        
        if stepCount % colCount:
            rowCount += 1
            
        separatorIndices = []
        for i, step in enumerate(self.steps):
            if (i > 0) and (not i % rowCount):
                separatorIndices.append(step.row())
        
        my = Page.margin.y()
        pageRect = self.rect()
        if self.submodelItem:
            pageRect.setTop(self.submodelItem.rect().height() + my + my)
        stepWidth = pageRect.width() / colCount
        
        for i in range(1, colCount):
            index = separatorIndices[i - 1]
            sep = self.addStepSeparator(index)
            sep.setPos(stepWidth * i, pageRect.top() + my)
            sep.setRect(QRectF(0, 0, 1, pageRect.height() - my - my))
            
        self.scene().emit(SIGNAL("layoutChanged()"))
    
    def removeAllSeparators(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        for separator in self.separators:
            self.children.remove(separator)
            self.scene().removeItem(separator)
        del self.separators[:]
        self.scene().emit(SIGNAL("layoutChanged()"))
    
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

        # Remove any separators, since we'll re-add them in the appropriate place later
        self.removeAllSeparators()

        pageRect = self.rect()
        mx = Page.margin.x()
        my = Page.margin.y()
        
        # Allocate space for the submodel image, if any
        if self.submodelItem:
            self.submodelItem.setPos(Page.margin)
            self.submodelItem.rect().setTopLeft(Page.margin)
            pageRect.setTop(self.submodelItem.rect().height() + my + my)

        label = "Initializing Page: %d" % self._number
        if len(self.steps) <= 0:
            return label # No steps - nothing more to do here

        self.layout.initGridLayout(pageRect, self.steps)
        
        if len(self.steps) < 2:
            return label # if there's only one step, no step separators needed

        # Add a step separator between each column of steps
        self.addAllSeparators()
        return label

    def scaleImages(self):
        for step in self.steps:
            if step.pli:
                step.pli.initLayout()
            
        if self.submodelItem:
            self.resetSubmodelImage()
        
    def renderFinalImage(self):

        for step in self.steps:
            step.csi.createPng()
            if step.pli:
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
                
            if step.pli:
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
        menu.addAction("Prepend blank Page", self.addPageBeforeSignal)
        menu.addAction("Append blank Page", self.addPageAfterSignal)
        menu.addSeparator()
        if self.separators:
            menu.addAction("Remove Step Separators", self.removeAllSeparators)
        else:
            menu.addAction("Add Step Separators", self.addAllSeparators)
        menu.addAction("Add blank Step", self.addBlankStepSignal)
        menu.addSeparator()
        menu.addAction("Delete Page", self.deletePageSignal)
        menu.exec_(event.screenPos())
    
    def addBlankStepSignal(self):
        step = Step(self, self.getNextStepNumber())
        self.scene().undoStack.push(AddRemoveStepCommand(step, True))

    def deletePageSignal(self):
        if self.steps: #Do not allow pages with steps to be deleted
            QMessageBox.warning(self.scene().views()[0], "Page Delete Error", "Cannot delete a Page that contains Steps.\nRemove or move Steps to a different page first.")
        else:
            self.scene().undoStack.push(AddRemovePageCommand(self, False))
        
    def addPageBeforeSignal(self):
        newPage = Page(self._parent, self.instructions, self.number, self._row)
        self.scene().undoStack.push(AddRemovePageCommand(newPage, True))
    
    def addPageAfterSignal(self):
        newPage = Page(self._parent, self.instructions, self.number + 1, self._row + 1)
        self.scene().undoStack.push(AddRemovePageCommand(newPage, True))

class Callout(QGraphicsRectItem):

    margin = QPointF(15, 15)

    def __init__(self, parent, number = 1, showStepNumbers = False):
        QGraphicsRectItem.__init__(self, parent)

        self.steps = []
        self.number = number
        self.showStepNumbers = showStepNumbers
        self.layout = Layout.GridLayout()
        
        self.setPos(0.0, 0.0)
        self.setRect(0.0, 0.0, 30.0, 30.0)
        self.setPen(QPen(Qt.black))
        self.setFlags(AllFlags)
        
    def child(self, row):
        if row < 0 or row >= len(self.steps):
            return None
        return self.steps[row]

    def rowCount(self):
        return len(self.steps)

    def getChildRow(self, child):
        if child in self.steps:
            return self.steps.index(child)

    def data(self, index):
        return "Callout %d - %d step%s" % (self.number, len(self.steps), 's' if len(self.steps) > 1 else '')

    def addBlankStep(self, useUndo = True):
        lastNum = self.steps[-1].number + 1 if self.steps else 1
        if lastNum > 1 and not self.showStepNumbers:
            self.toggleStepNumbers()
        step = Step(self, lastNum, False, self.showStepNumbers)
        if useUndo:
            self.scene().undoStack.push(AddRemoveStepCommand(step, True))
        else:
            self.insertStep(step)
        
    def insertStep(self, step):
        self.steps.append(step)
        step.setParentItem(self)

    def deleteStep(self, step):
        self.steps.remove(step)
        self.scene().removeItem(step)

    def addPart(self, part):
        self.steps[-1].addPart(part)

    def removePart(self, part):
        for step in self.steps:
            step.removePart(part)
        
    def resetRect(self):
        b = self.childrenBoundingRect()
        b.adjust(0.0, 0.0, Page.margin.x() * 2, Page.margin.y() * 2)
        self.setRect(0.0, 0.0, b.width(), b.height())
        
    def initLayout(self):

        if not self.steps:
            self.setRect(0.0, 0.0, 1.0, 1.0)
            return  # Nothing to layout here
        
        for step in self.steps:
            step.initMinimumLayout()
            
        self.layout.rowCount = self.layout.colCount = -1
        self.layout.initLayoutInsideOut(self.steps)

        self.resetRect()
        self.parentItem().initLayout()

    def toggleStepNumbers(self):
        for step in self.steps:
            step.toggleNumberItem()
        self.showStepNumbers = not self.showStepNumbers
        self.initLayout()
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add blank Step", self.addBlankStep)
        menu.addAction("%s Step numbers" % ("Hide" if self.showStepNumbers else "Show"), self.toggleStepNumbers)
        menu.exec_(event.screenPos())

    def getStep(self, number):
        for step in self.steps:
            if step.number == number:
                return step
        return None

class Step(QGraphicsRectItem):
    """ A single step in an Instruction book.  Contains one optional PLI and exactly one CSI. """

    def __init__(self, parentPage, number, hasPLI = True, hasNumberItem = True):
        QGraphicsRectItem.__init__(self, parentPage)

        # Children
        self._number = number
        self.numberItem = None
        self.csi = CSI(self)
        self.pli = PLI(self) if hasPLI else None
        self.callouts = []
        
        self.maxRect = None

        pen = self.pen()
        pen.setStyle(Qt.NoPen)
        self.setPen(pen)

        self.setPos(Page.margin)

        if hasNumberItem:
            self.toggleNumberItem()

        self.setFlags(AllFlags)

    def _setNumber(self, number):
        self._number = number
        if self.numberItem:
            self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(fget = _getNumber, fset = _setNumber)

    def child(self, row):
        if row == 0:
            return self.csi
        if row == 1:
            if self.pli:
                return self.pli
            if self.numberItem:
                return self.numberItem
        if row == 2:
            if self.numberItem:
                return self.numberItem

        offset = row - 1 - (1 if self.pli else 0) - (1 if self.numberItem else 0)
        if offset < len(self.callouts):
                return self.callouts[offset]

        return None

    def rowCount(self):
        return 1 + (1 if self.pli else 0) + (1 if self.numberItem else 0) + len(self.callouts)

    def data(self, index):
        return "Step %d" % self._number

    def getChildRow(self, child):
        if isinstance(child, CSI):
            return 0
        if isinstance(child, PLI):
            return 1
        if isinstance(child, QGraphicsSimpleTextItem):
            return 2 if self.pli else 1
        if child in self.callouts:
            return self.callouts.index(child) + 1 + (1 if self.pli else 0) + (1 if self.numberItem else 0)
        
    def addPart(self, part):
        self.csi.addPart(part)
        if self.pli:
            self.pli.addPart(part)

    def removePart(self, part):
        self.csi.removePart(part)
        if self.pli:
            self.pli.removePart(part)

    def addCallout(self, callout):
        callout.setParentItem(self)
        self.callouts.append(callout)
    
    def removeCallout(self, callout):
        self.callouts.remove(callout)
        self.scene().removeItem(callout)
    
    def resetRect(self):
        if self.maxRect:
            r = QRectF(0.0, 0.0, max(1, self.maxRect.width()), max(1, self.maxRect.height()))
        else:
            r = QRectF(0.0, 0.0, 1.0, 1.0)
        self.setRect(r | self.childrenBoundingRect())

        if hasattr(self.parentItem(), "resetRect"):
            self.parentItem().resetRect()

    def getNextStep(self):
        return self.parentItem().getStep(self.number + 1)

    def getPrevStep(self):
        return self.parentItem().getStep(self.number - 1)

    def toggleNumberItem(self):
        if self.numberItem:
            self.scene().removeItem(self.numberItem)
            self.numberItem = None
        else:
            self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
            self.numberItem.setPos(0, 0)
            self.numberItem.setFont(QFont("Arial", 15))
            self.numberItem.setFlags(AllFlags)
            self.numberItem.dataText = "Step Number Label"
        
    def initMinimumLayout(self):

        if self.pli: # Do not use on a step with PLI
            return

        if self.numberItem:
            self.numberItem.setPos(0.0, 0.0)
            self.csi.setPos(self.numberItem.boundingRect().bottomRight())
        else:
            self.csi.setPos(0.0, 0.0)

        self.setPos(0.0, 0.0)
        self.maxRect = QRectF()
        self.resetRect()
        self.maxRect = self.rect()

    def initLayout(self, destRect = None):

        if destRect:
            self.maxRect = destRect
        else:
            destRect = self.maxRect

        self.setPos(destRect.topLeft())
        self.setRect(0, 0, destRect.width(), destRect.height())
        
        if self.pli:
            self.pli.initLayout()  # Position PLI

        # Position Step number label beneath the PLI
        if self.numberItem:
            self.numberItem.setPos(0, 0)
            pliOffset = self.pli.rect().height() if self.pli else 0.0
            self.numberItem.moveBy(0, pliOffset + Page.margin.y() + 0.5)

        self.positionInternalBits()

    def positionInternalBits(self):

        r = self.rect()
        
        if self.pli:
            r.setTop(self.pli.rect().height())

        csiWidth = self.csi.width * CSI.scale
        csiHeight = self.csi.height * CSI.scale

        if not self.callouts:
            
            x = (r.width() - csiWidth) / 2.0
            y = (r.height() - csiHeight) / 2.0
            self.csi.setPos(x, r.top() + y)
            return

        cr = self.callouts[0].rect()
        remainingWidth = r.width() - cr.width() - csiWidth 
        remainingHeight = r.height() - cr.height() - csiHeight
        
        placeRight = remainingWidth > remainingHeight
        
        if placeRight:
            csiWidth += cr.width() + Page.margin.x()
        else:
            csiHeight += cr.height() + Page.margin.y()

        x = (r.width() - csiWidth) / 2.0
        y = (r.height() - csiHeight) / 2.0
        self.csi.setPos(x, r.top() + y)
        
        if placeRight:
            cx = x + csiWidth - cr.width()
            cy = (r.height() - cr.height()) / 2.0
        else:
            cx = (r.width() - cr.width()) / 2.0
            cy = y + csiHeight - cr.height()
            
        self.callouts[0].setPos(cx, r.top() + cy)

    def contextMenuEvent(self, event):

        selectedSteps = []
        for item in self.scene().selectedItems():
            if isinstance(item, Step):
                selectedSteps.append(item)

        menu = QMenu(self.scene().views()[0])
        undo = self.scene().undoStack
        parent = self.parentItem()

        if parent.prevPage():
            menu.addAction("Move to &Previous Page" % plural, self.moveToPrevPage)
            if parent.prevPage().steps:
                menu.addAction("Merge with Previous Step" % plural, self.mergeWithPrevStep)
        if parent.nextPage():
            menu.addAction("Move to &Next Page" % plural, self.moveToNextPage)
            if parent.nextPage().steps:
                menu.addAction("Merge with Next Step" % plural, self.mergeWithNextStep)
            
        menu.addSeparator()
        menu.addAction("Add blank Callout", self.addBlankCalloutSignal)
        menu.addSeparator()
        doLayout = menu.addAction("Re-layout affected Pages")
        doLayout.setCheckable(True)
        doLayout.setChecked(True)

        if not self.csi.parts:
            menu.addAction("&Delete Step", lambda: undo.push(AddRemoveStepCommand(self, False)))

        menu.exec_(event.screenPos())

    def addBlankCalloutSignal(self):
        number = self.callouts[-1].number + 1 if self.callouts else 1
        callout = Callout(self, number)
        callout.addBlankStep(False)
        self.scene().undoStack.push(AddRemoveCalloutCommand(callout, True))
    
    def moveToPrevPage(self):
        stepSet = []
        for step in self.scene().selectedItems():
            if isinstance(step, Step):
                stepSet.append((step, step.parentItem(), step.parentItem().prevPage()))
        step.scene().emit(SIGNAL("moveStepToNewPage"), stepSet)
        
    def moveToNextPage(self):
        stepSet = []
        for step in self.scene().selectedItems():
            if isinstance(step, Step):
                stepSet.append((step, step.parentItem(), step.parentItem().nextPage()))
        step.scene().emit(SIGNAL("moveStepToNewPage"), stepSet)
    
    def moveToPage(self, page):
        
        page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.parentItem().removeStep(self)
        page.addStep(self)
        page.instructions.emit(SIGNAL("layoutChanged()"))

    def mergeWithPrevStep(self):
        print "Merging Step %d with previous Step - NYI" % self._number

    def mergeWithNextStep(self, args = None):
        print "Merging Step %d with next Step - NYI" % self._number

class PLIItem(QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """

    def __init__(self, parent, partOGL, color, quantity = 0):
        QGraphicsRectItem.__init__(self, parent)

        self.partOGL = partOGL
        self.quantity = 0
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
        self.numberItem.setFlags(AllFlags)        
        self.setQuantity(quantity)

    def setQuantity(self, quantity):
        self.quantity = quantity
        self.numberItem.setText("%dx" % self.quantity)
        self.numberItem.dataText = "Qty. Label (%dx)" % self.quantity
        
    def addPart(self):
        self.setQuantity(self.quantity + 1)

    def removePart(self):
        self.quantity -= 1
        if self.quantity > 0:
            # Still have other parts - reduce qty label
            self.numberItem.setText("%dx" % self.quantity)
            self.numberItem.dataText = "Qty. Label (%dx)" % self.quantity
        else:
            # PLIItem is now empty - kill it
            self.parentItem().pliItems.remove(self)
            self.scene().removeItem(self)

    def child(self, row):
        return self.numberItem if row == 0 else None

    def rowCount(self):
        return 1

    def row(self):
        return self.parentItem().pliItems.index(self)

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
        if not self.pixmapItem.boundingRect().width():
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

    """        
    def paint(self, painter, option, widget = None):
        rect = self.boundingRect()
        painter.drawRect(rect)
        QGraphicsRectItem.paint(self, painter, option, widget)
    """

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

        self.pliItems = []  # {(part filename, color): PLIItem instance}

        self.dataText = "PLI"  # String displayed in Tree - reimplement data(self, index) to override
        self._row = 1
        
        self.setPos(0, 0)
        self.setPen(QPen(Qt.black))
        self.setFlags(AllFlags)

    def child(self, row):
        if row < 0 or row >= len(self.pliItems):
            print "ERROR: Looking up invalid row in PLI Tree"
            return None
        return self.pliItems[row] 

    def rowCount(self):
        return len(self.pliItems)

    def isEmpty(self):
        return True if len(self.pliItems) == 0 else False

    def resetRect(self):
        rect = self.childrenBoundingRect().adjusted(-PLI.margin.x(), -PLI.margin.y(), PLI.margin.x(), PLI.margin.y())
        self.setRect(rect)
        self.parentItem().resetRect()
        
    def addPart(self, part):

        for pliItem in self.pliItems:
            if pliItem.color == part.color and pliItem.partOGL.filename == part.partOGL.filename:
                return pliItem.addPart()

        # If we're here, did not find an existing PLI, so create a new one
        pliItem = PLIItem(self, part.partOGL, part.color)
        pliItem.addPart()
        self.pliItems.append(pliItem)
        
    def removePart(self, part):
        
        for pliItem in self.pliItems:
            if pliItem.color == part.color and pliItem.partOGL.filename == part.partOGL.filename:
                return pliItem.removePart()

    def initLayout(self):
        """
        Allocate space for all parts in this PLI, and choose a decent layout.
        This is the initial algorithm used to layout a PLI.
        """

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            self.setRect(QRectF())
            return

        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for i, item in enumerate(self.pliItems):
            item.initLayout()
            #print "{node [width=%f, height=%f] n%d}" % (item.rect().width() / 100.0, item.rect().height() / 100.0, i)
            
        nodes = range(0, len(self.pliItems))
        while nodes:
            x = nodes.pop()
            s = ""
            for i in nodes:
                s += "n%d--n%d;" % (x, i)
            #print s 
            
        # Sort list of parts to lay out by width (narrowest first), then remove tallest part, to be added first
        partList = list(self.pliItems)
        partList.sort(lambda x, y: cmp(x.rect().width(), y.rect().width()))
        tallestPart = max(partList, key = lambda x: x.partOGL.height)
        partList.remove(tallestPart)
        partList.append(tallestPart)

        # This rect will be enlarged as needed
        pliBox = QRectF(0, 0, -1, -1)

        overallX = maxX = xMargin = PLI.margin.x()
        overallY = maxY = yMargin = PLI.margin.y()

        prevItem = None
        remainingHeight = 0.0
        
        while partList:
            
            item = None
            
            if prevItem:
                remainingHeight = pliBox.height() - prevItem.pos().y() - prevItem.rect().height() - yMargin - yMargin 
                
            # Check if we can fit any parts under the last part without extending the PLI box vertically
            if remainingHeight > 0:
                for pliItem in partList:
                    if pliItem.rect().height() < remainingHeight:
                        item = pliItem
                        break

            # Found an item that fits below the previous - put it there
            if item:
                partList.remove(pliItem)
                overallX = prevItem.pos().x()
                newWidth = prevItem.rect().width()
                y = prevItem.pos().y() + prevItem.rect().height() + yMargin
                item.setPos(overallX, y)
            
            # Use last item in list (widest)
            if not item:
                item = partList.pop()
                item.setPos(overallX, overallY)
                newWidth = item.rect().width()

            # Increase overall x, to make PLI box big enough for this part
            overallX += newWidth + xMargin
 
            # If this part pushes this PLI beyond the step's right edge, wrap to new line           
            if overallX > self.parentItem().rect().width():
                overallX = xMargin
                overallY = pliBox.height()
                item.setPos(overallX, overallY)
                overallX += newWidth + xMargin
            
            maxX = max(maxX, overallX)
            maxY = max(maxY, overallY + item.rect().height() + yMargin)
            pliBox.setWidth(maxX)
            pliBox.setHeight(maxY)
            self.setRect(pliBox)
            prevItem = item

class CSI(QGraphicsPixmapItem):
    """
    Construction Step Image.  Includes border and positional info.
    """

    scale = 1.0

    def __init__(self, step):
        QGraphicsPixmapItem.__init__(self, step)

        self.center = QPointF()
        self.width = self.height = 0
        self.oglDispID = UNINIT_GL_DISPID
        self.setFlags(AllFlags)

        self.dataText = "CSI"  # String displayed in Tree - reimplement data(self, index) to override
        self._row = 0
        
        self.parts = []
        self.arrows = []

    def child(self, row):
        if row < 0 or row >= len(self.parts):
            return None
        return self.parts[row]

    def rowCount(self):
        return len(self.parts)

    def getPartList(self):
        partList = []
        for partItem in self.parts:
            partList += partItem.parts
        return partList
    
    def partCount(self):
        partCount = 0
        for partItem in self.parts:
            partCount += len(partItem.parts)
        return partCount
    
    def data(self, index):
        return "CSI - %d parts" % self.partCount()

    def addPart(self, part):
        for p in self.parts:
            if p.name == part.partOGL.name:
                p.addPart(part)
                return
            
        p = PartTreeItem(self, part.partOGL.name)
        p.addPart(part)
        self.parts.append(p)
        self.parts.sort(key = lambda partItem: partItem.name)

    def removePart(self, part):
        target = None
        for p in self.parts:
            if part in p.parts:
                target = p
        if target:
            target.parts.remove(part)
            if not target.parts:
                self.parts.remove(target)

    def addArrow(self, arrow):
        self.addPart(arrow)
        self.arrows.append(arrow)
        
    def removeArrow(self, arrow):
        self.removePart(arrow)
        self.scene().removeItem(arrow)
        self.arrows.remove(arrow)
    
    def __callPreviousOGLDisplayLists(self, isCurrent = False):

        # Call all previous step's CSI display list
        prevStep = self.parentItem().getPrevStep()
        if prevStep:
            prevStep.csi.__callPreviousOGLDisplayLists(False)

        # Draw all the parts in this CSI
        for partItem in self.parts:
            for part in partItem.parts:
                part.callGLDisplayList(isCurrent)

    def createOGLDisplayList(self):
        """
        Create a display list that includes all previous CSIs plus this one,
        for a single display list giving a full model rendering up to this step.
        """

        # If we've already created a list here; free it first
        if self.oglDispID != UNINIT_GL_DISPID:
            GL.glDeleteLists(self.oglDispID, 1)
            
        self.oglDispID = GL.glGenLists(1)
        GL.glNewList(self.oglDispID, GL.GL_COMPILE)
        self.__callPreviousOGLDisplayLists(True)
        GL.glEndList()

    def calculateGLSize(self):
        # TODO: If the pixmap & FBO solution gets too slow, try a pure GL solution (see project.py)
        minX, minY = 150, 150
        maxX, maxY = 0, 0
        
        for partItem in self.parts:
            for part in partItem.parts:
                for v in part.vertexIterator():
                    res = GLU.gluProject(v[0], v[1], v[2])
                    maxX = max(res[0], maxX)
                    maxY = max(res[1], maxY)
                
                    minX = min(res[0], minX)
                    minY = min(res[1], minY)
                
        print "x min: %f, max: %f" % (minX, maxX)
        print "y min: %f, max: %f" % (minY, maxY)
        
        aX, aY, aZ = GLU.gluUnProject(minX, minY, 0.0)
        bX, bY, bZ = GLU.gluUnProject(minX, maxY, 0.0)
        cX, cY, cZ = GLU.gluUnProject(maxX, maxY, 0.0)
        dX, dY, dZ = GLU.gluUnProject(maxX, minY, 0.0)
    
    def updatePixmap(self, rebuildDisplayList = True):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()

        if rebuildDisplayList or self.oglDispID == UNINIT_GL_DISPID:
            self.createOGLDisplayList()

        pBuffer = QGLPixelBuffer(self.width * CSI.scale, self.height * CSI.scale, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()
        self.initPixmap(pBuffer)
        GlobalGLContext.makeCurrent()
    
    def maximizePixmap(self):

        dx = (PageSize.width() - self.width) / 2.0
        dy = (PageSize.height() - self.height) / 2.0

        self.width = PageSize.width()
        self.height = PageSize.height()

        # Move pixmap to compensate for new size, so we don't actually move the CSI itself
        self.translate(-dx, -dy)

    def resetPixmap(self, reposition = True):
        global GlobalGLContext
        
        if not self.parts:
            self.center = QPointF()
            self.width = self.height = 0
            self.oglDispID = UNINIT_GL_DISPID
            self.setPixmap(QPixmap())
            return  # No parts = reset pixmap
        
        # First, enlarge this CSI as much as possible, in case 
        # recent changes pushed image out of existing bounds.
        self.maximizePixmap()
        
        GlobalGLContext.makeCurrent()
        self.createOGLDisplayList()
        sizes = [512, 1024, 2048]

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            if self.initSize(size, pBuffer):
                break

        self.resetTransform()
        self.updatePixmap(False)
        if reposition:
            self.parentItem().positionInternalBits()
        GlobalGLContext.makeCurrent()

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

        if self.oglDispID == UNINIT_GL_DISPID:
            print "ERROR: Trying to init a CSI size that has no display list"
            return False
        
        rawFilename = os.path.splitext(os.path.basename(currentModelFilename))[0]
        pageNumber, stepNumber = self.getPageStepNumberPair()
        filename = "%s_page_%d_step_%d" % (rawFilename, pageNumber, stepNumber)

        result = "Initializing CSI Page %d Step %d" % (pageNumber, stepNumber)
        if not self.parts:
            return result  # A CSI with no parts is already initialized

        params = GLHelpers.initImgSize(size, size, self.oglDispID, True, filename, None, pBuffer)
        if params is None:
            return False

        self.width, self.height, self.center, x, y = params  # x & y are just ignored place-holders
        return result

    def initPixmap(self, pBuffer):
        """ Requires a current GL Context, either the global one or a local PixelBuffer """

        GLHelpers.initFreshContext()
        w = self.width * CSI.scale
        h = self.height * CSI.scale
        x = self.center.x() * CSI.scale
        y = self.center.y() * CSI.scale
        GLHelpers.adjustGLViewport(0, 0, w, h)
        GLHelpers.rotateToDefaultView(x, y, 0.0, CSI.scale)

        GL.glCallList(self.oglDispID)

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
        pngFile = povray.createPngFromPov(povFile, self.width, self.height, self.center, CSI.scale, isPLIItem = False)
        self.pngImage = QImage(pngFile)
        
    def exportToLDrawFile(self, fh):
        prevStep = self.parentItem().getPrevStep()
        if prevStep:
            prevStep.csi.exportToLDrawFile(fh)
            
        for partItem in self.parts:
            for part in partItem.parts:
                part.exportToLDrawFile(fh)

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
        self.inverted = False  # TODO: Fix this! inverted = GL.GL_CW
        self.invertNext = False
        self.parts = []
        self.primitives = []
        self.oglDispID = UNINIT_GL_DISPID
        self.isPrimitive = False  # primitive here means any file in 'P'
        self.isSubmodel = False
        self.__boundingBox = None

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
            self.addPartFromLine(lineToPart(line), line)

        elif isValidTriangleLine(line):
            self.addPrimitive(lineToTriangle(line), GL.GL_TRIANGLES)

        elif isValidQuadLine(line):
            self.addPrimitive(lineToQuad(line), GL.GL_QUADS)

    def addPartFromLine(self, p, line):
        try:
            part = Part(p['filename'], p['color'], p['matrix'], False, True)
        except IOError:
            print "Could not find file: %s - Ignoring." % p['filename']
            return

        self.parts.append(part)
        return part

    def addPrimitive(self, p, shape):
        primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
        self.primitives.append(primitive)

    def vertexIterator(self):
        for primitive in self.primitives:
            for vertex in primitive.vertexIterator():
                yield vertex
        for part in self.parts:
            for vertex in part.vertexIterator():
                yield vertex

    def createOGLDisplayList(self):
        """ Initialize this part's display list."""

        if self.oglDispID != UNINIT_GL_DISPID:
            GL.glDeleteLists(self.oglDispID, 1)

        # Ensure any parts in this part have been initialized
        for part in self.parts:
            if part.partOGL.oglDispID == UNINIT_GL_DISPID:
                part.partOGL.createOGLDisplayList()

        self.oglDispID = GL.glGenLists(1)
        GL.glNewList(self.oglDispID, GL.GL_COMPILE)

        for part in self.parts:
            part.callGLDisplayList()

        for primitive in self.primitives:
            primitive.callGLDisplayList()

        GL.glEndList()

    def draw(self):
        GL.glCallList(self.oglDispID)

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
            GL.glColor4fv(color)

        self.draw()

        image = pBuffer.toImage()
        #if image:
        #    image.save("C:\\ldraw\\tmp\\buffer_%s.png" % self.filename, None)

        pixmap = QPixmap.fromImage(image)
        GlobalGLContext.makeCurrent()
        return pixmap
    
    def getBoundingBox(self):
        if self.__boundingBox:
            return self.__boundingBox
        
        box = None
        for primitive in self.primitives:
            p = primitive.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p)
                else:
                    box = p
            
        for part in self.parts:
            p = part.partOGL.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p)
                else:
                    box = p

        # TODO: There's a lot of completely empty partOGLs hanging around - parts
        # with nothing but (currently) useless edges - remove them?  Do something?
        self.__boundingBox = box
        return box

    def resetBoundingBox(self):
        self.__boundingBox = None
        for primitive in self.primitives:
            primitive.resetBoundingBox()
        for part in self.parts:
            part.partOGL.resetBoundingBox()

class BoundingBox(object):
    
    def __init__(self, x = 0.0, y = 0.0, z = 0.0):
        self.x1 = self.x2 = x
        self.y1 = self.y2 = y
        self.z1 = self.z2 = z

    def growByPoints(self, x, y, z):
        self.x1 = min(x, self.x1)
        self.x2 = max(x, self.x2)
        self.y1 = min(y, self.y1)
        self.y2 = max(y, self.y2)
        self.z1 = min(z, self.z1)
        self.z2 = max(z, self.z2)
        
    def growByBoudingBox(self, box):
        self.growByPoints(box.x1, box.y1, box.z1)
        self.growByPoints(box.x2, box.y2, box.z2)

class Submodel(PartOGL):
    """ A Submodel is just a PartOGL that also has pages & steps, and can be inserted into a tree. """

    def __init__(self, parent = None, instructions = None, filename = "", lineArray = None):
        PartOGL.__init__(self, filename)

        self.instructions = instructions
        self.lineArray = lineArray
        self.used = False

        self.pages = []
        self.submodels = []
        
        self._row = 0
        self._parent = parent
        self.isSubmodel = True
        self.currentPage = None # Track the currently selected page in this model
        
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
        """ Reads in an LDraw model file and populates this submodel with the info. """

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
            if isValidPartLine(line):
                self.addPartFromLine(lineToPart(line), line)

    def addInitialPagesAndSteps(self):

        # Add one step for every 5 parts, and one page per step
        # At this point, if model had no steps (assumed for now), we have one page per submodel
        PARTS_PER_STEP_MAX = 5
        
        for submodel in self.submodels:
            submodel.addInitialPagesAndSteps()

        csi  = self.pages[0].steps[0].csi
        while csi.partCount() > PARTS_PER_STEP_MAX:
            
            newPage = Page(self, self.instructions, self.pages[-1]._number + 1, self.pages[-1]._row + 1)
            newPage.addBlankStep()
            self.addPage(newPage)

            partList = csi.getPartList()
            partList.sort(key = lambda x: x.getXYZSortOrder())
            
            for part in partList[PARTS_PER_STEP_MAX : ]:
                part.getStep().removePart(part)
                newPage.steps[-1].addPart(part)
            csi = newPage.steps[-1].csi
    
    def syncPageNumbers(self, firstPageNumber = 1):

        rowList = self.pages + self.submodels
        rowList.sort(key = lambda x: x._row)

        pageNumber = firstPageNumber
        for row in rowList:
            if isinstance(row, Page):
                row.number = pageNumber
                pageNumber += 1
            elif isinstance(row, Submodel):
                pageNumber = row.syncPageNumbers(pageNumber)

        return pageNumber
    
    def pageCount(self):
        pageCount = len(self.pages)
        for submodel in self.submodels:
            pageCount += submodel.pageCount()
        return pageCount

    def appendBlankPage(self):

        if not self.pages and not self.submodels:
            row = 0
        else:
            row = 1 + max(self.pages[-1]._row if self.pages else 0, self.submodels[-1]._row if self.submodels else 0)
            
        page = Page(self, self.instructions, -1, row)
        for p in self.pages[page._row : ]:
            p._row += 1
        self.pages.insert(page._row, page)
        return page
    
    def addPage(self, page):
        
        for p in self.pages[page._row : ]:
            p._row += 1

        page._parent = self
        if page not in self.instructions.scene.items():
            self.instructions.scene.addItem(page)
        
        self.instructions.updatePageNumbers(page.number)
        self.pages.insert(page._row, page)

    def deletePage(self, page):

        for p in self.pages[page._row + 1 : ]:
            p._row -= 1

        page.scene().removeItem(page)
        self.pages.remove(page)
        self.instructions.updatePageNumbers(page.number, -1)
        
    def updateStepNumbers(self, newNumber, increment = 1):
        for p in self.pages:
            for s in p.steps:
                if s.number >= newNumber:
                    s.number += increment

    def updatePageNumbers(self, newNumber, increment = 1):
        
        for p in self.pages:
            if p.number >= newNumber:
                p.number += increment
                
        for submodel in self.submodels:
            submodel.updatePageNumbers(newNumber, increment)
        
    def deleteAllPages(self, scene):
        for page in self.pages:
            scene.removeItem(page)
            del(page)
        for submodel in self.submodels:
            submodel.deleteAllPages(scene)

    def getStep(self, stepNumber):
        for page in self.pages:
            for step in page.steps:
                if step.number == stepNumber:
                    return step
                
        for submodel in self.submodels:
            step = submodel.getStep(stepNumber)
            if step:
                return step
        return None

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

    def addPartFromLine(self, p, line):
        
        # First ensure we have a step in this submodel, so we can add the new part to it.
        if not self.pages:
            newPage = self.appendBlankPage()
            newPage.addBlankStep()

        part = PartOGL.addPartFromLine(self, p, line)
        if not part:
            return  # Error loading part - part .dat file may not exist
        
        self.pages[-1].steps[-1].addPart(part)
        if part.isSubmodel() and not part.partOGL.used:
            p = part.partOGL
            p._parent = self
            p._row = self.pages[-1]._row
            p.used = True
            self.pages[-1]._row += 1
            self.submodels.append(p)

    def getCSIList(self):
        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)

        for submodel in self.submodels:
            csiList += submodel.getCSIList()

        return csiList

    def getPageList(self):
        pageList = list(self.pages)
        for submodel in self.submodels:
            pageList += submodel.getPageList()
        return pageList
        
    def initLayout(self, currentCount):

        if self.pages:
            self.pages[0].addSubmodelImage()

        pageList = self.getPageList()
        pageList.sort(key = lambda x: x._number)
        
        for page in pageList:
            label = page.initLayout()
            currentCount += 1
            yield (currentCount, label)

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

class PartTreeItem(QGraphicsRectItem):

    def __init__(self, parent, name):
        QGraphicsPixmapItem.__init__(self, parent)
        self.name = name
        self.parts = []
        self.setFlags(AllFlags)
        
    def child(self, row):
        if row < 0 or row >= len(self.parts):
            return None
        return self.parts[row]

    def row(self):
        return self.parentItem().parts.index(self)

    def rowCount(self):
        return len(self.parts)
    
    def data(self, index):
        return "%s - x%d" % (self.name, len(self.parts))
    
    def addPart(self, part):
        part.setParentItem(self)
        self.parts.append(part)

class Part(QGraphicsRectItem):
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """

    def __init__(self, filename, color = 16, matrix = None, invert = False, setPartOGL = True):
        QGraphicsRectItem.__init__(self)
        global partDictionary, submodelDictionary

        self.color = color
        self.matrix = matrix
        self.inverted = invert
        self.filename = filename  # Needed for save / load
        self.partOGL = None

        self.displacement = []
        self.displaceDirection = None

        self.setFlags(NoMoveFlags)

        if setPartOGL:
            if filename in submodelDictionary:
                self.partOGL = submodelDictionary[filename]
                if not self.partOGL.used:
                    self.partOGL.loadFromLineArray()
            elif filename in partDictionary:
                self.partOGL = partDictionary[filename]
            else:
                self.partOGL = partDictionary[filename] = PartOGL(filename, loadFromFile = True)

    def row(self):
        return self.parentItem().parts.index(self)
    
    def data(self, index):
        x, y, z = OGLMatrixToXYZ(self.matrix)
        color = LDrawColors.getColorName(self.color)
        return "%s - (%.1f, %.1f, %.1f)" % (color, x, y, z)

    def getXYZSortOrder(self):
        x, y, z = OGLMatrixToXYZ(self.matrix)
        return (-y, -z, x)

    def csi(self):
        return self.parentItem().parentItem()
    
    def setSelected(self, selected, updatePixmap = True):
        QGraphicsRectItem.setSelected(self, selected)
        if updatePixmap:
            self.csi().updatePixmap()

    def getStep(self):
        return self.csi().parentItem()

    def isSubmodel(self):
        return isinstance(self.partOGL, Submodel)

    def vertexIterator(self, useDisplacement = False):
        if self.matrix:
            matrix = list(self.matrix)
            if useDisplacement and self.displacement:
                matrix[12] += self.displacement[0]
                matrix[13] += self.displacement[1]
                matrix[14] += self.displacement[2]
            GL.glPushMatrix()
            GL.glMultMatrixf(matrix)
            
        for vertex in self.partOGL.vertexIterator():
            yield vertex

        if self.matrix:
            GL.glPopMatrix()
    
    def callGLDisplayList(self, useDisplacement = False):

        # must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            if self.isSelected():
                color[3] = 0.5
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        if self.inverted:
            GL.glPushAttrib(GL.GL_POLYGON_BIT)
            GL.glFrontFace(GL.GL_CW)

        if self.matrix:
            matrix = list(self.matrix)
            if useDisplacement and self.displacement:
                matrix[12] += self.displacement[0]
                matrix[13] += self.displacement[1]
                matrix[14] += self.displacement[2]
            GL.glPushMatrix()
            GL.glMultMatrixf(matrix)

        if self.isSelected():
            self.drawGLBoundingBox()

        GL.glCallList(self.partOGL.oglDispID)

        if self.matrix:
            GL.glPopMatrix()

        if self.inverted:
            GL.glPopAttrib()

        if color != LDrawColors.CurrentColor:
            GL.glPopAttrib()

    def drawGLBoundingBox(self):
        b = self.partOGL.getBoundingBox()
        GL.glBegin(GL.GL_LINE_LOOP)
        GL.glVertex3f(b.x1, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y2, b.z1)
        GL.glVertex3f(b.x1, b.y2, b.z1)
        GL.glEnd()

        GL.glBegin(GL.GL_LINE_LOOP)
        GL.glVertex3f(b.x1, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y2, b.z2)
        GL.glVertex3f(b.x1, b.y2, b.z2)
        GL.glEnd()

        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(b.x1, b.y1, b.z1)
        GL.glVertex3f(b.x1, b.y1, b.z2)
        GL.glVertex3f(b.x1, b.y2, b.z1)
        GL.glVertex3f(b.x1, b.y2, b.z2)
        GL.glVertex3f(b.x2, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y2, b.z1)
        GL.glVertex3f(b.x2, b.y2, b.z2)
        GL.glEnd()

    def exportToLDrawFile(self, fh):
        line = createPartLine(self.color, self.matrix, self.partOGL.filename)
        fh.write(line + '\n')

    def duplicate(self):
        p = Part(self.filename, self.color, self.matrix, self.inverted, False)
        p.partOGL = self.partOGL
        p.setParentItem(self.parentItem())
        p.displacement = list(self.displacement)
        p.displaceDirection = self.displaceDirection
        return p

    def createCallout(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        step = self.getStep()
        step.addBlankCalloutSignal()
        callout = step.callouts[-1]

        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                callout.addPart(item.duplicate())
        callout.steps[0].csi.resetPixmap()
        callout.initLayout()
        self.scene().emit(SIGNAL("layoutChanged()"))
        
    def contextMenuEvent(self, event):
        """ 
        This is called if any part is the target of a right click.  
        self is guaranteed to be selected.  Other stuff may be selected too, so deal.
        """

        step = self.getStep()
        menu = QMenu(self.scene().views()[0])

        menu.addAction("Create Callout from Parts", self.createCallout)

        if step.callouts:
            arrowMenu = menu.addMenu("Move Part to Callout")
            for callout in step.callouts:
                arrowMenu.addAction("Callout %d" % callout.number, lambda x = callout: self.moveToCallout(x))
        
        menu.addSeparator()
        
        needSeparator = False
        if step.getPrevStep():
            menu.addAction("Move to &Previous Step", self.moveToPrevStep)
            needSeparator = True
            
        if step.getNextStep():
            menu.addAction("Move to &Next Step", self.moveToNextStep)
            needSeparator = True

        if needSeparator:
            menu.addSeparator()

        if self.displacement:
            menu.addAction("&Increase displacement", self.increaseDisplacement)
            menu.addAction("&Decrease displacement", self.decreaseDisplacement)
        else:
            s = self.scene()
            arrowMenu = menu.addMenu("Displace With &Arrow")
            arrowMenu.addAction("Move Up", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_PageUp, Arrow(Qt.Key_PageUp))))
            arrowMenu.addAction("Move Down", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_PageDown, Arrow(Qt.Key_PageDown))))
            arrowMenu.addAction("Move Forward", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_Down, Arrow(Qt.Key_Down))))
            arrowMenu.addAction("Move Back", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_Up, Arrow(Qt.Key_Up))))
            arrowMenu.addAction("Move Left", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_Left, Arrow(Qt.Key_Left))))
            arrowMenu.addAction("Move Right", lambda: s.emit(SIGNAL("beginDisplacement"), (self, Qt.Key_Right, Arrow(Qt.Key_Right))))

        menu.exec_(event.screenPos())

    def moveToCallout(self, callout):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                selectedParts.append(item.duplicate())
        action = AddPartsToCalloutCommand((selectedParts, callout))
        self.scene().undoStack.push(action)
    
    def startDisplacement(self, direction):
        self.displaceDirection = direction
        self.displacement = self.getDisplacementOffset(direction)
        self.arrow.setPosition(*OGLMatrixToXYZ(self.matrix))
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.csi().addArrow(self.arrow)
        self.scene().emit(SIGNAL("layoutChanged()"))
        self.csi().resetPixmap()
    
    def stopDisplacement(self):
        self.displaceDirection = None
        self.displacement = []
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.csi().removeArrow(self.arrow)
        self.scene().emit(SIGNAL("layoutChanged()"))
        self.csi().resetPixmap()
    
    def increaseDisplacement(self):
        self.displace(self.displaceDirection)
    
    def decreaseDisplacement(self):
        self.displace(Helpers.getOppositeDirection(self.displaceDirection))
        
    def keyReleaseEvent(self, event):
        direction = event.key()
        if direction == Qt.Key_Plus:
            return self.increaseDisplacement()
        if direction == Qt.Key_Minus:
            return self.decreaseDisplacement()
        self.displace(direction)

    def getDisplacementOffset(self, direction):
        offset = 20
        displacement = [0.0, 0.0, 0.0]

        if direction == Qt.Key_Up:
            displacement[0] -= offset
        elif direction == Qt.Key_Down:
            displacement[0] += offset
        elif direction == Qt.Key_PageUp:
            displacement[1] -= offset
        elif direction == Qt.Key_PageDown:
            displacement[1] += offset
        elif direction == Qt.Key_Left:
            displacement[2] -= offset
        elif direction == Qt.Key_Right:
            displacement[2] += offset
        else:
            return None

        return displacement
        
    def displace(self, direction):
        displacement = self.getDisplacementOffset(direction)
        if displacement:
            oldPos = self.displacement if self.displacement else [0.0, 0.0, 0.0]
            newPos = [oldPos[0] + displacement[0], oldPos[1] + displacement[1], oldPos[2] + displacement[2]]
            self.scene().emit(SIGNAL("displacePart"), (self, oldPos, newPos))

    def moveToPrevStep(self):
        self.moveToStep(self.getStep().getPrevStep())

    def moveToNextStep(self):
        self.moveToStep(self.getStep().getNextStep())
        
    def moveToStep(self, destStep):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                selectedParts.append(item)

        self.scene().undoStack.push(MovePartsToStepCommand((selectedParts, self.getStep(), destStep)))
        
class Arrow(Part):

    def __init__(self, direction):
        Part.__init__(self, "arrow", 4, None, False, False)
        self.partOGL = PartOGL("arrow")
        
        self.matrix = IdentityMatrix()

        x = [0.0, 20.0, 25.0, 50.0]
        y = [-5.0, -1.0, 0.0, 1.0, 5.0]

        self.tip = [x[0], y[2], 0.0]
        topEnd = [x[2], y[0], 0.0]
        botEnd = [x[2], y[4], 0.0]
        joint = [x[1], y[2], 0.0]
        
        tl = [x[1], y[1], 0.0]
        tr = [x[3], y[1], 0.0]
        br = [x[3], y[3], 0.0]
        bl = [x[1], y[3], 0.0]
        
        tip1 = Primitive(4, self.tip + topEnd + joint, GL.GL_TRIANGLES, invert = False)
        tip2 = Primitive(4, self.tip + joint + botEnd, GL.GL_TRIANGLES, invert = False)
        base = Primitive(4, tl + tr + br + bl, GL.GL_QUADS, invert = False)

        self.partOGL.primitives.append(tip1)
        self.partOGL.primitives.append(tip2)
        self.partOGL.primitives.append(base)
   
        self.displacement = [0.0, 0.0, 0.0]
        self.displaceDirection = direction
        self.partOGL.createOGLDisplayList()

    def data(self, index):
        x, y, z = OGLMatrixToXYZ(self.matrix)
        return "%s  (%.1f, %.1f, %.1f)" % (self.partOGL.filename, x, y, z)

    def setPosition(self, x, y, z):
        self.matrix[12] = x
        self.matrix[13] = y
        self.matrix[14] = z
        
    def getRotation(self):
        
        d = self.displaceDirection
        if d == Qt.Key_PageUp:
            return [1.0, 0.0, -1.0]
        elif d == Qt.Key_PageDown:
            return [-1.0, 0.0, 1.0]

        elif d == Qt.Key_Left:
            return [1.0, 1.0, 0.0]
        elif d == Qt.Key_Right:
            return [-1.0, -1.0, 0.0]

        elif d == Qt.Key_Up:
            return [1.0, 1.0, 1.0]
        elif d == Qt.Key_Down:
            return [-1.0, 0.0, 0.0]

    def callGLDisplayList(self, useDisplacement = False):

        # Must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            if self.isSelected():
                color[3] = 0.5
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        matrix = list(self.matrix)
        if useDisplacement and self.displacement:
            matrix[12] += self.displacement[0]
            matrix[13] += self.displacement[1]
            matrix[14] += self.displacement[2]
        GL.glPushMatrix()
        GL.glMultMatrixf(matrix)
        
        r = self.getRotation()
        if r[1] and r[2]:
            GL.glRotatef(180.0, 0.0, 1.0, 0.0) # Back arrow rotated 180      
        elif r[1] or r[2]:
            GL.glRotatef(90.0, 0.0, r[1], r[2]) # All but front & back
        GL.glRotatef(45.0, r[0], 0.0, 0.0)  # Rotate about x to face viewer

        if self.isSelected():
            self.drawGLBoundingBox()

        GL.glCallList(self.partOGL.oglDispID)

        if self.matrix:
            GL.glPopMatrix()

        if color != LDrawColors.CurrentColor:
            GL.glPopAttrib()

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        
        menu.addAction("Move &Forward", self.decreaseDisplacement)
        menu.addAction("Move &Back", self.increaseDisplacement)
        menu.addAction("&Longer", lambda: self.scene().emit(SIGNAL("adjustArrowLength"), (self, 20)))
        menu.addAction("&Shorter", lambda: self.scene().emit(SIGNAL("adjustArrowLength"), (self, -20)))

        menu.exec_(event.screenPos())

    def adjustLength(self, offset):
        p = self.partOGL.primitives[-1]
        p.points[3] = max(p.points[3] + offset, 0) 
        p.points[6] = max(p.points[6] + offset, 0)
        self.partOGL.resetBoundingBox()
        self.partOGL.createOGLDisplayList()
        self.csi().resetPixmap()
    
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
        self.__boundingBox = None

    def getBoundingBox(self):
        if self.__boundingBox:
            return self.__boundingBox
        
        p = self.points
        box = BoundingBox(p[0], p[1], p[2])
        box.growByPoints(p[3], p[4], p[5])
        box.growByPoints(p[6], p[7], p[8])
        if self.type == GL.GL_QUADS:
            box.growByPoints(p[9], p[10], p[11])
        self.__boundingBox = box
        return box

    def resetBoundingBox(self):
        self.__boundingBox = None

    def vertexIterator(self):
        p = self.points
        yield (p[0], p[1], p[2])
        yield (p[3], p[4], p[5])
        yield (p[6], p[7], p[8])
        if self.type == GL.GL_QUADS:
            yield (p[9], p[10], p[11])

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

    def callGLDisplayList(self):

        # must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        p = self.points

        if self.inverted:
            normal = self.addNormal(p[6:9], p[3:6], p[0:3])
            #GL.glBegin( GL.GL_LINES )
            #GL.glVertex3f(p[3], p[4], p[5])
            #GL.glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #GL.glEnd()

            GL.glBegin(self.type)
            GL.glNormal3fv(normal)
            if self.type == GL.GL_QUADS:
                GL.glVertex3f(p[9], p[10], p[11])
            GL.glVertex3f(p[6], p[7], p[8])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glVertex3f(p[0], p[1], p[2])
            GL.glEnd()
        else:
            normal = self.addNormal(p[0:3], p[3:6], p[6:9])
            #GL.glBegin( GL.GL_LINES )
            #GL.glVertex3f(p[3], p[4], p[5])
            #GL.glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #GL.glEnd()

            GL.glBegin(self.type)
            GL.glNormal3fv(normal)
            GL.glVertex3f(p[0], p[1], p[2])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glVertex3f(p[6], p[7], p[8])
            if self.type == GL.GL_QUADS:
                GL.glVertex3f(p[9], p[10], p[11])
            GL.glEnd()

        if color != LDrawColors.CurrentColor:
            GL.glPopAttrib()
