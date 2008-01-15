#from __future__ import division
import random
import sys
import math

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from Model_qt import *
import LicBinaryFile
import config
import l3p
import povray
import GLHelpers_qt

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
        moved = False
        
        if event.modifiers() & Qt.ShiftModifier:
            offset = 20 if event.modifiers() & Qt.ControlModifier else 5
    
        for item in self.scene().selectedItems():
            if key == Qt.Key_Left:
                item.moveBy(-offset, 0)
                moved = True
            elif key == Qt.Key_Right:
                item.moveBy(offset, 0)
                moved = True
            elif key == Qt.Key_Up:
                item.moveBy(0, -offset)
                moved = True
            elif key == Qt.Key_Down:
                item.moveBy(0, offset)
                moved = True
            if moved and hasattr(item.parentItem(), "resetRect"):
                    item.parentItem().resetRect()
        if moved:
            self.emit(SIGNAL("itemMoved"))
            
class LicWindow(QMainWindow):

    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)

        self.glWidget = QGLWidget(self)
        self.treeView = LicTreeView(self)

        self.scene = QGraphicsScene(self)
        self.graphicsView = InstructionViewWidget(self)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, PageSize.width(), PageSize.height())
        self.connect(self.graphicsView, SIGNAL("itemMoved"), self.invalidateInstructions)

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeView)
        self.mainSplitter.addWidget(self.graphicsView)
        self.setCentralWidget(self.mainSplitter)

        # temp debug code
        #self.modelName = None
        #self.modelName = "c:\\ldrawparts\\models\\Blaster.mpd"
        #self.modelName = "c:\\ldrawparts\\models\\3001.DAT"
        self.filename = "C:\\ldraw\\lic\\models\\pyramid_orig.lic"
        #self.filename = "C:\\ldraw\\lic\\pyramid_orig_displaced.lic"
        self.modelName = "C:\\ldraw\\lic\\models\\pyramid_orig.dat"

        self.initMenu()
        statusBar = self.statusBar()
        statusBar.showMessage("Model: " + self.modelName)

        self.instructions = Instructions(self.treeView, self.scene, self.glWidget)
        self.treeView.setModel(self.instructions)
        self.selectionModel = QItemSelectionModel(self.instructions)
        self.treeView.setSelectionModel(self.selectionModel)
        self.treeView.connect(self.scene, SIGNAL("selectionChanged()"), self.treeView.updateSelection)

        config.config = self.initConfig()

        if self.filename:
            LicBinaryFile.loadLicFile(self.filename, self.instructions)
