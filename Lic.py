#from __future__ import division
import random
import sys
import math
import os.path

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from Model import *
import LicTreeModel
import LicBinaryReader
import LicBinaryWriter
import LicTemplate
import config
import l3p
import povray
import LicDialogs
import LicUndoActions
import Layout
import GLHelpers

__version__ = 0.1

class LicGraphicsScene(QGraphicsScene):

    PageViewContinuous = -1
    PageViewContinuousFacing = -2
        
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)
        self.scaleFactor = 1.0
        self.pagesToDisplay = 1
        self.currentPage = None
        self.pages = []
        self.guides = []

    def clearSelectedParts(self):
        partList = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                partList.append(item)
        if partList:
            for part in partList[:-1]:
                part.setSelected(False, False)
            partList[-1].setSelected(False, True)

    def clear(self):
        QGraphicsScene.clear(self)
        self.pagesToDisplay = 1
        self.currentPage = None
        self.pages = []
        self.guides = []

    def drawForeground(self, painter, rect):
        GLHelpers.initFreshContext(False)
        for page in self.pages:
            if page.isVisible() and rect.intersects(page.rect().translated(page.pos())):
                page.drawGLItems(painter, rect)
    
    def pageUp(self):
        self.selectPage(max(1, self.currentPage._number - 1))

    def pageDown(self):
        self.selectPage(min(self.pages[-1]._number, self.currentPage._number + 1))

    def getSelectedPage(self):
        return self.currentPage._number
    
    def selectFirstPage(self):
        self.selectPage(1)

    def selectLastPage(self):
        self.selectPage(self.pages[-1]._number)

    def selectPage(self, pageNumber):
        for page in self.pages:
            if self.pagesToDisplay == 1 and page._number == pageNumber:
                page.setPos(0, 0)
                page.show()
                self.currentPage = page
            elif self.pagesToDisplay == 2 and page._number == pageNumber:
                page.setPos(10, 0)
                page.show()
                self.currentPage = page
            elif self.pagesToDisplay == 2 and page._number == pageNumber + 1:
                page.show()
                page.setPos(Page.PageSize.width() + 20, 0)
            elif self.pagesToDisplay == self.PageViewContinuous or self.pagesToDisplay == self.PageViewContinuousFacing:
                if page._number == pageNumber:
                    self.currentPage = page
            else:
                page.hide()
                page.setPos(0, 0)
            if self.pagesToDisplay == 2 and pageNumber == self.pages[-1]._number:
                self.pages[-1].setPos(Page.PageSize.width() + 20, 0)
                self.pages[-1].show()
                self.pages[-2].setPos(10, 0)
                self.pages[-2].show()
                
        self.scrollToPage(self.currentPage)

    def selectionChanged(self):
        selList = self.selectedItems()
        if self.pagesToDisplay == 1 or not selList or isinstance(selList[-1], Guide):
            return
        self.scrollToPage(self.selectedItems()[-1].getPage())
    
    def scrollToPage(self, page):
        view = self.views()[0]
        view.setInteractive(False)
        view.centerOn(page)
        view.setInteractive(True)
        
    def showOnePage(self):
        self.pagesToDisplay = 1
        self.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        for page in self.pages:
            page.hide()
            page.setPos(0.0, 0.0)
        if self.currentPage:
            self.selectPage(self.currentPage._number)
    
    def showTwoPages(self):
        if len(self.pages) < 2:
            return self.showOnePage()

        self.pagesToDisplay = 2
        self.setSceneRect(0, 0, (Page.PageSize.width() * 2) + 30, Page.PageSize.height() + 20)

        for page in self.pages:
            page.hide()
            page.setPos(0, 0)

        index = self.pages.index(self.currentPage)
        if self.currentPage == self.pages[-1]:
            p1 = self.pages[index - 1]
            p2 = self.currentPage
        else:
            p1 = self.currentPage
            p2 = self.pages[index + 1]
        
        p1.setPos(10, 0)
        p1.show()
        p2.setPos(Page.PageSize.width() + 20, 0)
        p2.show()

    def continuous(self):
        self.pagesToDisplay = self.PageViewContinuous
        pc = len(self.pages)
        ph = Page.PageSize.height()
        height = (10 * (pc + 1)) + (ph * pc)
        self.setSceneRect(0, 0, Page.PageSize.width() + 20, height)
        
        for guide in self.guides:
            if guide.orientation == Layout.Vertical:
                guide.setLength(height)
                
        for i, page in enumerate(self.pages):
            page.setPos(10, (10 * (i + 1)) + (ph * i))
            page.show()
    
    def continuousFacing(self):
        if len(self.pages) < 3:
            return self.continuous()
        self.pagesToDisplay = self.PageViewContinuousFacing
        pw = Page.PageSize.width()
        ph = Page.PageSize.height()
        rows = sum(divmod(len(self.pages) - 1, 2)) + 1
        width = pw + pw + 30
        height = (10 * (rows + 1)) + (ph * rows)
        self.setSceneRect(0, 0, width, height)
        
        for guide in self.guides:
            if guide.orientation == Layout.Vertical:
                guide.setLength(height)
            else:
                guide.setLength(width)
            
        self.pages[0].setPos(10, 10)  # Template page first
        self.pages[0].show()
        
        for i, page in enumerate(self.pages[1:]):
            i += 2
            x = 10 + ((pw + 10) * (i % 2))
            y = (10 * ((i // 2) + 1)) + (ph * (i // 2))
            page.setPos(x, y)
            page.show()
    
    def getPagesToDisplay(self):
        return self.pagesToDisplay
    
    def setPagesToDisplay(self, pagesToDisplay):
        if pagesToDisplay == self.PageViewContinuous:
            return self.continuous()
        if pagesToDisplay == self.PageViewContinuousFacing:
            return self.continuousFacing()
        if pagesToDisplay == 2:
            return self.showTwoPages()
        return self.showOnePage()

    def addItem(self, item):
        QGraphicsScene.addItem(self, item)
        if not isinstance(item, Page):
            return
        self.pages.append(item)
        self.pages.sort(key = lambda x: x._number)
        self.setPagesToDisplay(self.pagesToDisplay)
        
    def removeItem(self, item):
        QGraphicsScene.removeItem(self, item)
        if not isinstance(item, Page):
            return
        if isinstance(item, Page) and item in self.pages:
            self.pages.remove(item)
            if self.pagesToDisplay == self.PageViewContinuous:
                self.continuous()
            elif self.pagesToDisplay == self.PageViewContinuousFacing:
                self.continuousFacing()

    def removeAllGuides(self):
        self.undoStack.beginMacro("Remove all guides")
        for guide in list(self.guides):
            self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, guide, False))
        self.undoStack.endMacro()

    def addGuide(self, orientation, pos):
        guide = Guide(orientation)
        guide.setPos(pos)
        self.guides.append(guide)
        self.addItem(guide)

    def addNewGuide(self, orientation):
        self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, Guide(orientation), True))

    def snapToGuides(self, item):
        snapDistance = 30
        dx = dy = nearestX = nearestY = 100.0
        
        itemPt1 = item.mapToScene(item.mapFromParent(item.pos())) # pos is in item.parent coordinates
        itemPt2 = itemPt1 + QPointF(item.boundingRect().width(), item.boundingRect().height())
        
        def snap(nearest, current, d1, d2):
            i = d1 - d2
            if abs(i) < nearest:
                return abs(i), i
            return nearest, current
        
        for guide in self.guides:
            guidePt = guide.mapToScene(guide.line().p1())
            
            if guide.orientation == Layout.Vertical:
                nearestX, dx = snap(nearestX, dx, guidePt.x(), itemPt1.x())
                nearestX, dx = snap(nearestX, dx, guidePt.x(), itemPt2.x())
            else:
                nearestY, dy = snap(nearestY, dy, guidePt.y(), itemPt1.y())
                nearestY, dy = snap(nearestY, dy, guidePt.y(), itemPt2.y())
            
        if nearestX < snapDistance:
            item.moveBy(dx, 0)
        if nearestY < snapDistance:
            item.moveBy(0, dy)

    def mouseReleaseEvent(self, event):

        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)

        QGraphicsScene.mouseReleaseEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

    def mousePressEvent(self, event):
        
        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)
        
        QGraphicsScene.mousePressEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

    def contextMenuEvent(self, event):

        # We can't use the default handler at all because it calls the
        # menu of the item that was *right-clicked on*, not the menu of the selected items
        # TODO: need to handle this better: What if a page and a step are selected?
        for item in self.selectedItems():
            for t in [Part, Arrow, Step, Page, Callout, CalloutArrow, CSI, PLI, SubmodelPreview, QGraphicsSimpleTextItem]:
                if isinstance(item, t) or issubclass(type(item), t):
                    return item.contextMenuEvent(event)

    def keyPressEvent(self, event):
        if not self.selectedItems():
            event.ignore()
        else:
            event.accept()
        
    def keyReleaseEvent(self, event):

        for item in self.selectedItems():
            if isinstance(item, Part):
                item.keyReleaseEvent(event)
                return

        key = event.key()
        offset = 1
        x = y = 0

        if event.modifiers() & Qt.ShiftModifier:
            offset = 20 if event.modifiers() & Qt.ControlModifier else 5

        if key == Qt.Key_PageUp:
            self.emit(SIGNAL("pageUp"))
            return
        if key == Qt.Key_PageDown:
            self.emit(SIGNAL("pageDown"))
            return
        if key == Qt.Key_Home:
            self.emit(SIGNAL("home"))
            return
        if key == Qt.Key_End:
            self.emit(SIGNAL("end"))
            return

        if key == Qt.Key_Left:
            x = -offset
        elif key == Qt.Key_Right:
            x = offset
        elif key == Qt.Key_Up:
            y = -offset
        elif key == Qt.Key_Down:
            y = offset
        else:
            event.ignore()  # We do not handle this key stroke here - pass it on and return
            return

        movedItems = []
        for item in self.selectedItems():
            if isinstance(item, Page):
                continue  # Pages cannot be moved

            item.oldPos = item.pos()
            item.moveBy(x, y)
            movedItems.append(item)

        if movedItems:
            self.emit(SIGNAL("itemsMoved"), movedItems)
        event.accept()

