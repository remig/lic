import math   # for sqrt
import os     # for output path creation
import time

from OpenGL import GL
from OpenGL import GLU

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from LicUndoActions import *
from LicTreeModel import *
import GLHelpers
import l3p
import povray
import LDrawColors
import Helpers
import Layout
import LicDialogs
import GradientDialog

from LDrawFileFormat import *

MagicNumber = 0x14768126
FileVersion = 1

UNINIT_GL_DISPID = -1
partDictionary = {}      # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
submodelDictionary = {}  # {'filename': Submodel()}
currentModelFilename = ""

GlobalGLContext = None
NoMoveFlags = QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable
AllFlags = NoMoveFlags | QGraphicsItem.ItemIsMovable

def getGLFormat():
    format = QGLFormat(QGL.SampleBuffers)
    format.setSamples(8)
    return format

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.connect(self, SIGNAL("clicked(QModelIndex)"), self.clicked)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.scene = None

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

    def updateTreeSelection(self):
        """ This is called whenever the graphics scene's selection changes """
        
        # Deselect everything in the tree
        model = self.model()
        selection = self.selectionModel()
        selection.clear()

        # Select everything in the tree that's currently selected in the graphics view
        for item in self.scene.selectedItems():
            index = model.createIndex(item.row(), 0, item)
            if index:
                self.setCurrentIndex(index)
                selection.select(index, QItemSelectionModel.Select)
                self.scrollTo(index)

    def clicked(self, index = None):
    #def mouseReleaseEvent(self, event):

        #if event.button() == Qt.RightButton:
        if not index:
            return

        # Get a list of everything selected in the tree
        selList = self.selectionModel().selectedIndexes()
        #if not selList:
        #    return
        #index = selList[-1]

        # Clear any existing selection from the graphics view
        self.scene.clearSelectedParts()
        self.scene.clearSelection()

        # Find the selected item's parent page, then flip to that page
        if isinstance(index.internalPointer(), Submodel):
            self.scene.selectPage(index.internalPointer().pages[0].number)
            self.scrollTo(index.child(0, 0))
        else:
            page = index.internalPointer().getPage()
            self.scene.selectPage(page._number)

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

    def contextMenuEvent(self, event):
        # Pass right clicks on to the item right-clicked on
        selList = self.selectionModel().selectedIndexes()
        if not selList:
            return
        event.screenPos = event.globalPos  # QContextMenuEvent vs. QGraphicsSceneContextMenuEvent silliness
        item = selList[0].internalPointer()
        if type(item) in [Part, Step, Page, Callout, CSI]:
            return item.contextMenuEvent(event)

class GraphicsRoundRectItem(QGraphicsRectItem):
    
    defaultPen = QPen(Qt.black)
    defaultBrush = QBrush(Qt.transparent)
    
    def __init__(self, parent):
        QGraphicsRectItem.__init__(self, parent)
        self.cornerRadius = 10
        self.setPen(self.defaultPen)
        self.setBrush(self.defaultBrush)
       
    def paint(self, painter, option, widget = None):
        
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        if self.cornerRadius:
            painter.drawRoundedRect(self.rect(), self.cornerRadius, self.cornerRadius)
        else:
            painter.drawRect(self.rect())
    
        if self.isSelected():
            painter.setPen(QPen(Qt.red))
            painter.drawRect(self.rect())

    def pen(self):
        pen = QGraphicsRectItem.pen(self)
        pen.cornerRadius = self.cornerRadius
        return pen

    def setPen(self, newPen):
        QGraphicsRectItem.setPen(self, newPen)
        if hasattr(newPen, "cornerRadius"):  # Need this check because some setPen() calls come from Qt directly
            self.cornerRadius = newPen.cornerRadius

class Instructions(QObject):
    itemClassName = "Instructions"

    def __init__(self, parent, scene, glWidget, filename = None):
        QObject.__init__(self, parent)

        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"

        self.scene = scene
        self.mainModel = None
        
        global GlobalGLContext
        GlobalGLContext = glWidget
        GlobalGLContext.makeCurrent()

        if filename:
            self.importLDrawModel(filename)

    def clear(self):
        global partDictionary, submodelDictionary, currentModelFilename

        # Remove everything from the graphics scene
        if self.mainModel:
            self.mainModel.deleteAllPages(self.scene)

        self.mainModel = None
        partDictionary = {}
        submodelDictionary = {}
        currentModelFilename = ""
        CSI.scale = PLI.scale = 1.0
        GlobalGLContext.makeCurrent()

    def importLDrawModel(self, filename):
        #startTime = time.time()
        
        global currentModelFilename        
        currentModelFilename = filename

        self.mainModel = Submodel(self, self, filename)
        self.mainModel.importModel()
        
        self.mainModel.syncPageNumbers()
        self.mainModel.addInitialPagesAndSteps()
        
        t1, partStepCount, t2 = self.getPartDimensionListAndCount() 
        pageList = self.mainModel.getPageList()
        pageList.sort(key = lambda x: x._number)
        totalCount = (len(pageList) * 2) + 10 + partStepCount
        currentCount = 2
        
        yield (totalCount, "Initializing GL display lists")
        yield (currentCount, "Initializing GL display lists")

        self.initGLDisplayLists()  # generate all part GL display lists on the general glWidget
        currentCount += 1
        yield (currentCount, "Initializing Part Dimensions")
        
        for step, label in self.initPartDimensions(currentCount):  # Calculate width and height of each partOGL in the part dictionary
            currentCount = step
            yield (step, label)

        currentCount += 1
        yield (currentCount, "Initializing CSI Dimensions")
        for step, label in self.initCSIDimensions(currentCount):   # Calculate width and height of each CSI in this instruction book
            currentCount = step
            yield (step, label)
            
        currentCount += 1
        yield (currentCount, "Initializing Submodel Images")
        self.mainModel.addSubmodelImages()
        
        currentCount += 1
        yield (currentCount, "Laying out Pages")
        for page in pageList:
            label = page.initLayout()
            currentCount += 1
            yield (currentCount, label)

        self.mainModel.mergeInitialPages()
        #endTime = time.time()
        #print "Total load time: %.2f" % (endTime - startTime)
        
        yield (totalCount, "Import Complete!")

    def getModelName(self):
        return self.mainModel.filename

    def getPageList(self):
        return self.mainModel.getPageList()

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

    def getPartDimensionListAndCount(self):
        
        partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        submodelList = [submodel for submodel in submodelDictionary.values() if submodel.used]
        partList += submodelList
        partList.append(self.mainModel)

        partDivCount = 50
        partStepCount = int(len(partList) / partDivCount)
        return (partList, partStepCount, partDivCount)
    
    def initPartDimensions(self, initialCurrentCount):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        global GlobalGLContext

        partList, partStepCount, partDivCount = self.getPartDimensionListAndCount()
        currentPartCount = currentCount = 0

        if not partList:
            return    # If there's no parts to initialize, we're done here

        partList2 = []
        lines = []
        sizes = [128, 256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render each image and calculate their sizes
            for partOGL in partList:

                if partOGL.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    lines.append(partOGL.dimensionsToString())
                    currentPartCount += 1
                    if not currentPartCount % partDivCount:
                        currentPartCount = 0
                        initialCurrentCount += 1
                        currentCount +=1
                        yield (initialCurrentCount, "Initializing Part Dimensions (%d/%d)" % (currentCount, partStepCount))
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
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), GlobalGLContext)

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
    
    def updatePageNumbers(self, newNumber, increment = 1):
        if self.mainModel:
            self.mainModel.updatePageNumbers(newNumber, increment)

    def setPageSize(self, newPageSize):
        if self.mainModel:
            self.mainModel.setPageSize(newPageSize)

    def setCSIPLISize(self, newCSISize, newPLISize):

        print "Setting size to: %d, %d" % (newCSISize, newPLISize)
        oldCSISize = CSI.scale
        oldPLISize = PLI.scale
        
        if newCSISize != CSI.scale:
            CSI.scale = newCSISize

        if newPLISize != PLI.scale:
            PLI.scale = newPLISize
            self.initPLIPixmaps()
            
        if newCSISize != oldCSISize or newPLISize != oldPLISize:
            return ((oldCSISize, newCSISize), (oldPLISize, newPLISize))
        return None

    def enlargePixmaps(self):
        CSI.scale += 0.5
        PLI.scale += 0.5
        self.initPLIPixmaps()
    
    def shrinkPixmaps(self):
        CSI.scale -= 0.5
        PLI.scale -= 0.5
        self.initPLIPixmaps()

