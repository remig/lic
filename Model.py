import math   # for sqrt
import os     # for output path creation
import time
import Image

#import OpenGL
#OpenGL.ERROR_CHECKING = False
#OpenGL.ERROR_LOGGING = False

from OpenGL import GL
from OpenGL import GLU

from OpenGL.GL.ARB.framebuffer_object import *
from OpenGL.GL.EXT.framebuffer_object import *
from OpenGL.GL.EXT.framebuffer_multisample import *
from OpenGL.GL.EXT.framebuffer_blit import *

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
import resources  # Needed for ":/resource" type paths to work

from LDrawFileFormat import *

MagicNumber = 0x14768126
FileVersion = 2

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
        self.connect(self, SIGNAL("pressed(QModelIndex)"), self.clicked)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setAutoExpandDelay(400)
        self.scene = None
        self.expandedDepth = 0

    def walkTreeModel(self, cmp, action):
        
        model = self.model()
        
        def traverse(index):
            
            if index.isValid() and cmp(index):
                action(index)
                 
            for row in range(model.rowCount(index)):
                if not index.isValid() and row == 0:
                    continue  # Special case: skip the template page
                traverse(model.index(row, 0, index))
        
        traverse(QModelIndex())

    def hideRowInstance(self, instanceType, hide):
        # instanceType can be either concrete type like PLI or 
        # itemClassString like "Page Number" (for specific QGraphicsSimpleTextItems) 

        def cmp(index):
            ptr = index.internalPointer()
            if isinstance(instanceType, str):
                return ptr.itemClassName == instanceType
            return isinstance(ptr, instanceType)

        action = lambda index: self.setRowHidden(index.row(), index.parent(), hide)
        self.walkTreeModel(cmp, action)

    def collapseAll(self):
        QTreeView.collapseAll(self)
        self.expandedDepth = 0

    def expandOneLevel(self):
        self.expandToDepth(self.expandedDepth)
        self.expandedDepth += 1

    def keyPressEvent(self, event):
        
        key = event.key()
        if key == Qt.Key_PageUp:
            self.scene.pageUp()
        elif key == Qt.Key_PageDown:
            self.scene.pageDown()
        else:
            QTreeView.keyPressEvent(self, event)
            self.clicked(self.currentIndex())
    
    def updateTreeSelection(self):
        """ This is called whenever the graphics scene is clicked """
        
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

        if QApplication.mouseButtons() == Qt.RightButton:
            return  # Ignore right clicks - they're passed on to selected item for their context menu
        
        selList = self.selectionModel().selectedIndexes()
        internalPtr = index.internalPointer()

        # Clear any existing selection from the graphics view
        self.scene.clearSelectedParts()
        self.scene.clearSelection()

        # Find the selected item's parent page, then flip to that page
        if isinstance(internalPtr, Submodel):
            self.scene.selectPage(internalPtr.pages[0].number)
        else:
            page = internalPtr.getPage()
            self.scene.selectPage(page._number)

        # Finally, select the things we actually clicked on
        partList = []
        for index in selList:
            item = index.internalPointer()
            if isinstance(item, Part):
                partList.append(item)
            else:
                item.setSelected(True)
                
        # Optimization: don't just select each parts, because selecting a part forces its CSI to redraw.
        # Instead, only redraw the CSI once, on the last part update
        if partList:
            for part in partList[:-1]:
                part.setSelected(True, False)
            partList[-1].setSelected(True, True)

    def contextMenuEvent(self, event):
        # Pass right clicks on to the item right-clicked on
        selList = self.selectionModel().selectedIndexes()
        if not selList:
            event.ignore()
            return
        
        # 'Convert' QContextMenuEvent to QGraphicsSceneContextMenuEvent
        event.screenPos = event.globalPos
        item = selList[-1].internalPointer()
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
        
        if self.cornerRadius:
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            painter.drawRoundedRect(self.rect(), self.cornerRadius, self.cornerRadius)
            if self.isSelected():
                QGraphicsRectItem.paint(self, painter, option, widget)
        else:
            QGraphicsRectItem.paint(self, painter, option, widget)
    
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
        Page.PageSize = Page.defaultPageSize
        Page.Resolution = Page.defaultResolution
        CSI.defaultScale = PLI.defaultScale = SubmodelPreview.defaultScale = 1.0
        CSI.defaultRotation = [20.0, 45.0, 0.0]
        PLI.defaultRotation = [20.0, -45.0, 0.0]
        SubmodelPreview.defaultRotation = [20.0, 45.0, 0.0]
        GlobalGLContext.makeCurrent()

    def importLDrawModel(self, filename):
        #startTime = time.time()
        
        global currentModelFilename, submodelDictionary
        currentModelFilename = filename

        self.mainModel = Submodel(self, self, filename)
        self.mainModel.importModel()
        
        self.mainModel.syncPageNumbers()
        if not self.mainModel.hasImportedSteps:
            self.mainModel.addInitialPagesAndSteps()
        
        t1, partStepCount, t2 = self.getPartDimensionListAndCount() 
        pageList = self.getPageList()
        totalCount = (len(pageList) * 2) + 11 + partStepCount
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
        self.mainModel.reOrderSubmodelPages()
        self.mainModel.syncPageNumbers()

        currentCount += 1
        yield (currentCount, "Adjusting Submodel Images")
        for page in self.mainModel.getPageList():
            page.adjustSubmodelImages()
            page.resetPageNumberPosition()

        #endTime = time.time()
        #print "Total load time: %.2f" % (endTime - startTime)
        
        yield (totalCount, "Import Complete!")

    def getModelName(self):
        return self.mainModel.filename

    def getPageList(self):
        pageList = self.mainModel.getPageList()
        pageList.sort(key = lambda x: x._number)
        return pageList

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

    def getPartDimensionListAndCount(self, reset = False):
        
        if reset:
            partList = [part for part in partDictionary.values() if (not part.isPrimitive)]
        else:
            partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        submodelList = [submodel for submodel in submodelDictionary.values() if submodel.used]
        partList += submodelList
        partList.append(self.mainModel)

        partDivCount = 50
        partStepCount = int(len(partList) / partDivCount)
        return (partList, partStepCount, partDivCount)
    
    def initPartDimensions(self, initialCurrentCount, reset = False):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        global GlobalGLContext

        partList, partStepCount, partDivCount = self.getPartDimensionListAndCount(reset)
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

    def initCSIDimensions(self, currentCount, repositionCSI = False):
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
                oldRect = csi.rect()
                result = csi.initSize(size, pBuffer)
                if result:
                    currentCount += 1
                    yield (currentCount, result)
                    if repositionCSI:
                        newRect = csi.rect()
                        dx = oldRect.width() - newRect.width()
                        dy = oldRect.height() - newRect.height()
                        csi.moveBy(dx / 2.0, dy / 2.0)
                else:
                    csiList2.append(csi)

            if len(csiList2) < 1:
                break  # All images initialized successfully
            else:
                csiList = csiList2  # Some images rendered out of frame - loop and try bigger frame
                csiList2 = []

        GlobalGLContext.makeCurrent()

    def initAllPLILayouts(self):
        
        for page in self.mainModel.pages:
            for step in page.steps:
                if step.pli:
                    step.pli.initLayout()
            page.initLayout()
        
        for submodel in submodelDictionary.values():
            for page in submodel.pages:
                for step in page.steps:
                    if step.pli:
                        step.pli.initLayout()
                page.initLayout()
        
    def initPLIPixmaps(self):
        for page in self.mainModel.pages:
            page.scaleImages()
        
        for submodel in submodelDictionary.values():
            for page in submodel.pages:
                page.scaleImages()
    
    def initSubmodelImages(self):
        for page in self.mainModel.pages:
            page.resetSubmodelImage()
            page.initLayout()
                
        for submodel in submodelDictionary.values():
            for page in submodel.pages:
                page.resetSubmodelImage()
                page.initLayout()

    def exportToPOV(self):
        global submodelDictionary
        for model in submodelDictionary.values():
            if model.used:
                model.createPng()
        self.mainModel.createPng()
        self.mainModel.exportImages()
        
    def exportImages(self, scaleFactor = 1):

        currentPageNumber = self.scene.currentPage._number
        w, h = Page.PageSize.width() * scaleFactor, Page.PageSize.height() * scaleFactor
        
        if scaleFactor > 1:
            GL.glLineWidth(1.5)  # Make part lines a bit thicker for higher res output 

        # Create non-multisample FBO that we can call glReadPixels on
        frameBuffer = glGenFramebuffersEXT(1)
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, frameBuffer)

        # non-multisample color & depth buffers
        colorBuffer = glGenRenderbuffersEXT(1)
        glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, colorBuffer)
        glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, GL.GL_RGBA, w, h)
        
        depthBuffer = glGenRenderbuffersEXT(1)
        glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, depthBuffer)
        glRenderbufferStorageEXT(GL_RENDERBUFFER_EXT, GL.GL_DEPTH_COMPONENT, w, h)

        # bind depth & color buffer to non-multisample frame buffer
        glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT, GL_RENDERBUFFER_EXT, colorBuffer);
        glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_DEPTH_ATTACHMENT_EXT, GL_RENDERBUFFER_EXT, depthBuffer);
    
        # Setup multisample framebuffer
        multisampleFrameBuffer = glGenFramebuffersEXT(1)
        glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, multisampleFrameBuffer)
    
        # multisample color & depth buffers
        multisampleColorBuffer = glGenRenderbuffersEXT(1)
        glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, multisampleColorBuffer)
        glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER_EXT, 8, GL.GL_RGBA, w, h)
        
        multisampleDepthBuffer = glGenRenderbuffersEXT (1)
        glBindRenderbufferEXT(GL_RENDERBUFFER_EXT, multisampleDepthBuffer)
        glRenderbufferStorageMultisampleEXT(GL_RENDERBUFFER_EXT, 8, GL.GL_DEPTH_COMPONENT, w, h)

        # bind multisample color & depth buffers
        glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_COLOR_ATTACHMENT0_EXT, GL_RENDERBUFFER_EXT, multisampleColorBuffer);
        glFramebufferRenderbufferEXT(GL_FRAMEBUFFER_EXT, GL_DEPTH_ATTACHMENT_EXT, GL_RENDERBUFFER_EXT, multisampleDepthBuffer);

        # Make sure multisample fbo is fully initialized
        status = glCheckFramebufferStatusEXT(GL_FRAMEBUFFER_EXT);
        if status != GL_FRAMEBUFFER_COMPLETE_EXT:
            print "Error in framebuffer activation"
            return
    
        # Render & save each page, storing the created filename to return later
        pageFileNames = []
        pageList = self.getPageList()
        for page in pageList:

            page.lockIcon.hide()
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, multisampleFrameBuffer)
            
            GLHelpers.initFreshContext(True)
            page.drawGLItemsOffscreen(QRectF(0, 0, w, h), float(scaleFactor))

            # Bind multisampled FBO for reading, regular for writing and blit away
            glBindFramebufferEXT(GL_READ_FRAMEBUFFER_EXT, multisampleFrameBuffer);
            glBindFramebufferEXT(GL_DRAW_FRAMEBUFFER_EXT, frameBuffer);
            glBlitFramebufferEXT(0, 0, w, h, 0, 0, w, h, GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST);

            # Bind the normal FBO for reading then read
            glBindFramebufferEXT(GL_FRAMEBUFFER_EXT, frameBuffer);
            data = GL.glReadPixels(0, 0, w, h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            
            # Create an image from raw pixels and save to disk - would be nice to create QImage directly here
            exportedFilename = page.getGLImageFilename()
            image = Image.fromstring("RGBA", (w, h), data)
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
            image.save(exportedFilename)

            image = QImage(w, h, QImage.Format_ARGB32)
            painter = QPainter()
            painter.begin(image)

            self.scene.selectPage(page._number)
            self.scene.render(painter, QRectF(0, 0, w, h))
            
            glImage = QImage(exportedFilename)
            painter.drawImage(QPoint(0, 0), glImage)
            painter.end()
            newName = page.getExportFilename()
            image.save(newName)
            pageFileNames.append(newName)
            page.lockIcon.show()

        # Clean up - essential for recovering main glWidget's state
        glDeleteFramebuffersEXT(1, [frameBuffer])
        glDeleteRenderbuffersEXT(1, [colorBuffer])
        glDeleteRenderbuffersEXT(1, [depthBuffer])
        
        glDeleteFramebuffersEXT(1, [multisampleFrameBuffer])
        glDeleteRenderbuffersEXT(1, [multisampleDepthBuffer])
        glDeleteRenderbuffersEXT(1, [multisampleColorBuffer])
        
        self.scene.selectPage(currentPageNumber)
        return pageFileNames

    def exportToPDF(self):

        # Create an image for each page
        pageList = self.exportImages(3)
        filename = os.path.join(config.config['PDFPath'], os.path.basename(self.filename)[:-3] + "pdf")
        
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFileName(filename)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setFullPage(True)
        printer.setResolution(Page.Resolution)
        printer.setPaperSize(QSizeF(Page.PageSize), QPrinter.DevicePixel)

        painter = QPainter()
        painter.begin(printer)
        for pageFilename in pageList:
            image = QImage(pageFilename)
            painter.drawImage(QRectF(0.0, 0.0, Page.PageSize.width(), Page.PageSize.height()), image)
            if pageFilename != pageList[-1]:
                printer.newPage()
        painter.end()
        return filename
    
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

class Page(PageTreeManager, QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """

    itemClassName = "Page"
    
    PageSize = QSize(800, 600)  # Always pixels
    Resolution = 72.0           # Always pixels / inch
    
    defaultPageSize = QSize(800, 600)
    defaultResolution = 72.0
    
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
        self.numberItem.setFlags(AllFlags)
        self.numberItem.dataText = "Page Number Label"
        self.numberItem.itemClassName = "Page Number"
        self.children.append(self.numberItem)
        
        # Setup this page's layout lock icon
        self.lockIcon = LockIcon(self)

        # Position page number in bottom right page corner
        self.resetPageNumberPosition()
        
        # Need to explicitly add this page to scene, since it has no parent
        instructions.scene.addItem(self)

    def resetPageNumberPosition(self):
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.margin)
        self.numberItem.setPos(rect.topLeft())
    
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

    def getExportFilename(self):
        return os.path.join(config.config['imgPath'], "Page_%d.png" % self._number)
    
    def getGLImageFilename(self):
        return os.path.join(config.config['GLImgPath'], "Page_%d.png" % self._number)

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
        
        for page in self.subModel.pages:  # Look forward through pages
            if page._number > self._number and page.steps:
                return page.steps[0].number

        for page in reversed(self.subModel.pages):  # Look back
            if page._number < self._number and page.steps:
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

    def removeStep(self, step):
        self.steps.remove(step)
        self.children.remove(step)

    def isEmpty(self):
        return len(self.steps) == 0 and self.submodelItem is None

    def isLocked(self):
        return self.lockIcon.isLocked

    def lock(self, isLocked):
        for child in self.getAllChildItems():
            child.setFlags(NoMoveFlags if isLocked else AllFlags)
    
    def addChild(self, index, child):

        self.children.insert(index, child)

        # Adjust the z-order of all children: first child has highest z value
        length = len(self.children)
        for i, item in enumerate(self.children):
            item.setZValue(length - i)
        self.lockIcon.setZValue(len(self.children) + 1)

    def addStepSeparator(self, index, rect = None):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        s = QGraphicsRectItem(self)
        s.setRect(rect if rect else QRectF(0, 0, 1, 1))
        s.setFlags(AllFlags)
        s.setPen(QPen(Qt.black))
        s.setBrush(QBrush(Qt.black))
        s.itemClassName = "Separator"
        s.dataText = "Step Separator"
        self.separators.append(s)
        self.addChild(index, s)
        self.scene().emit(SIGNAL("layoutChanged()"))
        return s

    def removeAllSeparators(self):
        if not self.separators:
            return
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
    
    def addSubmodelImage(self):
        self.submodelItem = SubmodelPreview(self, self.subModel)
        self.submodelItem.setPos(Page.margin)
        self.children.append(self.submodelItem)
        
    def resetSubmodelImage(self):
        if self.submodelItem:
            self.submodelItem.resetPixmap()

    def checkForLayoutOverlaps(self):
        for step in self.steps:
            if step.checkForLayoutOverlaps():
                return True
        return False
    
    def initLayout(self):

        self.lockIcon.resetPosition()
        if self.lockIcon.isLocked:
            return  # Don't make any layout changes to locked pages

        self.resetPageNumberPosition()

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

    def adjustSubmodelImages(self):

        # Check if we should shrink submodel image
        if self.submodelItem and self.submodelItem.scaling > 0.5 and self.checkForLayoutOverlaps():
            
            # Scale submodel down and try again
            newScale = self.submodelItem.scaling - 0.2
            self.submodelItem.changeScale(newScale)
            print "scaling page %d submodel down to %.2f" % (self._number, newScale)
            self.initLayout()
            self.adjustSubmodelImages()
    
    def scaleImages(self):
        for step in self.steps:
            if step.hasPLI():
                step.pli.initLayout()
            
        if self.submodelItem:
            self.resetSubmodelImage()

    def renderFinalImageWithPov(self):

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
        image.save(self.getExportFilename())
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
            elif hasattr(glItem, "isDirty") and glItem.isDirty:
                glItem.paintGL()
            
        GLHelpers.popAllGLMatrices()

    def drawGLItemsOffscreen(self, rect, f):
        
        GLHelpers.pushAllGLMatrices()
        GLHelpers.adjustGLViewport(0, 0, rect.width(), rect.height(), True)
        
        for glItem in self.glItemIterator():
            glItem.paintGL(f)
            
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

    def acceptDragAndDropList(self, dragItems, row):

        steps = [s for s in dragItems if isinstance(s, Step)]
        if not steps:
            return False
        
        print "Dropping steps: %d"  %len(steps)
        return True
            
    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        if not self.isLocked():
            menu.addAction("Auto Layout", self.initLayout)
        menu.addAction("Check for Overlaps", self.checkForLayoutOverlaps)
        menu.addSeparator()
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
        if not self.isLocked():
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

class LockIcon(QGraphicsPixmapItem):

    loaded = False
    activeOpenIcon = None
    activeCloseIcon = None
    deactiveOpenIcon = None
    deactiveCloseIcon = None
    
    def __init__(self, parent):
        QGraphicsPixmapItem.__init__(self, parent)
        
        if not LockIcon.loaded:
            LockIcon.activeOpenIcon = QPixmap(":/lock_open")
            LockIcon.activeCloseIcon = QPixmap(":/lock_close")
            LockIcon.deactiveOpenIcon = QPixmap(":/lock_grey_open")
            LockIcon.deactiveCloseIcon = QPixmap(":/lock_grey_close")
            LockIcon.loaded = True

        self.setPixmap(LockIcon.deactiveOpenIcon)
        self.resetPosition()
        self.setFlags(NoMoveFlags)
        self.setAcceptHoverEvents(True)
        self.hoverEnterEvent = lambda event: self.changeIcon(True)
        self.hoverLeaveEvent = lambda event: self.changeIcon(False)
        
        self.isLocked = False
    
    def resetPosition(self):
        self.setPos(5, Page.PageSize.height() - self.boundingRect().height() - 5)
    
    def changeIcon(self, active):
        if active:
            self.setPixmap(LockIcon.activeCloseIcon if self.isLocked else LockIcon.activeOpenIcon)
        else:
            self.setPixmap(LockIcon.deactiveCloseIcon if self.isLocked else LockIcon.deactiveOpenIcon)
            
    def mousePressEvent(self, event):
        self.isLocked = not self.isLocked
        self.parentItem().lock(self.isLocked)
        self.changeIcon(True)
        event.ignore()
    
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
        
    def paint(self, painter, option, widget = None):
        if self.isSelected():
            QGraphicsRectItem.paint(self, painter, option, widget)
    
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
            QGraphicsRectItem.paint(self, painter, option, widget)

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
        self.setFlags(NoMoveFlags if self.getPage().isLocked() else AllFlags)
        
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

    def getStep(self, number):
        for step in self.steps:
            if step.number == number:
                return step
        return None

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
            self.positionQtyLabel()
            
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
        self.qtyLabel.setFlags(NoMoveFlags if self.getPage().isLocked() else AllFlags)
        self.qtyLabel.dataText = "Quantity Label"
            
    def removeQuantityLabel(self):
        self.scene().removeItem(self.qtyLabel)
        self.qtyLabel = None

    def getQuantity(self):
        return int(self.qtyLabel.text()[:-1])

    def setQuantity(self, qty):
        if self.qtyLabel is None:
            self.addQuantityLabel()
        self.qtyLabel.setText("%dx" % qty)
        self.positionQtyLabel()

    def positionQtyLabel(self):
        r = self.qtyLabel.boundingRect()
        r.moveBottomRight(self.rect().bottomRight() - Page.margin)
        self.qtyLabel.setPos(r.topLeft())

    def contextMenuEvent(self, event):
        stack = self.scene().undoStack
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add blank Step", self.addBlankStep)
        if self.qtyLabel:
            menu.addAction("Change Quantity", self.setQuantitySignal)
            menu.addAction("Remove Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, False)))
        else:
            menu.addAction("Add Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, True)))
        if self.showStepNumbers:
            menu.addAction("Hide Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, False)))
        else:
            menu.addAction("Show Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, True)))

        menu.addSeparator()
        menu.addAction("Convert To Submodel", lambda: stack.push(CalloutToSubmodelCommand(self)))
        menu.exec_(event.screenPos())

    def setQuantitySignal(self):
        parentWidget = self.scene().views()[0]
        qty, ok = QInputDialog.getInteger(parentWidget, "Callout Quantity", "Quantity:", self.getQuantity(),
                                           0, 999, 1, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if ok:
            self.scene().undoStack.push(ChangeCalloutQtyCommand(self, qty))

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
    
    def isEmpty(self):
        return len(self.csi.parts) == 0
    
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
        if (self.csi.pos().y() + self.csi.rect().height()) > self.rect().height():
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

        if self.getPage().isLocked():
            return  # Don't layout stuff on locked pages
         
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

        csiWidth = self.csi.rect().width()
        csiHeight = self.csi.rect().height()

        if not self.callouts:
            
            x = (r.width() - csiWidth) / 2.0
            y = (r.height() - csiHeight) / 2.0
            self.csi.setPos(x, r.top() + y)
            return

        self.callouts[0].initLayout()
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

    def acceptDragAndDropList(self, dragItems, row):

        parts = [p for p in dragItems if isinstance(p, Part)]
        if not parts:
            return False
        self.scene().undoStack.push(MovePartsToStepCommand(parts, self))
        return True
    
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
            menu.addAction("Swap with Previous Step", lambda: self.swapWithStepSignal(self.getPrevStep()))
        if self.getNextStep():
            menu.addAction("Merge with Next Step", lambda: self.mergeWithStepSignal(self.getNextStep()))
            menu.addAction("Swap with Next Step", lambda: self.swapWithStepSignal(self.getNextStep()))

        menu.addSeparator()
        menu.addAction("Add blank Callout", self.addBlankCalloutSignal)

        if not self.csi.parts:
            menu.addAction("&Delete Step", lambda: undo.push(AddRemoveStepCommand(self, False)))

        menu.exec_(event.screenPos())

    def addBlankCalloutSignal(self, useSignal = True):
        number = self.callouts[-1].number + 1 if self.callouts else 1
        callout = Callout(self, number)
        callout.addBlankStep(False)
        if useSignal:
            self.scene().undoStack.push(AddRemoveCalloutCommand(callout, True))
        else:
            self.addCallout(callout)
        return callout
    
    def moveToPrevPage(self):
        stepSet = []
        for step in self.scene().selectedItems():
            if isinstance(step, Step):
                stepSet.append((step, step.parentItem(), step.parentItem().prevPage()))
        step.scene().undoStack.push(MoveStepToPageCommand(stepSet))

        if self.scene().currentPage.isEmpty():
            self.scene().undoStack.push(AddRemovePageCommand(self.scene().currentPage, False))
        
    def moveToNextPage(self):
        stepSet = []
        for step in self.scene().selectedItems():
            if isinstance(step, Step):
                stepSet.append((step, step.parentItem(), step.parentItem().nextPage()))
        step.scene().undoStack.push(MoveStepToPageCommand(stepSet))

        if self.scene().currentPage.isEmpty():
            self.scene().undoStack.push(AddRemovePageCommand(self.scene().currentPage, False))
    
    def moveToPage(self, page, useSignals = True):
        if useSignals:
            page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.parentItem().removeStep(self)
        page.addStep(self)
        if useSignals:
            page.scene().emit(SIGNAL("layoutChanged()"))

    def mergeWithStepSignal(self, step):
        scene = self.scene()
        scene.undoStack.push(MovePartsToStepCommand(self.csi.getPartList(), step))
        scene.undoStack.push(AddRemoveStepCommand(self, False))

        if scene.currentPage.isEmpty():
            scene.undoStack.push(AddRemovePageCommand(scene.currentPage, False))
            
    def swapWithStepSignal(self, step):
        stack = self.scene().undoStack
        startList = self.csi.getPartList()
        endList = step.csi.getPartList()
        stack.beginMacro("Swap Steps")
        stack.push(MovePartsToStepCommand(startList, step))
        stack.push(MovePartsToStepCommand(endList, self))
        stack.endMacro()
    
class RotateScaleSignalItem(QObject):
    
    def rotateSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.RotationDialog(parentWidget, self.rotation)
        parentWidget.connect(dialog, SIGNAL("changeRotation"), self.changeRotation)
        parentWidget.connect(dialog, SIGNAL("acceptRotation"), self.acceptRotation)
        dialog.exec_()

    def changeRotation(self, rotation):
        self.rotation = list(rotation)
        self.resetPixmap()
        
    def acceptRotation(self, oldRotation):
        action = RotateItemCommand(self, oldRotation, self.rotation)
        self.scene().undoStack.push(action)
    
    def scaleSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.ScaleDlg(parentWidget, self.scaling)
        parentWidget.connect(dialog, SIGNAL("changeScale"), self.changeScale)
        parentWidget.connect(dialog, SIGNAL("acceptScale"), self.acceptScale)
        dialog.exec_()

    def changeScale(self, newScale):
        self.scaling = newScale
        self.resetPixmap()
        
    def acceptScale(self, oldScale):
        action = ScaleItemCommand(self, oldScale, self.scaling)
        self.scene().undoStack.push(action)

class SubmodelPreview(GraphicsRoundRectItem, RotateScaleSignalItem):
    itemClassName = "SubmodelPreview"
    
    defaultScale = 1.0
    defaultRotation = [20.0, 45.0, 0.0]
    
    def __init__(self, parent, partOGL):
        GraphicsRoundRectItem.__init__(self, parent)
        self.dataText = "Submodel Preview"
        self.cornerRadius = 10
        self.rotation = [0.0, 0.0, 0.0]
        self.scaling = 1.0
        self.setFlags(AllFlags)
        self.setPartOGL(partOGL)
        
    def resetPixmap(self):
        self.partOGL.resetPixmap(self.rotation, self.scaling)
        self.setPartOGL(self.partOGL)
        self.partOGL.resetPixmap()  # Restore partOGL - otherwise all pliItems screwed
        
    def setPartOGL(self, partOGL):
        self.partOGL = partOGL
        self.partCenter = (partOGL.center.x() / self.scaling, partOGL.center.y() / self.scaling)
        self.setRect(0, 0, partOGL.width + PLI.margin.x() * 2, partOGL.height + PLI.margin.y() * 2)

    def paintGL(self, f = 1.0):
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.rect().width() / 2.0) - (self.partOGL.center.x() - self.partCenter[0])
        dy = -Page.PageSize.height() + pos.y() + (self.rect().height() / 2.0) - (self.partOGL.center.y() - self.partCenter[1])
        self.partOGL.paintGL(dx * f, dy * f, self.rotation, self.scaling * f)

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        stack = self.scene().undoStack
        menu.addAction("Rotate Submodel Image", self.rotateSignal)
        menu.addAction("Scale Submodel Image", self.scaleSignal)
        menu.exec_(event.screenPos())
    
class PLIItem(PLIItemTreeManager, QGraphicsRectItem, RotateScaleSignalItem):
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
        self.numberItem._row = 0
        self.numberItem.setFont(QFont("Arial", 10))
        self.numberItem.setFlags(AllFlags)        
        self.setQuantity(quantity)

    def __getRotation(self):
        return self.partOGL.pliRotation
    
    def __setRotation(self, rotation):
        self.partOGL.pliRotation = rotation
        
    rotation = property(fget = __getRotation, fset = __setRotation)

    def __getScaling(self):
        return self.partOGL.pliScale
    
    def __setScaling(self, scaling):
        self.partOGL.pliScale = scaling
        
    scaling = property(fget = __getScaling, fset = __setScaling)

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
        self.numberItem.setPos(0.0, part.height)  
       
        lblWidth = self.numberItem.boundingRect().width()
        lblHeight = self.numberItem.boundingRect().height()
        if part.leftInset > lblWidth:
            if part.bottomInset > lblHeight:
                self.numberItem.moveBy(0, -lblHeight)  # Label fits entirely under part: bottom left corners now match
            else:
                li = part.leftInset   # Move label up until top right corner intersects bottom left inset line
                slope = part.bottomInset / float(li)
                dy = slope * (li - lblWidth)
                self.numberItem.moveBy(0, -dy)

        # Set this item to the union of its image and qty label rects
        partRect = QRectF(0.0, 0.0, self.partOGL.width, self.partOGL.height)
        numberRect = self.numberItem.boundingRect().translated(self.numberItem.pos())
        self.setRect(partRect | numberRect)
        self.moveBy(-self.rect().x(), -self.rect().y())

    def paintGL(self, f = 1.0):
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.partOGL.width / 2.0)
        dy = -Page.PageSize.height() + pos.y() + (self.partOGL.height / 2.0)
        self.partOGL.paintGL(dx * f, dy * f, scaling = f, color = self.color)

    """
    def paint(self, painter, option, widget = None):
        QGraphicsRectItem.paint(self, painter, option, widget)
        painter.drawRect(self.boundingRect())
    """

    def resetPixmap(self):
        self.partOGL.resetPixmap()
        self.parentItem().initLayout()
        
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
        pngFile = povray.createPngFromPov(povFile, part.width, part.height, part.center, PLI.defaultScale, PLI.defaultRotation)
        self.pngImage = QImage(pngFile)

    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Rotate PLI Item", self.rotateSignal)
        menu.addAction("Scale PLI Item", self.scaleSignal)
        menu.exec_(event.screenPos())

class PLI(PLITreeManager, GraphicsRoundRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """
    itemClassName = "PLI"

    defaultScale = 1.0
    defaultRotation = [20.0, -45.0, 0.0]
    margin = QPointF(15, 15)

    def __init__(self, parent):
        GraphicsRoundRectItem.__init__(self, parent)

        self.pliItems = []  # {(part filename, color): PLIItem instance}

        self.dataText = "PLI"  # String displayed in Tree - reimplement data(self, index) to override
        
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

    def changePartColor(self, part, oldColor, newColor):
        part.color = oldColor
        self.removePart(part)
        part.color = newColor
        self.addPart(part)
    
    def resetPixmap(self):
        
        for partOGL in set([item.partOGL for item in self.pliItems]):
            partOGL.resetPixmap()
        self.initLayout()
    
    def initLayout(self):
        """
        Allocate space for all parts in this PLI, and choose a decent layout.
        This is the initial algorithm used to layout a PLI.
        """

        self.setPos(0.0, 0.0)

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            self.setRect(QRectF())
            return

        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for item in self.pliItems:
            item.initLayout()
            
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

class CSI(CSITreeManager, QGraphicsRectItem, RotateScaleSignalItem):
    """ Construction Step Image.  Includes border and positional info. """
    itemClassName = "CSI"

    defaultScale = 1.0
    defaultRotation = [20.0, 45.0, 0.0]

    def __init__(self, step):
        QGraphicsRectItem.__init__(self, step)

        self.center = QPointF()
        self.oglDispID = UNINIT_GL_DISPID
        self.setFlags(AllFlags)
        self.setPen(QPen(Qt.NoPen))

        self.rotation = [0.0, 0.0, 0.0]
        self.scaling = 1.0
        
        self.parts = []
        self.arrows = []
        self.isDirty = True

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

    def paintGL(self, f = 1.0):
        """ 
        Assumes a current GL context.  Assumes that context has been transformed so the
        view runs from (0,0) to page width & height with (0,0) in the bottom left corner.
        """
         
        if self.isDirty:
            self.resetPixmap()
            self.isDirty = False
         
        GLHelpers.pushAllGLMatrices()
        
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.rect().width() / 2.0) + self.center.x()
        dy = -Page.PageSize.height() + pos.y() + (self.rect().height() / 2.0) + self.center.y()
        GLHelpers.rotateToView(CSI.defaultRotation, CSI.defaultScale * self.scaling * f, dx * f, dy * f, 0.0)
        GLHelpers.rotateView(*self.rotation)

        GL.glCallList(self.oglDispID)
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

        for p in [x for x in self.parts if not x.parts]:  # Delete empty part item groups
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

        params = GLHelpers.initImgSize(size, self.oglDispID, filename, CSI.defaultScale * self.scaling, CSI.defaultRotation, self.rotation, pBuffer)
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
        pngFile = povray.createPngFromPov(povFile, self.rect().width(), self.rect().height(), self.center, CSI.defaultScale * self.scaling, CSI.defaultRotation)
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
        menu.addAction("Rotate CSI", self.rotateSignal)
        menu.addAction("Scale CSI", self.scaleSignal)
        
        if self.parentItem().getNextStep():
            if self.rotation != [0.0, 0.0, 0.0]:
                menu.addAction("Copy Rotation to next X CSIs...", lambda: self.copyRotationScaleToNextCSIs(True))
            if self.scaling != 1.0:
                menu.addAction("Copy Scaling to next X CSIs...", lambda: self.copyRotationScaleToNextCSIs(False))

        menu.addSeparator()
        
        arrowMenu = menu.addMenu("Select Part")
        for part in self.getPartList():
            text = "%s - %s" % (part.partOGL.name, LDrawColors.getColorName(part.color))
            arrowMenu.addAction(text, lambda p = part: self.selectPart(p))
        arrowMenu.addAction("Select All", self.selectAllParts)
        
        menu.exec_(event.screenPos())
        
    def selectPart(self, part):
        self.scene().clearSelectedParts()
        self.scene().clearSelection()
        part.setSelected(True)
        
    def selectAllParts(self):
        self.scene().clearSelectedParts()
        self.scene().clearSelection()
        for part in self.getPartList():
            part.setSelected(True)

    def copyRotationScaleToNextCSIs(self, doRotation):

        # Build list of CSIs that need updating
        csiList = []
        step = self.parentItem().getNextStep()
        while step is not None:
            csiList.append(step.csi)
            step = step.getNextStep()

        # Get number of CSIs to update from user
        text = "Rotate" if doRotation else "Scale"
        parentWidget = self.scene().views()[0]
        i, ok = QInputDialog.getInteger(parentWidget, "CSI Count", text + " next CSIs:", 
                        1, 1, len(csiList), 1, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if not ok:
            return

        # Apply rotation | scaling to next chosen CSIs  
        self.scene().undoStack.beginMacro("%s next %d CSI%s" % (text, i, 's' if i > 1 else ''))
        for csi in csiList[0:i]:
            if doRotation:
                oldRotation = list(csi.rotation)
                csi.rotation = list(self.rotation)
                csi.acceptRotation(oldRotation)
            else:
                oldScaling = csi.scaling
                csi.scaling = self.scaling
                csi.acceptScale(oldScaling)
                
        self.scene().undoStack.endMacro()
    
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
        self._boundingBox = None
        
        self.pliScale = 1.0
        self.pliRotation = [0.0, 0.0, 0.0]

        self.width = self.height = -1
        self.leftInset = self.bottomInset = -1
        self.center = QPointF()

        if filename and loadFromFile:
            self.loadFromFile()

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

    def resetPixmap(self, extraRotation = None, extraScale = None):
        
        global GlobalGLContext
        GlobalGLContext.makeCurrent()
        self.createOGLDisplayList()
        sizes = [128, 256, 512, 1024, 2048]
        self.width, self.height, self.center, self.leftInset, self.bottomInset = [0] * 5

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            rotation = extraRotation if extraRotation else self.pliRotation
            scaling = extraScale if extraScale else self.pliScale
            if self.initSize(size, pBuffer, rotation, scaling):
                break

        GlobalGLContext.makeCurrent()

    def initSize(self, size, pBuffer, extraRotation = [0.0, 0.0, 0.0], extraScale = 1.0):
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
        rotation = SubmodelPreview.defaultRotation if self.isSubmodel else PLI.defaultRotation
        scaling = SubmodelPreview.defaultScale if self.isSubmodel else PLI.defaultScale
        params = GLHelpers.initImgSize(size, self.oglDispID, self.filename, scaling * extraScale, rotation, extraRotation, pBuffer)
        if params is None:
            return False

        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def paintGL(self, dx, dy, rotation = [0.0, 0.0, 0.0], scaling = 1.0, color = None):
         
        GLHelpers.pushAllGLMatrices()
        
        dr = SubmodelPreview.defaultRotation if self.isSubmodel else PLI.defaultRotation
        ds = SubmodelPreview.defaultScale if self.isSubmodel else PLI.defaultScale

        dx += self.center.x() * scaling
        dy += self.center.y() * scaling
        
        if color is not None:  # Color means we're drawing a PLIItem, so apply PLI specific scale & rotation
            ds *= self.pliScale
        
        GLHelpers.rotateToView(dr, ds * scaling, dx, dy, 0.0)
        GLHelpers.rotateView(*rotation)
        
        if color is not None:

            GLHelpers.rotateView(*self.pliRotation)
            
            colorRGB = LDrawColors.convertToRGBA(color)
            if colorRGB == LDrawColors.CurrentColor:
                colorRGB = LDrawColors.colors[2][:4]
            GL.glColor4fv(colorRGB)

        GL.glCallList(self.oglDispID)
        GLHelpers.popAllGLMatrices()

    def getBoundingBox(self):
        if self._boundingBox:
            return self._boundingBox
        
        box = None
        for primitive in self.primitives:
            p = primitive.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p)
                else:
                    box = p.copy()
            
        for part in self.parts:
            p = part.partOGL.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p, part.matrix)
                else:
                    box = p.copy(part.matrix)

        self._boundingBox = box
        return box

    def resetBoundingBox(self):
        for primitive in self.primitives:
            primitive.resetBoundingBox()
        for part in self.parts:
            part.partOGL.resetBoundingBox()
        self._boundingBox = None

