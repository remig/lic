"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicTreeModel.py) is part of Lic.

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

import LDrawColors
import LicHelpers

class LicTreeModel(QAbstractItemModel):

    def __init__(self, parent):
        QAbstractItemModel.__init__(self, parent)
        
        self.root = None

    def data(self, index, role = Qt.DisplayRole):
        if role != Qt.DisplayRole or not index.isValid():
            return QVariant()

        item = index.internalPointer()
        return QVariant(item.data(0))

    def rowCount(self, parent):

        if not parent.isValid():
            return self.root.rowCount() if self.root else 0

        item = parent.internalPointer()
        if hasattr(item, "rowCount"):
            return item.rowCount()
        return 0

    def columnCount(self, parent):
        return 1  # Every single item in the tree has exactly 1 column

    def supportedDropActions(self):
        return Qt.MoveAction
    
    def mimeTypes(self):
        return ["application/x-rowlist"]
    
    def mimeData(self, indexes):
        data = ""
        for index in [i for i in indexes if i.isValid()]:
            data += str(index.row())
            parent = index.parent()
            while parent.isValid():
                data += ',' + str(parent.row())
                parent = parent.parent()
            data += '|'
        data = data[:-1]  # Remove trailing '|'
                
        mimeData = QMimeData()
        mimeData.setData(self.mimeTypes()[0], data)
        return mimeData
        
    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.IgnoreAction:
            return True
        
        if not data.hasFormat(self.mimeTypes()[0]) or column > 0:
            return False

        targetItem = parent.internalPointer()  # item that dragged items were dropped on
        #target = self.index(row, column, parent) if row > 0 else parent  # TODO: Handle row argument
        
        dragItems = []
        stringData = str(data.data("application/x-rowlist"))
        
        # Build list of items that were dragged
        for rowList in stringData.split('|'):
            rowList = [int(x) for x in rowList.split(',')]
            rowList.reverse()
            
            parentIndex = QModelIndex()
            for r in rowList:
                parentIndex = self.index(r, 0, parentIndex)
            dragItems.append(parentIndex.internalPointer())

        # At this point, targetItem is an instance of the actual instruction item dropped on,
        # and dragItems is a list of actual instruction items dragged.  Let them sort out if
        # they can be dragged / dropped onto one another.
        if hasattr(targetItem, "acceptDragAndDropList"):
            return targetItem.acceptDragAndDropList(dragItems, row)
        return False
    
    def removeRows(self, row, count, parent = None):
        return False # Needed because otherwise the super gets called, but we handle all in dropMimeData
        
    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled

        item = index.internalPointer()
        if hasattr(item, 'dragDropFlags'):
            return item.dragDropFlags()
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index(self, row, column, parent):
        if row < 0 or column != 0:
            return QModelIndex()
        
        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self.root

        if not hasattr(parentItem, "child"):
            return QModelIndex()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem is self.root:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def headerData(self, section, orientation, role = Qt.DisplayRole):
        return QVariant("Instruction Book")

    def updatePersistentIndices(self):
        for index in self.persistentIndexList():
            item = index.internalPointer()
            if item is None:
                continue  # Happens whenever we delete a persistent index (below)
            newIndex = QModelIndex()
            if item and item.parent():
                newIndex = self.createIndex(item.row(), 0, item)
            self.changePersistentIndex(index, newIndex)

    def deletePersistentItem(self, item):
        if self.persistentIndexList():
            index = self.createIndex(item.row(), 0, item)
            self.changePersistentIndex(index, QModelIndex())

class BaseTreeManager(object):
    
    def parent(self):
        return self.parentItem()

    def row(self):
        if hasattr(self, '_row'):
            return self._row
        return self.parentItem().getChildRow(self)

QGraphicsSimpleTextItem.__bases__ += (BaseTreeManager,)
QGraphicsEllipseItem.__bases__ += (BaseTreeManager,)
QGraphicsRectItem.__bases__ += (BaseTreeManager,)
QGraphicsPixmapItem.__bases__ += (BaseTreeManager,)

class PageTreeManager(BaseTreeManager):

    def parent(self):
        return self.submodel

    def child(self, row):
        if row < 0 or row >= len(self.children):
            return None
        return self.children[row]

    def rowCount(self):
        return len(self.children)

    def setRow(self, row):
        self._row = row
        
    def getChildRow(self, child):
        return self.children.index(child)
    
    def data(self, index):
        return "Page %d" % self._number

    def dragDropFlags(self):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled

