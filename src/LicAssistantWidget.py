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

import os
import shutil
import re
import tempfile
import thread

import urllib2
from urlparse import urlparse

from PIL import Image
from PyQt4.Qt import *  

import LicGLHelpers
import LicHelpers
import config

from LicCustomPages import Page
from LicDialogs import MessageDlg, makeSpinBox
from LicLayout import AutoLayout
from LicModel import Step, PLIItem, Part, PLI
from LicQtWrapper import ExtendedLabel
from LicUndoActions import MovePartsToStepCommand , AddRemovePageCommand, \
    LayoutItemCommand


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
    
    def __init__(self ,fnList=[]):
        QObject.__init__(self)  
        
        self._counter = 0
        self._fn = fnList
        
        self._workerThread = QThread()        
        self._workerThread.started.connect(self._doLongWork)   
        self._workerThread.finished.connect(self._doFinishWork)             
        self._workerThread.terminated.connect(self._doFinishWork)             
    
    def start(self):
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
    fileToDownload = ["codes.ini","weights.ini"]
    iniGroup = {'codes.ini':'Design','weights.ini':'Part'}
    
    hasConnection = False
    hasSuccess = False
    
    def __init__(self , parent , lic_repository):
        MessageDlg.__init__(self, parent)     
        self.button1.setPixmap(QCommonStyle().standardIcon (QStyle.SP_BrowserReload).pixmap(16, 16))
        self.connect(self.button1, SIGNAL("clicked()"), self.init_download)
        
        self.worker = None
        self.location = lic_repository

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
            self.worker = LicWorker([self.job_1S ,self.job_1 ,self.job_2 ,self.job_3 ,self.job_3S])
        finally:
            self.worker.start()        
        
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
    def download_file(url, destDir):
        """
        File downloading from the web.
        Copy the contents of a file from a given URL
        to a local file.
        """
        webFile = urllib2.urlopen(url)
        basename = url.split('/')[-1]
        filename = os.path.join(destDir , basename) 
        localFile = open(filename +'.x', 'w')
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
        destfile = ""
        if self.hasConnection:
            for srcfile in self.fileToDownload:
                try:
                    destfile = self.download_file(self.location + srcfile.strip() ,config.grayscalePath())
                except Exception , ex:
                    self.setText("Failed to download %s" % os.path.basename(srcfile))
                    self.hasSuccess = False
                    self.button1.show()
                    break
                else:
                    self.setText("Downloaded %s" % os.path.basename(destfile).replace('.x',''))
                    self.hasSuccess = True
                    
    def job_3(self):
        """
         If destination not exist rename temporary file, in other case add only new entries.
        """
        def isNeeded(value):
            result = True
            if value:
                try:
                    result = value.__len__() <= 3
                except (ValueError ,TypeError):
                    result = True
            return result
        
        self.counter = 0
        for filename ,groupname in self.iniGroup.iteritems():
            destFile = os.path.join(config.grayscalePath() ,filename)
            tempFile = os.path.join(config.grayscalePath() ,filename +'.x')
            
            if not os.path.isfile(destFile):
                shutil.copyfile(tempFile ,destFile)
            else:
                self.newDB = QSettings(QString(tempFile), QSettings.IniFormat)
                self.curDB = QSettings(QString(destFile), QSettings.IniFormat)
                
                self.newDB.beginGroup(groupname)
                for key in self.newDB.childKeys():
                    name = '%s/%s' % (groupname ,key)
                    value= self.curDB.value(name ,"").toString()     
                    if isNeeded(value):
                        value = self.newDB.value(key ,"").toString()  
                        if value and value.__len__() > 3:
                            self.curDB.setValue(name ,QVariant(value))
                            self.counter += 1
                self.newDB.endGroup()
            
            os.unlink(tempFile)
        
    def job_3S(self):
        """
         Display post-processing information to user
        """
        if self.counter > 1:
            self.setText('Done. Added %d entries.' % self.counter)
        else:
            self.setText('Done. %s' % self._message.text())
            
        if self.hasSuccess:
            self.emit(SIGNAL('success(int)') , self.counter)    
        

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
        p.fillRect(self.rect(), QColor(LicHelpers.SUBWINDOW_BACKGROUND))
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
            
        y += ht * 2
        x = self.width() / 2 - self._padding
        

