"""
    LIC - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne
    Copyright (C) 2015 Jeremy Czajkowski

    This file (Lic.py) is part of LIC.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
   
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
   
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import subprocess
import sys
import time
import urllib

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from LicAssistantWidget import *
import LicBinaryReader
import LicBinaryWriter
from LicGraphicsWidget import *
from LicImporters import BuilderImporter
from LicInstructions import Instructions
from LicModel import *


def __recompileResources():
    # Handy personal function for rebuilding LicResources.py package (which contains the app's icons)
    src_path = os.path.dirname(os.path.abspath(__file__)).lower()
    python_home = os.environ.get("PYTHON_HOME", os.environ.get("PYTHONHOME", ""))
    
    if python_home:
        pyrcc_path = r"%s\Lib\site-packages\PyQt4\pyrcc4.exe" % python_home
        
        qrc_path = os.path.join(src_path , ".." , "resources.qrc")
        res_path = os.path.join(src_path , "LicResources.py")
        subprocess.call("%s %s -o %s" % (pyrcc_path, qrc_path, res_path))
        print "Resource bundle created: %s" % res_path
    
try:
    import LicResources  # Needed for ":/resource" type paths to work
except ImportError:
    try:
        __recompileResources()
        import LicResources
    except:
        pass  # Ignore missing Resource bundle silently - better to run without icons then to crash entirely

__version__ = "3.1.222"
_debug = False

if _debug:
    from modeltest import ModelTest

class LicTreeView(QTreeView):

    def __init__(self, parent):
        QTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setAutoExpandDelay(400)
        self.scene = None
        self.expandedDepth = 0        
    
    def __getEmptyText(self):
        return QString("Choose your model to build great manual. Because the world depends on it.")
 
    def __getTopIndex(self):
        return self.indexAt(self.rect().topLeft())   
    
    _padding = 20
    
    emptytext = property(__getEmptyText)
    topindex = property(__getTopIndex)
        
    def walkTreeModel(self, comp, action):
        
        model = self.model()
        
        def traverse(index):
            
            if index.isValid() and comp(index):
                action(index)
                 
            for row in range(model.rowCount(index)):
                if not index.isValid() and row == 0:
                    continue  # Special case: skip the template page
                traverse(model.index(row, 0, index))
        
        traverse(QModelIndex())             
                 
    def walkToNextTopChild(self):
        """ Jump to next|current top-level item at destination page """
        selected = self.selectionModel().currentIndex()
    # second level
        if selected.parent().data(Qt.WhatsThisRole).toPyObject():
            if selected.parent().data(Qt.WhatsThisRole).toPyObject().toLower().endsWith('page'):
                selected = selected.sibling(selected.row() + 1 , selected.column())
    # lower levels            
        chosen = selected
        if chosen.isValid():
            while True:
                if chosen.parent().isValid():
                    if chosen.parent().data(Qt.WhatsThisRole).toPyObject().toLower().endsWith('page'):
                        break
                chosen = chosen.parent()
                if not chosen.isValid():
                    break
                  
            if chosen.isValid():
                selected = chosen

    # if nothing is selected, get first on matching list
        if not selected.isValid():
                p = self.selectionModel().currentIndex()
                selected = p.sibling(0 , p.column())
    
    # if is valid clear and select chosen QModelIndex             
        if selected.isValid():
            self.selectionModel().select(selected, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            self.selectionModel().setCurrentIndex(selected , QItemSelectionModel.SelectCurrent)
            
    def hideRowInstance(self, instanceType, hide):
        # instanceType can be either concrete type like PLI or itemClassString
        # like "Page Number" (for specific QGraphicsSimpleTextItems) 

        def compare(index):
            ptr = index.internalPointer()
            if isinstance(instanceType, str):
                return ptr.itemClassName == instanceType
            return isinstance(ptr, instanceType)

        action = lambda index: self.setRowHidden(index.row(), index.parent(), hide)
        self.walkTreeModel(compare, action)

    def collapseAll(self):
        QTreeView.collapseAll(self)
        self.expandedDepth = 0

    def expandOneLevel(self):
        self.expandToDepth(self.expandedDepth)
        self.expandedDepth += 1
        self.collapse(self.topindex)
        
    def expandChildren(self):
        selection = self.selectionModel().currentIndex()
        if selection and selection.isValid():
            self.expand(selection)
            
            childCount = selection.model().rowCount(selection)
            for i in range(0, childCount):
                self.expand(selection.child(i, 0))

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
            self.scene.notificationArea.clear()
            if len(selList) < 2:
                # select item
                self.setCurrentIndex(index)
                # put information on status bar
                if item and isinstance(item, (PLIItem,Part)):
                    roleData = item.data(Qt.AccessibleDescriptionRole)
                    if roleData:
                        self.scene.notificationArea.setText(roleData)
                
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
            
        # Put information on status bar
            item = partList[0]
            if item and isinstance(item, (PLIItem,Part)):
                if partList.__len__() > 1:
                    roleData = "%d objects were selected" % partList.__len__()
                else:
                    roleData = item.data(Qt.AccessibleDescriptionRole)
                    
                self.scene.notificationArea.setText(roleData)
            
    def paintEvent(self, *args, **kwargs):
        if self.model() and self.model().rowCount(self.rootIndex()) > 0:
            return QTreeView.paintEvent(self, *args, **kwargs)
        else:
    # If no items draw a text in the center of the viewport.
            painter = QPainter(self.viewport())
            rect = painter.fontMetrics().boundingRect(self.emptytext)
            rect.setWidth(self.width() - self._padding)
            rect.setHeight(rect.height() * 3)
            rect.moveCenter(self.viewport().rect().center())
            painter.drawText(rect, Qt.AlignRight | Qt.TextWordWrap, self.emptytext)     
                    
    def keyPressEvent(self, event):
        if event.key() not in [Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:  
        # Ignore these 5 here - passed to Scene on release
            QTreeView.keyPressEvent(self, event)

    def keyReleaseEvent(self, event):
        if event.key() in [Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
        # Pass these keys on to the Scene
                return self.scene.keyReleaseEvent(event)

        QTreeView.keyReleaseEvent(self, event)
        # Let scene know about new selection
        self.pushTreeSelectionToScene()

    def mousePressEvent(self, event):
        """ Mouse click in Tree Widget means its selection has changed.  Copy selected items from Tree to Scene."""

        QTreeView.mousePressEvent(self, event)

        if event.button() == Qt.RightButton:
            return  # Ignore right clicks - they're passed on to selected item for their context menu

        self.pushTreeSelectionToScene()

    def contextMenuEvent(self, event):
        # Pass right clicks on to the item right-clicked on
        # Ignore multiple selection - contextMenu can handle only single item  
        event.screenPos = event.globalPos   
        item = self.indexAt(event.pos())
        if item.internalPointer():
                if self.selectionModel().selectedIndexes() > 1:
                    self.pushTreeSelectionToScene()
                if not isinstance(item.internalPointer(), QGraphicsSimpleTextItem):
                    return item.internalPointer().contextMenuEvent(event)

        
    def wheelEvent(self, event):
        current = self.selectionModel().currentIndex()
        scrollstep = -1
        if event.delta() < 0:
            scrollstep = 1
        if current.model():
            nextstep = current.row() + scrollstep
            parent = current.parent()
            if nextstep > current.model().rowCount(parent) - 1:
                nextstep = 0
            elif nextstep < 0:
                nextstep = current.model().rowCount(parent) - 1
                
            nextindex = current.model().index(nextstep , current.column() , parent)
            self.selectionModel().select(nextindex, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            self.selectionModel().setCurrentIndex(nextindex , QItemSelectionModel.SelectCurrent)
        
        QTreeView.wheelEvent(self, event)
        # Let scene know about new selection
        self.pushTreeSelectionToScene()


class LicTreeWidget(QWidget):
    """
    Combines a LicTreeView (itself a full widget) and a toolbar with a few buttons to control the tree layout.
    """
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        
        self.tree = LicTreeView(self)
        
        self.hiddenRowActions = []
        self.hiddenRowState = {}
        
        self.setMinimumWidth(250)
        self.setMaximumWidth(400)
        
        self.treeToolBar = QToolBar("Tree Toolbar", self)
        self.treeToolBar.setIconSize(QSize(18, 18))
        self.treeToolBar.setStyleSheet("QToolBar { border: 0px; }")
        self.treeToolBar.addAction(QIcon(":/expand_current"), "Expand current" , self.tree.expandChildren)
        self.treeToolBar.addAction(QIcon(":/expand"), "Expand", self.tree.expandOneLevel)
        self.treeToolBar.addAction(QIcon(":/collapse"), "Collapse", self.tree.collapseAll)

        # An empty widget with automatic expanding, it works like the spacers you can use in Qt Designer
        self.spacer = QWidget(self.treeToolBar)
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.treeToolBar.addWidget(self.spacer)

        viewToolButton = QToolButton(self.treeToolBar)
        viewToolButton.setIcon(QIcon(":/down_arrow"))
        viewToolButton.setStyleSheet("QToolButton::menu-indicator { image: url(:/blank) }")
        
        viewToolButton.setObjectName("viewToolButton")
        viewMenu = QMenu(viewToolButton)
        viewMenu.connect(viewMenu, SIGNAL("triggered(QAction *)"), self.menuEvent)

        def addViewAction(title, slot, checked=True):
            action = QAction(title, viewMenu)
            hexTitle = str(title.encode("hex"))
            action.setCheckable(True)
            action.setChecked(checked)
            action.setWhatsThis(hexTitle)
            action.connect(action, SIGNAL("toggled(bool)"), slot)
            action.action = slot
            viewMenu.addAction(action)
            
            return action

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
        viewToolButton.setToolTip("Show / Hide elements")
        viewToolButton.setFocusPolicy(Qt.NoFocus)
        self.treeToolBar.addWidget(viewToolButton)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.treeToolBar, 0, Qt.AlignRight)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def menuEvent(self, action):
        self.hiddenRowState[action.whatsThis()] = action.isChecked()

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
        CSITreeManager.showPartGroupings = show
        
        # Need to reset all cached Part data strings 
        compare = lambda index: isinstance(index.internalPointer(), Part)
        action = lambda index: index.internalPointer().resetDataString()
        self.tree.walkTreeModel(compare, action)
        
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def setShowCSI(self, show):
        model = self.tree.model()
        model.emit(SIGNAL("layoutAboutToBeChanged()"))
        StepTreeManager._showCSI = show
        model.emit(SIGNAL("layoutChanged()"))
        self.resetHiddenRows()

    def resetHiddenRows(self):
        for action in self.hiddenRowActions:
            action.action(action.isChecked())

class LicWindow(QMainWindow):

    defaultTemplateFilename = "default_template.lit"

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        QGL.setPreferredPaintEngine(QPaintEngine.OpenGL)
        
        self._loadTime = (0, 0)
        
        self._worker = None
        
        self.repository = None
        
        '''
         For LicShortcutAssistant single instance
        '''
        self.assistant = None
       
        '''
         For single instance from LicAssistantWidget.py file
         For single instance of MessageDlg class
         it is released via LicWindow.releaseAssist when:
          ::  user doing action not in this instance, like press key or mouse button outside dialog
          ::  dialog must be closed due to action not assigned to this dialog
        '''
        self.assistHandle = None
        
        self.hRuler = None
        self.vRuler = None
        
        self.latestimportfolder = ""
        
        self.loadSettings()
        self.setWindowIcon(QIcon(":/lic_logo"))
        self.setMinimumWidth(800)
        self.setMinimumHeight(400)
        self.setAcceptDrops(True)
        
        self.undoStack = QUndoStack()
        self.connect(self.undoStack, SIGNAL("cleanChanged(bool)"), lambda isClean: self.setWindowModified(not isClean))

        self.glWidget = QGLWidget(LicGLHelpers.getGLFormat(), self)
        self.treeWidget = LicTreeWidget(self)
        self.scene = LicGraphicsScene(self)
        self.scene.undoStack = self.undoStack  # Make undo stack easy to find for everything
        self.copySettingsToScene()

        self.graphicsView = LicGraphicsView(self)
        self.graphicsView.setViewport(self.glWidget)
        self.graphicsView.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.graphicsView.setScene(self.scene)
        self.scene.setSceneRect(0, 0, Page.PageSize.width() + 28, Page.PageSize.height() + 25)
        
        # Connect the items moved signal to a push command on undo stack
        self.connect(self.scene, SIGNAL("itemsMoved"), lambda x: self.undoStack.push(LicUndoActions.MoveCommand(x)))

        self.mainSplitter = QSplitter(Qt.Horizontal)
        self.mainSplitter.addWidget(self.treeWidget)
        self.mainSplitter.addWidget(self.graphicsView)
        self.mainSplitter.restoreState(self.splitterState)
        self.setCentralWidget(self.mainSplitter)
        
        self.initMenu()
        self.initToolBars()
        self.initStatusBar()

        self.scene.notificationArea = self.notificationArea  # Make this notification area easy to find for everything
        
        self.instructions = Instructions(self, self.scene, self.glWidget)
        self.treeModel = LicTreeModel(self.treeWidget.tree)
        if _debug:
            self.modelTest = ModelTest(self.treeModel, self)
        
        self.selectionModel = QItemSelectionModel(self.treeModel)  # MUST keep own reference to selection model here
        self.treeWidget.configureTree(self.scene, self.treeModel, self.selectionModel)
        self.treeWidget.tree.connect(self.scene, SIGNAL("sceneClick"), self.treeWidget.tree.updateTreeSelection)
        self.scene.connect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChangedHandler)
       
        # Needed to correct handling of key press 
        self.treeWidget.tree.installEventFilter(self)
        self.scene.installEventFilter(self)
        
        # Allow the graphics scene to emit the layoutAboutToBeChanged and layoutChanged
        # signals, for easy notification of layout changes everywhere
        self.connect(self.scene, SIGNAL("layoutAboutToBeChanged()"), self.treeModel, SIGNAL("layoutAboutToBeChanged()"))
        self.connect(self.scene, SIGNAL("layoutChanged()"), self.treeModel, SIGNAL("layoutChanged()"))

        # AbstractItemModels keep a list of persistent indices around, which we need to update after layout change
        self.connect(self.treeModel, SIGNAL("layoutChanged()"), self.treeModel.updatePersistentIndices)

        # Need to notify the Model when a particular index was deleted
        self.treeModel.connect(self.scene, SIGNAL("itemDeleted"), self.treeModel.deletePersistentItem)

        # Some attributes can be set as desired objects are created|initiated 
        self.loadSettingsAfter()
 
        self.filename = ""         # This will trigger __setFilename below
        
    def eventFilter(self, receiver, event):
        # hide previous assistant if visible
        if event.type() == QEvent.KeyPress:
            self.releaseAssist()
                
        # resize tool bar invisible space
        if event.type() == QEvent.Resize:
            if isinstance(receiver, LicTreeView):
                receiver.parent().spacer.setMinimumWidth(abs(event.size().width() - 110))
            
        if event.type() == QEvent.ShortcutOverride: 
        # Shift + Tab is not the same as trying to catch a Shift modifier and a tab Key.
        # Shift + Tab is a Backtab!!
            if event.key() == Qt.Key_Backtab:
                self.scene.selectNextPart()  
                return True
        
        if event.type() == QEvent.KeyPress:
        # TAB key        
            if event.key() == Qt.Key_Tab:
                tree = self.treeWidget.tree
                tree.walkToNextTopChild()
                tree.pushTreeSelectionToScene()
                return True
        # Function keys    
            if self.scene.pages:
                if event.key() == Qt.Key_F10: 
                    self.assistHandle = LicJumper(self.scene)
                    self.assistHandle.show()
                    return True
                    
                if event.key() == Qt.Key_F9:
                    self.scene.removeBlankPages()
                    return True
            
        # pass the event on to the parent class
        return QMainWindow.eventFilter(self, receiver, event)
        
    def modelBoxSignal(self):
        boxDict = {}
        mainModel = self.instructions.mainModel
        if self.scene.pages:
            self.releaseAssist()
            boxDict["main"+os.path.splitext(mainModel.filename)[1]] = mainModel.getBoundingBox()
            for submodel in mainModel.submodels:
                boxDict[submodel.filename] = submodel.getBoundingBox()
                
            self.assistHandle = LicModelBoxAssistant(None ,boxDict)
            self.assistHandle.show()
    
    def measureResult(self):
            
        # release and initiate new instance of dialog window
        self.releaseAssist()
        self.assistHandle = MessageDlg()
        
        # set title and show 
        self.assistHandle.setWindowTitle("Main Model Dimensions")
        self.assistHandle.show()     
        
        # initiate text
        self.assistHandle.setText(SUBWINDOW_CALCULATING_TEXT)
        
        # main model instance
        mainModel = self.instructions.mainModel
        
        # Dimensions calculation
        box = mainModel.getBoundingBox(self.excludedParts)
        x, y, z = box.xSize() ,box.ySize() ,box.zSize()
        
        # access to database
        weightDB = getWeightsFile()
        
        # array for collecting missing and excluded parts
        ignored = []
        
        # Weight calculation 
        amount  = 0
        weight  = 1.0
        unit    = "g"
        for csi in mainModel.getCSIList():
            amount += csi.getPartList().__len__()
            for partItem in csi.getPartList():
                name = partItem.filename
                if not self.excludedParts.contains(name, cs=Qt.CaseInsensitive):
                    value = weightDB.value("Part/%s" % name ,0).toFloat()
                    if value[1]:
                        weight += value[0]
                    else:
                        ignored.append(name)
                else:
                    ignored.append(name)
        
        # decrease value and change unit
        if weight < 20 or amount < 20:
            weight = 0
        if weight > 1000:
            weight = weight / 1000.0
            unit   = "kg"
            
        # convert pixels to physical metrics 
        # Conversion Table on http://www.brickwiki.info/wiki/LDraw_unit
        x *= 0.04
        y *= 0.04
        z *= 0.04         
        
        # create Tip without duplicated entries 
        ignoredTip = "Ignored parts: \n"
        ignoredTip += "\n".join(list(set(ignored)))
        
        # configure button to display ignoredTip variable
        self.assistHandle.releaseText()
        if ignored.__len__() > 0:
            self.assistHandle.button1.setPixmap(QIcon(":/warning").pixmap(16, 16))
            self.assistHandle.button1.setStatusTip(ignoredTip)
            self.assistHandle.button1.setToolTip(ignoredTip)
            self.assistHandle.button1.show()
        
        # create top level widgets
        sgbox=QGroupBox("Dimensions")
        wgbox=QGroupBox("Weight")
        
        # create layout and put result
        hbox = QHBoxLayout()
        hbox.setMargin(10)
        hbox.addWidget(QLabel("%.2fx%.2fx%.2f cm" % (x, y, z)) ,1 ,Qt.AlignHCenter)
        sgbox.setLayout(hbox)
        
        hbox = QHBoxLayout()
        hbox.setMargin(10)
        hbox.addWidget(QLabel("~%.2f %s" % (weight,unit) if weight else "---") ,1 ,Qt.AlignHCenter)
        wgbox.setLayout(hbox)
        
        # set layout with top widgets
        self.assistHandle.centreLayout.addWidget(sgbox)
        self.assistHandle.centreLayout.addWidget(wgbox)           
           
    def changeLayoutSignal(self):
        if self.scene.pages:
            self.releaseAssist()
            self.assistHandle = LicLayoutAssistant(self.scene)
            self.assistHandle.show()

    def toggleShortcutsDialog(self):
        # Initialize Assistant
        if self.assistant is None:
            self.assistant = LicShortcutAssistant(self.graphicsView)
        # Show or Hide    
        if self.assistant.isVisible():
            self.assistant.hide()
        else:
            self.assistant.show()     

    def aboutDialog(self):
        self.releaseAssist()
        self.assistHandle = MessageDlg(self ,QSize(455, 100))
        
        _copyright = QLabel("LEGO Instruction Creator %s\nCopyright 2015 - %s Jeremy Czajkowski & Remi Gagne\n" % (__version__ ,time.strftime("%Y")))
        _policy = QLabel("LEGO(R) and the LEGO logo are registered trademarks of the LEGO Group,\nwhich does not sponsor, endorse, or authorize this program.")
        
        grid = QGridLayout()
        grid.addWidget(_copyright ,0 ,0)
        grid.addWidget(_policy ,1 ,0)
        
        self.assistHandle.centreLayout.addLayout(grid)
        self.assistHandle.show()

    def releaseAssist(self):
        if self.assistHandle:
            self.assistHandle.close()
            self.assistHandle = None        
             
    def runCleanup(self):
        if self.instructions.mainModel:
            LicCleanupAssistant(self.instructions.mainModel.getPageList() , self.graphicsView).show()

    def showHideRules(self):
        if not isinstance(self.hRuler, Ruler):
            self.hRuler = Ruler(Qt.Horizontal, self.graphicsView)
        if not isinstance(self.vRuler, Ruler):
            self.vRuler = Ruler(Qt.Vertical, self.graphicsView)
        
        if self.hRuler.isVisible():
            self.hRuler.hide()
        else:    
            self.hRuler.show()
            
        if self.vRuler.isVisible():
            self.vRuler.hide()
        else:    
            self.vRuler.show()     
            
    @staticmethod
    def getSettingsFile():
        iniFile = os.path.join(config.appDataPath(), 'licreator.ini')
        return QSettings(QString(iniFile), QSettings.IniFormat)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(QString("text/uri-list")):
            filename = event.mimeData().getFilename()
            if filename is not None:
                ext = os.path.splitext(filename)[1].lower()
                if ext in LicImporters.getFileTypesList() or ext == '.lic':
                    event.acceptProposedAction()
                    return
        event.ignore()
    
    def dropEvent(self, event):
        # Assuming correct drop type, based on dragEnterEvent()
        # URL encoding
        # Convert extension to lower case for good work
        #    because MPD, Mpd ,mpd is not the same in matching
        filename = event.mimeData().getFilename()
        filename = urllib.unquote(filename).decode('utf8')
        ext = os.path.splitext(filename)[1].lower()
        if ext in LicImporters.getFileTypesList():
            self.importModel(filename)
        elif ext == '.lic':
            self.locationOpen(filename)
        event.acceptProposedAction()

    def loadSettings(self):
        settings = self.getSettingsFile()
        # repository
        self.repository  = str(settings.value("Locations/Repository").toString())
        if not self.repository:
            self.repository = "http://raw.githubusercontent.com/remig/lic/master/.settings/"        
        
        # directories
        self.recentFiles = settings.value("Locations/recentFiles").toStringList()
        self.favouriteDirectories = settings.value("Locations/favouriteDirectories").toStringList()
        self.latestimportfolder = settings.value("Locations/importDirectory" , ".").toString().__str__()
        
        # main window geometry
        self.restoreGeometry(settings.value("Geometry").toByteArray())
        self.restoreState(settings.value("MainWindow/State").toByteArray())
        self.splitterState = settings.value("SplitterSizes").toByteArray()
        
        # view
        self.pagesToDisplay = settings.value("PageView", 1).toInt()[0]
        self.snapToGuides = settings.value("SnapToGuides").toBool()
        self.snapToItems = settings.value("SnapToItems").toBool()
        
        # exluded parts
        self.excludedUserParts = settings.value("Exceptions/dimensionANDweight").toStringList()
        self.excludedParts = QStringList(BASEPLATES_FILE)
        for filename in self.excludedUserParts:
            self.excludedParts.append(filename)
        
        # tools activity
        config.writeL3PActivity = settings.value("L3PAccessLog" , False).toBool()
        config.writePOVRayActivity = settings.value("POVAccessLog" , False).toBool()

        # tools
        LDrawPath = str(settings.value("Tools/LDrawPath").toString())
        L3PPath = str(settings.value("Tools/L3PPath").toString())
        POVRayPath = str(settings.value("Tools/POVRayPath").toString())

        if LDrawPath and L3PPath and POVRayPath:
            config.LDrawPath = LDrawPath
            config.L3PPath = L3PPath 
            config.POVRayPath = POVRayPath
            LDrawImporter.LDrawPath = config.LDrawPath
            BuilderImporter.LDrawPath = config.LDrawPath
            self.needPathConfiguration = False
        else:
            self.needPathConfiguration = True
            
        if "." == config.POVRayPath.strip():
            config.POVRayPath = ""     
        if "." == config.L3PPath.strip():
            config.L3PPath = ""       
    
    def loadSettingsAfter(self):
        """
         Can apply this values only when corresponded object exist.
         Run Me after LicWindow.__init__ initialize this object properly. 
        """
        settings = self.getSettingsFile()
        # Set last used directory for part's import
        self.instructions.partImportDirectory = str(settings.value("Locations/partImportDirectory" , ".").toString())
        
        # Run database update when entry not present or invalid value has
        updated = settings.value("latestUpdate",0).toFloat()[0]
        if not updated:
            self.checkUpdates()
    
    def saveSettings(self):
        settings = self.getSettingsFile()
        recentFiles = QVariant(self.recentFiles) if self.recentFiles else QVariant()
        favouriteDirectories = QVariant(self.favouriteDirectories) if self.favouriteDirectories else QVariant()
        settings.setValue("Locations/recentFiles", recentFiles)
        settings.setValue("Locations/favouriteDirectories", favouriteDirectories)
        if os.path.isabs(self.latestimportfolder):
            settings.setValue("Locations/importDirectory" , self.latestimportfolder)
        if os.path.isabs(self.instructions.partImportDirectory):
            settings.setValue("Locations/partImportDirectory" , self.instructions.partImportDirectory)
        settings.setValue("Locations/Repository" , self.repository)            
        
        settings.setValue("Geometry", QVariant(self.saveGeometry()))
        settings.setValue("MainWindow/State", QVariant(self.saveState()))
        settings.setValue("SplitterSizes", QVariant(self.mainSplitter.saveState()))
        settings.setValue("PageView", QVariant(str(self.scene.pagesToDisplay)))

        settings.setValue("SnapToGuides", QVariant(str(self.scene.snapToGuides)))
        settings.setValue("SnapToItems", QVariant(str(self.scene.snapToItems)))
        
        if self.excludedUserParts.__len__() < 1:
            self.excludedUserParts.append("filename.dat")
            self.excludedUserParts.append("filename2.dat")
        settings.setValue("Exceptions/dimensionANDweight" ,self.excludedUserParts)
        
        settings.setValue("L3PAccessLog" , config.writeL3PActivity)
        settings.setValue("POVAccessLog" , config.writePOVRayActivity)

        if "" == config.L3PPath.strip():
            config.L3PPath = "."
        if "" == config.POVRayPath.strip():
            config.POVRayPath = "."
        settings.setValue("Tools/LDrawPath", QVariant(config.LDrawPath))
        settings.setValue("Tools/L3PPath", QVariant(config.L3PPath))
        settings.setValue("Tools/POVRayPath", QVariant(config.POVRayPath))
        

    def loadPosition(self):    
        settings = self.getSettingsFile()
        tree = self.treeWidget.tree
        text = settings.value("TreeView/" + os.path.basename(self.filename)).toStringList()

        startIndex = tree.topindex
        for t in text:
            matches = tree.model().match(startIndex, Qt.DisplayRole, t, 2, Qt.MatchRecursive)
            if [] != matches and matches[0].isValid():
                startIndex = matches[0]
                tree.expand(matches[0])
                
        try:
            tree.selectionModel() .select(matches[0], QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            tree.selectionModel() .setCurrentIndex(matches[0] , QItemSelectionModel.SelectCurrent)
        except:
            pass      
        else:
            tree.pushTreeSelectionToScene()          
        
    def savePosition(self, modelindex):
        settings = self.getSettingsFile()
        nodes = []
        while modelindex.isValid():
            nodes.append(modelindex.data(Qt.DisplayRole).toPyObject()) 
            modelindex = modelindex.parent()
        # reverses the list order -- we need this to restore state from top to bottom 
        nodes.reverse()
        if nodes.__len__() > 3:
            nodes.pop()
        settings.setValue("TreeView/" + os.path.basename(self.filename) , nodes)

    def copySettingsToScene(self):
        self.scene.setPagesToDisplay(self.pagesToDisplay)
        self.scene.snapToGuides = self.snapToGuides
        self.scene.snapToItems = self.snapToItems

    def checkUpdates(self):
        self.menuBar().setEnabled(False)
        downloader = LicDownloadAssistant(self.graphicsView, self.repository)
        self.connect(downloader, SIGNAL("finished(int)"), lambda: self.menuBar().setEnabled(True))
        self.connect(downloader, SIGNAL("success(int)"), self.updateDone)
        downloader.show()
        
    def updateDone(self ,arg1):
        settings = self.getSettingsFile()
        settings.setValue("latestUpdate",time.time())    
        
    def configurePaths(self, hideCancelButton=False):
        dialog = config.PathsDialog(self, hideCancelButton)
        dialog.exec_()
        LicImporters.LDrawImporter.LDrawPath = config.LDrawPath
        LicImporters.BuilderImporter.LDrawPath = config.LDrawPath
        self.saveSettings()

    def __getFilename(self):
        return self.__filename
    
    def __setFilename(self, filename):
        self.__filename = filename
        
        if filename:
            config.filename = filename
            self.setWindowTitle("LEGO Instruction Creator :: %s [*]" % os.path.basename(filename))
            self.notificationArea.setText("Instruction book loaded: %s  [%.0fmin %.3fs]" % (filename , self._loadTime[0] , self._loadTime[1]))
            enabled = True
        else:
            self.undoStack.clear()
            self.setWindowTitle("LEGO Instruction Creator [*]")
            self.statusBar().clearMessage()
            enabled = False

        self.undoStack.setClean()
        self.setWindowModified(False)
        self.enableMenus(enabled)

    filename = property(__getFilename, __setFilename)

    def initToolBars(self):
        self.toolBar = None

    def initStatusBar(self):
        self.notificationArea = QLabel(self)
        self.notificationArea.setAlignment(Qt.AlignRight)
        self.notificationArea.setMargin(5)
        self.zoomInfo = QLabel("100%")
        self.zoomInfo.setMargin(5)
        self.statusBar().insertPermanentWidget(0, self.notificationArea)
        self.statusBar().insertPermanentWidget(1, self.zoomInfo)        

    def initMenu(self):
        menu = self.menuBar()

        # File Menu
        self.fileMenu = menu.addMenu("&File")
        self.connect(self.fileMenu, SIGNAL("aboutToShow()"), self.updateFileMenu)

        fileOpenAction = self.makeAction("&Open...", self.locationOpen, QKeySequence.Open, "Open an existing Instruction book")
        self.fileOpenRecentMenu = QMenu("Open &Recent", self.fileMenu)
        self.fileOpenFavouriteMenu = QMenu("Open &Favourite", self.fileMenu)
        self.fileCloseAction = self.makeAction("&Close", self.fileClose, QKeySequence.Close, "Close current Instruction book")
        self.fileReopenAction = self.makeAction("R&eopen", self.fileReopen, None, "Re-opening this Instruction book without concern for the modifications")
         
        self.fileSaveAction = self.makeAction("&Save", self.fileSave, QKeySequence.Save, "Save the Instruction book")
        self.fileSaveAsAction = self.makeAction("Save &As...", self.fileSaveAs, QKeySequence("Ctrl+Shift+S"), "Save the Instruction book using a new filename")
        fileImportAction = self.makeAction("&Import Model...", self.fileImport, QKeySequence("Ctrl+I"), "Import an existing Model into a new Instruction book")

        self.fileSaveTemplateAction = self.makeAction("Save Template", self.fileSaveTemplate, None, "Save only the Template")
        self.fileSaveTemplateAsAction = self.makeAction("Save Template As...", self.fileSaveTemplateAs, None, "Save only the Template using a new filename")
        self.fileLoadTemplateAction = self.makeAction("Load Template...", self.fileLoadTemplate, None, "Discard the current Template and apply a new one")
        fileExitAction = self.makeAction("E&xit", SLOT("close()"), "Ctrl+Q", "Save own work and close Me")
        
        self.fileMenuActions = (fileOpenAction, self.fileOpenRecentMenu, self.fileOpenFavouriteMenu, None,
                                self.fileReopenAction, self.fileCloseAction, None,
                                self.fileSaveAction, self.fileSaveAsAction, fileImportAction, None,
                                self.fileSaveTemplateAction, self.fileSaveTemplateAsAction, self.fileLoadTemplateAction, None,
                                fileExitAction)
        
        # Edit Menu - undo / redo is generated dynamically in updateEditMenu()
        editMenu = menu.addMenu("&Edit")
        self.connect(editMenu, SIGNAL("aboutToShow()"), self.updateEditMenu)

        self.undoAction = self.makeAction("&Undo", None, "Ctrl+Z", "Undo last action")
        self.undoAction.connect(self.undoAction, SIGNAL("triggered()"), self.undoStack, SLOT("undo()"))
        self.undoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canUndoChanged(bool)"), self.undoAction, SLOT("setEnabled(bool)"))
        
        self.redoAction = self.makeAction("&Redo", None, "Ctrl+Y", "Redo the last undone action")
        self.redoAction.connect(self.redoAction, SIGNAL("triggered()"), self.undoStack, SLOT("redo()"))
        self.redoAction.setEnabled(False)
        self.connect(self.undoStack, SIGNAL("canRedoChanged(bool)"), self.redoAction, SLOT("setEnabled(bool)"))
        
        # Snap menu (inside Edit Menu): Snap -> Snap to Guides & Snap to Items
        guideSnapAction = self.makeAction("Guides", self.setSnapToGuides, None, "Snap To Guides", "toggled(bool)", True)
        guideSnapAction.setChecked(self.scene.snapToGuides)
        
        itemSnapAction = self.makeAction("Items", self.setSnapToItems, None, "Snap To Items", "toggled(bool)", True)
        itemSnapAction.setChecked(self.scene.snapToItems)
        
        snapMenu = editMenu.addMenu("Snap To")
        snapMenu.addAction(guideSnapAction)
        snapMenu.addAction(itemSnapAction)

        setPathsAction = self.makeAction("Paths...", self.configurePaths, QKeySequence("Ctrl+,"), "Set paths to LDraw parts, L3p, POVRay, etc.")
        editActions = (self.undoAction, self.redoAction, None, snapMenu, setPathsAction)
        self.addActions(editMenu, editActions)

        # View Menu
        self.viewMenu = menu.addMenu("&View")
        addHGuide = self.makeAction("Add Horizontal Guide", lambda: self.scene.addNewGuide(LicLayout.Horizontal))
        addVGuide = self.makeAction("Add Vertical Guide", lambda: self.scene.addNewGuide(LicLayout.Vertical))
        removeGuides_all = self.makeAction("Remove all Guides", self.scene.removeAllGuides)
        removeGuides_selected = self.makeAction("Remove chosen Guides", self.scene.removeSelectedGuides)
        self.toogleMarginsAction = self.makeAction("Show Margins", self.scene.showHideMargins, None, None, checkable=True)
        toogleRules = self.makeAction("Show Metrics", self.showHideRules, Qt.Key_F6, "", checkable=True)

        zoom100 = self.makeAction("Zoom &100%", lambda: self.zoom(1.0), QKeySequence("Ctrl+0"), "Show actual page size")
        zoomToFit = self.makeAction("Zoom To &Fit", lambda: self.zoom(), QKeySequence("Ctrl+2"), "Fit page by current view")
        zoomIn = self.makeAction("Zoom &In", lambda: self.zoom(1.2), QKeySequence.ZoomIn , "Increase zoom by ono step")
        zoomOut = self.makeAction("Zoom &Out", lambda: self.zoom(1.0 / 1.2), QKeySequence.ZoomOut , "Decrease zoom by one step")

        onePage = self.makeAction("Show One Page", self.scene.showOnePage, None, "Show One Page", checkable=True)
        twoPages = self.makeAction("Show Two Pages", self.scene.showTwoPages, None, "Show Two Pages", checkable=True)
        continuous = self.makeAction("Continuous", self.scene.continuous, None, "Continuous", checkable=True)
        continuousFacing = self.makeAction("Continuous Facing", self.scene.continuousFacing, None, "Continuous Facing", checkable=True)

        pageActions = {1: onePage, 2: twoPages,
                       LicGraphicsScene.PageViewContinuous: continuous,
                       LicGraphicsScene.PageViewContinuousFacing: continuousFacing}
        pageActions[self.pagesToDisplay].setChecked(True)
        
        pageGroup = QActionGroup(self)
        for action in pageActions.values():
            pageGroup.addAction(action)
        
        viewActions = (addHGuide, addVGuide, None, removeGuides_all, removeGuides_selected, None,
                       self.toogleMarginsAction, toogleRules, None,
                       zoom100, zoomToFit, zoomIn, zoomOut, None,
                       onePage, twoPages, continuous, continuousFacing)
        self.addActions(self.viewMenu, viewActions)

        # Export Menu
        self.exportMenu = menu.addMenu("E&xport")
        self.exportToImagesAction = self.makeAction("&Generate Final Images", self.exportImages, None, "Generate final images of each page in this Instruction book")
        self.exportToPDFAction = self.makeAction("Generate &PDF", self.exportToPDFExecutor, QKeySequence("Ctrl+E"), "Create a PDF from this instruction book")
        self.exportToPOVAction = self.makeAction("NYI - Generate Images with Pov-&Ray", self.exportToPOV, None, "Use Pov-Ray to generate images of each page in this Instruction book")
        self.exportToMPDAction = self.makeAction("Generate &MPD...", self.exportToMPD, None, "Generate an LDraw MPD file from the parts & steps in this Instruction book")
        self.addActions(self.exportMenu, (self.exportToImagesAction, self.exportToPDFAction, self.exportToPOVAction, None, self.exportToMPDAction))

        # Model Manu
        self.modelMenu = menu.addMenu("&Model")
        applyLayout = self.makeAction("Apply &Layout to Pages...", self.changeLayoutSignal, None, "Apply chosen layout to selected pages")
        modelBoxAssistant = self.makeAction("Model &Bounding Box", self.modelBoxSignal, QKeySequence("Ctrl+B"), "Informations about model geometry")
        measureResult = self.makeAction("Measure Final Result", self.measureResult, None, "Show physical dimensions and estimated weight")
        runCleanup = self.makeAction("Run &Clean-up", self.runCleanup, Qt.Key_F2, "Run clean-up utility")
        cacheFolder = self.makeAction("&Explore Cache", lambda: startfile(config.modelCachePath()), Qt.Key_F4, "Opens cache directory for this Instruction")
        checkUpdates = self.makeAction("Check for Library &Updates...", self.checkUpdates, None, "Checking repository for latest updated files")
        
        modelAction = (applyLayout, None, modelBoxAssistant, measureResult, None, runCleanup, None, cacheFolder, None, checkUpdates)
        self.addActions(self.modelMenu, modelAction)

        # Help Menu
        self.helpMenu = menu.addMenu("&Help") 
        toggleDialog = self.makeAction("Toggle &Shortcuts", lambda: self.toggleShortcutsDialog(), QKeySequence.HelpContents , "Show or hide the list of keyboard shortcuts information")
        aboutDiialog = self.makeAction("&About Me", self.aboutDialog, None, "Display copyright note")
        qtDialog  =  self.makeAction("About &Qt", lambda: QMessageBox.aboutQt(self))
        
        helpAction = (toggleDialog, aboutDiialog, qtDialog)
        self.addActions(self.helpMenu, helpAction)

    def zoom(self, factor=0.0):
        if factor == 0.0:
            scale = self.graphicsView.scaleToFit() * 100
        else:
            scale = self.graphicsView.scaleView(factor) * 100
                        
        self.zoomInfo.setText("%.0f%%" % scale)
        
    def setSnapToGuides(self, snap):
        self.snapToGuides = self.scene.snapToGuides = snap

    def setSnapToItems(self, snap):
        self.snapToItems = self.scene.snapToItems = snap

    def updateFileMenu(self):
        self.fileMenu.clear()
        self.addActions(self.fileMenu, self.fileMenuActions)
        
        recentFiles = []
        for filename in self.recentFiles:
            if filename != self.filename and QFile.exists(filename):
                recentFiles.append(filename)
             
        favouriteDirectories = []
        for dirname in self.favouriteDirectories:
            if os.path.isdir(dirname):
                favouriteDirectories.append(dirname)
            
        if recentFiles:
            self.fileOpenRecentMenu.clear()
            self.fileOpenRecentMenu.setEnabled(True)
            for i, filename in enumerate(recentFiles):
                action = QAction("&%d %s" % (i + 1, QFileInfo(filename).fileName()), self)
                action.setData(QVariant(filename))
                action.setStatusTip(filename)
                self.connect(action, SIGNAL("triggered()"), self.openRecentFile)
                self.fileOpenRecentMenu.addAction(action)
        else:
            self.fileOpenRecentMenu.setEnabled(False)
            
        if favouriteDirectories:
            self.fileOpenFavouriteMenu.clear()
            self.fileOpenFavouriteMenu.setEnabled(True)    
            for i, dirname in enumerate(favouriteDirectories):
                action = QAction("&%d %s" % (i + 1, dirname), self)
                action.setData(QVariant(dirname))
                action.setStatusTip(dirname)
                self.connect(action, SIGNAL("triggered()"), self.openFavouriteDirectory)
                self.fileOpenFavouriteMenu.addAction(action)
                
            clearAction = QAction("&Clear", self)
            self.connect(clearAction, SIGNAL("triggered()"), self.clearFavouriteList)
            self.fileOpenFavouriteMenu.addSeparator()
            self.fileOpenFavouriteMenu.addAction(clearAction)
        else:
            self.fileOpenFavouriteMenu.setEnabled(False)    

    def openRecentFile(self):
        action = self.sender()
        filename = unicode(action.data().toString())
        self.locationOpen(filename)
        
    def openFavouriteDirectory(self):    
        action = self.sender()
        dirname = unicode(action.data().toString())
        self.locationOpen(dirname);
    
    def clearFavouriteList(self):
        self.fileOpenFavouriteMenu.clear()
        self.favouriteDirectories.clear()

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
                
    def addFavouriteDirectory(self, filename):
        if filename:
            dirname = os.path.dirname(filename)            
            if os.path.isdir(dirname) and not self.favouriteDirectories.contains(dirname):
                self.favouriteDirectories.prepend(dirname)
    
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
    
    def makeAction(self, text, slot=None, shortcut=None, tip=None, signal="triggered()", checkable=False):
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
        self.savePosition(self.treeWidget.tree.selectionModel().currentIndex())
        self.releaseAssist()
        
        if self.offerSave():
            self.saveSettings()
            
            # Need to explicitly disconnect this signal, because the scene emits a selectionChanged right before it's deleted
            self.disconnect(self.scene, SIGNAL("selectionChanged()"), self.scene.selectionChangedHandler)
            self.glWidget.doneCurrent()  # Avoid a crash when exiting
            event.accept()
        else:
            event.ignore()

    def fileClose(self, offerSave=True):
        # Collect Tree View state
        self.savePosition(self.treeWidget.tree.selectionModel().currentIndex())
        
        # Hide dialog box
        self.releaseAssist()
        self.scene.releaseAssist()
        
        # Hide margins
        if self.toogleMarginsAction.isChecked():
            self.toogleMarginsAction.activate(QAction.Trigger)
        
        if offerSave and not self.offerSave():
            return False
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.addFavouriteDirectory(self.filename)
        self.zoomInfo.setText("100%")
        self.notificationArea.clear()
        self.instructions.clear()
        self.treeModel.reset()
        self.treeModel.root = None
        self.scene.clear()
        self.filename = ""
        self.scene.emit(SIGNAL("layoutChanged()"))
        
        return True
    
    def fileReopen(self):
        filename = self.filename
        self.fileClose(False)
        try:
            self.loadLicFile(filename)
        except IOError, ex:
            self.fileClose(False)        
            QMessageBox.warning(self, "Open Error", "%s\n%s" % (filename, ex.message))
            pass

    def offerSave(self):
        """ 
        Returns True if we should proceed with whatever operation
        was interrupted by this request.  False means cancel.
        """
        if not self.isWindowModified():
            return True
        reply = QMessageBox.question(self, "Unsaved Changes", "Save unsaved changes?",
                                     QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            return self.fileSave()
        return reply == QMessageBox.No

    def fileImport(self):
        if not self.offerSave():
            return
        formats = LicImporters.getFileTypesString()
        filename = unicode(QFileDialog.getOpenFileName(self, "Import Model", self.latestimportfolder, formats))
        if filename:
            self.setWindowModified(False)
            self.latestimportfolder = os.path.dirname(filename).__str__()
            QTimer.singleShot(50, lambda: self.importModel(filename))

    def importModel(self, filename):
        if not self.fileClose():
            return

        startTime = time.time()
        self.progress = LicDialogs.LicProgressDialog(self, "Importing " + os.path.basename(filename))
        self.progress.setValue(2)  # Try and force dialog to show up right away

        self.loader = self.instructions.importModel(filename)
        self.progress.setMaximum(self.loader.next())  # First value yielded after load is # of progress steps

        firstPage = self.instructions.mainModel.getPage(1)
        if firstPage and firstPage.isBlank():
            self.progress.cancel()
            
            self.assistHandle = MessageDlg(self)            
            self.assistHandle.setText("Invalid or unsupported content in %s" % os.path.basename(filename))
            self.assistHandle.show()
            return

        for label in self.loader:
            if self.progress.wasCanceled():
                self.loader.close()
                self.fileClose()
                return
            self.progress.incr(label)

        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.treeModel.root = self.instructions.mainModel

        try:
            self.template = LicBinaryReader.loadLicTemplate(self.defaultTemplateFilename, self.instructions)

#            import LicTemplate  # Use this to regenerate new default template from scratch, to add new stuff to it
#            template = LicTemplate.TemplatePage(self.instructions.mainModel, self.instructions)
#            template.createBlankTemplate(self.glWidget)
        except IOError, unused:
            # Could not load default template, so load template stored in resource bundle
            writeLogEntry("Could not load default template, so load template stored in resource bundle", self.__class__.__name__)
            self.template = LicBinaryReader.loadLicTemplate(":/default_template", self.instructions)
        
        self.template.filename = ""  # Do not preserve default template filename
        self.progress.incr("Adding Part List Page")
        self.instructions.template = self.template
        self.instructions.mainModel.partListPages = PartListPage.createPartListPages(self.instructions)
        self.template.applyFullTemplate(False)  # Template should apply to part list but not title pages

        self.progress.incr("Adding Title Page")
        self.instructions.mainModel.createNewTitlePage(False)

        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(1)

        self._loadTime = divmod(time.time() - startTime, 60)
        config.filename = filename
        self.notificationArea.setText("Model imported: %s  [%.0fmin %.3fs]" % (filename , self._loadTime[0] , self._loadTime[1]))
        self.setWindowModified(True)
        self.enableMenus(True)
        self.copySettingsToScene()

        self.progress.incr("Finishing up...")
        self.progress.setValue(self.progress.maximum())
        self.template = None
        self.loader = None
        
        self.fileReopenAction.setEnabled(False)        

    def loadLicFile(self, filename):    
        startTime = time.time()
        self.releaseAssist()
        progress = LicDialogs.LicProgressDialog(self, "Opening " + os.path.basename(filename))
        progress.setValue(2)  # Try and force dialog to show up right away

        loader = LicBinaryReader.loadLicFile(filename, self.instructions)
        count = loader.next() + 3
        # First value yielded after load is # of progress steps, +3 because we start at 2, and have to load colors
        progress.setMaximum(count)  

        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.instructions.loadLDrawColors()
        progress.incr()
        
        for unused in loader:
            if progress.wasCanceled():
                loader.close()
                self.fileClose()
                self.notificationArea.setText("Open File aborted")
                return
            progress.incr()

        self.treeModel.root = self.instructions.mainModel
        self.scene.emit(SIGNAL("layoutChanged()"))

        self.addRecentFile(filename)
        self.addFavouriteDirectory(filename)
        self.scene.selectPage(1)
        self.copySettingsToScene()
        progress.setValue(progress.maximum())
        self._loadTime = divmod(time.time() - startTime, 60)
        self.filename = filename

        self.loadPosition()
        
        # Restore Tree View options
        lst = self.treeWidget.hiddenRowActions
        opt = self.treeWidget.hiddenRowState
        for act in lst:
            idx = act.whatsThis()
            if opt.has_key(idx):
                act.setChecked(opt[idx])
                act.activate(QAction.Trigger)            

    def enableMenus(self, enabled):
        self.fileCloseAction.setEnabled(enabled)
        self.fileReopenAction.setEnabled(enabled)
        self.fileSaveAction.setEnabled(enabled)
        self.fileSaveAsAction.setEnabled(enabled)
        self.fileSaveTemplateAction.setEnabled(enabled)
        self.fileSaveTemplateAsAction.setEnabled(enabled)
        self.fileLoadTemplateAction.setEnabled(enabled)
        
        self.viewMenu.setEnabled(enabled)
        self.modelMenu.setEnabled(enabled)
        self.exportMenu.setEnabled(enabled)
        
        self.treeWidget.treeToolBar.setEnabled(enabled)

    def fileSaveAs(self):
        if self.filename:
            f = self.filename
        else:
            f = self.instructions.getModelName()
            f = os.path.splitext(f)[0] + ".lic"

        filename = unicode(QFileDialog.getSaveFileName(self, "Save File As", f, "Instruction Book (*.lic)"))
        if filename:
            self.filename = filename
            self.instructions.filename = filename
            return self.fileSave()
        return False

    def fileSave(self):
        if self.filename == "" or not self.filename:
            return self.fileSaveAs()

        tmpName = os.path.splitext(self.filename)[0] + "_bak.lic"
        tmpXName = self.filename + ".x"

        if os.path.isfile(tmpXName):
            os.remove(tmpXName)

        try:
            LicBinaryWriter.saveLicFile(tmpXName, self.instructions)
        except Exception, ex:
            QMessageBox.warning(self, "Save Error", "Failed to save %s: %s" % (self.filename, ex.message))
            return False

        try:
            if os.path.isfile(tmpName):
                os.remove(tmpName)
            if os.path.isfile(self.filename):
                os.rename(self.filename, tmpName)
            os.rename(tmpXName, self.filename)

            self.undoStack.setClean()
            self.addRecentFile(self.filename)
            self.addFavouriteDirectory(self.filename)
            self.notificationArea.setText("Saved to: " + self.filename)
            self.fileReopenAction.setEnabled(True)
            self.setWindowModified(False)
            return True

        except (IOError, OSError), ex:
            QMessageBox.warning(self, "Save Error", "Failed to save %s: %s" % (self.filename, ex.message))
        return False

    def fileSaveTemplate(self):
        template = self.instructions.template
        if template.filename == "":
            return self.fileSaveTemplateAs()

        if os.path.basename(template.filename) == self.defaultTemplateFilename:
            if QMessageBox.No == QMessageBox.question(self, "Replace Template",
                                                      "This will replace the default template!  Proceed?",
                                                      QMessageBox.Yes | QMessageBox.No):
                return

        try:
            LicBinaryWriter.saveLicTemplate(template)
            self.notificationArea.setText("Saved Template to: " + template.filename)
        except (IOError, OSError), ex:
            QMessageBox.warning(self, "Save Error", "Failed to save %s: %s" % (template.filename, ex.message))
    
    def fileSaveTemplateAs(self):
        template = self.instructions.template
        f = template.filename if template.filename else "template.lit"

        filename = unicode(QFileDialog.getSaveFileName(self, "Save Template As", f, "Template (*.lit)"))
        if filename:
            template.filename = filename
            return self.fileSaveTemplate()
    
    def fileLoadTemplate(self):
        templateName = self.instructions.template.filename
        directory = os.path.dirname(templateName) if templateName != "" else "."  
        newFilename = unicode(QFileDialog.getOpenFileName(self, "Load Template", directory, "Template (*.lit)"))
        if newFilename and os.path.basename(newFilename) != templateName:
            try:
                newTemplate = LicBinaryReader.loadLicTemplate(newFilename, self.instructions)
            except IOError, ex:
                error_message = "Failed to open %s: %s" % (newFilename, ex.message)
                QMessageBox.warning(self, "Load Template Error", error_message)
                writeLogEntry(error_message , self.__class__.__name__)
            else:
                self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))
                self.scene.removeItem(self.instructions.template)
                self.instructions.template = newTemplate
                newTemplate.applyFullTemplate(True)
                self.scene.emit(SIGNAL("layoutChanged()"))
                self.setWindowModified(True)
    
    def locationOpen(self, resource=None):
        if not self.offerSave():
            return
        directory = os.path.dirname(self.filename) if self.filename is not None else "."
        
        if resource is not None and os.path.isdir(resource):
            resource = unicode(QFileDialog.getOpenFileName(self, "Open Instruction Book", resource, "Instruction Book (*.lic)")) 
         
        if resource is None:
            resource = unicode(QFileDialog.getOpenFileName(self, "Open Instruction Book", directory, "Instruction Book (*.lic)"))
            
        if resource and resource != self.filename:
            self.fileClose(False)
            try:
                self.loadLicFile(resource)
            except IOError, e:
                QMessageBox.warning(self, "Open Error", "%s\n%s" % (resource, e.message))
                self.fileClose()

    def exportImages(self):

        progress = LicDialogs.LicProgressDialog(self, "Exporting Final Images")
        progress.setValue(2)  # Try and force dialog to show up right away

        loader = self.instructions.exportImages()
        progress.setMaximum(loader.next() + 2)  # +2 because we're already at 2

        for label in loader:
            if progress.wasCanceled():
                loader.close()
                self.notificationArea.setText("Image Export aborted")
                return
            label = "Rendering " + os.path.splitext(os.path.basename(label))[0].replace('_', ' ')
            progress.incr(label)

        self.glWidget.makeCurrent()
        self.notificationArea.setText("Exported images to: " + config.finalImageCachePath())
    
    def exportToPDFExecutor(self):
        self.scene.removeAllGuides()
        if self.toogleMarginsAction.isChecked():
            self.toogleMarginsAction.activate(QAction.Trigger)
        
        self._worker = LicWorker([self.exportToPDF])
        self._worker.start()
           
    def exportToPDF(self):
        loader = self.instructions.exportToPDF()
        filename = loader.next()
        title = "Exporting " + os.path.splitext(os.path.basename(filename))[0]

        progress = LicDialogs.LicProgressDialog(self, title)
        progress.setValue(2)  # Try and force dialog to show up right away
        progress.setMaximum(loader.next() + 2)  # +2 because we're already at 2

        for label in loader:
            if progress.wasCanceled():
                loader.close()
                self.notificationArea.setText("PDF Export aborted")
                return
            progress.incr(label)

        progress.setValue(progress.maximum())

        self.glWidget.makeCurrent()
        self.notificationArea.setText("Exported PDF to: " + filename)
                 
    def exportToPOV(self):
        warning = None
        if not self.instructions.mainModel.hasSimpleMode():
            warning = ("NYI - Can not progress on instruction with submodels")
        elif not LicPovrayWrapper.isExists() or not LicL3PWrapper.isExists():
            warning = ("NYI - Choose correct path for L3P and POV-Ray")
               
        if warning:
            dialog = MessageDlg(self)
            dialog.setText(warning)
            dialog.show()
        else:
            try:
                thread.start_new_thread(self.instructions.exportToPOV, ())
            except Exception:
                self.notificationArea.setText ("NYI - Export is broken")
            else:
                self.notificationArea.setText ("NYI - Export Done. Check %s" % config.modelCachePath())
                return True
            
        return False        

    def exportToMPD(self):
        f = self.filename if self.filename else self.instructions.getModelName()
        f = os.path.splitext(f)[0] + "_lic.mpd"
        filename = unicode(QFileDialog.getSaveFileName(self, "Create MPD File", f, "LDraw files (*.mpd)"))
        if filename:
            fh = open(filename, 'w')
            self.instructions.mainModel.exportToLDrawFile(fh)
            fh.close()
            self.notificationArea.setText ("MPD - Export Done. Check %s" % filename)

def setupExceptionLogger():

    def myExceptHook(*args):
        logging.error('Uncaught Root Exception:-------------------------------\n', exc_info=args)
        logging.info('------------------------------------------------------\n')
        sys.__excepthook__(*args)

    filepath = os.path.join(config.appDataPath(),"licreator.log")
    filesize = os.path.getsize(filepath)
    maxbytes = 5*1024*1024    
    
    if filesize > maxbytes and os.path.isfile(filepath):
        os.unlink(filepath)

    sys.excepthook = myExceptHook
    f = "%(levelname)s: %(asctime)s: %(message)s"
    l = logging.DEBUG if _debug else logging.ERROR
    logging.basicConfig(filename=filepath, level=l, format=f)
    pass
    

def loadFile(window, filename):

    if filename[-3:] in LicImporters.getFileTypesList():
        window.importModel(filename)
    elif filename[-3:] == 'lic':
        window.locationOpen(filename)
    else:
        return

    window.scene.selectFirstPage()

def updateAllSavedLicFiles(window):
    # Useful for when too many new features accumulate in LicBinaryReader & Writer.
    # Use this to open each .lic file in the project, save it & close it.
    for root, unused, files in os.walk("D:\\LeJOS\\Instructions\\Creator"):
        for f in files:
            if f[-3:] == 'lic':
                fn = os.path.join(root, f)
                print "Trying  to  open %s" % fn
                window.locationOpen(fn)
                if window.instructions.licFileVersion != FileVersion:
                    window.fileSave()
                    print "Successful save %s" % fn
                window.fileClose()


if __name__ == '__main__':
    config.checkPath("" ,config.appDataPath())
    setupExceptionLogger()

    app = QApplication(sys.argv)
    app.setOrganizationName("BugEyedMonkeys Inc.")
    app.setOrganizationDomain("bugeyedmonkeys.com")
    app.setApplicationName("LICreator")
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

    # Support of command line arguments 
    # Load a particular file on LIC launch - handy for debugging
    filename = ""
    if sys.argv.__len__() == 2:
        if os.path.isfile(sys.argv[1]):
            if sys.argv[1].lower()[-3:] not in ['exe', 'com', 'bat', 'py', 'pyw']:
                filename = sys.argv[1].strip().lower()
    if filename:
        QTimer.singleShot(50, lambda: loadFile(window, filename))

#     updateAllSavedLicFiles(window)
    app.exec_()

