from PyQt4.QtCore import *
from PyQt4.QtGui import *

from Model import *
from LicUndoActions import *
from LicTreeModel import *

class PartListPLI(PLI):
    itemClassName = "PartListPLI"

    def __init__(self, parent):
        PLI.__init__(self, parent)
        self.dataText = "Part List PLI"
        self._row = 1
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(QBrush(Qt.NoBrush))
        self.cornerRadius = 0

    def resetRect(self):
        inset = Page.margin.x()
        self.setPos(inset, inset)
        rect = self.parentItem().rect().adjusted(0, 0, -inset * 2, -inset * 2)
        self.setRect(rect)

    def doOverflowLayout(self):

        self.resetRect()

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            return

        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for item in self.pliItems:
            item.initLayout()
    
        partList = list(self.pliItems)
        partList.sort(key = lambda x: (x.color, x.rect().width()))
        
        columnWidth = 0
        mx, my = PLI.margin.x(), PLI.margin.y() 
        x, y = mx, my
        
        for item in partList:
            
            newHeight = item.rect().height() + my

            if y + newHeight > self.rect().height():  # Start new column
                x += columnWidth + (mx * 2)
                y = my
                columnWidth = item.rect().width()
                
            if x + item.rect().width() > self.rect().width():  # This item overflowed the right edge of page - abort
                index = partList.index(item)
                return partList[index:]

            item.setPos(x, y)
            y += newHeight
            columnWidth = max(columnWidth, item.rect().width())

        return []  # All items fit on this page

class PartListPage(PartListPageTreeManager, Page):
    
    def __init__(self, instructions, number = None, row = None):

        parentModel = instructions.mainModel
        if number is None and row is None:
            number = parentModel.pages[-1]._number + 1
            row = parentModel.pages[-1]._row + 1
        Page. __init__(self, parentModel, instructions, number, row)

        self.numberItem._row = 0
        self.pli = PartListPLI(self)

    def initFullPartList(self):
        for part in [p for p in self.subModel.parts if not p.isSubmodel()]:
            self.pli.addPart(part)
        for submodel in self.subModel.submodels:
            for part in [p for p in submodel.parts if not p.isSubmodel()]:
                self.pli.addPart(part)

    def initPartialItemList(self, itemList):
        self.pli.pliItems = itemList
        for item in itemList:
            item.setParentItem(self.pli)

    def doOverflowLayout(self):
        overflowItems = self.pli.doOverflowLayout()
        if overflowItems:
            for item in overflowItems:
                self.pli.pliItems.remove(item)
        return overflowItems

    def glItemIterator(self):
        for pliItem in self.pli.pliItems:
            yield pliItem

    def getAllChildItems(self):

        items = [self, self.numberItem, self.pli]

        for pliItem in self.pli.pliItems:
            items.append(pliItem)
            items.append(pliItem.numberItem)
        return items

    def contextMenuEvent(self, event):
        pass  # PartListPage has no context menu, yet

    @staticmethod
    def createPartListPages(instructions):

        page = PartListPage(instructions)
        page.initFullPartList()
        pageList = [page]
        overflowList = page.doOverflowLayout()
    
        while overflowList != []:
            page = PartListPage(instructions, pageList[-1]._number + 1, pageList[-1]._row + 1)
            page.initPartialItemList(overflowList)
            pageList.append(page)
            overflowList = page.doOverflowLayout()
    
        return pageList

class EditableTextItem(QGraphicsSimpleTextItem):
    
    itemClassName = "Page Number"

    def __init__(self, text, parent):
        QGraphicsSimpleTextItem.__init__(self, text, parent)
        self.setFlags(AllFlags)
        self.dataText = "Label: " + text
        self.setFont(QFont("Arial", 15))
        
    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Set Text", self.setTextSignal)
        menu.exec_(event.screenPos())
        
    def setTextSignal(self):
        newText, ok = QInputDialog.getText(self.scene().views()[0], "Set Text", "New Text:", 
                                           QLineEdit.Normal, self.text(), Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if ok:
            self.scene().undoStack.push(CalloutBorderFitCommand(self, self.text(), newText))

    def mouseDoubleClickEvent(self, event):
        self.setTextSignal()

class TitlePage(TitlePageTreeManager, Page):
    
    def __init__(self, instructions):
        Page. __init__(self, instructions.mainModel, instructions, 1, 1)
        instructions.mainModel.incrementRows(1)
        self.numberItem.hide()
        
        self.labels = []

        self.addSubmodelImage()
        si = self.submodelItem
        si._row = 0
        si.setPen(QPen(Qt.NoPen))
        si.setBrush(QBrush(Qt.NoBrush))

        si = EditableTextItem(self.subModel.getSimpleName(), self)
        si.setFont(QFont("Arial", 25))
        self.labels.append(si)

        si = EditableTextItem("1001", self)
        si.setPos(Page.margin * 2)
        self.labels.append(si)

        pw2, ph2 = Page.PageSize.width() / 2.0, Page.PageSize.height() / 2.0
        pmy = Page.margin.y()
        title = self.labels[0]
        x = pw2 - (self.submodelItem.rect().width() / 2.0)
        y = ph2 - (self.submodelItem.rect().height() / 2.0) + (title.boundingRect().height() / 2.0) + (pmy * 2)
        self.submodelItem.setPos(x, y)
        
        x = pw2 - (title.boundingRect().width() / 2.0)
        y = self.submodelItem.pos().y() - title.boundingRect().height() - (pmy * 3)
        title.setPos(x, y)

    def getAllChildItems(self):
        return [self, self.submodelItem ] + self.labels

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add Label", lambda: self.addLabel(event.scenePos()))
        menu.exec_(event.screenPos())

    def addLabel(self, pos = None):
        si = EditableTextItem("Blank Label", self)
        if pos:
            si.setPos(pos)
        self.labels.append(si)