class Page(PageTreeManager, QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """

    itemClassName = "Page"
    PageSize = QSize(800, 600)  # Always pixels
    Resolution = 72.0           # Always pixels / inch
    margin = QPointF(15, 15)
    defaultColor = QColor(Qt.white)
    defaultBrush = None

    def __init__(self, subModel, instructions, number, row):
        QGraphicsRectItem.__init__(self)

        # Position this rectangle inset from the containing scene
        self.setPos(0, 0)
        self.setRect(0, 0, self.PageSize.width(), self.PageSize.height())
        self.setFlags(NoMoveFlags)

        self.instructions = instructions
        self.subModel = subModel
        self._number = number
        self._row = row
        self.steps = []
        self.separators = []
        self.children = []
        self.submodelItem = None
        self.layout = Layout.GridLayout()
        self.color = self.defaultColor
        self.brush = self.defaultBrush

        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.dataText = "Page Number Label"
        self.numberItem.itemClassName = "Page Number"
        self.children.append(self.numberItem)

        # Position page number in bottom right page corner
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.margin)
        self.numberItem.setPos(rect.topLeft())
        self.numberItem.setFlags(AllFlags)

        # Need to explicitly add this page to scene, since it has no parent
        instructions.scene.addItem(self)

    def _setNumber(self, number):
        self._number = number
        self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(fget = _getNumber, fset = _setNumber)

    def getAllChildItems(self):

        items = [self, self.numberItem]

        for step in self.steps:
            items.append(step)
            items.append(step.csi)  # TODO: Verify this doesn't break final image rendering
            if step.numberItem:
                items.append(step.numberItem)
            if step.hasPLI():
                items.append(step.pli)
                for pliItem in step.pli.pliItems:
                    items.append(pliItem)
                    items.append(pliItem.numberItem)
            for callout in step.callouts:
                items.append(callout)
                items.append(callout.arrow)
                if callout.qtyLabel:
                    items.append(callout.qtyLabel)
                for step in callout.steps:
                    items.append(step)
                    if step.numberItem:
                        items.append(step.numberItem)

        for separator in self.separators:
            items.append(separator)

        if self.submodelItem:
            items.append(self.submodelItem)

        return items

    def getPage(self):
        return self
    
    def prevPage(self):
        i = self.subModel.pages.index(self)
        if i == 0:
            return None
        return self.subModel.pages[i - 1]

    def nextPage(self):
        i = self.subModel.pages.index(self)
        if i == len(self.subModel.pages) - 1:
            return None
        return self.subModel.pages[i + 1]
        
    def getStep(self, number):
        return self.subModel.getStep(number)

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
        
        for page in self.subModel.pages[self._row + 1 : ]:  # Look forward through pages
            if page.steps:
                return page.steps[0].number

        for page in reversed(self.subModel.pages[ : self._row]):  # Look back
            if page.steps:
                return page.steps[-1].number + 1

        return 1
        
    def addBlankStep(self):
        self.insertStep(Step(self, self.getNextStepNumber()))
    
    def insertStep(self, step):
        self.subModel.updateStepNumbers(step.number)
        self.addStep(step)

    def deleteStep(self, step):

        self.steps.remove(step)
        self.children.remove(step)
        self.scene().removeItem(step)
        self.subModel.updateStepNumbers(step.number, -1)

    def addChild(self, index, child):

        self.children.insert(index, child)

        # Adjust the z-order of all children: first child has highest z value
        for i, item in enumerate(self.children):
            item.setZValue(len(self.children) - i)

    def addStepSeparator(self, index, rect = None):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        s = QGraphicsRectItem(self)
        s.setRect(rect if rect else QRectF(0, 0, 1, 1))
        s.setFlags(AllFlags)
        s.itemClassName = "Separator"
        s.dataText = "Step Separator"
        self.separators.append(s)
        self.addChild(index, s)
        self.scene().emit(SIGNAL("layoutChanged()"))
        return s

    def removeAllSeparators(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        for separator in self.separators:
            self.children.remove(separator)
            self.scene().removeItem(separator)
        del self.separators[:]
        self.scene().emit(SIGNAL("layoutChanged()"))
    
    def showSeparators(self):
        for s in self.separators:
            s.show()
    
    def hideSeparators(self):
        for s in self.separators:
            s.hide()
    
    def removeStep(self, step):
        self.steps.remove(step)
        self.children.remove(step)

    def addSubmodelImage(self):
        self.submodelItem = SubmodelPreview(self, self.subModel)
        self.submodelItem.setPos(Page.margin)
        self.children.append(self.submodelItem)
        
    def resetSubmodelImage(self):
        self.submodelItem.setPartOGL(self.subModel)

    def checkForLayoutOverlaps(self):
        for step in self.steps:
            if step.checkForLayoutOverlaps():
                return True
        return False
    
    def initLayout(self):

        # Remove any separators; we'll re-add them in the appropriate place later
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
        for index, rect in self.layout.separators:
            self.addStepSeparator(index, rect)
        
        return label

    def scaleImages(self):
        for step in self.steps:
            if step.hasPLI():
                step.pli.initLayout()
            
        if self.submodelItem:
            self.resetSubmodelImage()
        
    def renderFinalImage(self):

        for step in self.steps:
            step.csi.createPng()
            
            for callout in step.callouts:
                for s in callout.steps:
                    s.csi.createPng()
                    
            if step.hasPLI():
                for item in step.pli.pliItems:
                    item.createPng()

        oldPos = self.pos()
        self.setPos(0, 0)
        image = QImage(self.rect().width(), self.rect().height(), QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(image)

        items = self.getAllChildItems()
        options = QStyleOptionGraphicsItem()
        optionList = [options] * len(items)
        self.scene().drawItems(painter, items, optionList)

        for step in self.steps:
            painter.drawImage(step.csi.scenePos(), step.csi.pngImage)
                
            for callout in step.callouts:
                for s in callout.steps:
                    painter.drawImage(s.csi.scenePos(), s.csi.pngImage)
            
            if step.hasPLI():
                for item in step.pli.pliItems:
                    painter.drawImage(item.scenePos(), item.pngImage)

        if self.submodelItem:
            painter.drawImage(self.submodelItem.pos() + PLI.margin, self.subModel.pngImage)

        painter.end()
        
        imgName = os.path.join(config.config['imgPath'], "Page_%d.png" % self._number)
        image.save(imgName, None)
        
        self.setPos(oldPos)
                
    def paint(self, painter, option, widget = None):

        # Draw a slightly down-right translated black rectangle, for the page shadow effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.rect().translated(3, 3))

        # Draw the page itself - white with a thin black border
        painter.setPen(QPen(Qt.black))
        painter.setBrush(QBrush(self.color))
        painter.drawRect(self.rect())
        
        # Draw any images or gradients this page may have
        if self.brush:
            painter.setBrush(self.brush)
            painter.drawRect(self.rect())

    def drawGLItems(self, painter, rect):
        
        GLHelpers.pushAllGLMatrices()
        vx = self.pos().x() - rect.x()
        vy = rect.height() + rect.y() - Page.PageSize.height() - self.pos().y()
        f = self.scene().scaleFactor
        GLHelpers.adjustGLViewport(vx * f, vy * f, Page.PageSize.width() * f, Page.PageSize.height() * f, True)
        GL.glTranslatef(rect.x(), rect.y(), 0.0)
        
        for glItem in self.glItemIterator():
            if rect.intersects(glItem.mapToScene(glItem.rect()).boundingRect()):
                glItem.paintGL()
            
        GLHelpers.popAllGLMatrices()

    def glItemIterator(self):
        if self.submodelItem:
            yield self.submodelItem
        for step in self.steps:
            yield step.csi
            if step.pli:
                for pliItem in step.pli.pliItems:
                    yield pliItem
            for callout in step.callouts:
                for step2 in callout.steps:
                    yield step2.csi
            
    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Prepend blank Page", self.addPageBeforeSignal)
        menu.addAction("Append blank Page", self.addPageAfterSignal)
        menu.addSeparator()
        if self.separators:
            if [x for x in self.separators if x.isVisible()]:
                menu.addAction("Hide Step Separators", self.hideSeparators)
            else:
                menu.addAction("Show Step Separators", self.showSeparators)
        menu.addAction("Add blank Step", self.addBlankStepSignal)
        menu.addSeparator()
        if self.layout.orientation == Layout.Horizontal:
            menu.addAction("Use Vertical layout", self.useVerticalLayout)
        else:
            menu.addAction("Use Horizontal layout", self.useHorizontalLayout)
        menu.addAction("Delete Page", self.deletePageSignal)
        menu.exec_(event.screenPos())
    
    def useVerticalLayout(self):
        self.layout.orientation = Layout.Vertical
        self.initLayout()
        
    def useHorizontalLayout(self):
        self.layout.orientation = Layout.Horizontal
        self.initLayout()
        
    def addBlankStepSignal(self):
        step = Step(self, self.getNextStepNumber())
        self.scene().undoStack.push(AddRemoveStepCommand(step, True))

    def deletePageSignal(self):
        if self.steps: #Do not allow pages with steps to be deleted
            QMessageBox.warning(self.scene().views()[0], "Page Delete Error", "Cannot delete a Page that contains Steps.\nRemove or move Steps to a different page first.")
        else:
            self.scene().undoStack.push(AddRemovePageCommand(self, False))
        
    def addPageBeforeSignal(self):
        newPage = Page(self.subModel, self.instructions, self.number, self._row)
        self.scene().undoStack.push(AddRemovePageCommand(newPage, True))
    
    def addPageAfterSignal(self):
        newPage = Page(self.subModel, self.instructions, self.number + 1, self._row + 1)
        self.scene().undoStack.push(AddRemovePageCommand(newPage, True))

class CalloutArrowEndItem(QGraphicsRectItem):
    itemClassName = "CalloutArrowEndItem"
    
    def __init__(self, parent, width, height, dataText, row):
        QGraphicsRectItem.__init__(self, parent)
        self.setRect(0, 0, width, height)
        self.dataText = dataText
        self._row = row
        
        self.point = QPointF()
        self.mousePoint = QPointF()
        self.setFlags(AllFlags)
        self.setPen(parent.pen())
    
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        QGraphicsItem.mousePressEvent(self, event)
        self.oldPoint = QPointF(self.point)
    
    def mouseMoveEvent(self, event):
        QGraphicsRectItem.mouseMoveEvent(self, event)
        self.point -= event.lastScenePos() - event.scenePos()
        self.mousePoint = event.pos()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        QGraphicsItem.mouseReleaseEvent(self, event)
        self.scene().undoStack.push(CalloutArrowMoveCommand(self, self.oldPoint, self.point))

class CalloutArrow(CalloutArrowTreeManager, QGraphicsRectItem):
    itemClassName = "CalloutArrow"
    
    defaultPen = QPen(Qt.black)
    defaultBrush = QBrush(Qt.transparent)  # Fill arrow head
    arrowTipLength = 22.0
    arrowTipHeight = 5.0
    arrowHead = QPolygonF([QPointF(),
                           QPointF(arrowTipLength + 3, -arrowTipHeight),
                           QPointF(arrowTipLength, 0.0),
                           QPointF(arrowTipLength + 3, arrowTipHeight)])
    
    def __init__(self, parent, csi):
        QGraphicsRectItem.__init__(self, parent)
        self.dataText = "Callout Arrow"

        self.csi = csi
        self.setPen(self.defaultPen)
        self.setBrush(self.defaultBrush)
        self.setFlags(NoMoveFlags)
        
        self.tipRect = CalloutArrowEndItem(self, 32, 32, "Arrow Tip", 0)
        self.baseRect = CalloutArrowEndItem(self, 20, 20, "Arrow Base", 1)

    def initializeEndPoints(self):
        # Find two target rects, both in *LOCAL* coordinates
        callout = self.parentItem()
        calloutRect = self.mapFromItem(callout, callout.rect()).boundingRect()
        csiRect = self.mapFromItem(self.csi, self.csi.rect()).boundingRect()

        if csiRect.right() < calloutRect.left():  # Callout right of CSI
            self.tipRect.point = csiRect.topRight() + QPointF(0.0, csiRect.height() / 2.0)
            self.baseRect.point = callout.getArrowBasePoint('left')
            
        elif calloutRect.right() < csiRect.left():  # Callout left of CSI
            self.tipRect.point = csiRect.topLeft() + QPointF(0.0, csiRect.height() / 2.0)
            self.baseRect.point = callout.getArrowBasePoint('right')
            
        elif calloutRect.bottom() < csiRect.top():  # Callout above CSI
            self.tipRect.point = csiRect.topLeft() + QPointF(csiRect.width() / 2.0, 0.0)
            self.baseRect.point = callout.getArrowBasePoint('bottom')

        else:  # Callout below CSI
            self.tipRect.point = csiRect.bottomLeft() + QPointF(csiRect.width() / 2.0, 0.0)
            self.baseRect.point = callout.getArrowBasePoint('top')
            
        self.tipRect.point = self.mapToItem(self.csi, self.tipRect.point)  # Store tip point in CSI space
        
    def paint(self, painter, option, widget = None):
        
        # Find two target rects, both in *LOCAL* coordinates
        callout = self.parentItem()
        calloutRect = self.mapFromItem(callout, callout.rect()).boundingRect()
        csiRect = self.mapFromItem(self.csi, self.csi.rect()).boundingRect()

        tip = self.mapFromItem(self.csi, self.tipRect.point)
        end = self.baseRect.point

        if csiRect.right() < calloutRect.left():  # Callout right of CSI
            rotation = 0.0
            offset = QPointF(self.arrowTipLength, 0)
            self.tipRect.setPos(tip - QPointF(3, 16))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(18, 10))  # 18 = 2 units overlap past end, 10 = 1/2 height
            
        elif calloutRect.right() < csiRect.left():  # Callout left of CSI
            rotation = 180.0
            offset = QPointF(-self.arrowTipLength, 0)
            self.tipRect.setPos(tip - QPointF(29, 16))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(2, 10))  # 2 units overlap past end, 10 = 1/2 height
            
        elif calloutRect.bottom() < csiRect.top():  # Callout above CSI
            rotation = -90.0
            offset = QPointF(0, -self.arrowTipLength)
            self.tipRect.setPos(tip - QPointF(16, 29))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(10, 2))  # 18 = 2 units overlap past end, 10 = 1/2 height

        else:  # Callout below CSI
            rotation = 90.0
            offset = QPointF(0, self.arrowTipLength)
            self.tipRect.setPos(tip - QPointF(16, 3))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(10, 18))  # 18 = 2 units overlap past end, 10 = 1/2 height

        if rotation == 0 or rotation == 180:
            midX = (tip.x() + offset.x() + end.x()) / 2.0
            mid1 = QPointF(midX, tip.y())
            mid2 = QPointF(midX, end.y())
        else:
            midY = (tip.y() + offset.y() + end.y()) / 2.0
            mid1 = QPointF(tip.x(), midY)
            mid2 = QPointF(end.x(), midY)

        l, r, t, b = calloutRect.left(), calloutRect.right(), calloutRect.top(), calloutRect.bottom()
        mp = self.mapFromItem(self.baseRect, self.baseRect.mousePoint)
        mx, my = mp.x(), mp.y()

        if mx > l and mx < r and my > t and my < b:  # cursor inside callout - lock to closest edge
            if min(mx - l, r - mx) < min(my - t, b - my):
                end.setX(l if (mx - l) < (r - mx) else r)  # lock to x
            else:
                end.setY(t if (my - t) < (b - my) else b)  # lock to y
        else:
            if mx < l:
                end.setX(l)
            elif mx > r:
                end.setX(r)
            if my < t:
                end.setY(t)
            elif my > b:
                end.setY(b)

        # Draw step line
        line = QPolygonF([tip + offset, mid1, mid2, end])
        painter.setPen(self.pen())
        painter.drawPolyline(line)

        # Draw arrow head
        painter.save()
        painter.translate(tip)
        painter.rotate(rotation)
        painter.setBrush(self.brush())
        painter.drawPolygon(self.arrowHead)
        painter.restore()

        # Widen / heighten bounding rect to include tip and end line
        r = QRectF(tip, end).normalized()
        if rotation == 0 or rotation == 180:
            self.setRect(r.adjusted(0.0, -self.arrowTipHeight - 2, 0.0, self.arrowTipHeight + 2))
        else:
            self.setRect(r.adjusted(-self.arrowTipHeight - 2, 0.0, self.arrowTipHeight + 2, 0.0))

        # Draw selection box, if selected
        if self.isSelected():
            painter.setPen(QPen(Qt.red))
            painter.drawRect(self.rect())

class Callout(CalloutTreeManager, GraphicsRoundRectItem):

    itemClassName = "Callout"
    margin = QPointF(15, 15)

    def __init__(self, parent, number = 1, showStepNumbers = False):
        GraphicsRoundRectItem.__init__(self, parent)

        self.arrow = CalloutArrow(self, self.parentItem().csi)
        self.steps = []
        self.number = number
        self.qtyLabel = None
        self.showStepNumbers = showStepNumbers
        self.layout = Layout.GridLayout()
        
        self.setPos(0.0, 0.0)
        self.setRect(0.0, 0.0, 30.0, 30.0)
        self.setFlags(AllFlags)
        
    def addBlankStep(self, useUndo = True):
        lastNum = self.steps[-1].number + 1 if self.steps else 1
        step = Step(self, lastNum, False, self.showStepNumbers)
        if useUndo:
            self.scene().undoStack.push(AddRemoveStepCommand(step, True))
        else:
            self.insertStep(step)
        
    def insertStep(self, step):
        self.steps.append(step)
        step.setParentItem(self)
        if len(self.steps) > 1:
            self.enableStepNumbers()

    def deleteStep(self, step):
        self.steps.remove(step)
        self.scene().removeItem(step)
        if len(self.steps) <= 1:
            self.disableStepNumbers()

    def addPart(self, part):
        self.steps[-1].addPart(part)

    def removePart(self, part):
        for step in self.steps:
            step.removePart(part)

    def resetRect(self):
        children = self.children()
        children.remove(self.arrow)  # Don't want Callout arrow inside its selection box

        b = QRectF()
        for child in children:
            b |= child.boundingRect().translated(child.pos())
            
        x, y = Page.margin.x(), Page.margin.y()
        if self.qtyLabel:
            b.adjust(0.0, 0.0, self.qtyLabel.boundingRect().width(), self.qtyLabel.boundingRect().height())
        self.setRect(b.adjusted(-x, -y, x, y))

    def getArrowBasePoint(self, side):
        # TODO: arrow base should come out of last step in callout
        r = self.rect()
        if side == 'right':
            return r.topRight() + QPointF(0.0, r.height() / 2.0)
        elif side == 'left':
            return r.topLeft() + QPointF(0.0, r.height() / 2.0)
        elif side == 'bottom':
            return r.bottomLeft() + QPointF(r.width() / 2.0, 0.0)
        else:
            return r.topLeft() + QPointF(r.width() / 2.0, 0.0)

    def initLayout(self):

        if not self.steps:
            self.setRect(0.0, 0.0, 1.0, 1.0)
            return  # Nothing to layout here
        
        for step in self.steps:
            step.initMinimumLayout()
            
        self.layout.initLayoutInsideOut(self.steps)
        
        if self.qtyLabel:  # Hide qty label inside step temporarily, so its bounding box is ignored
            self.qtyLabel.setPos(self.steps[0].pos())

        self.resetRect()
        
        if self.qtyLabel:
            r = self.qtyLabel.boundingRect()
            r.moveBottomRight(self.rect().bottomRight() - Page.margin)
            self.qtyLabel.setPos(r.topLeft())
            
        self.parentItem().initLayout()
        self.arrow.initializeEndPoints()

    def enableStepNumbers(self):
        for step in self.steps:
            step.enableNumberItem()
        self.showStepNumbers = True

    def disableStepNumbers(self):
        for step in self.steps:
            step.disableNumberItem()
        self.showStepNumbers = False

    def addQuantityLabel(self, pos = None, font = None):
        self.qtyLabel = QGraphicsSimpleTextItem("1x", self)
        self.qtyLabel.itemClassName = "Callout Quantity"
        self.qtyLabel.setPos(pos if pos else QPointF(0, 0))
        self.qtyLabel.setFont(font if font else QFont("Arial", 15))
        self.qtyLabel.setFlags(AllFlags)
        self.qtyLabel.dataText = "Quantity Label"
            
    def removeQuantityLabel(self):
        self.scene().removeItem(self.qtyLabel)
        self.qtyLabel = None
    
    def increaseQuantityLabel(self):
        self.setQuantity(int(self.qtyLabel.text()[:-1]) + 1)
    
    def decreaseQuantityLabel(self):
        self.setQuantity(int(self.qtyLabel.text()[:-1]) - 1)

    def setQuantity(self, qty):
        self.qtyLabel.setText("%dx" % qty)
        
    def contextMenuEvent(self, event):
        stack = self.scene().undoStack
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add blank Step", self.addBlankStep)
        if self.qtyLabel:
            menu.addAction("Increase Quantity", self.increaseQuantityLabel)
            menu.addAction("Decrease Quantity", self.decreaseQuantityLabel)
            menu.addAction("Remove Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, False)))
        else:
            menu.addAction("Add Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, True)))
        if self.showStepNumbers:
            menu.addAction("Hide Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, False)))
        else:
            menu.addAction("Show Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, True)))
        menu.exec_(event.screenPos())

    def getStep(self, number):
        for step in self.steps:
            if step.number == number:
                return step
        return None

class Step(StepTreeManager, QGraphicsRectItem):
    """ A single step in an Instruction book.  Contains one optional PLI and exactly one CSI. """
    itemClassName = "Step"

    def __init__(self, parentPage, number, hasPLI = True, hasNumberItem = True):
        QGraphicsRectItem.__init__(self, parentPage)

        # Children
        self._number = number
        self.numberItem = None
        self.csi = CSI(self)
        self.pli = PLI(self) if hasPLI else None
        self._hasPLI = hasPLI
        self.callouts = []
        
        self.maxRect = None

        self.setPen(QPen(Qt.NoPen))
        self.setPos(Page.margin)

        if hasNumberItem:
            self.enableNumberItem()

        self.setFlags(AllFlags)

    def _setNumber(self, number):
        self._number = number
        if self.numberItem:
            self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(fget = _getNumber, fset = _setNumber)

    def hasPLI(self):
        return self._hasPLI
    
    def enablePLI(self):
        self._hasPLI = True
        self.pli.show()
    
    def disablePLI(self):
        self._hasPLI = False
        self.pli.hide()
    
    def addPart(self, part):
        self.csi.addPart(part)
        if self.pli:  # Visibility here is irrelevant
            self.pli.addPart(part)

    def removePart(self, part):
        self.csi.removePart(part)
        if self.pli:  # Visibility here is irrelevant
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

    def getNextStep(self):
        return self.parentItem().getStep(self.number + 1)

    def getPrevStep(self):
        return self.parentItem().getStep(self.number - 1)

    def enableNumberItem(self):
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.itemClassName = "Step Number"
        self.numberItem.setPos(0, 0)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.setFlags(AllFlags)
        self.numberItem.dataText = "Step Number Label"
            
    def disableNumberItem(self):
        self.scene().removeItem(self.numberItem)
        self.numberItem = None
        
    def initMinimumLayout(self):

        if self.hasPLI(): # Do not use on a step with PLI
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

    def checkForLayoutOverlaps(self):
        # TODO: Test this with steps that don't have PLIs!
        if self.csi.pos().y() < self.pli.rect().bottom() and self.csi.pos().x() < self.pli.rect().right():
            return True
        if self.csi.pos().y() < self.pli.rect().top():
            return True
        if self.csi.rect().width() > self.rect().width():
            return True
        if self.pli.rect().width() > self.rect().width():
            return True
        page = self.getPage()
        topLeft = self.mapToItem(page, self.rect().topLeft())
        botRight = self.mapToItem(page, self.rect().bottomRight())
        if topLeft.x() < 0 or topLeft.y() < 0:
            return True
        if botRight.x() > page.rect().width() or botRight.y() > page.rect().height():
            return True
        return False

    def initLayout(self, destRect = None):

        if destRect is None:
            destRect = self.maxRect
        else:
            self.maxRect = destRect

        self.setPos(destRect.topLeft())
        self.setRect(0, 0, destRect.width(), destRect.height())
        
        if self.hasPLI():
            self.pli.initLayout()  # Position PLI

        # Position Step number label beneath the PLI
        if self.numberItem:
            self.numberItem.setPos(0, 0)
            pliOffset = self.pli.rect().height() if self.hasPLI() else 0.0
            self.numberItem.moveBy(0, pliOffset + Page.margin.y())

        self.positionInternalBits()

    def positionInternalBits(self):

        r = self.rect()
        
        if self.hasPLI():
            r.setTop(self.pli.rect().height())

        csiWidth = self.csi.rect().width() * CSI.scale
        csiHeight = self.csi.rect().height() * CSI.scale

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
            csiWidth += cr.width() + (Page.margin.x() * 3)
        else:
            csiHeight += cr.height() + (Page.margin.y() * 3)

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

        if isinstance(parent, Page):
            if parent.prevPage() and parent.steps[0] is self:
                menu.addAction("Move to &Previous Page", self.moveToPrevPage)
            if parent.nextPage() and parent.steps[-1] is self:
                menu.addAction("Move to &Next Page", self.moveToNextPage)
            
        if self.getPrevStep():
            menu.addAction("Merge with Previous Step", lambda: self.mergeWithStepSignal(self.getPrevStep()))
        if self.getNextStep():
            menu.addAction("Merge with Next Step", lambda: self.mergeWithStepSignal(self.getNextStep()))
                    
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
        step.scene().undoStack.push(MoveStepToPageCommand(stepSet))
        
    def moveToNextPage(self):
        stepSet = []
        for step in self.scene().selectedItems():
            if isinstance(step, Step):
                stepSet.append((step, step.parentItem(), step.parentItem().nextPage()))
        step.scene().undoStack.push(MoveStepToPageCommand(stepSet))
    
    def moveToPage(self, page, useSignals = True):
        if useSignals:
            page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.parentItem().removeStep(self)
        page.addStep(self)
        if useSignals:
            page.scene().emit(SIGNAL("layoutChanged()"))

    def mergeWithStepSignal(self, step):
        a = MovePartsToStepCommand(self.csi.getPartList(), self, step)
        self.scene().undoStack.push(a)

class SubmodelPreview(GraphicsRoundRectItem):
    itemClassName = "SubmodelPreview"
    
    def __init__(self, parent, partOGL):
        GraphicsRoundRectItem.__init__(self, parent)
        self.dataText = "Submodel Preview"
        self.cornerRadius = 10
        self.setFlags(AllFlags)
        self.setPartOGL(partOGL)
        
    def setPartOGL(self, partOGL):
        self.partOGL = partOGL
        self.setRect(0, 0, partOGL.width + PLI.margin.x() * 2, partOGL.height + PLI.margin.y() * 2)

    def paintGL(self):
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.rect().width() / 2.0)
        dy = -Page.PageSize.height() + pos.y() + (self.rect().height() / 2.0)
        self.partOGL.paintGL(dx, dy)
    
class PLIItem(PLIItemTreeManager, QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """
    itemClassName = "PLIItem"

    def __init__(self, parent, partOGL, color, quantity = 0):
        QGraphicsRectItem.__init__(self, parent)

        self.partOGL = partOGL
        self.quantity = 0
        self.color = color

        self.setPen(QPen(Qt.NoPen)) # QPen(Qt.black)
        self.setFlags(AllFlags)

        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem("0x", self)
        self.numberItem.itemClassName = "PLIItem Quantity"
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

    def resetRect(self):
        glRect = QRectF(0.0, 0.0, self.partOGL.width, self.partOGL.height)
        self.setRect(self.childrenBoundingRect() | glRect)
        self.parentItem().resetRect()
        
    def initLayout(self):

        part = self.partOGL

        # Put label directly below part, left sides aligned
        # Label's implicit lower top right corner (from qty 'x'), means no padding needed
        self.numberItem.setPos(0.0, part.height * PLI.scale)  
       
        lblWidth = self.numberItem.boundingRect().width()
        lblHeight = self.numberItem.boundingRect().height()
        if part.leftInset > lblWidth:
            if part.bottomInset > lblHeight:
                self.numberItem.moveBy(0, -lblHeight)  # Label fits entirely under part: bottom left corners now match
            else:
                li = part.leftInset * PLI.scale   # Move label up until top right corner intersects bottom left inset line
                slope = (part.bottomInset * PLI.scale) / float(li)
                dy = slope * (li - lblWidth)
                self.numberItem.moveBy(0, -dy)

        # Set this item to the union of its image and qty label rects
        partRect = QRectF(0.0, 0.0, self.partOGL.width, self.partOGL.height)
        numberRect = self.numberItem.boundingRect().translated(self.numberItem.pos())
        self.setRect(partRect | numberRect)
        self.moveBy(-self.rect().x(), -self.rect().y())

    def paintGL(self):
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.partOGL.width / 2.0)
        dy = -Page.PageSize.height() + pos.y() + (self.partOGL.height / 2.0)
        self.partOGL.paintGL(dx, dy, self.color)

    """
    def paint(self, painter, option, widget = None):
        QGraphicsRectItem.paint(self, painter, option, widget)
        painter.drawRect(self.boundingRect())
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

class PLI(PLITreeManager, GraphicsRoundRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """
    itemClassName = "PLI"

    scale = 1.0
    margin = QPointF(15, 15)

    def __init__(self, parent):
        GraphicsRoundRectItem.__init__(self, parent)

        self.pliItems = []  # {(part filename, color): PLIItem instance}

        self.dataText = "PLI"  # String displayed in Tree - reimplement data(self, index) to override
        self._row = 1
        
        self.setPos(0.0, 0.0)
        self.setFlags(AllFlags)

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