class BoundingBox(object):
    
    def __init__(self, x = 0.0, y = 0.0, z = 0.0):
        self.x1 = self.x2 = x
        self.y1 = self.y2 = y
        self.z1 = self.z2 = z

    def __str__(self):
        #return "x1: %.2f, x2: %.2f,  y1: %.2f, y2: %.2f,  z1: %.2f, z2: %.2f" % (self.x1, self.x2, self.y1, self.y2, self.z1, self.z2)
        return "%.0f %.0f | %.0f %.0f | %.0f %.0f" % (self.x1, self.x2, self.y1, self.y2, self.z1, self.z2)
    
    def copy(self, matrix = None):
        b = BoundingBox()
        if matrix:
            b.x1, b.y1, b.z1 = self.transformPoint(matrix,self.x1, self.y1, self.z1)
            b.x2, b.y2, b.z2 = self.transformPoint(matrix,self.x2, self.y2, self.z2)
            if b.y1 > b.y2:
                b.y1, b.y2 = b.y2, b.y1
        else:
            b.x1, b.y1, b.z1 = self.x1, self.y1, self.z1
            b.x2, b.y2, b.z2 = self.x2, self.y2, self.z2
        return b
        
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
        
    def growByBoudingBox(self, box, matrix = None):
        if matrix:
            if matrix[5] < 0:
                self.growByPoints(*self.transformPoint(matrix, box.x1, box.y2, box.z1))
                self.growByPoints(*self.transformPoint(matrix, box.x2, box.y1, box.z2))
            else:
                self.growByPoints(*self.transformPoint(matrix, box.x1, box.y1, box.z1))
                self.growByPoints(*self.transformPoint(matrix, box.x2, box.y2, box.z2))
        else:
            self.growByPoints(box.x1, box.y1, box.z1)
            self.growByPoints(box.x2, box.y2, box.z2)

    def transformPoint(self, matrix, x, y, z):
        x2 = (matrix[0] * x) + (matrix[4] * y) + (matrix[8] * z) + matrix[12]
        y2 = (matrix[1] * x) + (matrix[5] * y) + (matrix[9] * z) + matrix[13]
        z2 = (matrix[2] * x) + (matrix[6] * y) + (matrix[10] * z) + matrix[14]
        return (x2, y2, z2)
    
    def xSize(self):
        return abs(self.x2 - self.x1)

    def ySize(self):
        return abs(self.y2 - self.y1)

    def zSize(self):
        return abs(self.z2 - self.z1)
    
