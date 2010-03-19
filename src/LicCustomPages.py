"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicCustomPages.py) is part of Lic.

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

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from LicModel import *
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
            return []

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

    def initLayout(self):
        pass  # TODO: Need to handle bumping items from page to page, so can do post-loaded auto-layouts

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
            if pliItem.lengthIndicator:
                items.append(pliItem.lengthIndicator)
        return items

    def contextMenuEvent(self, event):
        pass  # PartListPage has no context menu, yet

    def updatePartList(self):

        self.pli.removeAllParts()
        self.initFullPartList()
        pageList = [self]
        overflowList = self.doOverflowLayout()
    
        while overflowList != []:
            page = PartListPage(self.instructions, pageList[-1]._number + 1, pageList[-1]._row + 1)
            page.initPartialItemList(overflowList)
            pageList.append(page)
            overflowList = page.doOverflowLayout()
    
        return pageList
    
    @staticmethod
    def createPartListPages(instructions):

        page = PartListPage(instructions)
        return page.updatePartList()

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
        menu.addAction("Remove Label", self.remove)
        menu.exec_(event.screenPos())
        
    def remove(self):
        action = AddRemoveLabelCommand(self.parentItem(), self, self.parentItem().labels.index(self), False)
        self.scene().undoStack.push(action)

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
        self.labels = []
        self.numberItem.hide()

    def addInitialContent(self):

        self.addSubmodelImage()
        si = self.submodelItem
        si._row = 0
        si.setPen(QPen(Qt.NoPen))
        si.setBrush(QBrush(Qt.NoBrush))
        si.itemClassName = "TitleSubmodelPreview"  # Override regular name so we don't set this in any template action

        self.addNewLabel(None, QFont("Arial", 25), self.subModel.getSimpleName())
        self.addNewLabel(Page.margin * 2, None, "1001")
        self.addPartCountLabel(False)
        self.initLayout()

    def initLayout(self):

        self.lockIcon.resetPosition()
        if self.lockIcon.isLocked:
            return  # Don't make any layout changes to locked pages

        pw2, ph2 = Page.PageSize.width() / 2.0, Page.PageSize.height() / 2.0
        pmy = Page.margin.y()
        title = self.labels[0]
        x = pw2 - (self.submodelItem.rect().width() / 2.0)
        y = ph2 - (self.submodelItem.rect().height() / 2.0) + (title.boundingRect().height() / 2.0) + (pmy * 2)
        self.submodelItem.setPos(x, y)

        # TODO: Auto-shrink submodelImage if it is too big

        x = pw2 - (title.boundingRect().width() / 2.0)
        y = self.submodelItem.pos().y() - title.boundingRect().height() - (pmy * 3)
        title.setPos(x, y)

        partCountLabel = self.getPartCountLabel()
        if partCountLabel:
            self.setPartCountLabelPos(partCountLabel)

    def getPartCountLabel(self):
        for label in reversed(self.labels):
            if label.text().count(" pcs.") > 0:
                return label
        return None

    def setPartCountLabelPos(self, label):
        label.setPos(self.rect().bottomLeft())
        label.moveBy(0, -label.boundingRect().height())
        label.moveBy(Page.margin.x(), -Page.margin.y())

    def getAllChildItems(self):
        return [self, self.submodelItem ] + self.labels

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Auto Layout", self.initLayout)
        menu.addAction("Add Label", lambda: self.addNewLabel(event.scenePos(), useUndo = True))
        if self.getPartCountLabel() is None:
            menu.addAction("Add Part Count Label", lambda: self.addPartCountLabel(True))
        menu.addAction("Remove Title Page", lambda: self.subModel.hideTitlePage())
        menu.exec_(event.screenPos())

    def addNewLabel(self, pos = None, font = None, text = "Blank Label", useUndo = False):
        label = EditableTextItem(text, self)
        if pos:
            label.setPos(pos)
        if font:
            label.setFont(font)
        if useUndo:
            self.scene().undoStack.push(AddRemoveLabelCommand(self, label, len(self.labels), True))
        else:
            self.labels.append(label)

    def addPartCountLabel(self, useUndo = False):
        parts = self.subModel.getFullPartList()
        text = "%d pcs." % len(parts)
        self.addNewLabel(None, None, text, useUndo)
        self.setPartCountLabelPos(self.labels[-1])
