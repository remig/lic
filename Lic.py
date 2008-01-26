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
import LicUndoActions

try:
    from OpenGL.GL import *
except ImportError:
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Lic 0.1",
                         "PyOpenGL must be installed to run Lic.",
                         QMessageBox.Ok | QMessageBox.Default,
                         QMessageBox.NoButton)
    sys.exit(1)

__version__ = 0.1
PageSize = QSize(800, 600)

class InstructionViewWidget(QGraphicsView):
    def __init__(self, parent):
        QGLWidget.__init__(self,  parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(Qt.gray))

    def keyReleaseEvent(self, event):

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
            # We do not handle this key stroke here - ignore and return
            event.ignore()
            return

        movedItems = []
        for item in self.scene().selectedItems():
            if isinstance(item, Page):
                continue  # Pages cannot be moved

            item.oldPos = item.pos()
            item.moveBy(x, y)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()
            movedItems.append(item)

        if movedItems:
            self.emit(SIGNAL("itemsMoved"), movedItems)

    # Will need this for when right-clicking on a selected Part, since they're not GraphicsItems
    """
    def contextMenuEvent(self, event):

        menu = None
        for item in self.scene().selectedItems():
            if isinstance(item, Part):
                item.contextMenuEvent(event)
                return
            
        event.ignore()
    """

class LicWindow(QMainWindow):

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), self._setWindowModified)
        
        self.glWidget = QGLWidget(self)
        self.treeView = LicTreeView(self)

        statusBar = self.statusBar()
        self.scene = QGraphicsScene(self)
        self.graphicsView = InstructionViewWidget(self)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, PageSize.width(), PageSize.height())
        
        self.connect(self.graphicsView, SIGNAL("itemsMoved"), self.itemsMoved)
        self.connect(self.scene, SIGNAL("itemsMoved"), self.itemsMoved)

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

        self.connect(self.graphicsView, SIGNAL("pageUp"), self.instructions.pageUp)
        self.connect(self.graphicsView, SIGNAL("pageDown"), self.instructions.pageDown)
        self.connect(self.graphicsView, SIGNAL("home"), self.instructions.selectFirstPage)
        self.connect(self.graphicsView, SIGNAL("end"), self.instructions.selectLastPage)
        
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
        
    def itemsMoved(self, itemList):
        self.undoStack.push(LicUndoActions.MoveCommand(itemList))

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
        self.fileMenu = menu.addMenu("&File")

        self.fileOpenAction = self.createMenuAction("&Open", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileMenu.addAction(self.fileOpenAction)

        self.fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")
        self.fileMenu.addAction(self.fileCloseAction)

        self.fileMenu.addSeparator()

        self.fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileMenu.addAction(self.fileSaveAction)

        self.fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        self.fileMenu.addAction(self.fileSaveAsAction)

        self.fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing LDraw Model into a new Instruction book")
        self.fileMenu.addAction(self.fileImportAction)

        self.fileMenu.addSeparator()

        self.fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")
        self.fileMenu.addAction(self.fileExitAction)

        self.editMenu = menu.addMenu("&Edit")
        
        self.undoAction = self.createMenuAction("&Undo", None, "Ctrl+Z", "Undo last action")
        self.undoAction.connect(self.undoAction, SIGNAL("triggered()"), self.undoStack, SLOT("undo()"))
        self.undoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canUndoChanged(bool)"), self.undoAction, SLOT("setEnabled(bool)"))
        self.editMenu.addAction(self.undoAction)
        
        self.redoAction = self.createMenuAction("&Redo", None, "Ctrl+Y", "Redo the last undone action")
        self.redoAction.connect(self.redoAction, SIGNAL("triggered()"), self.undoStack, SLOT("redo()"))
        self.redoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canRedoChanged(bool)"), self.redoAction, SLOT("setEnabled(bool)"))
        self.editMenu.addAction(self.redoAction)
        
        self.viewMenu = menu.addMenu("&View")
        
        self.pageMenu = menu.addMenu("&Page")

        self.pageSize = self.createMenuAction("Page Size...", self.changePageSize, None, "Change the overall size of all Pages in this Instruction book")
        self.pageMenu.addAction(self.pageSize)
        
        self.csipliSizeAction = self.createMenuAction("CSI | PLI Image Size...", self.changeCSIPLISize, None, "Change the relative size of all CSIs and PLIs throughout Instruction book")
        self.pageMenu.addAction(self.csipliSizeAction)
        
        self.exportMenu = menu.addMenu("E&xport")
        
        self.exportImagesAction = self.createMenuAction("Generate Final Images", self.exportImages, None, "Generate final, high res images of each page in this Instruction book")
        self.exportMenu.addAction(self.exportImagesAction)

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
            self.undoStack.push(LicUndoActions.ResizeCSIPLICommand(self.instructions, sizes))

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
            # Need to explicitly disconnect this signal, because the scene emits an updateSelection right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateSelection)
            event.accept()
        else:
            event.ignore()

    def fileClose(self):
        if not self.offerSave():
            return
        if self.filename:
            self.instructions.clear()
        self.filename = ""

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

    def loadModel(self, filename):
        self.instructions.loadModel(filename)
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
                LicBinaryReader.loadLicFile(filename, self.instructions)
                self.filename = filename
            except IOError, e:
                QMessageBox.warning(self, "Lic - Open Error", "Failed to open %s: %s" % (filename, e))
                self.fileClose()

    def exportImages(self):
        self.instructions.exportImages()
        print "\nExport complete"
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LicWindow()
    window.show()
    sys.exit(app.exec_())