class CSI(CSITreeManager, QGraphicsRectItem):
    """ Construction Step Image.  Includes border and positional info. """
    itemClassName = "CSI"

    scale = 1.0

    def __init__(self, step):
        QGraphicsRectItem.__init__(self, step)

        self.center = QPointF()
        self.oglDispID = UNINIT_GL_DISPID
        self.setFlags(AllFlags)
        self.setPen(QPen(Qt.NoPen))

        self._row = 0
        self.rotation = None
        
        self.__boxPoints = None
        
        self.parts = []
        self.arrows = []

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

    def paintGL(self):
        """ 
        Assumes a current GL context.  Assumes that context has been transformed so the
        view runs from (0,0) to page width & height with (0,0) in the bottom left corner.
        """
         
        GLHelpers.pushAllGLMatrices()
        
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.rect().width() / 2.0) + self.center.x()
        dy = -Page.PageSize.height() + pos.y() + (self.rect().height() / 2.0) + self.center.y()
        GLHelpers.rotateToDefaultView(dx, dy, 0.0, CSI.scale)
        
        if self.rotation:
            GLHelpers.rotateView(*self.rotation)

        GL.glCallList(self.oglDispID)
        #self.calculateGLSize()
        GLHelpers.popAllGLMatrices()
    
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

        for p in self.parts:
            p.removePart(part)

        for p in [x for x in self.parts if not x.parts]:
            self.parts.remove(p)

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

        if self.oglDispID == UNINIT_GL_DISPID:
            self.oglDispID = GL.glGenLists(1)
        GL.glNewList(self.oglDispID, GL.GL_COMPILE)
        #GLHelpers.drawCoordLines()
        self.__callPreviousOGLDisplayLists(True)
        GL.glEndList()

    def calculateGLSize(self):
        
        # TODO: This works, but its actually *slower* than the current image buffer solution.
        # If possible, try to speed it up, since there's way more room for optimization here
        # than the image buffer way (plus we can then ditch FBOs).
        if self.__boxPoints is None:

            minX, minY = 100000, 100000
            maxX, maxY = 0, 0
            i = 0
            
            for partItem in self.parts:
                for part in partItem.parts:
                    for v in part.vertexIterator(True):
                        i+=1
                        resX, resY, resZ = GLU.gluProject(v[0], v[1], v[2])
                        maxX = max(resX, maxX)
                        maxY = max(resY, maxY)
                    
                        minX = min(resX, minX)
                        minY = min(resY, minY)
                    
            print "x min: %f, max: %f" % (minX, maxX)
            print "y min: %f, max: %f" % (minY, maxY)
            print "vertex count: %d" % i
        
            aX, aY, aZ = GLU.gluUnProject(minX, minY, 0.0)
            bX, bY, bZ = GLU.gluUnProject(minX, maxY, 0.0)
            cX, cY, cZ = GLU.gluUnProject(maxX, maxY, 0.0)
            dX, dY, dZ = GLU.gluUnProject(maxX, minY, 0.0)
            
            self.__boxPoints = [[aX, aY, aZ], [bX, bY, bZ], [cX, cY, cZ], [dX, dY, dZ]]

        GL.glPushAttrib(GL.GL_CURRENT_BIT)
        GL.glColor4fv([1.0, 0.0, 0.0, 1.0])
        
        GL.glBegin(GL.GL_LINE_LOOP)
        GL.glVertex3fv(self.__boxPoints[0])
        GL.glVertex3fv(self.__boxPoints[1])
        GL.glVertex3fv(self.__boxPoints[2])
        GL.glVertex3fv(self.__boxPoints[3])
        GL.glEnd()
    
        GL.glPopAttrib()
    
    def resetPixmap(self):
        global GlobalGLContext
        
        if not self.parts:
            self.center = QPointF()
            self.setRect(QRectF())
            self.oglDispID = UNINIT_GL_DISPID
            return  # No parts = reset pixmap
        
        # Temporarily enlarge CSI, in case recent changes pushed image out of existing bounds.
        oldWidth, oldHeight = self.rect().width(), self.rect().height()
        self.setRect(0.0, 0.0, Page.PageSize.width(), Page.PageSize.height())
        
        GlobalGLContext.makeCurrent()
        self.createOGLDisplayList()
        sizes = [512, 1024, 2048]

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            if self.initSize(size, pBuffer):
                break

        # Move CSI so its new center matches its old
        dx = (self.rect().width() - oldWidth) / 2.0
        dy = (self.rect().height() - oldHeight) / 2.0
        self.moveBy(-dx, -dy)

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
        filename = self.getDatFilename()

        result = "Initializing CSI Page %d Step %d" % (pageNumber, stepNumber)
        if not self.parts:
            return result  # A CSI with no parts is already initialized

        params = GLHelpers.initImgSize(size, self.oglDispID, True, filename, self.rotation, pBuffer)
        if params is None:
            return False

        w, h, self.center, x, y = params  # x & y are just ignored place-holders
        self.setRect(0.0, 0.0, w, h)
        return result

    def createPng(self):

        csiName = self.getDatFilename()
        datFile = os.path.join(config.config['datPath'], csiName)
        
        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            self.exportToLDrawFile(fh)
            fh.close()
            
        povFile = l3p.createPovFromDat(datFile)
        pngFile = povray.createPngFromPov(povFile, self.rect().width(), self.rect().height(), self.center, CSI.scale, isPLIItem = False)
        self.pngImage = QImage(pngFile)
        
    def exportToLDrawFile(self, fh):
        prevStep = self.parentItem().getPrevStep()
        if prevStep:
            prevStep.csi.exportToLDrawFile(fh)
            
        for partItem in self.parts:
            for part in partItem.parts:
                part.exportToLDrawFile(fh)

    def getDatFilename(self):
        step = self.parentItem()
        parent = step.parentItem()
        if isinstance(parent, Callout):
            return "CSI_Callout_%d_Step_%d.dat" % (parent.number, step.number)
        else:
            return "CSI_Page_%d_Step_%d.dat" % (parent.number, step.number)
    
    def getPageStepNumberPair(self):
        step = self.parentItem()
        page = step.parentItem()
        return (page.number, step.number)

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        stack = self.scene().undoStack
        menu.addAction("Rotate CSI", self.rotateSignal)
        menu.exec_(event.screenPos())

    def rotateSignal(self):

        parentWidget = self.scene().views()[0]
        stack = self.scene().undoStack
        action = lambda rotation: stack.push(RotateCSICommand(self, self.rotation, rotation))
        dialog = LicDialogs.RotateCSIDialog(parentWidget, self.rotation)
        parentWidget.connect(dialog, SIGNAL("changed"), action)
        
        stack.beginMacro("rotate CSI")
        dialog.exec_()
        stack.endMacro()
    
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
        self.invertNext = False
        self.winding = GL.GL_CCW
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

    def sortEdgesToBack(self):
        for p in list(self.primitives):
            if p.type == GL.GL_LINES:
                self.primitives.remove(p)
                self.primitives.append(p)
            
    def loadFromFile(self):

        ldrawFile = LDrawFile(self.filename)
        ldrawFile.loadFileArray()
        
        self.isPrimitive = ldrawFile.isPrimitive
        self.name = ldrawFile.name

        # Loop over the specified LDraw file array, skipping the first (title) line
        for line in ldrawFile.fileArray[1:]:

            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return

            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):

        if isValidPartLine(line):
            self.addPartFromLine(lineToPart(line), line)

        elif isValidLineLine(line):
            self.addPrimitive(lineToLine(line), GL.GL_LINES)
        
        elif isValidTriangleLine(line):
            self.addPrimitive(lineToTriangle(line), GL.GL_TRIANGLES)

        elif isValidQuadLine(line):
            self.addPrimitive(lineToQuad(line), GL.GL_QUADS)
            
        elif isValidBFCLine(line):
            if line[3] == 'CERTIFY':
                self.winding = GL.GL_CW if line[4] == 'CW' else GL.GL_CCW
            elif line [3] == 'INVERTNEXT':
                self.invertNext = True

    def addPartFromLine(self, p, line):
        try:
            part = Part(p['filename'], p['color'], p['matrix'], False)
            part.setInversion(self.invertNext)
            part.initializePartOGL()
            if self.invertNext:
                self.invertNext = False
                
        except IOError:
            print "Could not find file: %s - Ignoring." % p['filename']
            return

        self.parts.append(part)
        return part

    def addPrimitive(self, p, shape):
        primitive = Primitive(p['color'], p['points'], shape, self.winding)
        self.primitives.append(primitive)

    def vertexIterator(self):

        prevVertex = None
        for primitive in self.primitives:
            if primitive.type == GL.GL_LINES:
                v1, v2 = primitive.vertexIterator()
                if v1 != prevVertex:
                    yield v1
                prevVertex = v2
                yield v2
                
        for part in self.parts:
            for vertex in part.vertexIterator():
                yield vertex

    def createOGLDisplayList(self):
        """ Initialize this part's display list."""

        # Ensure any parts in this part have been initialized
        for part in self.parts:
            if part.partOGL.oglDispID == UNINIT_GL_DISPID:
                part.partOGL.createOGLDisplayList()

        if self.oglDispID == UNINIT_GL_DISPID:
            self.oglDispID = GL.glGenLists(1)
        GL.glNewList(self.oglDispID, GL.GL_COMPILE)

        for part in self.parts:
            part.callGLDisplayList()

        for primitive in self.primitives:
            primitive.callGLDisplayList()

        GL.glEndList()

    def buildSubPartOGLDict(self, partDict):
            
        for part in self.parts:
            if part.partOGL.filename not in partDict:
                part.partOGL.buildSubPartOGLDict(partDict)
        partDict[self.filename] = self
    
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

        params = GLHelpers.initImgSize(size, self.oglDispID, self.isSubmodel, self.filename, None, pBuffer)
        if params is None:
            return False

        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def paintGL(self, dx, dy, color = None):
         
        if self.isPrimitive:
            return # Do not draw primitives directly

        GLHelpers.pushAllGLMatrices()

        dx += self.center.x() * PLI.scale
        dy += self.center.y() * PLI.scale
        
        if self.isSubmodel:
            GLHelpers.rotateToDefaultView(dx, dy, 0.0, CSI.scale)
        else:
            GLHelpers.rotateToPLIView(dx, dy, 0.0, CSI.scale)
        
        if color is not None:
            colorRGB = LDrawColors.convertToRGBA(color)
            if colorRGB == LDrawColors.CurrentColor:
                colorRGB = LDrawColors.colors[2][:4]
            GL.glColor4fv(colorRGB)

        GL.glCallList(self.oglDispID)
        #self.calculateGLSize()
        GLHelpers.popAllGLMatrices()

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

    def vertices(self):
        yield (self.x1, self.y1, self.z1)
        yield (self.x1, self.y1, self.z2)
        yield (self.x1, self.y2, self.z1)
        yield (self.x1, self.y2, self.z2)
        yield (self.x2, self.y1, self.z1)
        yield (self.x2, self.y1, self.z2)
        yield (self.x2, self.y2, self.z1)
        yield (self.x2, self.y2, self.z2)
        
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

    def xSize(self):
        return (abs(self.x1) + abs(self.x2)) / 2.0

    def ySize(self):
        return (abs(self.y1) + abs(self.y2)) / 2.0

    def zSize(self):
        return (abs(self.z1) + abs(self.z2)) / 2.0
    