class PartListPageTreeManager(BaseTreeManager):

    def child(self, row):
        if row == 0:
            return self.numberItem
        if row == 1:
            return self.pli
        return self.annotations[row - 2]

    def rowCount(self):
        return 2 + len(self.annotations)

    def getChildRow(self, child):
        if child is self.numberItem:
            return 0
        if child is self.pli:
            return 1
        return 2 + self.annotations.index(child)

    def data(self, index):
        return "Part List Page %d" % (self.submodel.partListPages.index(self) + 1)

class TitlePageTreeManager(BaseTreeManager):

    def child(self, row):
        if row == 0:
            return self.submodelItem
        if row <= len(self.labels):
            return self.labels[row - 1]
        return self.annotations[row - len(self.labels) - 1]

    def rowCount(self):
        return 1 + len(self.labels) + len(self.annotations)

    def getChildRow(self, child):
        if child is self.submodelItem:
            return 0
        if child in self.labels:
            return 1 + self.labels.index(child)
        return 1 + len(self.labels) + self.annotations.index(child)

    def data(self, index):
        return "Title Page"

class CalloutArrowTreeManager(BaseTreeManager):

    def child(self, row):
        return self.tipRect if row == 0 else self.baseRect

    def rowCount(self):
        return 2
    
class CalloutTreeManager(BaseTreeManager):
    
    def child(self, row):
        if row == 0:
            return self.arrow
        if row == 1 and self.qtyLabel:
            return self.qtyLabel
        offset = 2 if self.qtyLabel else 1
        return self.steps[row - offset]

    def rowCount(self):
        offset = 1 if self.qtyLabel else 0
        return 1 + len(self.steps) + offset

    def getChildRow(self, child):
        if child is self.arrow:
            return 0
        if child is self.qtyLabel:
            return 1
        if child in self.steps:
            offset = 2 if self.qtyLabel else 1
            return self.steps.index(child) + offset

    def data(self, index):
        return "Callout %d - %d step%s" % (self.number, len(self.steps), 's' if len(self.steps) > 1 else '')

class StepTreeManager(BaseTreeManager):
    
    _showCSI = True

    def getShowCSI(self):
        return StepTreeManager._showCSI or hasattr(self, "postLoadInit")  # Always show CSIs in Templates

    showCSI = property(getShowCSI)
    
    def child(self, row):
        if row == 0 and self.showCSI:
            return self.csi
        if not self.showCSI:
            row += 1
        if row == 1:
            if self.hasPLI():
                return self.pli
            if self.numberItem:
                return self.numberItem
        if row == 2 and self.numberItem and self.hasPLI():
            return self.numberItem

        offset = row - 1 - (1 if self.hasPLI() else 0) - (1 if self.numberItem else 0)
        if offset < len(self.callouts):
                return self.callouts[offset]

        offset -= len(self.callouts)

        if self.rotateIcon:
            if offset == 0:
                return self.rotateIcon
            offset -= 1

        if self.showCSI:
            assert False, "Looking up non-existent row %d in Step %d" % (row, self._number)
        return self.csi.child(offset)

    def rowCount(self):
        rows = (1 if self.hasPLI() else 0) + (1 if self.numberItem else 0) + (1 if self.rotateIcon else 0) + len(self.callouts)
        rows += 1 if self.showCSI else self.csi.rowCount()
        return rows

    def data(self, index):
        return "Step %d" % self._number

    def getChildRow(self, child):
        if child is self.csi:
            return 0
        row = 0
        if self.showCSI:
            row += 1
        if child is self.pli:
            return row
        if self.hasPLI():
            row += 1
        if child is self.numberItem:
            return row
        if self.numberItem:
            row += 1
        if child in self.callouts:
            return self.callouts.index(child) + row
        if child is self.rotateIcon:
            return row + len(self.callouts)
        return row + len(self.callouts) + self.csi._subChildRow(child)  # Showing Parts directly in Step
        
    def dragDropFlags(self):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        
class SubmodelPreviewTreeManager(BaseTreeManager):

    def child(self, row):
        if row != 0:
            return None
        if self.isSubAssembly and self.pli is not None:
            return self.pli
        if self.numberItem:
            return self.numberItem
        return None

    def rowCount(self):
        if self.isSubAssembly and self.pli is not None:
            return 1
        if self.numberItem:
            return 1
        return 0

    def getChildRow(self, child):
        if self.isSubAssembly and self.pli is not None:
            return 0
        if self.numberItem:
            return 0 
        return None

    def data(self, index):
        return "Sub-Assembly" if self.isSubAssembly else "Submodel Preview"

