"""
    LIC - Instruction Book Creation software
    Copyright (C) 2015 Jeremy Czajkowski

    This file (LicAssistantWidget.py) is part of LIC.

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

from copy import deepcopy
import shutil
import string
import thread
import urllib2
from urlparse import urlparse
from zipfile import *

from PyQt4.Qt import *  

from LicDialogs import MessageDlg, makeSpinBox
from LicHelpers import *
from LicLayout import AutoLayout, Horizontal
from LicModel import Step, PLIItem, Part, PLI
from LicQtWrapper import ExtendedLabel
from LicUndoActions import MovePartsToStepCommand , AddRemovePageCommand, \
    LayoutItemCommand, MoveCommand, RenameCommand , MoveStepToPageAtRowCommand
import config
import LicCustomPages


shortcuts = {
     1: ["Move vertically with 20 steps", "Shift + Down | Up"]
    , 2: ["Move vertically with 5 steps", "Ctrl + Down | Up"]
    , 3: ["Jump to next step on current page", "Tab"]
    , 4: ["Jump to next or first part", "Shift + Tab"]
    , 5: ["Move horizontally with 20 steps", "Shift + Right | Left"]
    , 6: ["Move horizontally with 5 steps", "Ctrl + Right | Left"]
    , 7: ["Jump to next page", "PageDown"]
    , 8: ["Jump to previous page", "PageUp"]
    , 9: ["Go to first or title page", "Home"]
    , 10:["Go to last page or part listing", "End"]
    , 11:["Jump to selected step or page", "F10"]
    , 12:["Remove blank pages", "F9"]
    , 13:["Show or hide rules", "F6"]
    , 14:["Show or hide this pop-up window", "F1"]
}


class LicWorker(QObject):
    """
    You can't move widgets into another thread - in order to keep user interface responsive, 
    Qt needs to do all GUI work inside main thread.
    
    If you have background work to do, then move background worker to other thread, and not the user interface.
    """       
    
    def __init__(self):
        QObject.__init__(self)  
        
        self._counter = 0
        self._fn = []
        
        self._workerThread = QThread()        
        self._workerThread.started.connect(self._doLongWork)   
        self._workerThread.finished.connect(self._doFinishWork)             
        self._workerThread.terminated.connect(self._doFinishWork)             
    
    def start(self ,fnList=[]):
        self._fn = fnList
        self._workerThread.start()
        
    def terminate(self):
        self._workerThread.terminate()
        
    def _doFinishWork(self):
        self._counter = 0  
        self._fn = []
    
    def _doLongWork(self ,ident=0):
        try:
            self._fn[ident]()
        except:
            self._workerThread.terminate()
            pass
        else:
            #  Long running operations can call PySide.QtCore.QCoreApplication.processEvents()
            #  to keep the application responsive.
            #
            #  This is necessary to handle self._fn content correctly. Like refresh pixmap in loop.
            QCoreApplication.processEvents()
        
            self._counter += 1
            if self._counter == self._fn.__len__():
                self._workerThread.quit()
            else:
                self._doLongWork(self._counter)

class LicRefactorAssistant(MessageDlg):
    def __init__(self ,scene ,entrusted):
        MessageDlg.__init__(self, scene.views()[0])    
        
        self._entrusted = entrusted
        self._scene = scene
        
        self.setText("Rename to:")
        self.setToolTip("Select new name for %s. Old will be preserved." % entrusted.__class__.__name__)
        self.setAcceptAction(self.acceptValue)
        
        self.textField = QLineEdit()
        if entrusted:
            self.textField.setText(entrusted.name)
        
        hbox = self.centreLayout
        hbox.addWidget(self.textField , 1)
        
    def acceptValue(self):
        if self._entrusted and self._scene:
            self._scene.undoStack.push(RenameCommand(self._entrusted ,self._entrusted.name ,self.textField.text()))
            self.close()

class LicModelBoxAssistant(MessageDlg):
    def __init__(self ,parent, modelBoxDict):
        MessageDlg.__init__(self, parent)   
        
        self.setWindowTitle("Module Bounding Box")
        # should be collection of AbstractPart.getBoundingBox()
        self.modelBoxDict = modelBoxDict
        
    def showEvent(self, event):  
            tbox = QGridLayout() 
            lbox = None
            row = 1
            column = 0
            
            # check if this instruction have more that one subordinate model 
            singlemodel = self.modelBoxDict.__len__() == 1
            
            # remove previous widgets
            self.centreLayout.removeItem( self.centreLayout.itemAt(0) )
                       
            for modelFile ,modelBox in self.modelBoxDict.iteritems(): 
                gbox = QGroupBox(modelFile)
                grid = QGridLayout()

                minLabel = QLabel( "Minimum    %.2f  %.2f  %.2f" % (modelBox.x1, modelBox.y1, modelBox.z1) )
                maxLabel = QLabel( "Maximum  %.2f  %.2f  %.2f" % (modelBox.x2, modelBox.y2, modelBox.z2) )
                boxLabel = QLabel( "Perimeter  %.0fx%.0fx%.0f" % (modelBox.xSize(), modelBox.ySize(), modelBox.zSize()) )
                
                grid.addWidget(minLabel ,0 ,0 ,Qt.AlignLeft)
                grid.addWidget(maxLabel ,1 ,0 ,Qt.AlignLeft)
                
            # QGridLayout must have second column when subordinate models exists
                grid.addWidget(boxLabel ,0 if singlemodel else 2 ,1 if singlemodel else 0 ,Qt.AlignLeft)
            
            # main model MUST always go first. In this case remember this instance 
            # to put on top in layout when loop 'for' come to THE END 
                if modelFile.startswith("main"):
                    lbox = grid
                else:
                    gbox.setLayout(grid)
                    tbox.addWidget(gbox ,row if column == 0 else row -1 ,column)
                
            # calculate position         
                column = 0 if column == 1 else 1
                row += 1
        
            # in simple manner, if current content of this file do not have any submodels,
            # put layout with informations of main model AS IS
            if lbox and singlemodel:
                self.centreLayout.addLayout(lbox)
            else:      
                if lbox:
                    mbox = QGroupBox("Main model")
                    mbox.setLayout(lbox)
                    tbox.addWidget(mbox ,1 ,1)
                self.centreLayout.addLayout(tbox)         
                                       
            return QWidget.showEvent(self, event)

class LicMovingStepAssistant(MessageDlg):
    def __init__(self , step):
        MessageDlg.__init__(self , step.scene().views()[0])
        
        self._step = step
        
        self.pageComboBox = QComboBox()
        self.centreLayout.addWidget(self.pageComboBox , 0)
        
        pageList = step.parent().submodel.pages
        for page in sorted(pageList ,key=lambda i: i.number):
            if not page == step.parent():
                if not page.isLocked() and not page.isEmpty():
                    self.pageComboBox.addItem(page.data(Qt.DisplayRole) ,userData=page)          
        
        self.setText("Move to:")
        self.setAcceptAction(self.acceptValue)
        
    def acceptValue(self):
        index= self.pageComboBox.currentIndex()
        data = self.pageComboBox.itemData(index)
        self._step.scene().undoStack.push(MoveStepToPageAtRowCommand(data.toPyObject() ,self._step ,0))

class LicJumper(MessageDlg):
    def __init__(self , scene):
        MessageDlg.__init__(self , scene.views()[0])
        
        self.scene = scene
        self.maxCount = [1, 1]
        
        self.setText("Jump to:")
        self.setStatusTip("Put the numer and press ENTER inside field to finish task")
        
        self.valueSpinBox = makeSpinBox(self , 1 , 1 , 1.0)
        self.pageCheckBox = QRadioButton("page" , self)
        self.stepCheckBox = QRadioButton("step" , self)
        
        self.valueSpinBox.setSingleStep(2)
        self.pageCheckBox.setChecked(True)
        
        self.connect(self.valueSpinBox, SIGNAL("editingFinished()") , self.acceptValue)
        self.connect(self.pageCheckBox, SIGNAL("toggled(bool)") , self.stateChanged)
        
        hbox = self.centreLayout
        hbox.addSpacing(5)
        hbox.addWidget(self.valueSpinBox , 1 , Qt.AlignLeft)
        hbox.addWidget(self.pageCheckBox , 1 , Qt.AlignLeft)        
        hbox.addWidget(self.stepCheckBox , 1 , Qt.AlignLeft)    
        hbox.addSpacing(100)    
        
    def showEvent(self, event):
        self.reset()
        self.valueSpinBox.setFocus(Qt.MouseFocusReason)
        self.valueSpinBox.selectAll()
        
        if self.scene.pages: 
            bShow = self.scene.pages[0].instructions.mainModel.submodels.__len__() == 0 
            self.stepCheckBox.setVisible(bShow)
        if not self.stepCheckBox.isVisible():
            self.pageCheckBox.setChecked(True) 
        
        return QWidget.showEvent(self, event)    
    
    def enterEvent(self, event):
        if self.scene:
            self.scene.clearSelection()
        
        return QWidget.enterEvent(self, event)
    
    def acceptValue(self):
        if self.valueSpinBox.hasFocus():
            self.close()
            if self.scene.pages:
                number = self.valueSpinBox.value()
                if self.pageCheckBox.isChecked():
                    self.scene.selectPageFullUpdate(number)
                if self.stepCheckBox.isChecked():
                    for page in self.scene.pages:
                        for step in page.steps:
                            if step.number == number:
                                self.scene.selectPage(step.parentItem().number)
                                step.setSelected(True)
                                self.scene.emit(SIGNAL("sceneClick"))
                                return
                                    
    def stateChanged(self, state):
        self.valueSpinBox.setMaximum(self.maxCount[state])
    
    def reset(self):
        self.valueSpinBox.setMaximum(1)
        if self.scene.pages:  
            pageCount = self.scene.pageCount()
            stepCount = 1
            
            if pageCount > 1:
                for page in self.scene.pages:
                    if not page.isEmpty():
                        stepCount += page.steps.__len__()
            
            self.maxCount = [stepCount, pageCount]
            self.valueSpinBox.setMaximum(pageCount)


class LicDownloadAssistant(MessageDlg):
    fileToDownload = ['default_template.lit','codes.ini','weights.ini','parts.zip']
    iniGroup = {'codes.ini':'Design','weights.ini':'Part'}
    fileToPath = {}
    
    hasConnection = False
    hasSuccess = False
    
    _tempsurfix = '.x'
    
    def __init__(self , parent , lic_repository):
        MessageDlg.__init__(self, parent)     
        self.button1.setPixmap(QCommonStyle().standardIcon (QStyle.SP_BrowserReload).pixmap(16, 16))
        self.connect(self.button1, SIGNAL("clicked()"), self.init_download)
        
        self.worker = None
        self.location = lic_repository
        
        for key in self.fileToDownload:
            self.fileToPath[key] = config.partsCachePath()
        self.fileToPath['default_template.lit'] = config.appDataPath()


    def showEvent(self, event):
        self.init_download()
        return MessageDlg.showEvent(self, event)
    
    def init_download(self):
        """
         Start download thread
        """
        self.hasSuccess = False
        try:
            del self.worker
            self.worker = LicWorker()
        finally:
            self.worker.start([self.job_1S ,self.job_1 ,self.job_2 ,self.job_3 ,self.job_4 ,self.job_4S])        
        
    @staticmethod
    def internet_on(address):
        """
         Using a numerical IP-address avoids a DNS lookup, which may block the urllib2.urlopen 
         call for more than a second. 
         By specifying the timeout=1 parameter, the call to urlopen will not take much longer 
         than 1 second even if the internet is not "on".
        """
        parsed = urlparse(address)
        try:
            urllib2.urlopen("%s://%s" % (parsed.scheme , parsed.hostname), timeout=1)
            return True
        except urllib2.URLError: 
            pass
        return False

    @staticmethod
    def download_file(url, destDir, surfix):
        """
        File downloading from the web.
        Copy the contents of a file from a given URL
        to a local file.
        """
        webFile = urllib2.urlopen(url)
        basename = url.split('/')[-1]
        filename = os.path.join(destDir , basename) 
        localFile = open(filename +surfix, 'wb')
        localFile.write(webFile.read())
        webFile.close()
        localFile.close()
        return localFile.name
    
    def job_1S(self):
        self.setText("Waiting for connection...") 
        self.button1.hide()
        
    def job_1(self):            
        """
         Check connection with outside world.
        """    
        self.hasConnection = self.internet_on(self.location)
        if not self.hasConnection:
            self.setText("Connection can not been established.")
            self.button1.show()   
            
    def job_2(self):
        """
         Download file from server to target location with temporary name.
        """
        if self.hasConnection:
            for srcfile in self.fileToDownload:
                try:
                    self.setText("Downloading %s" % srcfile)
                    self.download_file(self.location + srcfile.strip() ,self.fileToPath[srcfile] ,self._tempsurfix)
                except Exception as error:
                    logging.exception(error)
                    self.setText("Failed to download %s" % srcfile)
                    self.hasSuccess = False
                    self.button1.show()
                    return
                else:
                    self.hasSuccess = True
                    
    def job_3(self):
        """
         If destination not exist rename temporary file, in other case add only new entries.
        """
        self.counter = 0
        fileToRename = deepcopy(self.fileToDownload)
        for filename ,groupname in self.iniGroup.iteritems():
            destFile = os.path.join(self.fileToPath[filename] ,filename)
            tempFile = destFile +self._tempsurfix
            
            if not os.path.isfile(destFile):
                shutil.copyfile(tempFile ,destFile)
            else:
                self.newDB = QSettings(QString(tempFile), QSettings.IniFormat)
                self.curDB = QSettings(QString(destFile), QSettings.IniFormat)
                
                self.newDB.beginGroup(groupname)
                for key in self.newDB.childKeys():
                    name = '%s/%s' % (groupname ,key)
                    value= self.curDB.value(name ,defaultValue=0).toInt()[0]    
                    if value <= 0:
                        newvalue = self.newDB.value(key ,"").toInt()[0]  
                        if newvalue and newvalue > 0:
                            self.curDB.setValue(name ,QVariant(newvalue))
                            self.counter += 1
                self.newDB.endGroup()
            
            if filename in fileToRename:
                fileToRename.remove(filename)
            
            os.unlink(tempFile)
            
        for filename in fileToRename:
            destFile = os.path.join(self.fileToPath[filename] ,filename)
            tempFile = destFile +self._tempsurfix
            if os.path.exists(destFile):
                os.unlink(destFile)
            os.rename(tempFile, destFile)
        
    def job_4(self):       
        """
         Unpack archive that contains part's images
        """
        archivename = 'parts.zip'
        destFile = os.path.join(self.fileToPath[archivename] ,archivename)
        
        if os.path.exists(destFile):    
            self.setText("Extracting archive %s" % archivename)   
            try:      
                with ZipFile(destFile ,"r" ,ZIP_DEFLATED) as myzip:
                    for zib_e in myzip.namelist():
                        filename = os.path.basename(zib_e)
                        if not filename:
                            continue
                        myzip.extract(zib_e ,self.fileToPath[archivename])
                    myzip.close()
            except Exception as error:
                logging.exception(error)
            
        
    def job_4S(self):
        """
         Display post-processing information to user
        """
        if self.counter > 1:
            self.setText('Done. Added %d entries.' % self.counter)
        elif self.hasSuccess:
            self.setText('Done. %s' % self._message.text())
            
        if self.hasSuccess:
            self.emit(SIGNAL('success(int)') , self.counter)
        return    
        

class LicShortcutAssistant(QWidget):

    _padding = 5
    _space = 10

    def __init__(self , parent=None):
        QWidget.__init__(self, parent, Qt.SubWindow)
        fontHeight = QPainter(self).fontMetrics().height()
        ht = shortcuts.__len__() * fontHeight + shortcuts.__len__() * self._space 
        
        self.setGeometry(1, 1, 300, ht)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFocusProxy(parent)
        self.setMouseTracking(True)     

    def paintEvent(self, event):
        p = QPainter(self)
        ht = p.fontMetrics().height()
        p.fillRect(self.rect(), QColor(SUBWINDOW_BACKGROUND))
        p.setPen(QPen(QBrush(QColor(Qt.black) , Qt.Dense6Pattern), 4.0))
        p.drawRect(self.rect())
        p.setPen(Qt.black)
        for n in shortcuts:
            y = self._space * n + ht * n
            try:
                p.drawText(QPointF(self._padding , y - self._padding), shortcuts[n][0])
                p.drawText(QPointF(self._padding + 200, y - self._padding), shortcuts[n][1])
            except:
                pass
            else:
                p.drawLine(self._padding , y , self.width() - self._padding , y)
            

class LicLayoutAssistant(MessageDlg):
    
    _vertical = False
    
    def __init__(self , scene):
        MessageDlg.__init__(self , scene.views()[0] , QSize(500, 40))  
        
        self.scene = scene
        
        self.setText("Change to:")
        self.setStatusTip("Enter the page numbers separated by commas")
        
        self.nTextField = QLineEdit()
        self.hCheckBox = QRadioButton("horizontal" , self)
        self.vCheckBox = QRadioButton("vertical" , self)
        
        self.hCheckBox.setChecked(True)
        
        self.connect(self.vCheckBox, SIGNAL("toggled(bool)") , self.stateChanged)
        self.setAcceptAction(self.acceptValue)
        
        hbox = self.centreLayout
        hbox.addSpacing(5)
        hbox.addWidget(self.hCheckBox , 1 , Qt.AlignLeft)        
        hbox.addWidget(self.vCheckBox , 1 , Qt.AlignLeft)  
        hbox.addWidget(QLabel("layout for"))
        hbox.addWidget(self.nTextField , 1)
        hbox.addWidget(QLabel("pages"))   
        hbox.addSpacing(15)  
        
        self.nTextField.setFocus(Qt.MouseFocusReason)

    def enterEvent(self, event):
        if self.scene:
            self.nTextField.setFocus(Qt.MouseFocusReason)
            self.scene.clearSelection()
        
        return QWidget.enterEvent(self, event)
            
    def stateChanged(self, state):
        self._vertical = state
        
    def acceptValue(self):
        vals = self.nTextField.text()
        stack = self.scene.undoStack
        state = int(self._vertical)
        nums = []
        if vals and self.scene.pages:
            regexp = re.compile(r'^\d{1,}(-\d{1,}|)$')
            nums = rangeify(regexp, vals) 
                  
            if nums:
                stack.beginMacro("change layout%s" % ("s" if nums.__len__() > 1 else ""))
                for page in self.scene.pages:
                    try:
                        c = nums.index(page.number)
                    except:
                        c = -1
                    else:
                        if c > -1:  
                            lstate = state if page.steps and page.steps.__len__() > 1 else AutoLayout 
                            stack.push(LayoutItemCommand(page, page.getCurrentLayout(), lstate))
                stack.endMacro()
                self.close()


class LicPlacementAssistant(QWidget):    
    
    _buttonTip = { QStyle.SP_DialogCancelButton : "Release this item and close window" 
                  ,QStyle.SP_DialogApplyButton : "Put this item on scene" }
    _noSpecialPage = "You can not add parts here"
    _noPLIText = "non a PLI"
    _noMoveText = "You're still on the same page" 
    _noEmptyText = "Page can not be empty"
    _lockedPageText = "Stuff is locked on this page"
    _processingText = "Processing..."
    _noMoreParts = "You can not add more parts to transport"
    
    _maxQuantity = 3
    _thumbSize = 48
      
    def __init__(self , parent=None):
        QWidget.__init__(self, parent, Qt.SubWindow)

        x = parent.width() / 2 - self._thumbSize*6 if parent else 10
        self.setGeometry(x, 10, self._thumbSize*6, self._thumbSize*2)
        self.setBackgroundRole(QPalette.Base)
        self._item = None
        self.destItem = None
        self.partList = []
        
        warningFont = QFont("Times", 9)
        serifFont = QFont("Times", 12, QFont.Bold)
        serifFont.setCapitalization(QFont.SmallCaps)
        
        self._thumbnailbox = QHBoxLayout()
        self._warning = QLabel("")
        self._worker = LicWorker()
        
        self._thumbnailbox.setSpacing(0)
        
        self._apply = ExtendedLabel()
        self._apply.setPixmap(QCommonStyle().standardPixmap (QStyle.SP_DialogApplyButton))
        self._apply.setStatusTip(self._buttonTip[QStyle.SP_DialogApplyButton])
        self.connect(self._apply, SIGNAL('clicked()'), self.moveItemToStep)
        
        self._cancel = ExtendedLabel()
        self._cancel.move(0, 0)
        self._cancel.setPixmap(QCommonStyle().standardPixmap (QStyle.SP_DialogCancelButton))
        self._cancel.setStatusTip(self._buttonTip[QStyle.SP_DialogCancelButton])
        self.connect(self._cancel, SIGNAL('clicked()'), self.close)
        
        self._warning.setFont(warningFont)
        self._warning.setStyleSheet("QLabel { color : red; }")
        
        actions = QVBoxLayout()
        actions.addWidget(self._cancel)
        actions.addWidget(self._apply)
        
        content = QHBoxLayout()
        content.addLayout(actions)
        content.addLayout(self._thumbnailbox)
        
        box = QVBoxLayout()
        box.addLayout(content)
        box.addWidget(self._warning)

        self.setLayout(box)

    def moveItemToStep(self):
        self._warning.clear()
        if self._item is not None:
            self.scene = self._item.scene()
            srcPage = self._item.getStep().parentItem()      
            try:
                self.destItem = self.scene.selectedItems()[0]
            except IndexError:
                self.destItem = None
            
            # Find Step assigned to currently selected item
            if self.destItem and self.destItem.__class__.__name__ != "Page":
                while self.destItem and not isinstance(self.destItem, Step):
                    try:
                        self.destItem = self.destItem.parent()
                    except:
                        break
            
            # Convert Page to first step on the list
            if self.destItem and self.destItem.__class__.__name__ == "Page":
                if srcPage.number == self.destItem.number:
                    self._warning.setText(self._noMoveText)
                else:
                    if self.destItem.steps:
                        self.destItem = self.destItem.steps[0]
                    else:
                        self._warning.setText(self._noEmptyText)
                    
            # Find the selected item's parent page, then flip to that page
            # Move Part into Step
            canMove = True
            message = ""
            if isinstance(self.destItem, Step):
                destPage = self.destItem.parentItem()
                
                if srcPage.number == destPage.number:
                    canMove = False
                    message = self._noMoveText
                     
                if destPage.isLocked():
                    canMove = False
                    message = self._lockedPageText
                    
                if destPage.isEmpty():
                    canMove = False
                    message = self._noEmptyText
                
                if destPage.__class__.__name__.lower() in ['titlepage' , 'templatepage' ,'partlistpage']:
                    canMove = False
                    message = self._noSpecialPage
                 
                if canMove:        
                    self._worker.start([self.job_1S , self.job_2 , self.job_3])
                
            if message:
                self._warning.setText(string.rjust(message, self._thumbSize))
                                 
    def setItemtoMove(self , part=None):
        self.destItem = None
        self._item = part
        step = part
        while step and not isinstance(step, Step):
            step = step.parent()
            
        self._warning.clear()
        if not self.isVisible():
            self.show()
        
        if part:
            try:
                index = self.partList.index(part, )
            except ValueError:
                index = -1
            
            if self.partList.__len__() >= self._maxQuantity:
                self._warning.setText(self._noMoreParts)
                return
            elif index == -1:
                self.partList.append(part)
                  
                pItem = None
                if step and step.hasPLI():
                    for pliItem in step.pli.pliItems:
                        if pliItem.abstractPart.filename == part.abstractPart.filename:
                            pItem = pliItem
                            break
       
                sRect = QRect(0, 0, self._thumbSize *1.2, self._thumbSize *1.2) 
                image = QImage(sRect.size())
                if isinstance(pItem, (Part, PLIItem)):
                    a = pItem.abstractPart
                    filename = os.path.splitext(a.filename)[0] + ".png"
                    filepath = os.path.join(config.partsCachePath() ,filename ).lower()
                    if os.path.exists(filepath):
                        image.load(filepath,"LA")
                    else:
                        writeLogEntry("FileNotFoundError: [Errno 2] No such file or directory: '%s'" % filename)
                        image = QImage(":/no_pli")
                else:
                    image = QImage(":/no_pli")
                       
                # propagate to display
                image = image.scaledToHeight(sRect.height(), Qt.SmoothTransformation)
                image = image.copy(sRect)
                  
                # add to layout
                thumb = QLabel()
                thumb.setGeometry(sRect);
                thumb.setPixmap(QPixmap.fromImage(image))
                self._thumbnailbox.addWidget(thumb)

    def paintEvent(self, event):
    # prepare canvas
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(SUBWINDOW_BACKGROUND))
    # draw border
        p_old = p.pen()
        p_new = QPen(QBrush(QColor(Qt.black) , Qt.Dense6Pattern), 2.0)
        p.setPen(p_new)
        p.drawRect(QRectF(1, 1, self.width() - 2, self.height() - 2))
        p.setPen(p_old)
            
    def closeEvent(self, event):
    # clear all widgets in a layout
        for i in reversed(range(self._thumbnailbox.count())):  
            self._thumbnailbox.itemAt(i).widget().deleteLater()   
    # restore cursor
        self.window().setCursor(Qt.ArrowCursor)
    # reset variables
        self.destItem = None
        self.partList = []     
    # take action
        return QWidget.closeEvent(self, event)
                            
    def job_1S(self):
        if self.destItem:
            self._warning.setText( string.rjust(self._processingText, self._thumbSize) )
            self.window().setCursor(Qt.WaitCursor)
                            
            self.scene.setFocus(Qt.MouseFocusReason)
            self.scene.setFocusItem(self.destItem , Qt.MouseFocusReason)
            self.destItem.setSelected(True)

    def job_2(self):
        if self.destItem:
            self.scene.undoStack.push(MovePartsToStepCommand(self.partList, self.destItem))
        
    def job_3(self):
        self.close()      

 
class LicOrganizeAssistant(MessageDlg):
    
    _vertical = True
    _entrusted= None
    
    def __init__(self ,parent ,entrusted):
        MessageDlg.__init__(self, parent)       
        
        self._entrusted = entrusted
        
        self.setStatusTip("Enter how many parts per line to be")
        
        self.nTextField = QLineEdit()
        self.vCheckBox = QRadioButton("verticaly" , self)
        self.hCheckBox = QRadioButton("horizontaly" , self)        
         
        self.vCheckBox.setChecked(True)
        self.nTextField.setText("5")
        
        self.connect(self.vCheckBox, SIGNAL("toggled(bool)") , self.stateChanged)
        self.setAcceptAction(self.acceptValue)
        
        hbox = self.centreLayout
        hbox.addSpacing(5)
        hbox.addWidget(self.nTextField , 1)
        hbox.addWidget(QLabel("parts per line"))
        hbox.addWidget(self.vCheckBox , 1 , Qt.AlignLeft) 
        hbox.addWidget(self.hCheckBox , 1 , Qt.AlignLeft)        
        
    def stateChanged(self, state):
        self._vertical = state
        
    def acceptValue(self): 
        if self._entrusted:        
    # Save current position, because same behavior can change this
            oldPos = self._entrusted.pos()
    # Validate user input
            nItems = 1
            maxItems = 3
            limit = rangeify(re.compile(r'^[0-9]+$'), self.nTextField.text())
            if limit and limit[0] > 3:
                maxItems = int(limit[0])
    # Sort by color, reversed 
            partList = list(self._entrusted.pliItems)
            partList.sort(key=lambda i: i.color.sortKey() if (i.color) else LicColor.red().sortKey(), reverse=True)                   
    # Sort by width (then height, for ties)
            partList.sort(key=lambda i: (i.rect().width(), i.rect().height()))          
    # Restore to default state
            self._entrusted.initLayout()     
    # Set new position for each part in PLI
            x = xMargin = PLI.margin.x()
            y = yMargin = PLI.margin.y()
             
            for item in partList:
                item.oldPos = item.pos()
                item.setPos(x ,y)    
                 
                r = item.rect()
                if self._vertical:
                    y += r.y() + r.height() +yMargin
                else:
                    x += r.x() + r.width() +xMargin
                 
                if nItems == maxItems:
                    nItems = 1
                    if self._vertical:
                        x += r.x() + r.width() +xMargin
                    else:
                        x = xMargin  # Start new row
                    if self._vertical:
                        y = yMargin  # Start new column
                    else:
                        y += r.y() + r.height() +yMargin
                else:
                    nItems += 1
    # PLI position na size
            self._entrusted.resetRect()
            self._entrusted.setPos(oldPos)
                
            self._entrusted.scene().undoStack.push(MoveCommand(partList))
        self.close()
                 
    def changeEntrusted(self, entrusted):
        self._entrusted = entrusted
                 
                    
class LicCleanupAssistant(QDialog):        
        
    _steps = ["Initialing", "Remove blank pages" ,"Remove empty steps"
              ,"Merge pages with one step and one part" ,"Clean mesh of layout"]
    _iconsize = 16
    _defaulttitle = "Clean-up"
    
    def __init__(self , pages , view):
        QDialog.__init__(self, view, Qt.Dialog | Qt.WindowTitleHint | Qt.WindowModal)
        self.setWindowTitle(self._defaulttitle)
        self.setModal(True)
        self.setFixedHeight(32 + self._iconsize * self._steps.__len__())
        
        n = 0
        self._icons = []
        self._dirtypages = []
        self._pages = pages
        self._pixmap = QCommonStyle().standardIcon (QStyle.SP_DialogApplyButton).pixmap(self._iconsize , self._iconsize)
        
        
        grid = QGridLayout()
        for s in (self._steps):
            icon_box = QLabel()
            self._icons.append(icon_box)
            grid.addWidget(QLabel(s), n, 0, Qt.AlignLeft)
            grid.addWidget(icon_box, n, 1, Qt.AlignRight)
            n += 1
        self.setLayout(grid)
        
        self._icons[0].setPixmap(self._pixmap)
        self._icons[0].setMask(self._pixmap.mask())
        
        self.worker = LicWorker()
        self._jobs = [self.job_1S, self.job_1, self.job2S, self.job_2, self.job_3S, self.job_4, self.job_5]
        
    def showEvent(self, event):
        thread.start_new_thread(self.worker.start , (self._jobs,))
        return QDialog.showEvent(self, event)
    
    def closeEvent(self, event):
        self.worker.terminate()
        return QDialog.closeEvent(self, event)
    
    def job_5(self):
        # clean-up post processed actions
        self._pages = []
        self._dirtypages = []
        self.setWindowTitle(self._defaulttitle)
        self.close()
            
    def job_1(self):       
        """ Remove blank pages """    
        self.setWindowTitle(self._defaulttitle)
            
        if [] != self._pages:
            stack = self._pages[0].scene().undoStack
            stack.beginMacro("Remove blank pages")
            for p in reversed(self._pages):
                if p.isBlank() and not p.isLocked():
                    self._pages.remove(p)
                    stack.push(AddRemovePageCommand(p.scene() , p , False))
            stack.endMacro()
        
    def job_2(self):
        """ Merge pages with one step and one part """
        """ Remove empty steps """
        for p in reversed(self._pages):
            if p.isLocked():
                continue
            sp = None
            ly = None
            for ch in p.children: 
                dirty = False
                if isinstance(ch, Step):  
                    if sp is None:
                        sp = ch.parentItem()
                        ly = sp.getCurrentLayout()
                    nparts = ch.csi.parts.__len__()
                    if nparts == 0:
                        ch.setSelected(False)
                        sp.removeStep(ch)
                        sp.revertToLayout(ly)
                        dirty = True
                    if nparts == 1:
                        self.setWindowTitle("{0} {1}".format(self._defaulttitle , p.data(Qt.DisplayRole)))
                        if ch.getPrevStep():
                            ch.mergeWithStepSignal(ch.getPrevStep())
                            dirty = True
                if dirty:
                    self._dirtypages.append(p)

    def job_1S(self):
        self._icons[1].setPixmap(self._pixmap)
        self._icons[1].setMask(self._pixmap.mask())  
 
    def job2S(self):
        self._icons[2].setPixmap(self._pixmap)
        self._icons[2].setMask(self._pixmap.mask())
                  
    def job_3S(self):    
        # work is done in step 2 so set visual signal here
        self._icons[3].setPixmap(self._pixmap)
        self._icons[3].setMask(self._pixmap.mask())  
        
    def job_4(self):
        self._icons[4].setPixmap(self._pixmap)    
        for p in self._dirtypages:
            if not p.isBlank() and not p.isLocked():
                orientation = p.layout.orientation
                p.initLayout()
                if orientation == Horizontal:
                    p.useVerticalLayout
                else:
                    p.useHorizontalLayout
                
                            