class Guide(QGraphicsLineItem):
    
    extends = 500
    
    def __init__(self, orientation):
        QGraphicsLineItem.__init__(self)
        
        self.orientation = orientation
        self.setFlags(AllFlags)
        self.setPen(QPen(QColor(0, 0, 255, 128)))  # Blue 1/2 transparent
        #self.setPen(QPen(QBrush(QColor(0, 0, 255, 128)), 1.5))  # Blue 1/2 transparent, 1.5 thick
        self.row = lambda: -1
        self.setZValue(10000)  # Put on top of everything else
        
        pw, ph = Page.PageSize.width(), Page.PageSize.height()
        if orientation == Layout.Horizontal:
            self.setCursor(Qt.SplitVCursor)
            self.setLine(-self.extends, ph / 2.0, pw + self.extends, ph / 2.0)
        else:
            self.setCursor(Qt.SplitHCursor)
            self.setLine(pw / 2.0, -self.extends, pw / 2.0, ph + self.extends)

    def setLength(self, length):
        line = self.line()
        line.setLength(length + self.extends + self.extends)
        self.setLine(line)

    def mouseMoveEvent(self, event):
        if self.orientation == Layout.Horizontal:
            x = self.pos().x()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(x, self.pos().y())
        else:
            y = self.pos().y()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(self.pos().x(), y)

