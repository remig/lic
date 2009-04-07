#from __future__ import division
import random
import sys
import math

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from Model import *
import LicBinaryReader
import LicBinaryWriter
import config
import l3p
import povray
import LicDialogs
from LicUndoActions import *

__version__ = 0.1
PageSize = QSize(800, 600)

class LicGraphicsScene(QGraphicsScene):

    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)

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
        # menu that was *clicked on*, not the menu of the selected items
        # TODO: need to handle this better: What if a page and a step are selected?
        for item in self.selectedItems():
            if isinstance(item, Part):
                item.contextMenuEvent(event)
                return
            if isinstance(item, Step):
                item.contextMenuEvent(event)
                return
            if isinstance(item, Page):
                item.contextMenuEvent(event)
                return
            if isinstance(item, Callout):
                item.contextMenuEvent(event)
                return

    def keyReleaseEvent(self, event):

        for item in self.selectedItems():
            if isinstance(item, Part):
                QGraphicsScene.keyReleaseEvent(self, event)
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
            # We do not handle this key stroke here - pass it on and return
            QGraphicsScene.keyReleaseEvent(self, event)
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

class LicGraphicsView(QGraphicsView):
    def __init__(self, parent):
        QGLWidget.__init__(self,  parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(Qt.gray))

class LicWindow(QMainWindow):

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        
        self.initWindowSettings()
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), self._setWindowModified)
        
        self.glWidget = QGLWidget(self)
        self.treeView = LicTreeView(self)

        statusBar = self.statusBar()
        self.scene = LicGraphicsScene(self)
        self.scene.undoStack = self.undoStack  # Make undo stack easy to find for everything

        self.graphicsView = LicGraphicsView(self)
        self.graphicsView.setScene(self.scene)
        self.graphicsView.setViewport(self.glWidget)
        self.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.scene.setSceneRect(0, 0, PageSize.width(), PageSize.height())
        
        self.createUndoSignals()

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeView)
        self.mainSplitter.addWidget(self.graphicsView)
        self.setCentralWidget(self.mainSplitter)

        self.initMenu()

        self.instructions = Instructions(self.treeView, self.scene, self.glWidget)
        self.treeView.setModel(self.instructions)
        self.selectionModel = QItemSelectionModel(self.instructions)
        self.treeView.setSelectionModel(self.selectionModel)
        self.treeView.connect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateSelection)

        self.connect(self.scene, SIGNAL("pageUp"), self.instructions.pageUp)
        self.connect(self.scene, SIGNAL("pageDown"), self.instructions.pageDown)
        self.connect(self.scene, SIGNAL("home"), self.instructions.selectFirstPage)
        self.connect(self.scene, SIGNAL("end"), self.instructions.selectLastPage)
        
        # Allow the graphics scene to emit the layoutAboutToBeChanged and layoutChanged 
        # signals, for easy notification of layout changes everywhere
        self.connect(self.scene, SIGNAL("layoutAboutToBeChanged()"), self.instructions, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.scene, SIGNAL("layoutChanged()"), self.instructions, SIGNAL("layoutChanged()"))
            
        self.filename = ""   # This will trigger the __setFilename method below

        # temp debug code from here to the end 
        self.__filename = self.modelName = ""
        #self.__filename = "C:\\ldraw\\lic\\models\\pyramid_orig.lic"
        #self.modelName = "C:\\ldraw\\lic\\models\\pyramid_orig.dat"

        if self.__filename:
            LicBinaryReader.loadLicFile(self.__filename, self.instructions)
            self.filename = self.__filename
            
        if self.modelName:
            self.loadModel(self.modelName)
            statusBar.showMessage("Model: " + self.modelName)

    def initWindowSettings(self):
        settings = QSettings()
        self.recentFiles = settings.value("RecentFiles").toStringList()
        self.restoreGeometry(settings.value("Geometry").toByteArray())
        self.restoreState(settings.value("MainWindow/State").toByteArray())
    
    def keyReleaseEvent(self, event):
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

        signals = [("itemsMoved", MoveCommand),
                   ("moveStepToNewPage", MoveStepToPageCommand),
                   ("displacePart", DisplacePartCommand),
                   ("adjustArrowLength", AdjustArrowLength)]

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

    def initMenu(self):
        
        menu = self.menuBar()
        
        # File Menu
        self.fileMenu = menu.addMenu("&File")
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"), self.updateFileMenu)

        self.fileOpenAction = self.createMenuAction("&Open...", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")

        self.fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        self.fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing LDraw Model into a new Instruction book")

        self.fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")

        self.fileMenuActions = (self.fileOpenAction, self.fileCloseAction, None, self.fileSaveAction, self.fileSaveAsAction, self.fileImportAction, None, self.fileExitAction)
        
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

        # Page Menu
        self.pageMenu = menu.addMenu("&Page")

        self.pageSizeAction = self.createMenuAction("Page Size...", self.changePageSize, None, "Change the overall size of all Pages in this Instruction book")       
        self.csipliSizeAction = self.createMenuAction("CSI | PLI Image Size...", self.changeCSIPLISize, None, "Change the relative size of all CSIs and PLIs throughout Instruction book")
        self.addActions(self.pageMenu, (self.pageSizeAction, self.csipliSizeAction))
        
        # Export Menu
        self.exportMenu = menu.addMenu("E&xport")
        self.exportImagesAction = self.createMenuAction("Generate Final Images", self.exportImages, None, "Generate final, high res images of each page in this Instruction book")
        self.exportMenu.addAction(self.exportImagesAction)

    def updateFileMenu(self):
        self.fileMenu.clear()
        self.addActions(self.fileMenu, self.fileMenuActions[:-1])  # Don't add last Exit yet
        
        recentFiles = []
        for filename in self.recentFiles:
            if filename != QString(self.filename):
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
    
    def changeCSIPLISize(self):
        dialog = LicDialogs.CSIPLIImageSizeDlg(self, CSI.scale, PLI.scale)
        self.connect(dialog, SIGNAL("newCSIPLISize"), self.setCSIPLISize)
        dialog.show()

    def setCSIPLISize(self, newCSISize, newPLISize):
        if newCSISize != CSI.scale or newPLISize != PLI.scale:
            sizes = ((CSI.scale, newCSISize), (PLI.scale, newPLISize))
            self.undoStack.push(ResizeCSIPLICommand(self.instructions, sizes))

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
            settings = QSettings()
            recentFiles = QVariant(self.recentFiles) if self.recentFiles else QVariant()
            settings.setValue("RecentFiles", recentFiles)
            settings.setValue("Geometry", QVariant(self.saveGeometry()))
            settings.setValue("MainWindow/State", QVariant(self.saveState()))
            
            # Need to explicitly disconnect this signal, because the scene emits an updateSelection right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateSelection)
            event.accept()
        else:
            event.ignore()

    def fileClose(self):
        if not self.offerSave():
            return
        self.instructions.clear()
        self.filename = ""
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
            self.fileClose()
            self.loadModel(filename)
            self.statusBar().showMessage("LDraw Model imported: " + filename)

    def loadLicFile(self, filename = None):
        
        if filename is None:
            action = self.sender()
            filename = unicode(action.data().toString())
            if not self.offerSave():
                return
            
        LicBinaryReader.loadLicFile(filename, self.instructions)
        self.filename = filename
        self.addRecentFile(filename)
    
    def loadModel(self, filename):
        
        loader = self.instructions.loadModel(filename)
        startValue = 0
        stopValue, title = loader.next()

        progress = QProgressDialog(title, "Cancel", startValue, stopValue, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("Importing " + os.path.splitext(os.path.basename(filename))[0])
        
        for step, label in loader:
            progress.setValue(step)
            progress.setLabelText(label)
            
            if progress.wasCanceled():
                loader.close()
                self.fileClose()
                return

        progress.setValue(stopValue)
        
        config.config = self.initConfig()
        self.statusBar().showMessage("Instruction book loaded")
        self.fileCloseAction.setEnabled(True)
        self.fileSaveAsAction.setEnabled(True)
        self.editMenu.setEnabled(True)
        self.pageMenu.setEnabled(True)
        self.viewMenu.setEnabled(True)
        self.exportMenu.setEnabled(True)

    def fileSaveAs(self):
        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe File As", self.filename, "Lic Instruction Book files (*.lic)"))
        if filename:
            self.filename = filename
            return self.fileSave()

    def fileSave(self):
        try:
            LicBinaryWriter.saveLicFile(self.filename, self.instructions)
            self.setWindowModified(False)
            self.addRecentFile(self.filename)
            self.statusBar().showMessage("Saved to: " + self.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (self.filename, e))

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

    def exportImages(self):
        self.instructions.exportImages()
        print "\nExport complete"
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setOrganizationName("BugEyedMonkeys Inc.")
    app.setOrganizationDomain("bugeyedmonkeys.com")
    app.setApplicationName("Lic")
    window = LicWindow()
    window.show()
    sys.exit(app.exec_())