class LicLayoutAssistant(MessageDlg):
    
    _vertical = False
    
    def __init__(self , scene):
        MessageDlg.__init__(self , scene.views()[0] , QSize(500, 40))  
        
        self.scene = scene
        
        self.setText("Change to")
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
            nums = LicHelpers.rangeify(regexp, vals) 
                  
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
    
    _buttonTip = {
                    QStyle.SP_DialogCancelButton : "Release this item and close window"
                    , QStyle.SP_DialogApplyButton : "Put this item on scene"
                    }
    _noPLIText = "non a PLI"
    _noMoveText = "You're still on the same page" 
    _noBlankText = "Page or Step can not be blank"
    _lockedPageText = "Stuff is locked on this page"
    _processingText = "Processing..."
    _noMoreParts = "You can not add more parts to transport"
    
    _maxQuantity = 3
    _thumbSize = 48
      
    def __init__(self , parent=None):
        QWidget.__init__(self, parent, Qt.SubWindow)

        x = parent.width() / 2 - self._thumbSize*6 if parent else 10
        self.setGeometry(x, 10, self._thumbSize*6, self._thumbSize*1.5)
        self.setBackgroundRole(QPalette.Base)
        self._item = None
        self.destItem = None
        self.partList = []
        
        warningFont = QFont("Times", 9)
        serifFont = QFont("Times", 12, QFont.Bold)
        serifFont.setCapitalization(QFont.SmallCaps)
        
        self._page = QLabel("")
        self._thumbnailbox = QHBoxLayout()
        self._step = QLabel("")
        self._warning = QLabel("")
        
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
        
        self._page.setFont(serifFont)
        self._step.setFont(serifFont)

        self._warning.setFont(warningFont)
        self._warning.setStyleSheet("QLabel { color : red; }")
        
        actions = QVBoxLayout()
        actions.addWidget(self._cancel)
        actions.addWidget(self._apply)
        
        content = QHBoxLayout()
        content.addWidget(self._page)
        content.addLayout(self._thumbnailbox)
        content.addWidget(self._step)
        
        grid = QGridLayout()
        grid.addLayout(actions, 1, 0, Qt.AlignTop)
        grid.addLayout(content, 1, 1, Qt.AlignLeft)
        grid.addWidget(self._warning, 2, 1, Qt.AlignHCenter)
        self.setLayout(grid)

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
                    self.destItem = self.destItem.steps[0]
                    
            # Find the selected item's parent page, then flip to that page
            # Move Part into Step
            canMove = True
            if isinstance(self.destItem, Step):
                destPage = self.destItem.parentItem()
                
                if srcPage.number == destPage.number:
                    canMove = False
                    self._warning.setText(self._noMoveText)
                     
                if destPage.isLocked():
                    canMove = False
                    self._warning.setText(self._lockedPageText)
                    
                if destPage.isEmpty():
                    canMove = False
                    self._warning.setText(self._noBlankText)
                 
                if canMove:        
                    self._worker = LicWorker([self.job_1S , self.job_2 , self.job_3])
                    self._worker.start()
   
    @staticmethod
    def exportPartImage(source ,sourcePage):
        pRect = source.sceneBoundingRect().toRect()
        wt = Page.PageSize.width()
        ht = Page.PageSize.height()
        mx = int(PLI.margin.x() / 2)
        bufferManager = LicGLHelpers.FrameBufferManager(wt, ht)
        try:
            # prepareToDraw
            bufferManager.bindMSFB()
            LicGLHelpers.initFreshContext(True)                                   
            # content of entire current page
            sourcePage.drawGLItemsOffscreen(QRectF(0, 0, wt, ht), 1.0)
            # readContent
            bufferManager.blitMSFB()
            temp_data = bufferManager.readFB()               
            # coordination in scene of this PLI part where image of pItem part is       
            temp_cord = (pRect.left() -mx ,pRect.top() -mx ,source.abstractPart.width +pRect.left() +mx ,source.abstractPart.height +pRect.top() +mx)
            # temporary Image instance
            temp_name = tempfile.TemporaryFile() .name + ".png" .lower()
            temp = Image.frombytes("RGBA", (wt, ht), temp_data)
        finally:
            temp = temp.transpose(Image.FLIP_TOP_BOTTOM)
            temp = temp.crop(temp_cord)
            temp.save(temp_name)
            
            return temp_name 
                              
    def setItemtoMove(self , part=None):
        self.destItem = None
        self._item = part
        step = part
        while step and not isinstance(step, Step):
            step = step.parent()
        self._step.setText(step.data(Qt.DisplayRole))
        self._page.setText(step.parentItem().data(Qt.DisplayRole))
        self._warning.clear()
        if part:
            try:
                index = self.partList.index(part, )
            except ValueError:
                index = -1
            
            if self.partList.__len__() > self._maxQuantity:
                self._warning.setText(self._noMoreParts)
            elif index == -1:
                self.partList.append(part)
                
                pItem = None
                if step and step.hasPLI():
                    for pliItem in step.pli.pliItems:
                        if pliItem.abstractPart.filename == part.abstractPart.filename:
                            pItem = pliItem
                            break
     
                sRect = QRect(0, 0, self._thumbSize, self._thumbSize) 
                image = QImage(sRect.size())
                if isinstance(pItem, (Part, PLIItem)):
                    a = pItem.abstractPart
                    filepath = os.path.join(config.grayscalePath() , os.path.splitext(a.filename)[0] + ".jpg").lower()
                    if not os.path.exists(filepath):
                        try:
                            tempfilepath = self.exportPartImage(pItem ,step.parentItem())
                        finally:
                            image.load(tempfilepath,"LA")
                       
                            for i in range(0, image.width()):
                                for j in range(0, image.height()):
                                    pix = image.pixel(i, j)
                                    if pix > 0:
                                        color = qGray(pix)
                                        image.setPixel(i, j, qRgb(color, color, color)) 
                                    else:
                                        image.setPixel(i, j, qRgb(255, 255, 255))
                              
                            image.save(filepath, "JPG")
                            os.remove(tempfilepath)
                    else:
                        image.load(filepath, "LA")
                else:
                    image = QImage(":/no_pli")
                     
                # propagate to display
                image = image.scaledToHeight(self._thumbSize, Qt.SmoothTransformation)
                image = image.copy(sRect)
                
                thumb = QLabel()
                thumb.setGeometry(sRect);
                thumb.setPixmap(QPixmap.fromImage(image))
                self._thumbnailbox.addWidget(thumb)

        if not self.isVisible():
            self.show()

    def paintEvent(self, event):
    # prepare canvas
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(LicHelpers.SUBWINDOW_BACKGROUND))
    # draw border
        p_old = p.pen()
        p_new = QPen(QBrush(QColor(Qt.black) , Qt.Dense6Pattern), 2.0)
        p.setPen(p_new)
        p.drawRect(QRectF(1, 1, self.width() - 2, self.height() - 2))
        p.setPen(p_old)
            
    def closeEvent(self, event):
    # restore cursor
        self.window().setCursor(Qt.ArrowCursor)
    # reset variables
        self.destItem = None
        self.partList = []
    # clear all widgets in a layout
        for i in reversed(range(self._thumbnailbox.count())):  
            self._thumbnailbox.itemAt(i).widget().deleteLater()        
    # take action
        return QWidget.closeEvent(self, event)
                    
    def job_1S(self):
        if self.destItem:
            self._warning.setText(self._processingText)
            self.window().setCursor(Qt.WaitCursor)
                            
            self.scene.setFocus(Qt.MouseFocusReason)
            self.scene.setFocusItem(self.destItem , Qt.MouseFocusReason)
            self.destItem.setSelected(True)

    def job_2(self):
        if self.destItem:
            self.scene.undoStack.push(MovePartsToStepCommand(self.partList, self.destItem))
        
    def job_3(self):
        self.close()      

                    