class Submodel(SubmodelTreeManager, PartOGL):
    """ A Submodel is just a PartOGL that also has pages & steps, and can be inserted into a tree. """
    itemClassName = "Submodel"

    def __init__(self, parent = None, instructions = None, filename = "", lineArray = None):
        PartOGL.__init__(self, filename)

        self.instructions = instructions
        self.lineArray = lineArray
        self.used = False
        self.hasImportedSteps = False

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
            if isValidStepLine(line):
                self.hasImportedSteps = True
                newPage = self.appendBlankPage()
            if isValidPartLine(line):
                self.addPartFromLine(lineToPart(line), line)

    def addInitialPagesAndSteps(self):

        # Add one step for every 5 parts, and one page per step
        # At this point, if model had no steps (assumed for now), we have one page per submodel
        PARTS_PER_STEP_MAX = 5
        
        for submodel in self.submodels:
            submodel.addInitialPagesAndSteps()

        csi  = self.pages[0].steps[0].csi
        while csi.partCount() > 0:
            
            partList = csi.getPartList()
            #partList.sort(key = lambda x: x.getXYZSortOrder())
            partList.sort(cmp = Helpers.compareParts)
            
            currentPart = 0
            part = partList[currentPart]
            y, dy = part.by(), part.ySize()
            currentPart = 1
            
            if len(partList) > 1:
                
                # Advance part list splice point forward until we find the next 'layer' of parts
                nextPart = partList[currentPart]
                while y == nextPart.by() and abs(dy - nextPart.ySize()) <= 4.0:
                    currentPart += 1
                    if currentPart >= len(partList):
                        break
                    nextPart = partList[currentPart]
                    
                if currentPart > PARTS_PER_STEP_MAX:
                    
                    # Have lots of parts in this layer: keep most popular part here, bump rest to next step
                    partCounts = {}
                    for part in partList[:currentPart]:
                        if part.partOGL.name in partCounts:
                            partCounts[part.partOGL.name] += 1
                        else:
                            partCounts[part.partOGL.name] = 1
                    popularPartName = max(partCounts, key = partCounts.get)
                    partList = [x for x in partList[:currentPart] if x.partOGL.name != popularPartName] + partList[currentPart:]
                    currentPart = 0
                    
                elif currentPart == 1:
                    
                    # Have only one part in this layer: search forward until we hit a layer with several parts
                    part = partList[0]
                    nextPart = partList[1]
                    while (abs(part.by2() - nextPart.by()) <= 4.0) and \
                          (currentPart < PARTS_PER_STEP_MAX - 1) and \
                          (currentPart < len(partList) - 1):
                        part = partList[currentPart]
                        nextPart = partList[currentPart + 1]
                        currentPart += 1
                        
                    if currentPart > 1:
                        # Add an up displacement to last part, if it's basically above previous part
                        p1 = partList[currentPart - 1]
                        p2 = partList[currentPart]
                        px1, pz1, px2, pz2 = p1.x(), p1.z(), p2.x(), p2.z()
                        if abs(px1 - px2) < 2 and abs(pz1 - pz2) < 2:
                            p2.addNewDisplacement(Qt.Key_PageUp)
                        currentPart += 1
            
            if len(partList[currentPart: ]) == 0:
                break  # All done

            # Create a new page, give it a step, then push all remaining parts to that step
            newPage = Page(self, self.instructions, self.pages[-1]._number + 1, self.pages[-1]._row + 1)
            newPage.addBlankStep()
            self.addPage(newPage)
            
            for part in partList[currentPart: ]:  # Move all but the first x parts to next step
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
                currentPage.initLayout()  # TODO: Try both horizontal and vertical layout here
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

    def reOrderSubmodelPages(self):
        """ Reorder the tree so a submodel is right before the page it's used on """
        for submodel in self.submodels:
            submodel.reOrderSubmodelPages()
            
        for submodel in self.submodels:
            page = self.findSubmodelStep(submodel).getPage()
            if page is None or submodel._row == page._row - 1:
                continue  # submodel not used or in right spot
            
            self.removeRow(submodel._row)
            newRow = page._row
            self.addRow(newRow)
            submodel._row = newRow

    def addRow(self, row):
        for page in [p for p in self.pages if p._row >= row]:
            page._row += 1
        for s in [p for p in self.submodels if p._row >= row]:
            s._row += 1
    
    def removeRow(self, row):
        for page in [p for p in self.pages if p._row > row]:
            page._row -= 1
        for s in [p for p in self.submodels if p._row > row]:
            s._row -= 1
    
    def addSubmodel(self, submodel):
        # Assume Submodel already exists as a Part on an appropriate Step

        step = self.findSubmodelStep(submodel)
        
        if step is None:  # Submodel doesn't live here - try existing submodels
            for model in self.submodels:
                model.addSubmodel(submodel)
        else:
            submodel._parent = self
            submodel._row = self.rowCount()
            self.submodels.append(submodel)
            self.reOrderSubmodelPages()
            self.instructions.mainModel.syncPageNumbers()
            for page in submodel.pages:
                self.instructions.scene.addItem(page)
    
    def removeSubmodel(self, submodel):
        self.removeRow(submodel._row)
        self.submodels.remove(submodel)
        for page in submodel.pages:
            page.scene().removeItem(page)
        self.instructions.mainModel.syncPageNumbers()
        submodel._parent = None

    def findSubmodelStep(self, submodel):
        for page in self.pages:
            for step in page.steps:
                if submodel in [part.partOGL for part in step.csi.getPartList()]:
                    return step
        return None
     
    def syncPageNumbers(self, firstPageNumber = 1):

        rowList = self.pages + self.submodels
        rowList.sort(key = lambda x: x._row)

        pageNumber = firstPageNumber
        for item in rowList:
            if isinstance(item, Page):
                item.number = pageNumber
                pageNumber += 1
            elif isinstance(item, Submodel):
                pageNumber = item.syncPageNumbers(pageNumber)

        return pageNumber
    
    def appendBlankPage(self):

        if not self.pages and not self.submodels:
            row = 0
        else:
            row = 1 + max(self.pages[-1]._row if self.pages else 0, self.submodels[-1]._row if self.submodels else 0)
            
        pageNumber = self.pages[-1].number + 1 if self.pages else 1
        page = Page(self, self.instructions, pageNumber, row)
        for p in self.pages[page._row : ]:
            p._row += 1
        self.pages.insert(page._row, page)
        page.addBlankStep()
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

        index = len([p for p in self.pages if p._row < page._row])
        self.pages.insert(index, page)

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
            page.setRect(0, 0, newPageSize.width(), newPageSize.height())
            page.initLayout()
            
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
            page.renderFinalImageWithPov()

        for submodel in self.submodels:
            submodel.exportImages(widget)

    def createPng(self):

        datFile = os.path.join(config.config['datPath'], self.filename)

        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            for part in self.parts:
                part.exportToLDrawFile(fh)
            fh.close()

        povFile = l3p.createPovFromDat(datFile)
        pngFile = povray.createPngFromPov(povFile, self.width, self.height, self.center, PLI.defaultScale, PLI.defaultRotation)
        self.pngImage = QImage(pngFile)

    def contextMenuEvent(self, event):

        menu = QMenu()
        menu.addAction("Change Submodel to Callout", self.convertToCalloutSignal)
        menu.exec_(event.screenPos())
        
    def convertToCalloutSignal(self):
        self.pages[0].scene().undoStack.push(SubmodelToCalloutCommand(self))
        