class Submodel(SubmodelTreeManager, PartOGL):
    """ A Submodel is just a PartOGL that also has pages & steps, and can be inserted into a tree. """
    itemClassName = "Submodel"

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
        
    def setSelected(self, selected):
        self.pages[0].setSelected(selected)
        
    def importModel(self):
        """ Reads in an LDraw model file and populates this submodel with the info. """

        ldrawFile = LDrawFile(self.filename)
        ldrawFile.loadFileArray()
        submodelList = ldrawFile.getSubmodels()

        # Add any submodels found in this LDraw file to the submodel dictionary, unused and uninitialized
        if submodelList:
            global submodelDictionary
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
            
            for part in partList[PARTS_PER_STEP_MAX : ]:  # Move all but the first 5 parts to next step
                part.getStep().removePart(part)
                newPage.steps[-1].addPart(part)

            csi = newPage.steps[-1].csi

    def mergeInitialPages(self):
        
        for submodel in self.submodels:
            submodel.mergeInitialPages()
        
        if len(self.pages) < 2:
            return
        
        currentPage = self.pages[0]
        nextPage = self.pages[1]
        
        while True:   # yeah yeah, nested infinite loops of nastiness
            while True:
                nextPage.steps[0].moveToPage(currentPage, False)
                currentPage.initLayout()
                if currentPage.checkForLayoutOverlaps():  # Have overlap - move back & redo layouts
                    currentPage.steps[-1].moveToPage(nextPage, False)
                    currentPage.initLayout()
                    nextPage.initLayout()
                    break  # This page is full: move on to the next
                else:
                    tmp = nextPage.nextPage()  # No overlap - delete empty page & move on
                    self.deletePage(nextPage)
                    if tmp is None:  # At last page - all done
                        return
                    nextPage = tmp
                    
            currentPage = nextPage
            nextPage = nextPage.nextPage()
            if nextPage is None:  # At last page - all done
                return

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
        
        for p in self.pages:
            if p._row >= page._row: 
                p._row += 1

        for s in self.submodels:
            if s._row >= page._row: 
                s._row += 1

        page.subModel = self
        self.instructions.updatePageNumbers(page.number)
        self.pages.insert(page._row, page)
        if page in self.instructions.scene.items():
            self.instructions.scene.removeItem(page)  # Need to re-add page to trigger scene page layout
        self.instructions.scene.addItem(page)

    def deletePage(self, page):

        for p in self.pages:
            if p._row > page._row: 
                p._row -= 1

        for s in self.submodels:
            if s._row > page._row: 
                s._row -= 1

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

    def setPageSize(self, newPageSize):
        
        for page in self.pages:
            page.setPos(0, 0)
            page.setRect(0, 0, newPageSize.width(), newPageSize.height())
            
        for submodel in self.submodels:
            submodel.setPageSize(newPageSize)

    def getCSIList(self):
        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)
                for callout in step.callouts:
                    for step2 in callout.steps:
                        csiList.append(step2.csi)

        for submodel in self.submodels:
            csiList += submodel.getCSIList()

        return csiList

    def pageCount(self):
        pageCount = len(self.pages)
        for submodel in self.submodels:
            pageCount += submodel.pageCount()
        return pageCount

    def getPageList(self):
        pageList = list(self.pages)
        for submodel in self.submodels:
            pageList += submodel.getPageList()
        return pageList
        
    def addSubmodelImages(self):
        self.pages[0].addSubmodelImage()
        for submodel in self.submodels:
            submodel.addSubmodelImages()

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

