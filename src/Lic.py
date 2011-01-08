"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (Lic.py) is part of Lic.

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

#from __future__ import division
import sys
import time
import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from LicModel import *
from LicCustomPages import *
from LicInstructions import *

import LicGraphicsWidget
import LicTreeModel
import LicBinaryReader
import LicBinaryWriter
import config
import LicDialogs
import LicUndoActions
import LicLayout
import LicGLHelpers
import LicImporters

#from modeltest import ModelTest

__version__ = 0.5

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
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
        # instanceType can be either concrete type like PLI or itemClassString
        # like "Page Number" (for specific QGraphicsSimpleTextItems) 

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

    def updateTreeSelection(self):
        """ This is called whenever the graphics Scene is clicked, in order to copy selection from Scene to this Tree. """
        
        # Deselect everything in the tree
        model = self.model()
        selection = self.selectionModel()
        selection.clear()

        # Select everything in the tree that's currently selected in the graphics view
        index = None
        selList = QItemSelection()
        for item in self.scene.selectedItems():
            if not hasattr(item, "row"):  # Ignore stuff like guides & snap lines
                continue
            index = model.createIndex(item.row(), 0, item)
            if index:
                selList.append(QItemSelectionRange(index))

        selection.select(selList, QItemSelectionModel.SelectCurrent)

        if index:
            if len(selList) < 2:
                self.setCurrentIndex(index)
            self.scrollTo(index)

    def pushTreeSelectionToScene(self):

        # Clear any existing selection from the graphics view
        self.scene.clearSelection()
        selList = self.selectionModel().selectedIndexes()

        if not selList:
            return  # Nothing selected = nothing to do here

        target = selList[-1].internalPointer()

        # Find the selected item's parent page, then flip to that page
        if isinstance(target, Submodel):
            self.scene.selectPage(target.pages[0].number)
        else:
            page = target.getPage()
            self.scene.selectPage(page._number)

        # Finally, select the things we actually clicked on
        partList = []
        for index in selList:
            item = index.internalPointer()
            if isinstance(item, Part):
                partList.append(item)
            elif isinstance(item, Submodel):
                item.setSelected(True)
                self.scene.selectedSubmodels.append(item)
            else:
                item.setSelected(True)

        # Optimization: don't just select each parts, because selecting a part forces its CSI to redraw.
        # Instead, only redraw the CSI once, on the last part update
        if partList:
            for part in partList[:-1]:
                part.setSelected(True, False)
            partList[-1].setSelected(True, True)

    def keyPressEvent(self, event):
        if event.key() not in [Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:  # Ignore these 4 here - passed to Scene on release
            QTreeView.keyPressEvent(self, event)

    def keyReleaseEvent(self, event):
        if event.key() in [Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
            return self.scene.keyReleaseEvent(event)  # Pass these keys on to the Scene
        QTreeView.keyReleaseEvent(self, event)
        self.pushTreeSelectionToScene()  # Let scene know about new selection

    def mousePressEvent(self, event):
        """ Mouse click in Tree Widget means its selection has changed.  Copy selected items from Tree to Scene."""

        QTreeView.mousePressEvent(self, event)

        if event.button() == Qt.RightButton:
            return  # Ignore right clicks - they're passed on to selected item for their context menu

        self.pushTreeSelectionToScene()

    def contextMenuEvent(self, event):
        # Pass right clicks on to the item right-clicked on
        event.screenPos = event.globalPos   # 'Convert' QContextMenuEvent to QGraphicsSceneContextMenuEvent
        item = self.indexAt(event.pos()).internalPointer()
        if item:
            return item.contextMenuEvent(event)

class LicTreeWidget(QWidget):
    """
    Combines a LicTreeView (itself a full widget) and a toolbar with a few buttons to control the tree layout.
    """
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
        self.tree = LicTreeView(self)
        self.hiddenRowActions = []
        
        self.treeToolBar = QToolBar("Tree Toolbar", self)
        self.treeToolBar.setIconSize(QSize(15, 15))
        self.treeToolBar.setStyleSheet("QToolBar { border: 0px; }")
        self.treeToolBar.addAction(QIcon(":/expand"), "Expand", self.tree.expandOneLevel)
        self.treeToolBar.addAction(QIcon(":/collapse"), "Collapse", self.tree.collapseAll)

        viewToolButton = QToolButton(self.treeToolBar)
        viewToolButton.setIcon(QIcon(":/down_arrow"))
        viewToolButton.setStyleSheet("QToolButton::menu-indicator { image: url(:/blank) }")
        
        viewMenu = QMenu(viewToolButton)

        def addViewAction(title, slot, checked = True):
            action = QAction(title, viewMenu)
            action.setCheckable(True)
            action.setChecked(checked)
            action.connect(action, SIGNAL("toggled(bool)"), slot)
            action.action = slot
            viewMenu.addAction(action)
            return action

        #viewMenu.addAction("Show All", self.tree.showAll)
        addViewAction("Show Page | Step | Part", self.setShowPageStepPart, False)
        viewMenu.addSeparator()
        addViewAction("Group Parts by type", self.setShowCSIPartGroupings)
        viewMenu.addSeparator()

        self.hiddenRowActions.append(addViewAction("Show Page Number", lambda show: self.tree.hideRowInstance("Page Number", not show)))
        self.hiddenRowActions.append(addViewAction("Show Step Number", lambda show: self.tree.hideRowInstance("Step Number", not show)))
        
        self.csiCheckAction = addViewAction("Show CSI", self.setShowCSI)  # Special case - stuff inside CSI needs to move into Step if CSI hidden
        
        self.hiddenRowActions.append(addViewAction("Show PLI", lambda show: self.tree.hideRowInstance(PLI, not show)))
        self.hiddenRowActions.append(addViewAction("Show PLI Items", lambda show: self.tree.hideRowInstance(PLIItem, not show)))
        self.hiddenRowActions.append(addViewAction("Show PLI Item Qty", lambda show: self.tree.hideRowInstance("PLIItem Quantity", not show)))
        self.hiddenRowActions.append(addViewAction("Show Callouts", lambda show: self.tree.hideRowInstance(Callout, not show)))
        self.hiddenRowActions.append(addViewAction("Show Submodel Previews", lambda show: self.tree.hideRowInstance(SubmodelPreview, not show)))
        
        viewToolButton.setMenu(viewMenu)
        viewToolButton.setPopupMode(QToolButton.InstantPopup)
        viewToolButton.setToolTip("Show / Hide")
        viewToolButton.setFocusPolicy(Qt.NoFocus)
        self.treeToolBar.addWidget(viewToolButton)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.treeToolBar, 0, Qt.AlignRight)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def configureTree(self, scene, treeModel, selectionModel):
        self.tree.scene = scene
        self.tree.setModel(treeModel)
        self.tree.setSelectionModel(selectionModel)

    def setShowPageStepPart(self, show):
        self.csiCheckAction.setChecked(not show)
        for action in self.hiddenRowActions:
            action.setChecked(not show)
    
    def setShowCSIPartGroupings(self, show):
        model = self.tree.model()
        model.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicTreeModel.CSITreeManager.showPartGroupings = show
        
        # Need to reset all cached Part data strings 
        cmp = lambda index: isinstance(index.internalPointer(), Part)
        action = lambda index: index.internalPointer().resetDataString()
        self.tree.walkTreeModel(cmp, action)
        
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def setShowCSI(self, show):
        model = self.tree.model()
        model.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicTreeModel.StepTreeManager._showCSI = show
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def resetHiddenRows(self, ):
        for action in self.hiddenRowActions:
            action.action(action.isChecked())

class LicWindow(QMainWindow):

    defaultTemplateFilename = "dynamic_template.lit"

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        QGL.setPreferredPaintEngine(QPaintEngine.OpenGL)
        
        self.loadSettings()
        self.setWindowIcon(QIcon(":/lic_logo_16x16"))
        self.setAcceptDrops(True)
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), lambda isClean: self.setWindowModified(not isClean))

        self.glWidget = QGLWidget(LicGLHelpers.getGLFormat(), self)
        self.treeWidget = LicTreeWidget(self)

        self.scene = LicGraphicsWidget.LicGraphicsScene(self)
        self.scene.undoStack = self.undoStack  # Make undo stack easy to find for everything
        self.copySettingsToScene()

        self.graphicsView = LicGraphicsWidget.LicGraphicsView(self)
        self.graphicsView.setViewport(self.glWidget)
        self.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        
        # Connect the items moved signal to a push command on undo stack
        self.connect(self.scene, SIGNAL("itemsMoved"), lambda x: self.undoStack.push(LicUndoActions.MoveCommand(x)))

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeWidget)
        self.mainSplitter.addWidget(self.graphicsView)
        self.mainSplitter.restoreState(self.splitterState)
        self.setCentralWidget(self.mainSplitter)

        self.initMenu()
        self.initToolBars()

        self.instructions = Instructions(self, self.scene, self.glWidget)
        self.treeModel = LicTreeModel.LicTreeModel(self.treeWidget.tree)
        #self.modelTest = ModelTest(self.treeModel, self)
        
        self.selectionModel = QItemSelectionModel(self.treeModel)  # MUST keep own reference to selection model here
        self.treeWidget.configureTree(self.scene, self.treeModel, self.selectionModel)
        self.treeWidget.tree.connect(self.scene, SIGNAL("sceneClick"), self.treeWidget.tree.updateTreeSelection)
        self.scene.connect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChangedHandler)

        # Allow the graphics scene to emit the layoutAboutToBeChanged and layoutChanged
        # signals, for easy notification of layout changes everywhere
        self.connect(self.scene, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.scene, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))

        # AbstractItemModels keep a list of persistent indices around, which we need to update after layout change
        self.connect(self.treeModel, SIGNAL("layoutChanged()"), self.treeModel.updatePersistentIndices)

        # Need to notify the Model when a particular index was deleted
        self.treeModel.connect(self.scene, SIGNAL("itemDeleted"), self.treeModel.deletePersistentItem)

        self.filename = ""   # This will trigger __setFilename below

    def getSettingsFile(self):
        iniFile = os.path.join(os.path.dirname(sys.argv[0]), 'Lic.ini')
        return QSettings(QString(iniFile), QSettings.IniFormat)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(QString("text/uri-list")):
            filename = event.mimeData().getFilename()
            if filename is not None:
                ext = os.path.splitext(filename)[1]
                if ext in LicImporters.getFileTypesList() or ext == '.lic':
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        filename = event.mimeData().getFilename()  # Assuming correct drop type, based on dragEnterEvent()
        ext = os.path.splitext(filename)[1]
        if ext == '.dat' or ext == '.mpd' or ext == '.ldr':
            self.importModel(filename)
        elif ext == '.lic':
            self.fileOpen(filename)
        event.acceptProposedAction()

    def loadSettings(self):
        settings = self.getSettingsFile()
        self.recentFiles = settings.value("RecentFiles").toStringList()
        self.restoreGeometry(settings.value("Geometry").toByteArray())
        self.restoreState(settings.value("MainWindow/State").toByteArray())
        self.splitterState = settings.value("SplitterSizes").toByteArray()
        self.pagesToDisplay = settings.value("PageView").toInt()[0]
        self.snapToGuides = settings.value("SnapToGuides").toBool()
        self.snapToItems = settings.value("SnapToItems").toBool()

        LDrawPath = str(settings.value("LDrawPath").toString())
        L3PPath = str(settings.value("L3PPath").toString())
        POVRayPath = str(settings.value("POVRayPath").toString())

        if LDrawPath and L3PPath and POVRayPath:
            config.LDrawPath = LDrawPath 
            config.L3PPath = L3PPath 
            config.POVRayPath = POVRayPath
            self.needPathConfiguration = False
        else:
            self.needPathConfiguration = True
    
    def saveSettings(self):
        settings = self.getSettingsFile()
        recentFiles = QVariant(self.recentFiles) if self.recentFiles else QVariant()
        settings.setValue("RecentFiles", recentFiles)
        settings.setValue("Geometry", QVariant(self.saveGeometry()))
        settings.setValue("MainWindow/State", QVariant(self.saveState()))
        settings.setValue("SplitterSizes", QVariant(self.mainSplitter.saveState()))
        settings.setValue("PageView", QVariant(str(self.scene.pagesToDisplay)))
        settings.setValue("SnapToGuides", QVariant(str(self.scene.snapToGuides)))
        settings.setValue("SnapToItems", QVariant(str(self.scene.snapToItems)))

        settings.setValue("LDrawPath", QVariant(config.LDrawPath))
        settings.setValue("L3PPath", QVariant(config.L3PPath))
        settings.setValue("POVRayPath", QVariant(config.POVRayPath))

    def copySettingsToScene(self):
        self.scene.setPagesToDisplay(self.pagesToDisplay)
        self.scene.snapToGuides = self.snapToGuides
        self.scene.snapToItems = self.snapToItems

    def configurePaths(self, hideCancelButton = False):
        dialog = config.PathsDialog(self, hideCancelButton)
        dialog.exec_()

    def __getFilename(self):
        return self.__filename
    
    def __setFilename(self, filename):
        self.__filename = filename
        
        if filename:
            config.filename = filename
            self.setWindowTitle("Lic %s - %s [*]" % (__version__, os.path.basename(filename)))
            self.statusBar().showMessage("Instruction book loaded: " + filename)
            enabled = True
        else:
            self.undoStack.clear()
            self.setWindowTitle("Lic %s [*]" % __version__)
            self.statusBar().showMessage("")
            enabled = False

        self.undoStack.setClean()
        self.setWindowModified(False)
        self.enableMenus(enabled)

    filename = property(__getFilename, __setFilename)

    def initToolBars(self):
        self.toolBar = None

    def initMenu(self):

        menu = self.menuBar()

        # File Menu
        self.fileMenu = menu.addMenu("&File")
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"), self.updateFileMenu)

        fileOpenAction = self.createMenuAction("&Open...", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileOpenRecentMenu = QMenu("Open &Recent", self.fileMenu)
        self.fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")
         
        self.fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing Model into a new Instruction book")

        self.fileSaveTemplateAction = self.createMenuAction("Save Template", self.fileSaveTemplate, None, "Save only the Template")
        self.fileSaveTemplateAsAction = self.createMenuAction("Save Template As...", self.fileSaveTemplateAs, None, "Save only the Template using a new filename")
        self.fileLoadTemplateAction = self.createMenuAction("Load Template", self.fileLoadTemplate, None, "Discard the current Template and apply a new one")
        fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")

        self.fileMenuActions = (fileOpenAction, self.fileOpenRecentMenu, self.fileCloseAction, None, 
                                self.fileSaveAction, self.fileSaveAsAction, fileImportAction, None, 
                                self.fileSaveTemplateAction, self.fileSaveTemplateAsAction, self.fileLoadTemplateAction, None,
                                fileExitAction)
        
        # Edit Menu - undo / redo is generated dynamically in updateEditMenu()
        editMenu = menu.addMenu("&Edit")
        self.connect(editMenu, SIGNAL("aboutToShow()"), self.updateEditMenu)

        self.undoAction = self.createMenuAction("&Undo", None, "Ctrl+Z", "Undo last action")
        self.undoAction.connect(self.undoAction, SIGNAL("triggered()"), self.undoStack, SLOT("undo()"))
        self.undoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canUndoChanged(bool)"), self.undoAction, SLOT("setEnabled(bool)"))
        
        self.redoAction = self.createMenuAction("&Redo", None, "Ctrl+Y", "Redo the last undone action")
        self.redoAction.connect(self.redoAction, SIGNAL("triggered()"), self.undoStack, SLOT("redo()"))
        self.redoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canRedoChanged(bool)"), self.redoAction, SLOT("setEnabled(bool)"))
        
        # Snap menu (inside Edit Menu): Snap -> Snap to Guides & Snap to Items
        guideSnapAction = self.createMenuAction("Guides", self.setSnapToGuides, None, "Snap To Guides", "toggled(bool)", True)
        guideSnapAction.setChecked(self.scene.snapToGuides)
        
        itemSnapAction = self.createMenuAction("Items", self.setSnapToItems, None, "Snap To Items", "toggled(bool)", True)
        itemSnapAction.setChecked(self.scene.snapToItems)
        
        snapMenu = editMenu.addMenu("Snap To")
        snapMenu.addAction(guideSnapAction)
        snapMenu.addAction(itemSnapAction)

        setPathsAction = self.createMenuAction("Paths...", self.configurePaths, None, "Set paths to LDraw parts, L3p, POVRay, etc")
        editActions = (self.undoAction, self.redoAction, None, snapMenu, setPathsAction)
        self.addActions(editMenu, editActions)

        # View Menu
        self.viewMenu = menu.addMenu("&View")
        addHGuide = self.createMenuAction("Add Horizontal Guide", lambda: self.scene.addNewGuide(LicLayout.Horizontal), None, "Add Guide")
        addVGuide = self.createMenuAction("Add Vertical Guide", lambda: self.scene.addNewGuide(LicLayout.Vertical), None, "Add Guide")
        removeGuides = self.createMenuAction("Remove Guides", self.scene.removeAllGuides, None, "Add Guide")

        zoom100 = self.createMenuAction("Zoom &100%", lambda: self.zoom(1.0), None, "Zoom 100%")
        zoomIn = self.createMenuAction("Zoom &In", lambda: self.zoom(1.2), None, "Zoom In")
        zoomOut = self.createMenuAction("Zoom &Out", lambda: self.zoom(1.0 / 1.2), None, "Zoom Out")

        onePage = self.createMenuAction("Show One Page", self.scene.showOnePage, None, "Show One Page", checkable=True)
        twoPages = self.createMenuAction("Show Two Pages", self.scene.showTwoPages, None, "Show Two Pages", checkable=True)
        continuous = self.createMenuAction("Continuous", self.scene.continuous, None, "Continuous", checkable=True)
        continuousFacing = self.createMenuAction("Continuous Facing", self.scene.continuousFacing, None, "Continuous Facing", checkable=True)

        pageActions = {1: onePage, 2: twoPages, LicGraphicsWidget.LicGraphicsScene.PageViewContinuous: continuous, LicGraphicsWidget.LicGraphicsScene.PageViewContinuousFacing: continuousFacing}
        pageActions[self.pagesToDisplay].setChecked(True)
        
        pageGroup = QActionGroup(self)
        for action in pageActions.values():
            pageGroup.addAction(action)
        
        viewActions = (addHGuide, addVGuide, removeGuides, None, zoom100, zoomIn, zoomOut, None, onePage, twoPages, continuous, continuousFacing)
        self.addActions(self.viewMenu, viewActions)

        # Export Menu
        self.exportMenu = menu.addMenu("E&xport")
        self.exportToImagesAction = self.createMenuAction("&Generate Final Images", self.exportImages, None, "Generate final images of each page in this Instruction book")
        self.exportToPDFAction = self.createMenuAction("Generate &PDF", self.exportToPDF, None, "Create a PDF from this instruction book")
        self.exportToPOVAction = self.createMenuAction("NYI - Generate Images with Pov-Ray", self.exportToPOV, None, "Use Pov-Ray to generate final, ray-traced images of each page in this Instruction book")
        self.exportToMPDAction = self.createMenuAction("Generate &MPD", self.exportToMPD, None, "Generate an LDraw MPD file from the parts & steps in this Instruction book")
        self.addActions(self.exportMenu, (self.exportToImagesAction, self.exportToPDFAction, self.exportToPOVAction, None, self.exportToMPDAction))

    def zoom(self, factor):
        self.graphicsView.scaleView(factor)
        
    def setSnapToGuides(self, snap):
        self.snapToGuides = self.scene.snapToGuides = snap

    def setSnapToItems(self, snap):
        self.snapToItems = self.scene.snapToItems = snap

    def updateFileMenu(self):
        self.fileMenu.clear()
        self.addActions(self.fileMenu, self.fileMenuActions)
        
        recentFiles = []
        for filename in self.recentFiles:
            if filename != QString(self.filename) and QFile.exists(filename):
                recentFiles.append(filename)
                
        if recentFiles:
            self.fileOpenRecentMenu.clear()
            self.fileOpenRecentMenu.setEnabled(True)
            for i, filename in enumerate(recentFiles):
                action = QAction("&%d %s" % (i+1, QFileInfo(filename).fileName()), self)
                action.setData(QVariant(filename))
                action.setStatusTip(filename)
                self.connect(action, SIGNAL("triggered()"), self.openRecentFile)
                self.fileOpenRecentMenu.addAction(action)
        else:
            self.fileOpenRecentMenu.setEnabled(False)

    def openRecentFile(self):
        action = self.sender()
        filename = unicode(action.data().toString())
        self.fileOpen(filename)

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
    
    def addActions(self, target, actions):
        for item in actions:
            if item is None:
                target.addSeparator()
            elif isinstance(item, QAction):
                target.addAction(item)
            elif isinstance(item, QActionGroup):
                target.addActions(item)
            elif isinstance(item, QMenu):
                target.addMenu(item)
    
    def createMenuAction(self, text, slot = None, shortcut = None, tip = None, signal = "triggered()", checkable = False):
        action = QAction(text, self)
        action.setCheckable(checkable)
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
            
            # Need to explicitly disconnect this signal, because the scene emits a selectionChanged right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChangedHandler)
            self.glWidget.doneCurrent()  # Avoid a crash when exiting
            event.accept()
        else:
            event.ignore()

    def fileClose(self, offerSave = True):
        if offerSave and not self.offerSave():
            return False
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.instructions.clear()
        self.treeModel.reset()
        self.treeModel.root = None
        self.scene.clear()
        self.filename = ""
        self.scene.emit(SIGNAL("layoutChanged()"))
        return True

    def offerSave(self):
        """ 
        Returns True if we should proceed with whatever operation
        was interrupted by this request.  False means cancel.
        """
        if not self.isWindowModified():
            return True
        reply = QMessageBox.question(self, "Lic - Unsaved Changes", "Save unsaved changes?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            return self.fileSave()
        return reply == QMessageBox.No

    def fileImport(self):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        formats = LicImporters.getFileTypesString()
        filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Import Model", dir, formats))
        if filename:
            self.setWindowModified(False)
            QTimer.singleShot(50, lambda: self.importModel(filename))

    def importModel(self, filename):

        if not self.fileClose():
            return

        #startTime = time.time()
        progress = LicDialogs.LicProgressDialog(self, "Importing " + os.path.basename(filename))
        progress.setValue(2)  # Try and force dialog to show up right away

        loader = self.instructions.importModel(filename)
        progress.setMaximum(loader.next())  # First value yielded after load is # of progress steps

        for label in loader:
            if progress.wasCanceled():
                loader.close()
                self.fileClose()
                return
            progress.incr(label)

        progress.setValue(progress.maximum())

        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.treeModel.root = self.instructions.mainModel

        try:
            template = LicBinaryReader.loadLicTemplate(self.defaultTemplateFilename, self.instructions)
            template.filename = ""  # Do not preserve default template filename
        except (IOError), e:
            # Could not load default template, so generate one from scratch
            import LicTemplate
            template = LicTemplate.TemplatePage(self.instructions.mainModel, self.instructions)
            template.createBlankTemplate(self.glWidget)
        
        self.instructions.template = template
        self.instructions.mainModel.partListPages = PartListPage.createPartListPages(self.instructions)
        template.applyFullTemplate(False)  # Template should apply to part list but not title pages

        self.instructions.mainModel.createNewTitlePage(False)
        
        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(1)

        config.filename = filename
        self.statusBar().showMessage("Model imported: " + filename)
        self.setWindowModified(True)
        self.enableMenus(True)
        self.copySettingsToScene()

        #endTime = time.time()
        #print "Total load time: %.2f" % (endTime - startTime)

    def loadLicFile(self, filename):

        #startTime = time.time()  # TODO: need to provide a status bar, since some files take forever to load
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        LicBinaryReader.loadLicFile(filename, self.instructions)
        self.treeModel.root = self.instructions.mainModel
        self.scene.emit(SIGNAL("layoutChanged()"))
        
        self.filename = filename
        self.addRecentFile(filename)
        self.scene.selectPage(1)
        self.copySettingsToScene()
        #endTime = time.time()
        #print "Total load time: %.2f" % (endTime - startTime)

    def enableMenus(self, enabled):
        self.fileCloseAction.setEnabled(enabled)
        self.fileSaveAction.setEnabled(enabled)
        self.fileSaveAsAction.setEnabled(enabled)
        self.fileSaveTemplateAction.setEnabled(enabled)
        self.fileSaveTemplateAsAction.setEnabled(enabled)
        self.fileLoadTemplateAction.setEnabled(enabled)
        self.viewMenu.setEnabled(enabled)
        self.exportMenu.setEnabled(enabled)
        self.treeWidget.treeToolBar.setEnabled(enabled)

    def fileSaveAs(self):
        if self.filename:
            f = self.filename
        else:
            f = self.instructions.getModelName()
            f = os.path.splitext(f)[0] + ".lic"

        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Save File As", f, "Lic Instruction Book files (*.lic)"))
        if filename:
            self.filename = filename
            self.instructions.filename = filename
            return self.fileSave()
        return False

    def fileSave(self):
        if self.filename == "":
            return self.fileSaveAs()

        tmpName = os.path.splitext(self.filename)[0] + "_bak.lic"
        tmpXName = self.filename + ".x"

        try:
            if os.path.isfile(tmpXName):
                os.remove(tmpXName)

            LicBinaryWriter.saveLicFile(tmpXName, self.instructions)

            if os.path.isfile(tmpName):
                os.remove(tmpName)
            if os.path.isfile(self.filename):
                os.rename(self.filename, tmpName)
            os.rename(tmpXName, self.filename)

            self.undoStack.setClean()
            self.addRecentFile(self.filename)
            self.statusBar().showMessage("Saved to: " + self.filename)
            return True

        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (self.filename, e))
        return False

    def fileSaveTemplate(self):
        template = self.instructions.template
        if template.filename == "":
            return self.fileSaveTemplateAs()

        if os.path.basename(template.filename) == self.defaultTemplateFilename:
            if QMessageBox.No == QMessageBox.question(self, "Lic - Replace Template", "This will replace the default template!  Proceed?", QMessageBox.Yes | QMessageBox.No):
                return

        try:
            LicBinaryWriter.saveLicTemplate(template)
            self.statusBar().showMessage("Saved Template to: " + template.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (template.filename, e))
    
    def fileSaveTemplateAs(self):
        template = self.instructions.template
        f = template.filename if template.filename else "template.lit"

        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Save Template As", f, "Lic Template files (*.lit)"))
        if filename:
            template.filename = filename
            return self.fileSaveTemplate()
    
    def fileLoadTemplate(self):
        templateName = self.instructions.template.filename
        dir = os.path.dirname(templateName) if templateName != "" else "."  # TODO: Check what happens if templateName has no path
        newFilename = unicode(QFileDialog.getOpenFileName(self, "Lic - Load Template", dir, "Lic Template files (*.lit)"))
        if newFilename and os.path.basename(newFilename) != templateName:
            try:
                newTemplate = LicBinaryReader.loadLicTemplate(newFilename, self.instructions)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Load Template Error", "Failed to open %s: %s" % (newFilename, e))
            else:
                self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
                self.scene.removeItem(self.instructions.template)
                self.instructions.template = newTemplate
                newTemplate.applyFullTemplate(True)
                self.scene.emit(SIGNAL("layoutChanged()"))
                self.setWindowModified(True)
    
    def fileOpen(self, filename = None):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        
        if filename is None:
            filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Open Instruction Book", dir, "Lic Instruction Book files (*.lic)"))
            
        if filename and filename != self.filename:
            self.fileClose(False)
            try:
                self.loadLicFile(filename)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Open Error", "Failed to open %s: %s" % (filename, e))
                self.fileClose()

    def exportImages(self):

        progress = LicDialogs.LicProgressDialog(self, "Exporting Final Images")
        progress.setValue(2)  # Try and force dialog to show up right away

        loader = self.instructions.exportImages()
        progress.setMaximum(loader.next() + 2)  # +2 because we're already at 2

        for label in loader:
            if progress.wasCanceled():
                loader.close()
                self.statusBar().showMessage("Image Export aborted")
                return
            label = "Rendering " + os.path.splitext(os.path.basename(label))[0].replace('_', ' ')
            progress.incr(label)

        self.glWidget.makeCurrent()
        self.statusBar().showMessage("Exported images to: " + config.finalImageCachePath())

    def exportToPDF(self):
        loader = self.instructions.exportToPDF()
        filename = loader.next()
        title = "Exporting " + os.path.splitext(os.path.basename(filename))[0] + " to PDF"

        progress = LicDialogs.LicProgressDialog(self, title)
        progress.setValue(2)  # Try and force dialog to show up right away
        progress.setMaximum(loader.next() + 2)  # +2 because we're already at 2

        for label in loader:
            if progress.wasCanceled():
                loader.close()
                self.statusBar().showMessage("PDF Export aborted")
                return
            progress.incr(label)

        progress.setValue(progress.maximum())

        self.glWidget.makeCurrent()
        self.statusBar().showMessage("Exported PDF to: " + filename)
                 
    def exportToPOV(self):
        self.instructions.exportToPOV()
        self.statusBar().showMessage("NYI - POV Export is broken")

    def exportToMPD(self):
        f = self.filename if self.filename else self.instructions.getModelName()
        f = os.path.splitext(f)[0] + "_lic.mpd"
        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Create MPD File", f, "LDraw files (*.mpd)"))
        if filename:
            fh = open(filename, 'w')
            self.instructions.mainModel.exportToLDrawFile(fh)
            fh.close()

def main():
    
    app = QApplication(sys.argv)
    app.setOrganizationName("BugEyedMonkeys Inc.")
    app.setOrganizationDomain("bugeyedmonkeys.com")
    app.setApplicationName("Lic")
    window = LicWindow()

    try:
        import psyco
        psyco.full()
    except ImportError:
        pass  # Ignore missing psyco silently - it's a nice optimization to have, not required

    window.show()
    window.raise_()  # Work around bug in OSX Qt where app launches behind all other windows.  Harmless on other platforms.

    if window.needPathConfiguration:
        window.configurePaths(True)

    # Load a particular file on Lic launch - handy for debugging 
    filename = ""
    #filename = unicode("C:/lic/viper.mpd")
    #filename = unicode("C:/lic/6x10.lic")
    #filename = unicode("C:/lic/6x10.dat")
    #filename = unicode("C:/lic/template.dat")
    #filename = unicode("C:/lic/stack.lic")
    #filename = unicode("C:/lic/1x1.dat")
    filename = unicode("C:/lic/pyramid.lic")
    #filename = unicode("C:/lic/SubSubModel.mpd")

    if filename:
        QTimer.singleShot(50, lambda: loadFile(window, filename))

    #updateAllSavedLicFiles(window)
    
    sys.exit(app.exec_())

def loadFile(window, filename):

    if filename[-3:] == 'dat' or filename[-3:] == 'mpd' or filename[-3:] == 'ldr':
        window.importModel(filename)
    elif filename[-3:] == 'lic':
        window.fileOpen(filename)
    else:
        print "Bad file extension: " + filename
        return

    window.scene.selectFirstPage()

def recompileResources():
    # Handy function for rebuilding the resources.py package (which contains all the app's icons)
    # Note that this call is utterly specific to Remi's dev environment, and is not meant to be called anywhere else
    ret = os.spawnl(os.P_WAIT, r"C:\Python25\Lib\site-packages\PyQt4\pyrcc4.exe", "pyrcc4.exe", "-o", r"C:\lic\src\resources.py", r"C:\lic\resources.qrc")
    print ret

def updateAllSavedLicFiles(window):
    # Useful for when too many new features accumulate in LicBinaryReader & Writer.
    # Use this to open each .lic file in the project, save it & close it.
    for root, unused, files in os.walk("C:\\lic"):
        for f in files:
            if f[-3:] == 'lic':
                fn = os.path.join(root, f)
                print "Trying  to  open %s" % fn
                window.fileOpen(fn)
                if window.instructions.licFileVersion != FileVersion:
                    window.fileSave()
                    print "Successfull save %s" % fn
                window.fileClose()

if __name__ == '__main__':
    #import cProfile
    #cProfile.run('main()', 'profile_run')
    main()
    #recompileResources()