class PartTreeItem(PartTreeItemTreeManager, QGraphicsRectItem):
    itemClassName = "Part Tree Item"

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
        b = self.getPartBoundingBox()
        return (-b.y1, b.ySize(), -b.z1, b.x1)

    def getPartBoundingBox(self):
        m = list(self.matrix)
        if self.displacement:
            m[12] += self.displacement[0]
            m[13] += self.displacement[1]
            m[14] += self.displacement[2]

        return self.partOGL.getBoundingBox().copy(m)
    
    def getXYZ(self):
        return [self.matrix[12], self.matrix[13], self.matrix[14]]
    
    def bx(self):
        return self.getPartBoundingBox().x1

    def by(self):
        return self.getPartBoundingBox().y2

    def bz(self):
        return self.getPartBoundingBox().z1

    def bx2(self):
        return self.getPartBoundingBox().x2

    def by2(self):
        return self.getPartBoundingBox().y1

    def bz2(self):
        return self.getPartBoundingBox().z2

    def x(self):
        return self.matrix[12]
    
    def y(self):
        return self.matrix[13]
    
    def z(self):
        return self.matrix[14]

    def getXYZSize(self):
        return [self.xSize(), self.ySize(), self.zSize()]
    
    def xSize(self):
        return self.getPartBoundingBox().xSize()

    def ySize(self):
        return self.getPartBoundingBox().ySize()

    def zSize(self):
        return self.getPartBoundingBox().zSize()
    
    def getCSI(self):
        return self.parentItem().parentItem()
    
    def getStep(self):
        return self.parentItem().parentItem().parentItem()

    def setSelected(self, selected, updatePixmap = True):
        QGraphicsRectItem.setSelected(self, selected)
        if updatePixmap:
            self.getCSI().createOGLDisplayList()

    def addNewDisplacement(self, direction):
        
        self.displaceDirection = direction
        self.displacement = Helpers.getDisplacementOffset(direction, True, self.partOGL.getBoundingBox())
        
        self.displaceArrow = Arrow(direction)
        self.displaceArrow.setPosition(*Helpers.GLMatrixToXYZ(self.matrix))
        self.displaceArrow.setLength(Helpers.getOffsetFromPart(self))
        self.getCSI().addArrow(self.displaceArrow)
        self._dataString = None
    
    def removeDisplacement(self):
        self.displaceDirection = None
        self.displacement = []
        self.getCSI().removeArrow(self.displaceArrow)
        self._dataString = None
        
    def isSubmodel(self):
        return isinstance(self.partOGL, Submodel)

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
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4f(1.0, 0.0, 0.0, 1.0)
            self.drawGLBoundingBox()
            GL.glPopAttrib()

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
            #menu.addAction("&Increase displacement", lambda: self.displaceSignal(self.displaceDirection))
            #menu.addAction("&Decrease displacement", lambda: self.displaceSignal(Helpers.getOppositeDirection(self.displaceDirection)))
            menu.addAction("&Change displacement", self.adjustDisplaceSignal)
            menu.addAction("&Remove displacement", lambda: self.displaceSignal(None))
        else:
            s = self.scene().undoStack
            arrowMenu = menu.addMenu("Displace With &Arrow")
            arrowMenu.addAction("Move Up", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_PageUp)))
            arrowMenu.addAction("Move Down", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_PageDown)))
            arrowMenu.addAction("Move Forward", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_Down)))
            arrowMenu.addAction("Move Back", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_Up)))
            arrowMenu.addAction("Move Left", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_Left)))
            arrowMenu.addAction("Move Right", lambda: s.push(BeginEndDisplacementCommand(self, Qt.Key_Right)))
            
        menu.addSeparator()
        menu.addAction("Change Color", self.changeColorSignal)
        
        menu.exec_(event.screenPos())

    def createCalloutSignal(self):
        self.scene().undoStack.beginMacro("Create new Callout from Parts")
        step = self.getStep()
        callout = step.addBlankCalloutSignal()
        self.moveToCalloutSignal(callout)
        step.initLayout()
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
        if direction:
            displacement = Helpers.getDisplacementOffset(direction, False, self.partOGL.getBoundingBox())
            if displacement:
                oldPos = self.displacement if self.displacement else [0.0, 0.0, 0.0]
                newPos = [oldPos[0] + displacement[0], oldPos[1] + displacement[1], oldPos[2] + displacement[2]]
                self.scene().undoStack.push(DisplacePartCommand(self, oldPos, newPos))
        else:
            # Remove any displacement
            self.scene().undoStack.push(BeginEndDisplacementCommand(self, self.displaceDirection, end = True))

    def adjustDisplaceSignal(self):
            
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.DisplaceDlg(parentWidget, self.displacement, self.displaceDirection)
        parentWidget.connect(dialog, SIGNAL("changeDisplacement"), self.changeDisplacement)
        parentWidget.connect(dialog, SIGNAL("acceptDisplacement"), self.acceptDisplacement)
        dialog.exec_()
        
    def changeDisplacement(self, displacement, changeArrow):
        self.displacement = displacement
        self.getCSI().resetPixmap()

    def acceptDisplacement(self, oldDisplacement, changeArrow):
        self.scene().undoStack.push(DisplacePartCommand(self, oldDisplacement, self.displacement))

    def moveToStepSignal(self, destStep):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                selectedParts.append(item)

        currentStep = self.getStep()
        self.scene().undoStack.push(MovePartsToStepCommand(selectedParts, destStep))
        
        currentPage = currentStep.getPage()
        if currentStep.isEmpty():
            self.scene().undoStack.push(AddRemoveStepCommand(currentStep, False))
            
        if currentPage.isEmpty():
            self.scene().undoStack.push(AddRemovePageCommand(currentPage, False))
            
    def changeColorSignal(self):
        self.scene().clearSelection()
        self.getCSI().isDirty = True
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.LDrawColorDialog(parentWidget, self.color)
        parentWidget.connect(dialog, SIGNAL("changeColor"), self.changeColor)
        parentWidget.connect(dialog, SIGNAL("acceptColor"), self.acceptColor)
        dialog.exec_()
        
    def changeColor(self, newColor):
        self.color = newColor
        self.getCSI().isDirty = True
        self.scene().update()
    
    def acceptColor(self, oldColor):
        action = ChangePartColorCommand(self, oldColor, self.color)
        self.scene().undoStack.push(action)
        