class PartTreeItem(PartTreeItemTreeManager, QGraphicsRectItem):

    def __init__(self, parent, name):
        QGraphicsRectItem.__init__(self, parent)
        self.name = name
        self.parts = []
        self._dataString = None  # Cache data string for tree
        self.setFlags(AllFlags)
        
    def setSelected(self, selected):
        self.parts[0].setSelected(selected)

    def addPart(self, part):
        part.setParentItem(self)
        self._dataString = None
        self.parts.append(part)
        
    def removePart(self, part):
        if part in self.parts:
            self.parts.remove(part)
            self._dataString = None

class Part(PartTreeManager, QGraphicsRectItem):
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """

    itemClassName = "Part"

    def __init__(self, filename, color = 16, matrix = None, invert = False):
        QGraphicsRectItem.__init__(self)

        self.filename = filename  # Needed for save / load
        self.color = color
        self.matrix = matrix
        self.inverted = invert
        self.partOGL = None
        self._dataString = None  # Cache data string for tree

        self.displacement = []
        self.displaceDirection = None

        #self.setPos(0.0, 0.0)
        #self.setRect(0.0, 0.0, 30.0, 30.0)
        #self.setPen(QPen(Qt.black))
        self.setFlags(NoMoveFlags)

    def initializePartOGL(self):
        global partDictionary, submodelDictionary
        
        fn = self.filename
        if fn in submodelDictionary:
            self.partOGL = submodelDictionary[fn]
            if not self.partOGL.used:
                self.partOGL.loadFromLineArray()
        elif fn in partDictionary:
            self.partOGL = partDictionary[fn]
        else:
            self.partOGL = partDictionary[fn] = PartOGL(fn, loadFromFile = True)
        
    def setInversion(self, invert):
        # Inversion is annoying as hell.  
        # Possible the containing part used a BFC INVERTNEXT (invert arg)
        # Possible this part's matrix implies an inversion (det < 0)
        det = Helpers.determinant3x3([self.matrix[0:3], self.matrix[4:7], self.matrix[8:11]])
        self.inverted = (True if det < 0 else False) ^ invert
        
    def getXYZSortOrder(self):
        x, y, z = Helpers.GLMatrixToXYZ(self.matrix)
        return (-y, -z, x)

    def x(self):
        return self.matrix[12]
    
    def y(self):
        return self.matrix[13]
    
    def z(self):
        return self.matrix[14]

    def getCSI(self):
        return self.parentItem().parentItem()
    
    def getStep(self):
        return self.parentItem().parentItem().parentItem()

    def setSelected(self, selected, updatePixmap = True):
        QGraphicsRectItem.setSelected(self, selected)
        if updatePixmap:
            self.getCSI().createOGLDisplayList()

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
        p = Part(self.filename, self.color, self.matrix, self.inverted)
        p.partOGL = self.partOGL
        p.setParentItem(self.parentItem())
        p.displacement = list(self.displacement)
        p.displaceDirection = self.displaceDirection
        return p

    def contextMenuEvent(self, event):
        """ 
        This is called if any part is the target of a right click.  
        self is guaranteed to be selected.  Other stuff may be selected too, so deal.
        """

        step = self.getStep()
        menu = QMenu(self.scene().views()[0])

        menu.addAction("Create Callout from Parts", self.createCalloutSignal)

        if step.callouts:
            subMenu = menu.addMenu("Move Part to Callout")
            for callout in step.callouts:
                subMenu.addAction("Callout %d" % callout.number, lambda x = callout: self.moveToCalloutSignal(x))
        
        menu.addSeparator()
        
        needSeparator = False
        if step.getPrevStep():
            menu.addAction("Move to &Previous Step", lambda: self.moveToStepSignal(step.getPrevStep()))
            needSeparator = True
            
        if step.getNextStep():
            menu.addAction("Move to &Next Step", lambda: self.moveToStepSignal(step.getNextStep()))
            needSeparator = True

        if needSeparator:
            menu.addSeparator()

        if self.displacement:
            menu.addAction("&Increase displacement", lambda: self.displaceSignal(self.displaceDirection))
            menu.addAction("&Decrease displacement", lambda: self.displaceSignal(Helpers.getOppositeDirection(self.displaceDirection)))
        else:
            s = self.scene().undoStack
            arrowMenu = menu.addMenu("Displace With &Arrow")
            arrowMenu.addAction("Move Up", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_PageUp, Arrow(Qt.Key_PageUp))))
            arrowMenu.addAction("Move Down", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_PageDown, Arrow(Qt.Key_PageDown))))
            arrowMenu.addAction("Move Forward", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_Down, Arrow(Qt.Key_Down))))
            arrowMenu.addAction("Move Back", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_Up, Arrow(Qt.Key_Up))))
            arrowMenu.addAction("Move Left", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_Left, Arrow(Qt.Key_Left))))
            arrowMenu.addAction("Move Right", lambda: s.push(BeginDisplacementCommand(self, Qt.Key_Right, Arrow(Qt.Key_Right))))
            
        menu.exec_(event.screenPos())

    def createCalloutSignal(self):
        self.scene().undoStack.beginMacro("Create new Callout from Parts")
        step = self.getStep()
        step.addBlankCalloutSignal()
        self.moveToCalloutSignal(step.callouts[-1])
        self.scene().undoStack.endMacro()
        
    def moveToCalloutSignal(self, callout):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                selectedParts.append(item.duplicate())
        self.scene().undoStack.push(AddPartsToCalloutCommand(callout, selectedParts))
    
    def keyReleaseEvent(self, event):
        direction = event.key()
        if direction == Qt.Key_Plus:
            return self.displaceSignal(self.displaceDirection)
        if direction == Qt.Key_Minus:
            return self.displaceSignal(Helpers.getOppositeDirection(self.displaceDirection))
        self.displaceSignal(direction)

    def displaceSignal(self, direction):
        displacement = Helpers.getDisplacementOffset(direction, False, self.partOGL.getBoundingBox())
        if displacement:
            oldPos = self.displacement if self.displacement else [0.0, 0.0, 0.0]
            newPos = [oldPos[0] + displacement[0], oldPos[1] + displacement[1], oldPos[2] + displacement[2]]
            self.scene().undoStack.push(DisplacePartCommand(self, oldPos, newPos))

    def moveToStepSignal(self, destStep):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                selectedParts.append(item)

        self.scene().undoStack.push(MovePartsToStepCommand(selectedParts, self.getStep(), destStep))
        
class Arrow(Part):
    itemClassName = "Arrow"

    def __init__(self, direction):
        Part.__init__(self, "arrow", 4, None, False)
        
        self.displaceDirection = direction
        self.displacement = [0.0, 0.0, 0.0]
        
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
        
        tip1 = Primitive(4, self.tip + topEnd + joint, GL.GL_TRIANGLES)
        tip2 = Primitive(4, self.tip + joint + botEnd, GL.GL_TRIANGLES)
        base = Primitive(4, tl + tr + br + bl, GL.GL_QUADS)

        self.partOGL.primitives.append(tip1)
        self.partOGL.primitives.append(tip2)
        self.partOGL.primitives.append(base)
        self.partOGL.createOGLDisplayList()

    def data(self, index):
        x, y, z = Helpers.GLMatrixToXYZ(self.matrix)
        return "%s  (%.1f, %.1f, %.1f)" % (self.partOGL.filename, x, y, z)

    def positionToBox(self, direction, box):
        y = box.getBottomOffset()
        self.addToPosition(0, y + self.length, 0)

    def addToPosition(self, x, y, z):
        self.matrix[12] += x
        self.matrix[13] += y
        self.matrix[14] += z
        
    def setPosition(self, x, y, z):
        self.matrix[12] = x
        self.matrix[13] = y
        self.matrix[14] = z
        
    def doGLRotation(self):
        
        d = self.displaceDirection
        if d == Qt.Key_PageUp:  # Up
            GL.glRotatef(-90, 0.0, 0.0, 1.0)
            GL.glRotatef(45, 1.0, 0.0, 0.0)
        elif d == Qt.Key_PageDown:  # Down
            GL.glRotatef(90, 0.0, 0.0, 1.0)
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        elif d == Qt.Key_Left:  # Left
            GL.glRotatef(90, 0.0, 1.0, 0.0)
            GL.glRotatef(225, 1.0, 0.0, 0.0)
        elif d == Qt.Key_Right:  # Right
            GL.glRotatef(-90, 0.0, 1.0, 0.0)
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        elif d == Qt.Key_Up:  # Back
            GL.glRotatef(180, 0.0, 0.0, 1.0)
            GL.glRotatef(45, 1.0, 0.0, 0.0)
        elif d == Qt.Key_Down:  # Forward
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        if self.getCSI().rotation:
            GLHelpers.rotateView(*self.getCSI().rotation)

    def callGLDisplayList(self, useDisplacement = False):
        if not useDisplacement:
            return

        # Must be called inside a glNewList/EndList pair
        color = LDrawColors.convertToRGBA(self.color)
        if color != LDrawColors.CurrentColor:
            if self.isSelected():
                color[3] = 0.5
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        matrix = list(self.matrix)
        if self.displacement:
            matrix[12] += self.displacement[0]
            matrix[13] += self.displacement[1]
            matrix[14] += self.displacement[2]
        GL.glPushMatrix()
        GL.glMultMatrixf(matrix)
        
        #GLHelpers.drawCoordLines()
        self.doGLRotation()

        if self.isSelected():
            self.drawGLBoundingBox()

        GL.glCallList(self.partOGL.oglDispID)
        GL.glPopMatrix()

        if color != LDrawColors.CurrentColor:
            GL.glPopAttrib()

    def getLength(self):
        p = self.partOGL.primitives[-1]
        return p.points[3]

    def setLength(self, length):
        p = self.partOGL.primitives[-1]
        p.points[3] = length 
        p.points[6] = length
        self.partOGL.resetBoundingBox()
        self.partOGL.createOGLDisplayList()
    
    def adjustLength(self, offset):
        self.setLength(self.getLength() + offset)
        
    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        stack = self.scene().undoStack
        
        menu.addAction("Move &Forward", lambda: self.displaceSignal(Helpers.getOppositeDirection(self.displaceDirection)))
        menu.addAction("Move &Back", lambda: self.displaceSignal(self.displaceDirection))
        menu.addAction("&Longer", lambda: stack.push(AdjustArrowLength(self, 20)))
        menu.addAction("&Shorter", lambda: stack.push(AdjustArrowLength(self, -20)))

        menu.exec_(event.screenPos())

class Primitive(object):
    """
    Not a primitive in the LDraw sense, just a single line/triangle/quad.
    Used mainly to construct an OGL display list for a set of points.
    """

    def __init__(self, color, points, type, winding = GL.GL_CW):
        self.color = color
        self.type = type
        self.points = points
        self.winding = winding
        self.__boundingBox = None

    def getBoundingBox(self):
        if self.__boundingBox:
            return self.__boundingBox
        
        p = self.points
        box = BoundingBox(p[0], p[1], p[2])
        box.growByPoints(p[3], p[4], p[5])
        if self.type != GL.GL_LINES:
            box.growByPoints(p[6], p[7], p[8])
            if self.type == GL.GL_QUADS:
                box.growByPoints(p[9], p[10], p[11])
                
        self.__boundingBox = box
        return box

    def resetBoundingBox(self):
        self.__boundingBox = None

    def vertexIterator(self):
        p = self.points
        return (p[0], p[1], p[2]), (p[3], p[4], p[5])

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
        p = self.points
        if self.type == GL.GL_LINES:
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4f(0.0, 0.0, 0.0, 1.0)
            GL.glBegin(self.type)
            GL.glVertex3f(p[0], p[1], p[2])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glEnd()
            GL.glPopAttrib()
            return

        color = LDrawColors.convertToRGBA(self.color)

        if color != LDrawColors.CurrentColor:
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)


        if self.winding == GL.GL_CCW:
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
            
        elif self.winding == GL.GL_CW:
            normal = self.addNormal(p[0:3], p[6:9], p[3:6])
            #GL.glBegin( GL.GL_LINES )
            #GL.glVertex3f(p[3], p[4], p[5])
            #GL.glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #GL.glEnd()

            GL.glBegin(self.type)
            GL.glNormal3fv(normal)
            GL.glVertex3f(p[0], p[1], p[2])
            if self.type == GL.GL_QUADS:
                GL.glVertex3f(p[9], p[10], p[11])
            GL.glVertex3f(p[6], p[7], p[8])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glEnd()

        if color != LDrawColors.CurrentColor:
            GL.glPopAttrib()
