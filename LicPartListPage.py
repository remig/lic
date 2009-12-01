from PyQt4.QtCore import *
from PyQt4.QtGui import *

from Model import *
from LicTreeModel import PartListPageTreeManager

class PartListPLI(PLI):

    def __init__(self, parent):
        PLI.__init__(self, parent)
        self.dataText = "Part List PLI"
        self._row = 0
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(QBrush(Qt.NoBrush))

    def resetRect(self):
        inset = Page.margin.x()
        self.setPos(inset, inset)
        rect = self.parentItem().rect().adjusted(0, 0, -inset * 2, -inset * 2)
        self.setRect(rect)

    def initLayout(self):

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
                
            item.setPos(x, y)
            y += newHeight
            columnWidth = max(columnWidth, item.rect().width())

class PartListPage(PartListPageTreeManager, Page):
    
    def __init__(self, instructions):
        parentModel = instructions.mainModel
        number = parentModel.pages[-1]._number + 1
        row = parentModel.pages[-1]._row + 1
        Page. __init__(self, parentModel, instructions, number, row)
        
        self.pli = PartListPLI(self)

        self.initPartList()
        self.initLayout()
        
    def initPartList(self):

        for part in [p for p in self.subModel.parts if not p.isSubmodel()]:
            self.pli.addPart(part)
        for submodel in self.subModel.submodels:
            for part in [p for p in submodel.parts if not p.isSubmodel()]:
                self.pli.addPart(part)

    def initLayout(self):
        self.pli.initLayout()

    def glItemIterator(self):
        for pliItem in self.pli.pliItems:
            yield pliItem