class LicCleanupAssistant(QDialog):        
        
    _steps = ["Initialing", "Remove blank pages", "Remove empty steps", "Merge pages with one step and one part", "Calculate area of the parts list"]
    _iconsize = 16
    _defaulttitle = "Clean-up"
    
    def __init__(self , pages , view):
        QDialog.__init__(self, view, Qt.Dialog | Qt.WindowTitleHint | Qt.WindowModal)
        self.setWindowTitle(self._defaulttitle)
        self.setModal(True)
        self.setFixedHeight(32 + self._iconsize * self._steps.__len__())
        
        n = 0
        self._icons = []
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
        
        self.worker = LicWorker([self.job_1S, self.job_1, self.job2S, self.job_2, self.job_3S, self.job_4, self.job_postProcessed])
        
    def showEvent(self, event):
        thread.start_new_thread(self.worker.start , ())
        return QDialog.showEvent(self, event)
    
    def closeEvent(self, event):
        self.worker.terminate()
        return QDialog.closeEvent(self, event)
    
    def job_postProcessed(self):
        # clean-up post processed actions
        self.setWindowTitle(self._defaulttitle)
        self._pages = []
            
    def job_1(self):       
        """ Remove blank pages """    
        self.setWindowTitle(self._defaulttitle)
            
        if [] != self._pages:
            stack = self._pages[0].scene().undoStack
            stack.beginMacro("Remove blank pages")
            for p in self._pages:
                if p.isEmpty():
                    self._pages.remove(p)
                    stack.push(AddRemovePageCommand(p.scene() , p , False))
            stack.endMacro()
        
    def job_2(self):
        """ Merge pages with one step and one part """
        """ Remove empty steps """
        for p in reversed(self._pages):
            sp = None
            ly = None
            for ch in p.children: 
                if isinstance(ch, Step):  
                    if sp is None:
                        sp = ch.parentItem()
                        ly = sp.getCurrentLayout()
                    nparts = ch.csi.parts.__len__()
                    if nparts == 0:
                        ch.setSelected(False)
                        sp.removeStep(ch)
                        sp.revertToLayout(ly)
                    if nparts == 1:
                        self.setWindowTitle("{0} {1}".format(self._defaulttitle , p.data(Qt.DisplayRole)))
                        if ch.getPrevStep():
                            ch.mergeWithStepSignal(ch.getPrevStep())

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
        for p in self._pages:
            for ch in p.children: 
                if isinstance(ch, Step):  
                    self.setWindowTitle("{0} {1}".format(self._defaulttitle , ch.data(Qt.DisplayRole)))
                    if ch.hasPLI():
                        topLeft = PLI.margin
                        displacement = 0
                        for item in ch.pli.pliItems:
                            item.initLayout()
                            item.resetRect()   
                            item.setPos(topLeft)
                            item.moveBy(displacement + topLeft.x(), 0)       
                            displacement += item.abstractPart.width
                        ch.pli.resetRect()
                            