class PLIItemTreeManager(BaseTreeManager):
    
    def child(self, row):
        if row == 0:
            return self.numberItem
        if row == 1 and self.lengthIndicator:
            return self.lengthIndicator
        return None

    def rowCount(self):
        return 2 if self.lengthIndicator else 1

    def row(self):
        return self.parentItem().pliItems.index(self)

    def data(self, index):
        return "%s - %s" % (self.abstractPart.name, LDrawColors.getColorName(self.color))

class PLITreeManager(BaseTreeManager):

    def child(self, row):
        if row < 0 or row >= len(self.pliItems):
            print "ERROR: Looking up invalid row in PLI Tree"
            return None
        return self.pliItems[row] 

    def rowCount(self):
        return len(self.pliItems)

class CSITreeManager(BaseTreeManager):

    showPartGroupings = True

    def _subChildRow(self, child):
        if isinstance(child, PartTreeItemTreeManager):
            return self.parts.index(child)
        if isinstance(child, PartTreeManager):
            return self.getPartList().index(child)
        
    def getChildRow(self, child):
        if self.parentItem().showCSI:
            return self._subChildRow(child)
        return self.parentItem().getChildRow(child)
    
    def child(self, row):
        if CSITreeManager.showPartGroupings:
            return self.parts[row]
        return self.getPartList()[row]

    def rowCount(self):
        if CSITreeManager.showPartGroupings:
            return len(self.parts)
        return self.partCount()

class SubmodelTreeManager(BaseTreeManager):

    def parent(self):
        return self._parent

    def child(self, row):
        for page in self.pages:
            if page._row == row:
                return page
        for submodel in self.submodels:
            if submodel._row == row:
                return submodel
        return None

    def setRow(self, row):
        self._row = row
        
    def rowCount(self):
        return len(self.pages) + len(self.submodels)

    def data(self, index):
        return "Submodel: %s" % self.getSimpleName()

class MainModelTreeManager(SubmodelTreeManager):

    def child(self, row):
        if row == 0:
            return self.template
        if row == 1 and self.hasTitlePage():
            return self.titlePage

        offset = len(self.pages) + len(self.submodels) + 1 + (1 if self.hasTitlePage() else 0)
        if row >= offset:
            return self.partListPages[row - offset]
        return SubmodelTreeManager.child(self, row)

    def rowCount(self):
        return len(self.pages) + len(self.submodels) + len(self.partListPages) + 1 + (1 if self.hasTitlePage() else 0)

    def incrementRows(self, increment):
        for page in self.pages:
            page._row += increment
        for submodel in self.submodels:
            submodel._row += increment
        for page in self.partListPages:
            page._row += increment

class PartTreeItemTreeManager(BaseTreeManager):

    def child(self, row):
        if row < 0 or row >= len(self.parts):
            assert False, "Looking up non-existent row %d in Part Item" % (row)
        return self.parts[row]

    def getChildRow(self, child):
        if CSITreeManager.showPartGroupings:
            return self.parts.index(child)
        return self.parentItem().getChildRow(child)

    def rowCount(self):
        return len(self.parts)

    def parent(self):
        step = self.getStep()
        return self.parentItem() if step.showCSI else step

    def data(self, index):
        if self._dataString:
            return self._dataString
        self._dataString = "%s - x%d" % (self.name, len(self.parts))
        return self._dataString

class PartTreeManager(BaseTreeManager):

    def parent(self):
        if CSITreeManager.showPartGroupings:
            return self.parentItem()
        step = self.getStep()
        return step.csi if step.showCSI else step

    def resetDataString(self):  # Useful for reseting dataString inside a lambda
        self._dataString = None

    def data(self, index):
        if self._dataString:
            return self._dataString

        color = LDrawColors.getColorName(self.color)
        if CSITreeManager.showPartGroupings:
            x, y, z = LicHelpers.GLMatrixToXYZ(self.matrix)
            self._dataString = "%s - (%.1f, %.1f, %.1f)" % (color, x, y, z)
            #self._dataString = "%s - (%s)" % (color, self.getPartBoundingBox())
        else:
            self._dataString = "%s - %s" % (self.abstractPart.name, color)

        return self._dataString
    
    def dragDropFlags(self):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
    
    def rowCount(self):
        return len(self.arrows)

    def child(self, row):
        if row < 0 or row >= len(self.arrows):
            assert False, "Looking up non-existent row %d in Part" % (row)
        return self.arrows[row]

    def getChildRow(self, child):
        assert child in self.arrows, "Looking up non-existent Arrow %s in Part" % (child)
        return self.arrows.index(child)