class LicGraphicsView(QGraphicsView):
    def __init__(self, parent):
        QGraphicsView.__init__(self,  parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(Qt.gray))

    def scaleView(self, scaleFactor):
        
        if scaleFactor == 1.0:
            self.scene().scaleFactor = scaleFactor
            self.resetTransform()
        else:
            factor = self.matrix().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()
    
            if factor >= 0.15 and factor <= 5:
                self.scene().scaleFactor = factor
                self.scale(scaleFactor, scaleFactor)

class LicWindow(QMainWindow):

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        
        self.loadSettings()
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), self._setWindowModified)
        
        self.glWidget = QGLWidget(getGLFormat(), self)
        self.treeView = LicTreeView(self)

        statusBar = self.statusBar()
        self.scene = LicGraphicsScene(self)
        self.scene.undoStack = self.undoStack  # Make undo stack easy to find for everything

        self.graphicsView = LicGraphicsView(self)
        self.graphicsView.setViewport(self.glWidget)
        self.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        
        self.createUndoSignals()

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeView)
        self.mainSplitter.addWidget(self.graphicsView)
        self.mainSplitter.restoreState(self.splitterState)
        self.setCentralWidget(self.mainSplitter)

        self.initMenu()
        self.initToolBars()

        self.instructions = Instructions(self, self.scene, self.glWidget)
        self.treeModel = LicTreeModel.LicTreeModel(self.treeView)
        
        self.treeView.scene = self.scene
        self.treeView.setModel(self.treeModel)
        self.selectionModel = QItemSelectionModel(self.treeModel)  # MUST keep own reference to selection model here
        self.treeView.setSelectionModel(self.selectionModel)
        
        self.treeView.connect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateTreeSelection)
        self.scene.connect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChanged)

        self.connect(self.scene, SIGNAL("pageUp"), self.scene.pageUp)
        self.connect(self.scene, SIGNAL("pageDown"), self.scene.pageDown)
        self.connect(self.scene, SIGNAL("home"), self.scene.selectFirstPage)
        self.connect(self.scene, SIGNAL("end"), self.scene.selectLastPage)
        
        # Allow the graphics scene and instructions to emit the layoutAboutToBeChanged and layoutChanged 
        # signals, for easy notification of layout changes everywhere
        self.connect(self.scene, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.scene, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))
        self.connect(self.instructions, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.instructions, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))
            
        self.filename = ""   # This will trigger the __setFilename method below

    def getSettingsFile(self):
        iniFile = os.path.join(os.path.dirname(sys.argv[0]), 'Lic.ini')
        return QSettings(QString(iniFile), QSettings.IniFormat)
        
    def loadSettings(self):
        settings = self.getSettingsFile()
        self.recentFiles = settings.value("RecentFiles").toStringList()
        self.restoreGeometry(settings.value("Geometry").toByteArray())
        self.restoreState(settings.value("MainWindow/State").toByteArray())
        self.splitterState = settings.value("SplitterSizes").toByteArray()
        self.pagesToDisplay = settings.value("PageView").toInt()[0]
    
    def saveSettings(self):
        settings = self.getSettingsFile()
        recentFiles = QVariant(self.recentFiles) if self.recentFiles else QVariant()
        settings.setValue("RecentFiles", recentFiles)
        settings.setValue("Geometry", QVariant(self.saveGeometry()))
        settings.setValue("MainWindow/State", QVariant(self.saveState()))
        settings.setValue("SplitterSizes", QVariant(self.mainSplitter.saveState()))
        settings.setValue("PageView", QVariant(str(self.scene.pagesToDisplay)))
    
    def keyReleaseEvent(self, event):
        pass
        key = event.key()
        
        if key == Qt.Key_Plus:
            self.instructions.enlargePixmaps()
        elif key == Qt.Key_Minus:
            self.instructions.shrinkPixmaps()
        else:
            event.ignore()
    
    def _setWindowModified(self, bool):
        # This is tied to the undo stack's cleanChanged signal.  Problem with that signal 
        # is it sends the *opposite* bool to what we need to pass to setWindowModified,
        # so can't just connect that signal straight to setWindowModified slot.
        self.setWindowModified(not bool)
        
    def createUndoSignals(self):

        signals = [("itemsMoved", LicUndoActions.MoveCommand)]

        for signal, command in signals:
            self.connect(self.scene, SIGNAL(signal), lambda x, c = command: self.undoStack.push(c(x)))

    def __getFilename(self):
        return self.__filename
    
    def __setFilename(self, filename):
        self.__filename = filename
        
        if filename:
            config.config = self.initConfig()
            self.setWindowTitle("Lic %s - %s [*]" % (__version__, os.path.basename(filename)))
            self.statusBar().showMessage("Instruction book loaded: " + filename)
            enabled = True
        else:
            config.config = {}
            self.undoStack.clear()
            self.setWindowTitle("Lic %s [*]" % __version__)
            self.statusBar().showMessage("")
            enabled = False

        self.undoStack.setClean()
        self.fileCloseAction.setEnabled(enabled)
        self.fileSaveAction.setEnabled(enabled)
        self.fileSaveAsAction.setEnabled(enabled)
        self.fileSaveTemplateAction.setEnabled(enabled)
        self.fileSaveTemplateAsAction.setEnabled(enabled)
        self.fileLoadTemplateAction.setEnabled(enabled)
        self.pageMenu.setEnabled(enabled)
        self.viewMenu.setEnabled(enabled)
        self.exportMenu.setEnabled(enabled)

    filename = property(fget = __getFilename, fset = __setFilename)
            
    def initConfig(self):
        """ 
        Create cache folders for temp dats, povs & pngs, if necessary.
        Cache folders are stored as 'LicPath/cache/modelName/[DATs|POVs|PNGs]'
        """
        
        config = {}
        cachePath = os.path.join(os.getcwd(), 'cache')        
        if not os.path.isdir(cachePath):
            os.mkdir(cachePath)
            
        modelPath = os.path.join(cachePath, os.path.basename(self.filename))
        if not os.path.isdir(modelPath):
            os.mkdir(modelPath)
        
        config['datPath'] = os.path.join(modelPath, 'DATs')
        if not os.path.isdir(config['datPath']):
            os.mkdir(config['datPath'])   # Create DAT directory if needed

        config['povPath'] = os.path.join(modelPath, 'POVs')
        if not os.path.isdir(config['povPath']):
            os.mkdir(config['povPath'])   # Create POV directory if needed

        config['pngPath'] = os.path.join(modelPath, 'PNGs')
        if not os.path.isdir(config['pngPath']):
            os.mkdir(config['pngPath'])   # Create PNG directory if needed

        config['imgPath'] = os.path.join(modelPath, 'Final_Images')
        if not os.path.isdir(config['imgPath']):
            os.mkdir(config['imgPath'])   # Create final image directory if needed

        return config

    def initToolBars(self):
        self.toolBar = None
    
    def initMenu(self):
        
        menu = self.menuBar()
        
        # File Menu
        self.fileMenu = menu.addMenu("&File")
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"), self.updateFileMenu)

        fileOpenAction = self.createMenuAction("&Open...", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")

        self.fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing LDraw Model into a new Instruction book")

        self.fileSaveTemplateAction = self.createMenuAction("Save Template", self.fileSaveTemplate, None, "Save only the Template")
        self.fileSaveTemplateAsAction = self.createMenuAction("Save Template As...", self.fileSaveTemplateAs, None, "Save only the Template using a new filename")
        self.fileLoadTemplateAction = self.createMenuAction("Load Template", self.fileLoadTemplate, None, "Discard the current Template and apply a new one")
        fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")

        self.fileMenuActions = (fileOpenAction, self.fileCloseAction, None, 
                                self.fileSaveAction, self.fileSaveAsAction, fileImportAction, None, 
                                self.fileSaveTemplateAction, self.fileSaveTemplateAsAction, self.fileLoadTemplateAction, None,
                                fileExitAction)
        
        # Edit Menu - undo / redo is generated dynamicall in updateEditMenu()
        self.editMenu = menu.addMenu("&Edit")
        self.connect(self.editMenu, SIGNAL("aboutToShow()"), self.updateEditMenu)

        self.undoAction = self.createMenuAction("&Undo", None, "Ctrl+Z", "Undo last action")
        self.undoAction.connect(self.undoAction, SIGNAL("triggered()"), self.undoStack, SLOT("undo()"))
        self.undoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canUndoChanged(bool)"), self.undoAction, SLOT("setEnabled(bool)"))
        
        self.redoAction = self.createMenuAction("&Redo", None, "Ctrl+Y", "Redo the last undone action")
        self.redoAction.connect(self.redoAction, SIGNAL("triggered()"), self.undoStack, SLOT("redo()"))
        self.redoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canRedoChanged(bool)"), self.redoAction, SLOT("setEnabled(bool)"))
        
        editActions = (self.undoAction, self.redoAction)
        self.addActions(self.editMenu, editActions)

        # View Menu
        self.viewMenu = menu.addMenu("&View")
        addHGuide = self.createMenuAction("Add Horizontal Guide", lambda: self.scene.addNewGuide(Layout.Horizontal), None, "Add Guide")
        addVGuide = self.createMenuAction("Add Vertical Guide", lambda: self.scene.addNewGuide(Layout.Vertical), None, "Add Guide")
        removeGuides = self.createMenuAction("Remove Guides", self.scene.removeAllGuides, None, "Add Guide")

        zoom100 = self.createMenuAction("Zoom &100%", lambda: self.zoom(1.0), None, "Zoom 100%")
        zoomIn = self.createMenuAction("Zoom &In", lambda: self.zoom(1.2), None, "Zoom In")
        zoomOut = self.createMenuAction("Zoom &Out", lambda: self.zoom(1.0 / 1.2), None, "Zoom Out")

        onePage = self.createMenuAction("Show One Page", self.scene.showOnePage, None, "Show One Page")
        twoPages = self.createMenuAction("Show Two Pages", self.scene.showTwoPages, None, "Show Two Pages")
        continuous = self.createMenuAction("Continuous", self.scene.continuous, None, "Continuous")
        continuousFacing = self.createMenuAction("Continuous Facing", self.scene.continuousFacing, None, "Continuous Facing")
        self.addActions(self.viewMenu, (addHGuide, addVGuide, removeGuides, None, zoom100, zoomIn, zoomOut, onePage, twoPages, continuous, continuousFacing))

        # Page Menu
        self.pageMenu = menu.addMenu("&Page")

        pageSizeAction = self.createMenuAction("Page Size...", self.changePageSizeAction, None, "Change the overall size of all Pages in this Instruction book")       
        csipliSizeAction = self.createMenuAction("CSI | PLI Image Size...", self.changeCSIPLISizeAction, None, "Change the relative size of all CSIs and PLIs throughout Instruction book")
        self.addActions(self.pageMenu, (pageSizeAction, csipliSizeAction))
        
        # Export Menu
        self.exportMenu = menu.addMenu("E&xport")
        self.exportImagesAction = self.createMenuAction("&Generate Final Images", lambda: self.exportImages(self.glWidget), None, "Generate final images of each page in this Instruction book")
        self.exportRenderedImagesAction = self.createMenuAction("Generate Images with Pov-Ray", lambda: self.exportImages(), None, "Use Pov-Ray to generate final, ray-traced images of each page in this Instruction book")
        self.addActions(self.exportMenu, (self.exportImagesAction, self.exportRenderedImagesAction))

    def changePageSizeAction(self):
        dialog = LicDialogs.PageSizeDlg(self, Page.PageSize, Page.Resolution)
        self.connect(dialog, SIGNAL("newPageSize"), self.setPageSize)
        dialog.exec_()

    def setPageSize(self, newPageSize, newResolution):
        
        if (newPageSize.width() != Page.PageSize.width() or newPageSize.height() != Page.PageSize.height()) or (newResolution != Page.Resolution):
            Page.PageSize = newPageSize
            Page.Resolution = newResolution
            self.scene.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
            self.instructions.setPageSize(Page.PageSize)

    def zoom(self, factor):
        self.graphicsView.scaleView(factor)
        
    def updateFileMenu(self):
        self.fileMenu.clear()
        self.addActions(self.fileMenu, self.fileMenuActions[:-1])  # Don't add last Exit yet
        
        recentFiles = []
        for filename in self.recentFiles:
            if filename != QString(self.filename) and QFile.exists(filename):
                recentFiles.append(filename)
                
        if recentFiles:
            self.fileMenu.addSeparator()
            
            for i, filename in enumerate(recentFiles):
                action = QAction("&%d %s" % (i+1, QFileInfo(filename).fileName()), self)
                action.setData(QVariant(filename))
                self.connect(action, SIGNAL("triggered()"), self.loadLicFile)
                self.fileMenu.addAction(action)
            
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.fileMenuActions[-1])

    def updateEditMenu(self):
        self.undoAction.setText("&Undo %s " % self.undoStack.undoText())
        self.redoAction.setText("&Redo %s " % self.undoStack.redoText())

    def addRecentFile(self, filename):
        if self.recentFiles.contains(filename):
            self.recentFiles.move(self.recentFiles.indexOf(filename), 0)
        else:
            self.recentFiles.prepend(QString(filename))
            while self.recentFiles.count() > 9:
                self.recentFiles.takeLast()

    def changePageSize(self):
        dialog = LicDialogs.PageSizeDlg(self)
        if dialog.exec_():
            pageSize = dialog.pageSize()
    
    def changeCSIPLISizeAction(self):
        dialog = LicDialogs.CSIPLIImageSizeDlg(self, CSI.defaultScale, PLI.defaultScale)
        self.connect(dialog, SIGNAL("newCSIPLISize"), self.setCSIPLISize)
        dialog.show()

    def setCSIPLISize(self, newCSISize, newPLISize):
        if newCSISize != CSI.defaultScale or newPLISize != PLI.defaultScale:
            sizes = ((CSI.defaultScale, newCSISize), (PLI.defaultScale, newPLISize))
            self.undoStack.push(LicUndoActions.ResizeCSIPLICommand(self.instructions, sizes))

    def addActions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)
    
    def createMenuAction(self, text, slot = None, shortcut = None, tip = None, signal = "triggered()"):
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None:
            self.connect(action, SIGNAL(signal), slot)
        return action

    def closeEvent(self, event):
        if self.offerSave():
            self.saveSettings()
            
            # Need to explicitly disconnect these signals, because the scene emits a selectionChanged right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateTreeSelection)
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChanged)
            self.glWidget.doneCurrent()  # Avoid a crash when exiting
            event.accept()
        else:
            event.ignore()

    def fileClose(self):
        if not self.offerSave():
            return
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.instructions.clear()
        self.treeModel.reset()
        self.treeModel.root = None
        self.scene.clear()
        self.filename = ""
        self.scene.emit(SIGNAL("layoutChanged()"))
        # TODO: Redraw background, to clear up any leftover drawing bits

    def offerSave(self):
        """ 
        Returns True if we should proceed with whatever operation
        was interrupted by this request.  False means cancel.
        """
        if not self.isWindowModified():
            return True
        reply = QMessageBox.question(self, "Lic - Unsaved Changes", "Save unsaved changes?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Yes:
            self.fileSave()
        return True

    def fileImport(self):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        formats = ["*.mpd", "*.dat"]
        filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Import LDraw Model", dir, "LDraw Models (%s)" % " ".join(formats)))
        if filename:
            QTimer.singleShot(50, lambda: self.importLDrawModelTimerAction(filename))

    def importLDrawModelTimerAction(self, filename):
        self.fileClose()
        self.importLDrawModel(filename)
        self.statusBar().showMessage("LDraw Model imported: " + filename)
        self.scene.setPagesToDisplay(self.pagesToDisplay)

    def loadLicFile(self, filename = None):
        
        if filename is None:
            action = self.sender()
            filename = unicode(action.data().toString())

        if not self.offerSave():
            return
        
        if self.filename and filename != self.filename:
            self.fileClose()

        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicBinaryReader.loadLicFile(filename, self.instructions, self.treeModel)
        self.treeModel.root = self.instructions.mainModel
        self.scene.emit(SIGNAL("layoutChanged()"))
        
        self.filename = filename
        self.addRecentFile(filename)
        self.scene.setPagesToDisplay(self.pagesToDisplay)
    
    def importLDrawModel(self, filename):

        progress = QProgressDialog(self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("Importing " + os.path.splitext(os.path.basename(filename))[0])
        progress.setMinimumDuration(0)
        progress.setCancelButtonText("Cancel")
        progress.setRange(0, 10)
        progress.setLabelText("Reading LDraw File")
        progress.setValue(1)  # Force dialog to show up right away
        
        loader = self.instructions.importLDrawModel(filename)
        stopValue, title = loader.next()  # First value yielded after load is # of progress steps
        progress.setMaximum(stopValue)
        
        for step, label in loader:
            progress.setLabelText(label)
            progress.setValue(step)
            
            if progress.wasCanceled():
                loader.close()
                self.fileClose()
                return

        progress.setValue(progress.maximum())
        
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.treeModel.root = self.instructions.mainModel

        templatePage = LicBinaryReader.loadLicTemplate(r"C:\lic\dynamic_template.lit", self.instructions)
        #templatePage = LicTemplate.TemplatePage(self.instructions.mainModel, self.instructions)
        #templatePage.createBlankTemplate(self.glWidget)

        self.treeModel.setTemplatePage(templatePage)
        self.treeModel.templatePage.applyFullTemplate()
        self.treeModel.templatePage.applyDefaults()
        
        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(1)

        config.config = self.initConfig()
        self.statusBar().showMessage("Instruction book loaded")
        self.fileCloseAction.setEnabled(True)
        self.fileSaveAsAction.setEnabled(True)
        self.fileSaveTemplateAsAction.setEnabled(True)
        self.fileLoadTemplateAction.setEnabled(True)
        self.editMenu.setEnabled(True)
        self.pageMenu.setEnabled(True)
        self.viewMenu.setEnabled(True)
        self.exportMenu.setEnabled(True)

    def fileSaveAs(self):
        if self.filename:
            f = self.filename
        else:
            f = self.instructions.getModelName()
            f = f.split('.')[0] + '.lic'
            
        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe File As", f, "Lic Instruction Book files (*.lic)"))
        if filename:
            self.filename = filename
            return self.fileSave()

    def fileSave(self):
        try:
            LicBinaryWriter.saveLicFile(self.filename, self.instructions, self.treeModel.templatePage)
            self.setWindowModified(False)
            self.addRecentFile(self.filename)
            self.statusBar().showMessage("Saved to: " + self.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (self.filename, e))

    def fileSaveTemplate(self):
        template = self.treeModel.templatePage
        try:
            LicBinaryWriter.saveLicTemplate(template)
            self.statusBar().showMessage("Saved Template to: " + template.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (template.filename, e))
    
    def fileSaveTemplateAs(self):
        template = self.treeModel.templatePage
        f = template.filename if template.filename else "template.lic"

        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe Template As", f, "Lic Template files (*.lit)"))
        if filename:
            template.filename = filename
            self.fileSaveTemplateAction.setEnabled(True)
            return self.fileSaveTemplate()
    
    def fileLoadTemplate(self):
        if not self.offerSave():
            return
        templateName = self.treeModel.templatePage.filename
        dir = os.path.dirname(templateName) if templateName is not None else "."
        newFilename = unicode(QFileDialog.getOpenFileName(self, "Lic - Load Template", dir, "Lic Template files (*.lit)"))
        if newFilename and newFilename != templateName:
            try:
                newTemplate = LicBinaryReader.loadLicTemplate(newFilename, self.instructions)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Load Template Error", "Failed to open %s: %s" % (newFilename, e))
            else:
                self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
                self.treeModel.templatePage = newTemplate
                self.treeModel.templatePage.applyFullTemplate()
                self.treeModel.templatePage.applyDefaults()
                self.scene.emit(SIGNAL("layoutChanged()"))
                self.setWindowModified(True)
    
    def fileOpen(self):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Open Instruction Book", dir, "Lic Instruction Book files (*.lic)"))
        if filename and filename != self.filename:
            self.fileClose()
            try:
                self.loadLicFile(filename)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Open Error", "Failed to open %s: %s" % (filename, e))
                self.fileClose()

    def exportImages(self, widget = None):
        self.instructions.exportImages(widget)
        
        #image = QImage(1000, 800, QImage.Format_ARGB32)
        #painter = QPainter()
        #painter.begin(image)
        #self.scene.render(painter, QRectF(0, 0, 1000, 800), QRectF(400, 100, 1000, 800))
        #painter.end()
        #image.save(r"c:\lic\tmp\widget.png")
        
        print "\nExport complete"

def main():
    
    #f = QGLFormat.defaultFormat()
    #f.setSampleBuffers(True)
    #QGLFormat.setDefaultFormat(f)
    
    app = QApplication(sys.argv)
    app.setOrganizationName("BugEyedMonkeys Inc.")
    app.setOrganizationDomain("bugeyedmonkeys.com")
    app.setApplicationName("Lic")
    window = LicWindow()

    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    window.show()
    filename = ""
    #filename = unicode("C:\\lic\\tardis.mpd")
    #filename = unicode("C:\\lic\\tardis.lic")
    #filename = unicode("C:\\lic\\viper_wing.lic")
    #filename = unicode("C:\\lic\\viper_short.lic")
    #filename = unicode("C:\\lic\\viper_short.mpd")
    #filename = unicode("C:\\lic\\viper.mpd")
    #filename = unicode("C:\\lic\\Blaster.mpd")
    #filename = unicode("C:\\lic\\6x10.lic")
    #filename = unicode("C:\\lic\\6x10.dat")
    #filename = unicode("C:\\lic\\template.dat")
    if filename:
        QTimer.singleShot(50, lambda: loadFile(window, filename))

    sys.exit(app.exec_())

def loadFile(window, filename):

    if filename[-3:] == 'dat' or filename[-3:] == 'mpd':
        window.importLDrawModelTimerAction(filename)
    elif filename[-3:] == 'lic':
        window.loadLicFile(filename)
    else:
        print "Bad file extension: " + filename
        return

    window.scene.selectPage(1)

def recompileResources():
    import os
    ret = os.spawnl(os.P_WAIT, r"C:\Python25\Lib\site-packages\PyQt4\pyrcc4.exe", "pyrcc4.exe", "-o", r"c:\lic\resources.py", r"c:\lic\resources.qrc")
    print ret
    
if __name__ == '__main__':
    #import cProfile
    #cProfile.run('main()', 'profile_run')
    main()
    #recompileResources()