#            self.loadModel(self.modelName)

        title = "Lic %s" % __version__
        if self.filename:
            title += " - " + os.path.basename(self.filename)
        self.setWindowTitle(title)

    def initConfig(self):
        config = {}
        cwd = os.path.join(os.getcwd(), 'cache')
        
        if not os.path.isdir(cwd):
            os.mkdir(cwd)   # Create DAT directory if needed
            
        config['datPath'] = os.path.join(cwd, 'DATs')
        if not os.path.isdir(config['datPath']):
            os.mkdir(config['datPath'])   # Create DAT directory if needed

        config['povPath'] = os.path.join(cwd, 'POVs')
        if not os.path.isdir(config['povPath']):
            os.mkdir(config['povPath'])   # Create POV directory if needed

        config['pngPath'] = os.path.join(cwd, 'PNGs')
        if not os.path.isdir(config['pngPath']):
            os.mkdir(config['pngPath'])   # Create PNG directory if needed

        return config

    def invalidateInstructions(self):
        self.instructions.dirty = True
        
    def initMenu(self):
        menu = self.menuBar()
        fileMenu = menu.addMenu("&File")

        fileOpenAction = self.createMenuAction("&Open", self.fileOpen, QKeySequence.Open, "Open an existing Instruction book")
        fileMenu.addAction(fileOpenAction)

        fileCloseAction = self.createMenuAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")
        fileMenu.addAction(fileCloseAction)

        fileMenu.addSeparator()

        fileSaveAction = self.createMenuAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        fileMenu.addAction(fileSaveAction)

        fileSaveAsAction = self.createMenuAction("Save &As...", self.fileSaveAs, None, "Save the Instruction book using a new filename")
        fileMenu.addAction(fileSaveAsAction)

        fileImportAction = self.createMenuAction("&Import Model", self.fileImport, None, "Import an existing LDraw Model into a new Instruction book")
        fileMenu.addAction(fileImportAction)

        fileMenu.addSeparator()

        fileExitAction = self.createMenuAction("E&xit", SLOT("close()"), "Ctrl+Q", "Exit Lic")
        fileMenu.addAction(fileExitAction)

        editMenu = menu.addMenu("&Edit")
        
        viewMenu = menu.addMenu("&View")
        
        exportMenu = menu.addMenu("E&xport")
        
        exportImagesAction = self.createMenuAction("Generate Final Images", self.exportImages, None, "Generate final, high res images of each page in this Instruction book")
        exportMenu.addAction(exportImagesAction)

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
        self.instructions.clear()
        self.setWindowTitle("Lic %s" % __version__)
        self.filename = ""
        self.update()

    def offerSave(self):
        """ 
        Returns True if we should proceed with whateve 
        operation was interrupted by this request.  False means cancel.
        """
        if not self.instructions.dirty:
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
            self.statusBar().showMessage("LDraw Model imported: " + self.modelName)

    def fileSaveAs(self):
        filename = unicode(QFileDialog.getSaveFileName(self, "Lic - Safe File As", self.filename, "Lic Instruction Book files (*.lic)"))
        if filename:
            self.filename = filename
            self.setWindowTitle("Lic %s - %s" % (__version__, os.path.basename(self.filename)))
            return self.fileSave()

    def fileSave(self):
        try:
            LicBinaryFile.saveLicFile(self.filename, self.instructions)
            self.statusBar().showMessage("Saved to: " + self.filename)
        except (IOError, OSError), e:
            QMessageBox.warning(self, "Lic - Save Error", "Failed to save %s: %s" % (filename, e))

    def fileOpen(self):
        if not self.offerSave():
            return
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        filename = unicode(QFileDialog.getOpenFileName(self, "Lic - Open Instruction Book", dir, "Lic Instruction Book files (*.lic)"))
        if filename and filename != self.filename:
            self.fileClose()
            try:
                LicBinaryFile.loadLicFile(filename, self.instructions)
                self.filename = filename
                self.setWindowTitle("Lic %s - %s" % (__version__, os.path.basename(self.filename)))
                self.statusBar().showMessage("Instruction book loaded: " + self.filename)
            except IOError, e:
                QMessageBox.warning(self, "Lic - Open Error", "Failed to open %s: %s" % (filename, e))
                self.fileClose()

    def loadModel(self, filename):
        self.instructions.loadModel(filename)
        self.modelName = filename
        self.update()

    def exportImages(self):
        image = QImage(PageSize.width(), PageSize.height(), QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(image)
        self.graphicsView.drawBackground(painter, QRectF(0, 0, PageSize.width(), PageSize.height()))
        
        page = self.instructions.currentPage
        items = page.getAllChildItems()
        print "exporting %d items..." % len(items)
        options = QStyleOptionGraphicsItem()
        optionList = [options] * len(items)
        self.graphicsView.drawItems(painter, items, optionList)
        painter.end()
        image.save("C:\\LDraw\\tmp\\hello.png", None)
        
        modelname = self.instructions.filename
        datPath = os.path.join(config.config['datPath'], self.instructions.filename)
        if not os.path.isdir(datPath):
            os.mkdir(datPath)
            
        for page in self.instructions.pages:
            for step in page.steps:
                csiName = "CSI_Page_%d_Step_%d.dat" % step.csi.getPageStepNumberPair()
                datFile = os.path.join(datPath, csiName)
                
                if not os.path.isfile(datFile):
                    fh = open(datFile, 'w')
                    step.csi.exportToLDrawFile(fh)
                    fh.close()
                    
                camera = GLHelpers_qt.getDefaultCamera()
                povFile = l3p.createPovFromDat(datFile, modelname)
                pngFile = povray.createPngFromPov(povFile, modelname, step.csi.width, step.csi.height, step.csi.center, camera, None)
    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LicWindow()
    window.show()
    sys.exit(app.exec_())