class Arrow(Part):
    itemClassName = "Arrow"

    def __init__(self, direction):
        Part.__init__(self, "arrow", 4, None, False)
        
        self.displaceDirection = direction
        self.displacement = [0.0, 0.0, 0.0]
        self.axisRotation = 0.0
        
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

        if self.axisRotation:
            GL.glRotatef(self.axisRotation, 1.0, 0.0, 0.0)

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
        self._dataString = None
    
    def adjustLength(self, offset):
        self.setLength(self.getLength() + offset)
        
    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        stack = self.scene().undoStack
        
        #menu.addAction("Move &Forward", lambda: self.displaceSignal(Helpers.getOppositeDirection(self.displaceDirection)))
        #menu.addAction("Move &Back", lambda: self.displaceSignal(self.displaceDirection))
        #menu.addAction("&Longer", lambda: stack.push(AdjustArrowLength(self, 20)))
        #menu.addAction("&Shorter", lambda: stack.push(AdjustArrowLength(self, -20)))
        menu.addAction("&Change Position and Length", self.adjustDisplaceSignal)

        menu.exec_(event.screenPos())

    def adjustDisplaceSignal(self):
            
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.ArrowDisplaceDlg(parentWidget, self)
        parentWidget.connect(dialog, SIGNAL("changeDisplacement"), self.changeDisplacement)
        parentWidget.connect(dialog, SIGNAL("changeLength"), self.changeLength)
        parentWidget.connect(dialog, SIGNAL("changeRotation"), self.changeRotation)
        parentWidget.connect(dialog, SIGNAL("accept"), self.accept)
        dialog.exec_()
        
    def changeDisplacement(self, displacement):
        self.displacement = displacement
        self.getCSI().resetPixmap()

    def changeLength(self, length):
        self.setLength(length)
        self.getCSI().resetPixmap()
        
    def changeRotation(self, rotation):
        self.axisRotation = rotation
        self.getCSI().resetPixmap()

    def accept(self, oldDisplacement, oldLength, oldRotation):
        stack = self.scene().undoStack
        stack.beginMacro("Change Arrow Position")
        self.scene().undoStack.push(DisplacePartCommand(self, oldDisplacement, self.displacement))
        self.scene().undoStack.push(AdjustArrowLength(self, oldLength, self.getLength()))
        self.scene().undoStack.push(AdjustArrowRotation(self, oldRotation, self.axisRotation))
        stack.endMacro()

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
        self._boundingBox = None

    def getBoundingBox(self):
        if self._boundingBox:
            return self._boundingBox
        
        p = self.points
        box = BoundingBox(p[0], p[1], p[2])
        box.growByPoints(p[3], p[4], p[5])
        if self.type != GL.GL_LINES:
            box.growByPoints(p[6], p[7], p[8])
            if self.type == GL.GL_QUADS:
                box.growByPoints(p[9], p[10], p[11])
                
        self._boundingBox = box
        return box

    def resetBoundingBox(self):
        self._boundingBox = None

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
