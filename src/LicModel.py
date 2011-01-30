"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (Model.py) is part of Lic.

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

import math   # for sqrt
import os     # for output path creation
import time
import Image

#import OpenGL
#OpenGL.ERROR_CHECKING = False
#OpenGL.ERROR_LOGGING = False

from OpenGL import GL
from OpenGL import GLU

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from LicUndoActions import *
from LicTreeModel import *
from LicQtWrapper import *
from LicLayout import *

import LicGLHelpers
import LicL3PWrapper
import LicPovrayWrapper
import LicHelpers
import LicDialogs
import LicPartLengths
import LicImporters
from LicImporters import LDrawImporter

import resources  # Needed for ":/resource" type paths to work
import config     # For user path info

MagicNumber = 0x14768126
FileVersion = 14

NoFlags = QGraphicsItem.GraphicsItemFlags()
NoMoveFlags = QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable
AllFlags = NoMoveFlags | QGraphicsItem.ItemIsMovable

class CalloutArrowEndItem(QGraphicsRectItem):
    itemClassName = "CalloutArrowEndItem"
    
    def __init__(self, parent, width, height, dataText, row):
        QGraphicsRectItem.__init__(self, parent)
        self.setRect(0, 0, width, height)
        self.data = lambda index: dataText
        self._row = row
        self.isAnnotation = True
        
        self.point = QPointF()
        self.mousePoint = self.keyPoint = None
        self.setFlags(AllFlags)
        self.setPen(parent.pen())

    def paint(self, painter, option, widget = None):
        if self.isSelected():
            painter.drawSelectionRect(self.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        QGraphicsItem.mousePressEvent(self, event)
        self.oldPoint = QPointF(self.point)
    
    def mouseMoveEvent(self, event):
        if self.flags() == NoMoveFlags:
            return
        self.parentItem().internalPoints = []
        QGraphicsItem.mouseMoveEvent(self, event)
        self.point -= event.lastScenePos() - event.scenePos()
        self.mousePoint = event.scenePos()
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        QGraphicsItem.mouseReleaseEvent(self, event)
        self.scene().undoStack.push(CalloutArrowMoveCommand(self, self.oldPoint, self.point))

    def moveBy(self, x, y):
        QGraphicsRectItem.moveBy(self, x, y)
        self.keyPoint = True
        self.scene().undoStack.push(CalloutArrowMoveCommand(self, self.point, self.point + QPointF(x, y)))

class CalloutArrow(CalloutArrowTreeManager, QGraphicsRectItem):
    itemClassName = "CalloutArrow"
    
    defaultPen = QPen(Qt.black)
    defaultBrush = QBrush(Qt.white)  # Fill arrow head
    arrowTipLength = 22.0
    arrowTipHeight = 5.0
    ArrowHead = QPolygonF([QPointF(),
                           QPointF(arrowTipLength + 3, -arrowTipHeight),
                           QPointF(arrowTipLength, 0.0),
                           QPointF(arrowTipLength + 3, arrowTipHeight)])
    
    def __init__(self, parent):
        QGraphicsRectItem.__init__(self, parent)
        self.data = lambda index: "Callout Arrow"

        self.setPen(self.defaultPen)
        self.setBrush(self.defaultBrush)
        self.setFlags(NoMoveFlags)
        self.isAnnotation = True
        
        self.tipRect = CalloutArrowEndItem(self, 32, 32, "Arrow Tip", 0)
        self.baseRect = CalloutArrowEndItem(self, 20, 20, "Arrow Base", 1)
        
        # TODO: Add ability to add and drag around arbitrary points to Callout arrow
        self.internalPoints = []

    def initializeEndPoints(self):
        # Find two target rects, both in *LOCAL* coordinates
        callout = self.parentItem()
        csi = callout.parentItem().csi
        calloutRect = self.mapFromItem(callout, callout.rect()).boundingRect()
        csiRect = self.mapFromItem(csi, csi.rect()).boundingRect()
        self.internalPoints = []  # Reset cached internal points

        if csiRect.right() < calloutRect.left():  # Callout right of CSI
            self.tipRect.point = csiRect.topRight() + QPointF(0.0, csiRect.height() / 2.0)
            self.baseRect.point = callout.getArrowBasePoint('left')
            
        elif calloutRect.right() < csiRect.left():  # Callout left of CSI
            self.tipRect.point = csiRect.topLeft() + QPointF(0.0, csiRect.height() / 2.0)
            self.baseRect.point = callout.getArrowBasePoint('right')
            
        elif calloutRect.bottom() < csiRect.top():  # Callout above CSI
            self.tipRect.point = csiRect.topLeft() + QPointF(csiRect.width() / 2.0, 0.0)
            self.baseRect.point = callout.getArrowBasePoint('bottom')

        else:  # Callout below CSI
            self.tipRect.point = csiRect.bottomLeft() + QPointF(csiRect.width() / 2.0, 0.0)
            self.baseRect.point = callout.getArrowBasePoint('top')
            
        self.tipRect.point = self.mapToItem(csi, self.tipRect.point)  # Store tip point in CSI space
        
    def boundPointToRect(self, point, rect, destPoint):
        l, r, t, b = rect.left(), rect.right(), rect.top(), rect.bottom()
        x, y = point

        if x > l and x < r and y > t and y < b:  # cursor inside callout - lock to closest edge
            if min(x - l, r - x) < min(y - t, b - y):
                destPoint.setX(l if (x - l) < (r - x) else r)  # lock to x
            else:
                destPoint.setY(t if (y - t) < (b - y) else b)  # lock to y
        else:
            destPoint.setX(min(max(x, l), r))
            destPoint.setY(min(max(y, t), b))

    def initializePoints(self):

        # Find two target rects, both in *LOCAL* coordinates
        callout = self.parentItem()
        csi = callout.parentItem().csi
        calloutRect = self.mapFromItem(callout, callout.rect()).boundingRect()
        csiRect = self.mapFromItem(csi, csi.rect()).boundingRect()

        tip = self.mapFromItem(csi, self.tipRect.point)
        end = self.baseRect.point

        if self.baseRect.keyPoint:
            self.boundPointToRect(end, calloutRect, end)
            self.baseRect.keyPoint = False
        elif self.baseRect.mousePoint:
            point = self.mapFromScene(self.baseRect.mousePoint)
            self.boundPointToRect(point, calloutRect, end)
            self.baseRect.mousePoint = None

        if csiRect.right() < calloutRect.left():  # Callout right of CSI
            rotation = 0.0
            offset = QPointF(self.arrowTipLength, 0)
            self.tipRect.setPos(tip - QPointF(3, 16))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(18, 10))  # 18 = 2 units overlap past end, 10 = 1/2 height
            
        elif calloutRect.right() < csiRect.left():  # Callout left of CSI
            rotation = 180.0
            offset = QPointF(-self.arrowTipLength, 0)
            self.tipRect.setPos(tip - QPointF(29, 16))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(2, 10))  # 2 units overlap past end, 10 = 1/2 height
            
        elif calloutRect.bottom() < csiRect.top():  # Callout above CSI
            rotation = -90.0
            offset = QPointF(0, -self.arrowTipLength)
            self.tipRect.setPos(tip - QPointF(16, 29))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(10, 2))  # 18 = 2 units overlap past end, 10 = 1/2 height

        else:  # Callout below CSI
            rotation = 90.0
            offset = QPointF(0, self.arrowTipLength)
            self.tipRect.setPos(tip - QPointF(16, 3))    # 3 = nice inset, 10 = 1/2 height
            self.baseRect.setPos(end - QPointF(10, 18))  # 18 = 2 units overlap past end, 10 = 1/2 height

        if rotation == 0 or rotation == 180:
            midX = (tip.x() + offset.x() + end.x()) / 2.0
            mid1 = QPointF(midX, tip.y())
            mid2 = QPointF(midX, end.y())
        else:
            midY = (tip.y() + offset.y() + end.y()) / 2.0
            mid1 = QPointF(tip.x(), midY)
            mid2 = QPointF(end.x(), midY)

        tr = self.tipRect.rect().translated(self.tipRect.pos())
        br = self.baseRect.rect().translated(self.baseRect.pos())
        self.setRect(tr | br)

        self.internalPoints = [tip + offset, mid1, mid2, end]
        self.tipPoint, self.tipRotation = tip, rotation

    def paint(self, painter, option, widget = None):
        
        if not self.internalPoints:
            self.initializePoints()
        
        painter.save()
        painter.setPen(self.pen())
        painter.setBrush(self.brush())

        # Draw step line
        painter.drawPolyline(QPolygonF(self.internalPoints))

        # Draw arrow head
        painter.translate(self.tipPoint)
        painter.rotate(self.tipRotation)
        painter.drawPolygon(self.ArrowHead)
        painter.restore()

        # Draw any selection boxes
        painter.save()
        if self.isSelected():
            painter.drawSelectionRect(self.rect())
        painter.restore()

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add Point", self.addPoint)
        menu.exec_(event.screenPos())
        
    def addPoint(self):
        print "NYI"

class Callout(CalloutTreeManager, GraphicsRoundRectItem):

    itemClassName = "Callout"
    margin = QPointF(15, 15)

    DefaultBorder, RectangleBorder, StepBorder, TightBorder = range(4)
    defaultBorderFit = RectangleBorder

    def __init__(self, parent, number = 1, showStepNumbers = False):
        GraphicsRoundRectItem.__init__(self, parent)

        self.arrow = CalloutArrow(self)
        self.steps = []
        self.mergedCallouts = []
        self.number = number
        self.qtyLabel = None
        self.showStepNumbers = showStepNumbers
        self.borderFit = Callout.DefaultBorder
        self.layout = GridLayout()
        
        self.setPos(0.0, 0.0)
        self.setRect(0.0, 0.0, 30.0, 30.0)
        self.setFlags(NoMoveFlags if self.getPage().isLocked() else AllFlags)

    def getAllChildItems(self):
        items = [self, self.arrow, self.arrow.tipRect, self.arrow.baseRect]
        if self.qtyLabel:
            items.append(self.qtyLabel)
        for step in self.steps:
            items += [step, step.csi]
            if step.numberItem:
                items.append(step.numberItem)
        return items

    def addBlankStep(self, useUndo = True):
        lastNum = self.steps[-1].number + 1 if self.steps else 1
        step = Step(self, lastNum, False, self.showStepNumbers)
        if useUndo:
            self.scene().undoStack.push(AddRemoveStepCommand(step, True))
        else:
            self.insertStep(step)

    def insertStep(self, newStep):
        self.steps.insert(newStep._number - 1, newStep)
        newStep.setParentItem(self)
        self.syncStepNumbers()

    def removeStep(self, step):
        self.scene().removeItem(step)
        self.steps.remove(step)
        self.syncStepNumbers()

    def syncStepNumbers(self):
        for i, step in enumerate(self.steps):
            step.number = i + 1
        if len(self.steps) > 1:
            self.enableStepNumbers()  
        else:
            self.disableStepNumbers()

    def getStepByNumber(self, number):
        for step in self.steps:
            if step.number == number:
                return step
        return None

    def addPart(self, part, step = None):
        newPart = part.duplicate()
        newPart.originalPart = part
        part.calloutPart = newPart
        if step is None:
            step = self.steps[-1]
        step.addPart(newPart)

    def removePart(self, part):
        newPart = part.calloutPart
        newPart.originalPart = None
        part.calloutPart = None
        for step in self.steps:
            step.removePart(newPart)

    def getPartList(self):
        partList = []
        for step in self.steps:
            partList += step.csi.getPartList()
        return partList

    def getOriginalPartList(self):
        return [p.originalPart for p in self.getPartList()]

    def partCount(self):
        partCount = 0
        for step in self.steps:
            partCount += step.csi.partCount()
        return partCount

    def isEmpty(self):
        return len(self.steps) == 0

    def createBlankSubmodel(self):
        parentModel = self.getPage().parent()
        fn = "Callout_To_Submodel_%d" % self.number
        model = Submodel(parentModel, parentModel.instructions, fn)
        #submodelDictionary[fn] = model
        return model

    def setBorderFit(self, fit):
        self.borderFit = fit

    def resetRect(self):

        b = QRectF()
        for step in self.steps:
            b |= step.rect().translated(step.pos())
            
        if self.qtyLabel:
            b |= self.qtyLabel.rect().translated(self.qtyLabel.pos())

        x, y = self.getPage().margin
        self.setRect(b.adjusted(-x, -y, x, y))
        self.normalizePosition([self.arrow])
        self.resetArrow()

    def resetArrow(self):
        self.arrow.internalPoints = []

    def resetStepSet(self, minStepNum, maxStepNum):

        if minStepNum > maxStepNum:
            minStepNum, maxStepNum = maxStepNum, minStepNum

        for step in self.steps:
            if step.number >= minStepNum and step.number <= maxStepNum:
                step.csi.isDirty = True
                step.initLayout()
                step.parentItem().initLayout()

    def getArrowBasePoint(self, side):
        # TODO: arrow base should come out of last step in callout
        r = self.rect()
        if side == 'right':
            return r.topRight() + QPointF(0.0, r.height() / 2.0)
        elif side == 'left':
            return r.topLeft() + QPointF(0.0, r.height() / 2.0)
        elif side == 'bottom':
            return r.bottomLeft() + QPointF(r.width() / 2.0, 0.0)
        else:
            return r.topLeft() + QPointF(r.width() / 2.0, 0.0)

    def getCurrentLayout(self, buf = None):
        if buf is None:
            buf = []
        for item in self.getAllChildItems():
            buf.append([item, item.pos(), item.rect()])
        return buf
    
    def revertToLayout(self, originalLayout):
        for item, pos, rect in originalLayout:
            item.setPos(pos)
            if hasattr(item, 'setRect'):
                item.setRect(rect)
            if hasattr(item, 'internalPoints'):
                item.internalPoints = []

    def initLayout(self):

        if not self.steps:
            self.setRect(0.0, 0.0, 10.0, 10.0)
            return  # Nothing to layout here

        for step in self.steps:
            step.initMinimumLayout()

        self.layout.initLayoutInsideOut(self.steps)

        if self.qtyLabel:
            self.positionQtyLabel()

        self.resetRect()

        self.arrow.initializeEndPoints()

    def initEndPoints(self):
        self.arrow.initializeEndPoints()
        
    def enableStepNumbers(self):
        if not self.showStepNumbers:
            for step in self.steps:
                step.enableNumberItem()
            self.showStepNumbers = True

    def disableStepNumbers(self):
        if self.showStepNumbers:
            for step in self.steps:
                step.disableNumberItem()
            self.showStepNumbers = False

    def addQuantityLabel(self, pos = None, font = None):
        self.qtyLabel = QGraphicsSimpleTextItem("1x", self)
        self.qtyLabel.itemClassName = "Callout Quantity"
        self.qtyLabel.setPos(pos if pos else QPointF(0, 0))
        self.qtyLabel.setFont(font if font else QFont("Arial", 15))
        self.qtyLabel.setFlags(NoMoveFlags if self.getPage().isLocked() else AllFlags)
        self.qtyLabel.data = lambda index: "Quantity Label"
            
    def removeQuantityLabel(self):
        if self.qtyLabel and self.scene():  # Need this check because, in some undo / redo ops, self is not in a scene
            self.scene().removeItem(self.qtyLabel)
            self.qtyLabel.setParentItem(None)
            self.qtyLabel = None

    def getQuantity(self):
        return int(self.qtyLabel.text()[:-1])

    def setQuantity(self, qty):
        if self.qtyLabel is None:
            self.addQuantityLabel()
        self.qtyLabel.setText("%dx" % qty)

    def setMergedQuantity(self):
        qty = len(self.mergedCallouts)
        if qty:
            self.setQuantity(qty + 1)
        else:
            self.removeQuantityLabel()

    def positionQtyLabel(self):
        if self.steps:
            step = self.steps[-1]
            pos = step.rect().translated(step.pos()).bottomRight()
            self.qtyLabel.setPos(pos)
        else:
            self.qtyLabel.setPos(0, 0)

    def mouseMoveEvent(self, event):
        GraphicsRoundRectItem.mouseMoveEvent(self, event)
        self.resetArrow()

    def mergeCallout(self, callout, append = False):
        if not append:
            self.mergedCallouts.append(callout)
        for c in callout.mergedCallouts:
            self.mergeCallout(c)
        if append:
            self.mergedCallouts.append(callout)
        callout.setMergedCallouts([])
        self.setMergedQuantity()

    def removeMergedCallout(self, callout):
        self.mergedCallouts.remove(callout)
        self.setMergedQuantity()

    def setMergedCallouts(self, calloutList):
        self.mergedCallouts = calloutList
        self.setMergedQuantity()

    def calloutMatches(self, callout):
        if self is callout:
            return True
        
        if self.parentItem() != callout.parentItem():
            return False

        c1Parts = self.getPartList()
        c2Parts = callout.getPartList()
        
        if len(c1Parts) != len(c2Parts):
            return False
        
        # Add a temporary equality check to Parts, to make the next step easier
        Part.__eq__ = lambda self, other: self.color == other.color and self.filename == other.filename
        
        # Check if two callout part lists have basically the same parts
        # Two parts are similar if they have the same filename & color (matrix is irrelevant here (__eq__ above))
        for p1 in c1Parts:
            if p1 in c2Parts:
                c2Parts.remove(p1)
            else:
                del(Part.__eq__)
                return False

        del(Part.__eq__)
        return True
    
    def mergeCalloutContextMenu(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Merge similar Callouts", self.mergeCalloutSignal)
        menu.exec_(event.screenPos())

    def mergeCalloutSignal(self):
        selectedCallouts = [x for x in self.scene().selectedItems() if isinstance(x, Callout)]
        selectedCallouts.remove(self)
        self.scene().undoStack.push(MergeCalloutsCommand(self, selectedCallouts, True))

    def contextMenuEvent(self, event):

        # Special case: check if all selected items are Callouts - try merge if so
        selectedItems = self.scene().selectedItems()
        selectedCallouts = [x for x in selectedItems if isinstance(x, Callout)]
        if len(selectedCallouts) == len(selectedItems) and len(selectedCallouts) > 1 and self in selectedCallouts:
            matches = [x for x in selectedCallouts if self.calloutMatches(x)]
            if len(matches) == len(selectedCallouts):
                return self.mergeCalloutContextMenu(event)

        stack = self.scene().undoStack
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add blank Step", self.addBlankStep)
        
        if self.qtyLabel:
            menu.addAction("Hide Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, False)))
        elif self.mergedCallouts:
            menu.addAction("Show Quantity Label", lambda: stack.push(ToggleCalloutQtyCommand(self, True)))

        if self.showStepNumbers:
            menu.addAction("Hide Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, False)))
        else:
            menu.addAction("Show Step numbers", lambda: stack.push(ToggleStepNumbersCommand(self, True)))

        menu.addSeparator()
        
        if self.mergedCallouts:
            menu.addAction("Use next Callout as Base", lambda: stack.push(SwitchToNextCalloutBase(self, True)))
            menu.addSeparator()

        if self.parentItem().getPrevStep():
            menu.addAction("Move to Previous Step", self.moveToPrevStepSignal)
        if self.parentItem().getNextStep():
            menu.addAction("Move to Next Step", self.moveToNextStepSignal)

        menu.addSeparator()
        arrowMenu = menu.addMenu("Border Shape")
        arrowMenu.addAction("Rectangle", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.RectangleBorder)))
        arrowMenu.addAction("Step Fit", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.StepBorder)))
        arrowMenu.addAction("Tight Fit", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.TightBorder)))
        arrowMenu.addAction("Default", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.DefaultBorder)))
        menu.addSeparator()

        if self.partCount() > 0:
            menu.addAction("Convert To Submodel", lambda: stack.push(CalloutToSubmodelCommand(self)))
            menu.addAction("Remove Callout", self.removeCalloutSignal)
        else:
            menu.addAction("Delete empty Callout", lambda: stack.push(AddRemoveCalloutCommand(self, False)))
        menu.exec_(event.screenPos())

    def paint(self, painter, option, widget = None):

        fit = Callout.defaultBorderFit if self.borderFit == Callout.DefaultBorder else self.borderFit
        if fit == Callout.RectangleBorder:
            GraphicsRoundRectItem.paint(self, painter, option, widget)
            return

        painter.setPen(self.pen())
        painter.setBrush(self.brush())

        # Get tight border polygon
        poly = QPolygonF()
        for step in self.steps:
            poly = poly.united(QPolygonF(step.getOrderedCorners(Callout.margin)))

        # Cannot iterate over QPolygonF normally - QPolygonF doesn't implement __iter__
        newPoly = []
        for i in range(len(poly) - 1):  # Skip last (duplicated) point
            newPoly.append(poly[i])

        if fit == Callout.TightBorder:
            path = LicHelpers.polygonToCurvedPath(newPoly, self.cornerRadius * 2.5)
            painter.drawPath(path)
            if self.isSelected():
                painter.drawSelectionRect(self.rect(), self.cornerRadius)
            return

        l = t = 2000
        r = b = -2000
        for pt in newPoly:
            l = min(l, pt.x())
            r = max(r, pt.x())
            t = min(t, pt.y())
            b = max(b, pt.y())

        minWidth = minHeight = 2000
        for step in self.steps:
            rect = step.rect()
            minWidth = min(minWidth, rect.width())
            minHeight = min(minHeight, rect.height())

        for pt in newPoly:
            if abs(pt.x() - l) < minWidth:
                pt.setX(l)
            elif abs(pt.x() - r) < minWidth:
                pt.setX(r)

            if abs(pt.y() - t) < minHeight:
                pt.setY(t)
            elif abs(pt.y() - b) < minHeight:
                pt.setY(b)

        tops = [p for p in newPoly if p.y() == t]
        lefts = [p for p in newPoly if p.x() == l]
        rights = [p for p in newPoly if p.x() == r]
        bottoms = [p for p in newPoly if p.y() == b]

        t1, t2 = min(tops, key = lambda i: i.x()), max(tops, key = lambda i: i.x()) 
        r1, r2 = min(rights, key = lambda i: i.y()), max(rights, key = lambda i: i.y()) 
        b1, b2 = min(bottoms, key = lambda i: i.x()), max(bottoms, key = lambda i: i.x()) 
        l1, l2 = min(lefts, key = lambda i: i.y()), max(lefts, key = lambda i: i.y())

        newPoly = [t1, t2]
        if t2.x() != r:
            newPoly += [QPointF(t2.x(), r1.y()), r1]

        newPoly.append(r2)
        if r2.y() != b:
            newPoly += [QPointF(b2.x(), r2.y()), b2]

        newPoly.append(b1)
        if b1.x() != l:
            newPoly += [QPointF(b1.x(), l2.y()), l2]

        if l1 != t1:
            newPoly.append(l1)
            if l1.y() != t:
                newPoly.append(QPointF(t1.x(), l1.y()))

        path = LicHelpers.polygonToCurvedPath(newPoly, self.cornerRadius * 2.5)
        painter.drawPath(path)

        if self.isSelected():
            painter.drawSelectionRect(self.rect(), self.cornerRadius)

    def removeCalloutSignal(self):
        scene = self.scene()
        stack = scene.undoStack
        
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        stack.beginMacro("Remove Callout")
        
        stack.push(RemovePartsFromCalloutCommand(self, self.getOriginalPartList()))
        stack.push(AddRemoveCalloutCommand(self, False))

        stack.endMacro()
        scene.emit(SIGNAL("layoutChanged()"))

    def moveToPrevStepSignal(self):
        destStep = self.parentItem().getPrevStep()
        self.moveToStepSignal(destStep, "Previous")

    def moveToNextStepSignal(self):
        destStep = self.parentItem().getNextStep()
        self.moveToStepSignal(destStep, "Next")
    
    def moveToStepSignal(self, destStep, text):
        stack = self.scene().undoStack
        
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        stack.beginMacro("Move Callout to %s Step" % text)

        stack.push(AddRemoveCalloutCommand(self, False))
        self.setParentItem(destStep)
        stack.push(AddRemoveCalloutCommand(self, True))
        stack.push(MovePartsToStepCommand(self.getOriginalPartList(), destStep))

        stack.endMacro()
        self.scene().emit(SIGNAL("layoutChanged()"))

class Step(StepTreeManager, QGraphicsRectItem):
    """ A single step in an Instruction book.  Contains one optional PLI and exactly one CSI. """
    itemClassName = "Step"

    def __init__(self, parentPage, number, hasPLI = True, hasNumberItem = True):
        QGraphicsRectItem.__init__(self, parentPage)

        # Children
        self._number = number
        self.numberItem = None
        self.csi = CSI(self)
        self.pli = PLI(self) if hasPLI else None
        self._hasPLI = hasPLI
        self.callouts = []
        self.rotateIcon = None
        
        self.maxRect = None

        self.setPen(QPen(Qt.NoPen))
        self.setPos(self.getPage().margin)

        if hasNumberItem:
            self.enableNumberItem()

        self.setAcceptHoverEvents(True)
        self.setFlags(AllFlags)

    def _setNumber(self, number):
        self._number = number
        if self.numberItem:
            self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(_getNumber, _setNumber)

    def hasPLI(self):
        return self._hasPLI and len(self.pli.pliItems) > 0

    def enablePLI(self):
        self._hasPLI = True
        if self.isVisible():
            self.pli.show()

    def disablePLI(self):
        self._hasPLI = False
        self.pli.hide()

    def isEmpty(self):
        return len(self.csi.parts) == 0

    def addPart(self, part):
        self.csi.addPart(part)
        if self.pli and not part.isSubmodel():  # Visibility here is irrelevant
            self.pli.addPart(part)

    def removePart(self, part):
        self.csi.removePart(part)
        if self.pli:  # Visibility here is irrelevant
            self.pli.removePart(part)
            if self.pli.isEmpty():
                self.pli.setRect(0, 0, 0, 0)
                self.pli.setPos(0, 0)

    def addCallout(self, callout):
        callout.setParentItem(self)
        self.callouts.append(callout)
    
    def removeCallout(self, callout):
        self.scene().removeItem(callout)
        self.callouts.remove(callout)

    def addRotateIcon(self):

        def iconContextMenuEvent(self, event):
            stack = self.scene().undoStack
            menu = QMenu(self.scene().views()[0])
            menu.addAction("Remove", lambda: stack.push(AddRemoveRotateIconCommand(self.parentItem(), False)))
            menu.exec_(event.screenPos())

        if self.rotateIcon is None:
            self.rotateIcon = GraphicsRotateArrowItem(self)
        GraphicsRotateArrowItem.contextMenuEvent = iconContextMenuEvent
        self.rotateIcon.setFlags(AllFlags)

    def removeRotateIcon(self):
        self.scene().removeItem(self.rotateIcon)
        self.rotateIcon = None

    def moveToPage(self, page):
        self.parentItem().steps.remove(self)
        self.parentItem().children.remove(self)
        page.addStep(self)

    def resetRect(self):
        if self.maxRect:
            r = QRectF(0.0, 0.0, max(1, self.maxRect.width()), max(1, self.maxRect.height()))
        else:
            r = QRectF(0.0, 0.0, 1.0, 1.0)

        children = self.childItems()
        if not self.hasPLI() and self.pli in children:
            children.remove(self.pli)

        for child in children:
            r |= child.rect().translated(child.pos())

        self.setRect(r)
        self.normalizePosition()
        if self.isInCallout():
            self.parentItem().resetRect()

    def isInCallout(self):
        return isinstance(self.parentItem(), Callout)

    def getNextStep(self):
        return self.parentItem().getStepByNumber(self.number + 1)

    def getPrevStep(self):
        return self.parentItem().getStepByNumber(self.number - 1)

    def enableNumberItem(self):
        if self.numberItem is None:
            self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setText(str(self._number))
        self.numberItem.itemClassName = "Step Number"
        self.numberItem.setPos(0, 0)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.setFlags(AllFlags)
        self.numberItem.data = lambda index: "Step Number Label"

    def disableNumberItem(self):
        self.scene().removeItem(self.numberItem)
        self.numberItem = None

    def exportToLDrawFile(self, fh):
        fh.write(LDrawImporter.createStepLine())

    def initMinimumLayout(self):

        if self.hasPLI(): # Do not use on a step with PLI
            return

        if self.csi.isDirty or self.csi.rect().width() <= 0.0 or self.csi.rect().height() <= 0.0:
            self.csi.resetPixmap()

        if self.numberItem:
            self.numberItem.setPos(0.0, 0.0)
            self.csi.setPos(self.numberItem.rect().bottomRight())
        else:
            self.csi.setPos(0.0, 0.0)

        self.setPos(self.getPage().margin)
        self.maxRect = QRectF()
        self.resetRect()
        self.maxRect = self.rect()

    def checkForLayoutOverlaps(self):
        if self.csi.pos().y() < self.pli.rect().bottom() and self.csi.pos().x() < self.pli.rect().right():
            return True
        if self.csi.pos().y() < self.pli.rect().top():
            return True
        if self.csi.rect().width() > self.rect().width():
            return True
        if self.pli.rect().width() > self.rect().width():
            return True
        if (self.csi.pos().y() + self.csi.rect().height()) > self.rect().height():
            return True
        page = self.getPage()
        topLeft = self.mapToItem(page, self.rect().topLeft())
        botRight = self.mapToItem(page, self.rect().bottomRight())
        if topLeft.x() < 0 or topLeft.y() < 0:
            return True
        if botRight.x() > page.rect().width() or botRight.y() > page.rect().height():
            return True
        return False

    def initLayout(self, destRect = None):

        if self.getPage().isLocked():
            return  # Don't layout stuff on locked pages
         
        if destRect is None:
            destRect = self.maxRect
        else:
            self.maxRect = destRect

        self.setPos(destRect.topLeft())
        self.setRect(0, 0, destRect.width(), destRect.height())
        
        if self.hasPLI():
            self.pli.initLayout()  # Position PLI

        # Position Step number label beneath the PLI
        if self.numberItem:
            self.numberItem.setPos(0, 0)
            pliOffset = self.pli.rect().height() if self.hasPLI() else 0.0
            self.numberItem.moveBy(0, pliOffset + self.getPage().margin.y())

        self.positionInternalBits()
        self.resetRect()

    def positionInternalBits(self):

        r = self.rect()
        
        if self.hasPLI():
            r.setTop(self.pli.rect().height())

        csiWidth = self.csi.rect().width()
        csiHeight = self.csi.rect().height()
        if self.csi.isDirty or csiWidth <= 0.0 or csiHeight <= 0.0:
            self.csi.resetPixmap()
            csiWidth = self.csi.rect().width()
            csiHeight = self.csi.rect().height()

        if not self.callouts:
            x = (r.width() - csiWidth) / 2.0
            y = (r.height() - csiHeight) / 2.0
            self.csi.setPos(x, r.top() + y)
            self.positionRotateIcon()
            return

        for callout in self.callouts:
            callout.initLayout()

        GridLayout.initCrossLayout(r, [self.csi] + self.callouts)

        self.positionRotateIcon()
        for callout in self.callouts:
            callout.initEndPoints()

    def positionRotateIcon(self):
        if self.rotateIcon:
            margin = self.getPage().margin
            x = self.csi.pos().x() - self.rotateIcon.rect().width() - margin.x()
            y = self.csi.pos().y() - self.rotateIcon.rect().height() - margin.y()
            if self.hasPLI() and y < self.pli.rect().bottom():
                y = self.csi.pos().y()  # Not enough space to place above CSI, so put beside
                x -= margin.x()
            self.rotateIcon.setPos(x, y)

    def glItemIterator(self):
        yield self.csi
        if self.pli and self.hasPLI():
            for pliItem in self.pli.pliItems:
                yield pliItem
        for callout in self.callouts:
            for step in callout.steps:
                for glItem in step.glItemIterator():
                    yield glItem

    def acceptDragAndDropList(self, dragItems, row):

        parts = [p for p in dragItems if isinstance(p, Part)]
        if not parts:
            return False
        self.scene().undoStack.push(MovePartsToStepCommand(parts, self))
        return True

    def _setEdge(self, edge, cursor):
        self.edge = edge
        if cursor is None:
            self.unsetCursor()
            self.setHandlesChildEvents(False)
        else:
            self.setCursor(cursor)
            self.setHandlesChildEvents(True)

    def hoverMoveEvent(self, event):
        if not self.isSelected():
            return

        x, y = event.pos()
        inset = 5

        if x < inset:
            if y < inset:
                self._setEdge("topLeft", Qt.SizeFDiagCursor)
            elif y > self.rect().height() - inset:
                self._setEdge("bottomLeft", Qt.SizeBDiagCursor)
            else:
                self._setEdge("left", Qt.SplitHCursor)
        elif x > self.rect().width() - inset:
            if y < inset:
                self._setEdge("topRight", Qt.SizeBDiagCursor)
            elif y > self.rect().height() - inset:
                self._setEdge("bottomRight", Qt.SizeFDiagCursor)
            else:
                self._setEdge("right", Qt.SplitHCursor)
        elif y < inset:
            self._setEdge("top", Qt.SplitVCursor)
        elif y > self.rect().height() - inset:
            self._setEdge("bottom", Qt.SplitVCursor)
        else:
            self._setEdge(None, None)

    def hoverLeaveEvent(self, event):
        self._setEdge(None, None)

    def mousePressEvent(self, event):
        if self.hasCursor():  # This is a resize move event
            self.oldRect = self.rect().translated(self.pos())
        else:
            QGraphicsRectItem.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if self.hasCursor():  # This is a resize move event
            rect = self.rect().translated(self.pos())
            x, y = event.pos()
            w, h = x - rect.width(), y - rect.height()

            if self.edge == "left":
                self.newRect = rect.adjusted(x, 0, 0, 0)
            elif self.edge == "top":
                self.newRect = rect.adjusted(0, y, 0, 0)
            elif self.edge == "right":
                self.newRect = rect.adjusted(0, 0, w, 0)
            elif self.edge == "bottom":
                self.newRect = rect.adjusted(0, 0, 0, h)
            elif self.edge == "topLeft":
                self.newRect = rect.adjusted(x, y, 0, 0)
            elif self.edge == "topRight":
                self.newRect = rect.adjusted(0, y, w, 0)
            elif self.edge == "bottomLeft":
                self.newRect = rect.adjusted(x, 0, 0, h)
            elif self.edge == "bottomRight":
                self.newRect = rect.adjusted(0, 0, w, h)
            self.initLayout(self.newRect)
        else:
            QGraphicsRectItem.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if self.hasCursor():  # This is a resize move event
            self.scene().undoStack.push(ResizeCommand(self, self.oldRect, self.newRect))
        else:
            QGraphicsRectItem.mouseReleaseEvent(self, event)

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        undo = self.scene().undoStack
        parent = self.parentItem()

        selList = self.scene().selectedItems()
        if len(selList) > 1 and all(isinstance(item, Step) for item in selList):
            menu.addAction("Merge selected Steps", self.mergeAllStepsSignal)
            menu.addSeparator()

        if not self.isInCallout():
            if parent.prevPage() and parent.steps[0] is self:
                menu.addAction("Move to &Previous Page", lambda: self.moveToPrevOrNextPage(True))
            if parent.nextPage() and parent.steps[-1] is self:
                menu.addAction("Move to &Next Page", lambda: self.moveToPrevOrNextPage(False))

        menu.addSeparator()
        if self.getPrevStep():
            menu.addAction("Merge with Previous Step", lambda: self.mergeWithStepSignal(self.getPrevStep()))
            menu.addAction("Swap with Previous Step", lambda: self.swapWithStepSignal(self.getPrevStep()))
        if self.getNextStep():
            menu.addAction("Merge with Next Step", lambda: self.mergeWithStepSignal(self.getNextStep()))
            menu.addAction("Swap with Next Step", lambda: self.swapWithStepSignal(self.getNextStep()))

        menu.addSeparator()
        menu.addAction("Add blank Callout", self.addBlankCalloutSignal)
        menu.addAction("Prepend blank Step", lambda: self.addBlankStepSignal(self._number))
        menu.addAction("Append blank Step", lambda: self.addBlankStepSignal(self._number + 1))

        if self.rotateIcon is None:
            menu.addSeparator()
            menu.addAction("Add Rotate Icon", lambda: undo.push(AddRemoveRotateIconCommand(self, True)))

        if not self.csi.parts:
            menu.addAction("&Delete Step", lambda: undo.push(AddRemoveStepCommand(self, False)))

        menu.exec_(event.screenPos())

    def addBlankStepSignal(self, number):
        step = Step(self.parentItem(), number, not self.isInCallout())
        action = AddRemoveStepCommand(step, True)
        self.scene().undoStack.push(action)

    def addBlankCalloutSignal(self, useUndo = True, useSelection = True):
        number = self.callouts[-1].number + 1 if self.callouts else 1
        callout = Callout(self, number)
        callout.addBlankStep(False)
        if useUndo:
            self.scene().undoStack.push(AddRemoveCalloutCommand(callout, True))
        else:
            self.addCallout(callout)
        if useSelection:
            self.scene().fullItemSelectionUpdate(callout)
        return callout

    def moveToPrevOrNextPage(self, toPrev = True):
        scene = self.scene()
        currentPage = self.parentItem()
        targetPage = currentPage.prevPage() if toPrev else currentPage.nextPage()
        stepSet = []
        for step in [s for s in scene.selectedItems() if isinstance(s, Step)]:
            stepSet.append((step, currentPage, targetPage))
        scene.undoStack.push(MoveStepToPageCommand(stepSet))
        self.scene().fullItemSelectionUpdate(currentPage)

    def mergeWithStepSignal(self, step):
        parent = self.parentItem()
        scene = self.scene()
        stack = scene.undoStack

        stack.beginMacro("Merge Steps")
        stack.push(MovePartsToStepCommand(self.csi.getPartList(), step))
        stack.push(AddRemoveStepCommand(self, False))

        if parent.isEmpty():
            if self.isInCallout():
                stack.push(AddRemoveCalloutCommand(parent, False))
            else:
                stack.push(AddRemovePageCommand(scene, parent, False))
        stack.endMacro()

    def mergeAllStepsSignal(self):
        scene = self.scene()
        scene.undoStack.beginMacro("merge multiple Steps")
        selList = scene.selectedItems()
        assert len(selList) > 1 and self in selList and all(isinstance(item, Step) for item in selList), "Bad selection list passed to mergeAllSteps" 
        selList.remove(self)
        for step in selList:
            step.mergeWithStepSignal(self)
        scene.undoStack.endMacro()

    def swapWithStepSignal(self, step):
        self.scene().undoStack.push(SwapStepsCommand(self, step))

class RotateScaleSignalItem(object):

    def rotateSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.RotationDialog(parentWidget, self.rotation)
        parentWidget.connect(dialog, SIGNAL("changeRotation"), self.changeRotation)
        parentWidget.connect(dialog, SIGNAL("acceptRotation"), self.acceptRotation)
        dialog.exec_()

    def changeRotation(self, rotation):
        self.rotation = list(rotation)
        self.resetPixmap()

    def acceptRotation(self, oldRotation):
        action = RotateItemCommand(self, oldRotation, self.rotation)
        self.scene().undoStack.push(action)

    def scaleSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.ScaleDlg(parentWidget, self.scaling)
        parentWidget.connect(dialog, SIGNAL("changeScale"), self.changeScale)
        parentWidget.connect(dialog, SIGNAL("acceptScale"), self.acceptScale)
        dialog.exec_()

    def changeScale(self, newScale):
        self.scaling = newScale
        self.resetPixmap()
        
    def acceptScale(self, oldScale):
        action = ScaleItemCommand(self, oldScale, self.scaling)
        self.scene().undoStack.push(action)

class SubmodelPreview(SubmodelPreviewTreeManager, GraphicsRoundRectItem, RotateScaleSignalItem):
    itemClassName = "SubmodelPreview"

    defaultScale = 1.0
    defaultRotation = [20.0, 45.0, 0.0]
    fixedSize = True

    def __init__(self, parent, abstractPart):
        GraphicsRoundRectItem.__init__(self, parent)
        self.rotation = [0.0, 0.0, 0.0]
        self.scaling = 1.0
        self.setFlags(AllFlags)
        self.pli = None             # TODO: Need to support both sub-model pic and sub-assembly PLI
        self.isSubAssembly = False  # TODO: Need to include main step number under this sub-assembly drawing
        self.numberItem = None
        self.quantity = 0

        self.setAbstractPart(abstractPart)

    def resetPixmap(self):
        glContext = self.getPage().instructions.glContext
        self.abstractPart.resetPixmap(glContext, self.rotation, self.scaling)
        self.abstractPart.center /= self.scaling
        self.resetRect()
        
    def resetRect(self):
        if self.isSubAssembly:
            self.setPos(self.mapToParent(self.pli.pos()))
            self.pli.setPos(0, 0)
            self.setRect(self.pli.rect())
        else:
            part = self.abstractPart
            self.setRect(0, 0, part.width + (PLI.margin.x() * 2), part.height + (PLI.margin.y() * 2))
            if self.numberItem:
                numRect = self.numberItem.rect().translated(self.numberItem.pos())
                numRect.adjust(0, 0, PLI.margin.x(), PLI.margin.y())
                self.setRect(self.rect() | numRect)
    
    def setAbstractPart(self, part):
        self.abstractPart = part.duplicate()
        self.resetRect()

    def paintGL(self, f = 1.0):
        dx = self.pos().x() + PLI.margin.x() + (self.abstractPart.width / 2.0)
        dy = -self.getPage().PageSize.height() + self.pos().y() + PLI.margin.y() + (self.abstractPart.height / 2.0)
        self.abstractPart.paintGL(dx * f, dy * f, self.rotation, self.scaling * f)

    def initLayout(self, destRect = None):
        if destRect:
            self.setPos(destRect.topLeft())
        self.resetRect()
        if self.numberItem:
            self.numberItem.setPos(self.abstractPart.width, self.abstractPart.height)
            self.numberItem.moveBy(PLI.margin.x(), PLI.margin.y())
            self.resetRect()

    def convertToSubAssembly(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.isSubAssembly = True
        self.setRect(self.parentItem().rect().adjusted(0, 0, -self.getPage().margin.x() * 2, -self.getPage().margin.y() * 2))
        self.setPen(QPen(Qt.transparent))
        self.setBrush(QBrush(Qt.transparent))
        self.pli = PLI(self)
        for part in self.abstractPart.parts:
            self.pli.addPart(part)
        self.pli.resetPixmap()
        self.setRect(self.pli.rect())
        self.parentItem().initLayout()
        self.scene().emit(SIGNAL("layoutChanged()"))

    def convertToSubmodel(self):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        self.isSubAssembly = False
        self.scene().removeItem(self.pli)
        self.pli.setParentItem(None)
        self.pli = None
        self.resetPixmap()
        self.setPen(GraphicsRoundRectItem.defaultPen)
        self.setBrush(GraphicsRoundRectItem.defaultBrush)
        self.parentItem().initLayout()
        self.scene().emit(SIGNAL("layoutChanged()"))

    def addQuantityLabel(self, qty):
        self.numberItem = QGraphicsSimpleTextItem("0x", self)
        self.numberItem.itemClassName = "SubmodelItem Quantity"
        self.numberItem._row = 0
        self.numberItem.setFont(QFont("Arial", 12))
        self.numberItem.setFlags(AllFlags)
        self.quantity = qty
        self.numberItem.setText("%dx" % qty)
        self.numberItem.data = lambda index: "Qty. Label (%dx)" % qty

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Rotate Submodel Image", self.rotateSignal)
        menu.addAction("Scale Submodel Image", self.scaleSignal)
        menu.exec_(event.screenPos())
    
class PLIItem(PLIItemTreeManager, QGraphicsRectItem, RotateScaleSignalItem):
    """ Represents one part inside a PLI along with its quantity label. """
    itemClassName = "PLIItem"

    def __init__(self, parent, abstractPart, color, quantity = 0):
        QGraphicsRectItem.__init__(self, parent)

        self.abstractPart = abstractPart
        self.quantity = 0
        self.color = color

        self.setPen(QPen(Qt.NoPen)) # QPen(Qt.black)
        self.setFlags(AllFlags)

        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem("0x", self)
        self.numberItem.itemClassName = "PLIItem Quantity"
        self.numberItem._row = 0
        self.numberItem.setFont(QFont("Arial", 10))
        self.numberItem.setFlags(AllFlags)
        self.setQuantity(quantity)

        # Initialize the circular length indicator, if there should be one on this part
        self.lengthIndicator = None
        name = self.abstractPart.filename.lower()
        length = LicPartLengths.partLengths.get(name)
        if length:
            self.lengthIndicator = GraphicsCircleLabelItem(self, str(length))
            self.lengthIndicator.setFlags(AllFlags)

    def __getRotation(self):
        return self.abstractPart.pliRotation
    
    def __setRotation(self, rotation):
        self.abstractPart.pliRotation = rotation
        
    rotation = property(__getRotation, __setRotation)

    def __getScaling(self):
        return self.abstractPart.pliScale
    
    def __setScaling(self, scaling):
        self.abstractPart.pliScale = scaling
        
    scaling = property(__getScaling, __setScaling)

    def setQuantity(self, quantity):
        self.quantity = quantity
        self.numberItem.setText("%dx" % self.quantity)
        self.numberItem.data = lambda index: "Qty. Label (%dx)" % self.quantity
        
    def addPart(self):
        self.setQuantity(self.quantity + 1)

    def removePart(self):
        self.quantity -= 1
        self.numberItem.setText("%dx" % self.quantity)
        self.numberItem.data = lambda index: "Qty. Label (%dx)" % self.quantity

    def resetRect(self):
        glRect = QRectF(0.0, 0.0, self.abstractPart.width, self.abstractPart.height)
        self.setRect(self.childrenBoundingRect() | glRect)
        #self.normalizePosition()  # Don't want to normalize PLIItem positions, otherwise we end up with GLItem in top left always.
        self.parentItem().resetRect()

    def initLayout(self):

        part = self.abstractPart

        # Put label directly below part, left sides aligned
        # Label's implicit lower top right corner (from qty 'x'), means no padding needed
        self.numberItem.setPos(0.0, part.height)  
       
        lblWidth = self.numberItem.rect().width()
        lblHeight = self.numberItem.rect().height()
        if part.leftInset > lblWidth:
            if part.bottomInset > lblHeight:
                self.numberItem.moveBy(0, -lblHeight)  # Label fits entirely under part: bottom left corners now match
            else:
                li = part.leftInset   # Move label up until top right corner intersects bottom left inset line
                slope = part.bottomInset / float(li)
                dy = slope * (li - lblWidth)
                self.numberItem.moveBy(0, -dy)

        if self.lengthIndicator:
            self.lengthIndicator.setPos(self.abstractPart.width, -self.lengthIndicator.rect().height())

        glRect = QRectF(0.0, 0.0, self.abstractPart.width, self.abstractPart.height)
        self.setRect(self.childrenBoundingRect() | glRect)

    def paintGL(self, f = 1.0):
        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.abstractPart.width / 2.0)
        dy = -self.getPage().PageSize.height() + pos.y() + (self.abstractPart.height / 2.0)
        self.abstractPart.paintGL(dx * f, dy * f, scaling = f, color = self.color)

    """
    def paint(self, painter, option, widget = None):
        QGraphicsRectItem.paint(self, painter, option, widget)
        painter.drawRect(self.boundingRect())
    """

    def resetPixmap(self):
        glContext = self.getPage().instructions.glContext
        self.abstractPart.resetPixmap(glContext)
        self.parentItem().initLayout()
        
    def createPng(self):

        part = self.abstractPart
        if part.isSubmodel:
            self.pngImage = part.pngImage
            return

        fn = part.filename
        datFile = os.path.join(config.LDrawPath, 'PARTS', fn)
        if not os.path.isfile(datFile):
            datFile = os.path.join(config.LDrawPath, 'P', fn)
            if not os.path.isfile(datFile):
                datFile = os.path.join(config.LDrawPath, 'MODELS', fn)
                if not os.path.isfile(datFile):
                    datFile = os.path.join(config.datCachePath(), fn)
                    if not os.path.isfile(datFile):
                        print " *** Error: could not find dat file for part %s" % fn
                        return

        povFile = LicL3PWrapper.createPovFromDat(datFile, self.color)
        pngFile = LicPovrayWrapper.createPngFromPov(povFile, part.width, part.height, part.center, PLI.defaultScale, PLI.defaultRotation)
        self.pngImage = QImage(pngFile)

    def contextMenuEvent(self, event):
        
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Rotate PLI Item", self.rotateSignal)
        menu.addAction("Scale PLI Item", self.scaleSignal)
        menu.exec_(event.screenPos())

class PLI(PLITreeManager, GraphicsRoundRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """
    itemClassName = "PLI"

    defaultScale = 1.0
    defaultRotation = [20.0, -45.0, 0.0]
    margin = QPointF(15, 15)

    def __init__(self, parent):
        GraphicsRoundRectItem.__init__(self, parent)
        self.pliItems = []  # {(part filename, color): PLIItem instance}
        self.data = lambda index: "PLI"
        self.setPos(0.0, 0.0)
        self.setFlags(AllFlags)

    def isEmpty(self):
        return len(self.pliItems) == 0

    def resetRect(self):
        rect = self.childrenBoundingRect().adjusted(-PLI.margin.x(), -PLI.margin.y(), PLI.margin.x(), PLI.margin.y())
        self.setRect(rect)
        self.normalizePosition()
        self.parentItem().resetRect()
        
    def addPart(self, part):

        for pliItem in self.pliItems:
            if pliItem.color == part.color and pliItem.abstractPart.filename == part.abstractPart.filename:
                return pliItem.addPart()

        # If we're here, did not find an existing PLI, so create a new one
        pliItem = PLIItem(self, part.abstractPart, part.color)
        pliItem.addPart()
        self.pliItems.append(pliItem)
        
    def removePart(self, part):
        
        for pliItem in self.pliItems:
            if pliItem.color == part.color and pliItem.abstractPart.filename == part.abstractPart.filename:
                pliItem.removePart()
                break

        for pliItem in [i for i in self.pliItems if i.quantity <= 0]: # Check for & delete empty PLIItems
            self.scene().removeItem(pliItem)
            self.pliItems.remove(pliItem)
            pliItem.setParentItem(None)

    def removeAllParts(self):
        scene = self.scene()
        for pliItem in self.pliItems:
            scene.removeItem(pliItem.numberItem)
            scene.removeItem(pliItem)
        self.pliItems = []

    def changePartColor(self, part, oldColor, newColor):
        part.color = oldColor
        self.removePart(part)
        part.color = newColor
        self.addPart(part)
        self.initLayout()
    
    def resetPixmap(self):
        
        glContext = self.getPage().instructions.glContext
        for part in set([item.abstractPart for item in self.pliItems]):
            part.resetPixmap(glContext)
        self.initLayout()
    
    def initLayout(self):
        """
        Allocate space for all parts in this PLI, and choose a decent layout.
        This is the initial algorithm used to layout a PLI.
        """

        self.setPos(0.0, 0.0)

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            self.setRect(QRectF())
            return

        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
        for item in self.pliItems:
            item.initLayout()

        # Sort list of parts to lay out first by color (in reverse order), then by width (narrowest first), then remove tallest part, to be added first
        partList = list(self.pliItems)
        partList.sort(key = lambda i: i.color.sortKey(), reverse = True)  # Sort by color, reversed 
        partList.sort(key = lambda i: (i.rect().width(), i.rect().height()))  # Sort by width (then height, for ties)
        tallestPart = max(reversed(partList), key = lambda x: x.abstractPart.height)  # reverse list so we choose last part if two+ parts equally tall
        partList.remove(tallestPart)
        partList.append(tallestPart)

        """
        # Try rectangle packer instead
        from RectanglePacker import CygonRectanglePacker

        mx = self.margin.x()
        mx2 = mx * 2.0
        my = self.margin.y()
        my2 = my * 2.0
        rMaxWidth = self.parentItem().rect().width() / 2.0
        rMaxHeight = (tallestPart.rect().height() * 1.5) + my2
        rectanglePacker = CygonRectanglePacker(rMaxWidth, rMaxHeight)
        
        for pliItem in partList:
            point = rectanglePacker.Pack(pliItem.rect().width() + mx, pliItem.rect().height() + my)
            if point:
                pliItem.setPos(point.x + self.margin.x(), point.y + self.margin.y())
            else:
                print "PLIItem doesn't fit!!!  DOOM!!!"
                
        rect = self.childrenBoundingRect().adjusted(-PLI.margin.x(), -PLI.margin.y(), PLI.margin.x(), PLI.margin.y())
        self.setRect(rect)
        
        return
        """
    
        # This rect will be enlarged as needed
        pliBox = QRectF(0, 0, -1, -1)

        overallX = maxX = xMargin = PLI.margin.x()
        overallY = maxY = yMargin = PLI.margin.y()

        prevItem = None
        remainingHeight = 0.0
        
        while partList:
            
            item = None
            
            if prevItem:
                remainingHeight = pliBox.height() - prevItem.pos().y() - prevItem.rect().height() - yMargin - yMargin 
                
            # Check if we can fit any parts under the last part without extending the PLI box vertically
            if remainingHeight > 0:
                for pliItem in partList:
                    if pliItem.rect().height() < remainingHeight:
                        item = pliItem
                        break

            # Found an item that fits below the previous - put it there
            if item:
                partList.remove(pliItem)
                overallX = prevItem.pos().x()
                newWidth = prevItem.rect().width()
                y = prevItem.pos().y() + prevItem.rect().height() + yMargin
                item.setPos(overallX, y)
            
            # Use last item in list (widest)
            if not item:
                item = partList.pop()
                item.setPos(overallX, overallY)
                newWidth = item.rect().width()

            # Increase overall x, to make PLI box big enough for this part
            overallX += newWidth + xMargin
 
            # If this part pushes this PLI beyond the step's right edge, wrap to new line           
            if overallX > self.parentItem().rect().width():
                overallX = xMargin
                overallY = pliBox.height()
                item.setPos(overallX, overallY)
                overallX += newWidth + xMargin
            
            maxX = max(maxX, overallX)
            maxY = max(maxY, overallY + item.rect().height() + yMargin)
            pliBox.setWidth(maxX)
            pliBox.setHeight(maxY)
            self.setRect(pliBox)
            prevItem = item
            
        self.pliItems.sort(key = lambda i: i.pos().x())  # Sort pliITems so tree Model list roughly matches item paint order (left to right)

        # Need to nudge any PLIItems that have length indicators down, to accommodate placing indicators above part        
        for item in self.pliItems:
            if item.lengthIndicator:
                item.moveBy(0, item.lengthIndicator.rect().height())

class CSI(CSITreeManager, QGraphicsRectItem, RotateScaleSignalItem):
    """ Construction Step Image.  Includes border and positional info. """
    itemClassName = "CSI"

    defaultScale = 1.0
    defaultRotation = [20.0, 45.0, 0.0]
    highlightNewParts = False

    def __init__(self, step):
        QGraphicsRectItem.__init__(self, step)

        self.center = QPointF()
        self.glDispID = LicGLHelpers.UNINIT_GL_DISPID
        self.setFlags(AllFlags)
        self.setPen(QPen(Qt.NoPen))

        self.rotation = [0.0, 0.0, 0.0]
        self.scaling = 1.0

        self.parts = []
        self.isDirty = True
        self.nextCSIIsDirty = False

    def getPartList(self):
        partList = []
        for partItem in self.parts:
            partList += partItem.parts
        return partList
    
    def partCount(self):
        partCount = 0
        for partItem in self.parts:
            partCount += len(partItem.parts)
        return partCount
    
    def data(self, index):
        return "CSI - %d parts" % self.partCount()

    def paintGL(self, f = 1.0):
        """ 
        Assumes a current GL context.  Assumes that context has been transformed so the
        view runs from (0,0) to page width & height with (0,0) in the bottom left corner.
        """

        if self.isDirty:
            self.resetPixmap()
            if self.nextCSIIsDirty:
                nextStep = self.parentItem().getNextStep()
                if nextStep:
                    nextStep.csi.isDirty = nextStep.csi.nextCSIIsDirty = True
                self.nextCSIIsDirty = False

        LicGLHelpers.pushAllGLMatrices()

        pos = self.mapToItem(self.getPage(), self.mapFromParent(self.pos()))
        dx = pos.x() + (self.rect().width() / 2.0) + self.center.x()
        dy = -self.getPage().PageSize.height() + pos.y() + (self.rect().height() / 2.0) + self.center.y()
        LicGLHelpers.rotateToView(CSI.defaultRotation, CSI.defaultScale * self.scaling * f, dx * f, dy * f, 0.0)
        LicGLHelpers.rotateView(*self.rotation)

        GL.glCallList(self.glDispID)
        LicGLHelpers.popAllGLMatrices()

    def addPart(self, part):
        for p in self.parts:
            if p.name == part.abstractPart.name:
                p.addPart(part)
                return
            
        p = PartTreeItem(self, part.abstractPart.name)
        p.addPart(part)
        self.parts.append(p)
        self.parts.sort(key = lambda partItem: partItem.name)

    def removePart(self, part):

        for p in self.parts:
            if part in p.parts:
                p.removePart(part)
                break

        for p in [x for x in self.parts if not x.parts]:  # Delete empty part item groups
            self.scene().removeItem(p)
            self.parts.remove(p)
            p.setParentItem(None)

    def containsSubmodel(self):
        return any(part.isSubmodel() for part in self.getPartList())

    def __callPreviousGLDisplayLists(self, isCurrent = False):

        # Call all previous step's CSI display list
        prevStep = self.parentItem().getPrevStep()
        if prevStep:
            #if prevStep.csi.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            prevStep.csi.__callPreviousGLDisplayLists(False)
            #else:
            #    GL.glCallList(prevStep.csi.glDispID)

        # Draw all the parts in this CSI
        for partItem in self.parts:
            for part in partItem.parts:
                part.callGLDisplayList(isCurrent)

    def createGLDisplayList(self):
        """
        Create a display list that includes all previous CSIs plus this one,
        for a single display list giving a full model rendering up to this step.
        """

        if self.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            self.glDispID = GL.glGenLists(1)
        GL.glNewList(self.glDispID, GL.GL_COMPILE)
        #LicGLHelpers.drawCoordLines()
        self.__callPreviousGLDisplayLists(True)
        GL.glEndList()

    def resetPixmap(self):

        if not self.parts:
            self.center = QPointF()
            self.setRect(QRectF())
            self.glDispID = LicGLHelpers.UNINIT_GL_DISPID
            return  # No parts = reset pixmap

        # Temporarily enlarge CSI, in case recent changes pushed image out of existing bounds.
        oldWidth, oldHeight = self.rect().width(), self.rect().height()
        self.setRect(0.0, 0.0, self.getPage().PageSize.width(), self.getPage().PageSize.height())

        glContext = self.getPage().instructions.glContext
        glContext.makeCurrent()
        self.createGLDisplayList()
        sizes = [512, 1024, 2048]

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, LicGLHelpers.getGLFormat(), glContext)
            pBuffer.makeCurrent()

            if self.initSize(size, pBuffer):
                break

        # Move CSI so its new center matches its old
        dx = (self.rect().width() - oldWidth) / 2.0
        dy = (self.rect().height() - oldHeight) / 2.0
        self.moveBy(-dx, -dy)
        self.isDirty = False

        glContext.makeCurrent()

    def initSize(self, size, pBuffer):
        """
        Initialize this CSI's display width, height and center point. To do
        this, draw this CSI to the already initialized GL Frame Buffer Object.
        These dimensions are required to properly lay out PLIs and CSIs.
        Note that an appropriate FBO *must* be initialized before calling initSize.

        Parameters:
            size: Width & height of FBO to render to, in pixels.  Note that FBO is assumed square.

        Returns:
            True if CSI rendered successfully.
            False if the CSI has been rendered partially or wholly out of frame.
        """

        if self.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            print "ERROR: Trying to init a CSI size that has no display list"
            return False
        
        pageNumber, stepNumber = self.getPageStepNumberPair()
        filename = self.getDatFilename()

        result = "Rendering CSI Page %d Step %d" % (pageNumber, stepNumber)
        if not self.parts:
            return result  # A CSI with no parts is already initialized

        params = LicGLHelpers.initImgSize(size, self.glDispID, filename, CSI.defaultScale * self.scaling, CSI.defaultRotation, self.rotation)
        if params is None:
            return False

        w, h, self.center, unused1, unused2 = params
        self.setRect(0.0, 0.0, w, h)
        self.isDirty = False
        return result

    def createPng(self):

        csiName = self.getDatFilename()
        datFile = os.path.join(config.datCachePath(), csiName)
        
        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            self.exportToLDrawFile(fh)
            fh.close()

        povFile = LicL3PWrapper.createPovFromDat(datFile)
        pngFile = LicPovrayWrapper.createPngFromPov(povFile, self.rect().width(), self.rect().height(), self.center, CSI.defaultScale * self.scaling, CSI.defaultRotation)
        self.pngImage = QImage(pngFile)

    def exportToLDrawFile(self, fh):
        prevStep = self.parentItem().getPrevStep()
        if prevStep:
            prevStep.csi.exportToLDrawFile(fh)

        for partItem in self.parts:
            for part in partItem.parts:
                part.exportToLDrawFile(fh)

    def getDatFilename(self):
        step = self.parentItem()
        parent = step.parentItem()
        if isinstance(parent, Callout):
            return "CSI_Callout_%d_Step_%d.dat" % (parent.number, step.number)
        else:
            return "CSI_Page_%d_Step_%d.dat" % (parent.number, step.number)

    def getPageStepNumberPair(self):
        step = self.parentItem()
        page = step.parentItem()
        return (page.number, step.number)

    def resetArrow(self):
        for callout in self.parentItem().callouts:
            callout.resetArrow()

    def mouseMoveEvent(self, event):
        QGraphicsRectItem.mouseMoveEvent(self, event)
        self.resetArrow()

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Rotate CSI", self.rotateSignal)
        if self.rotation != [0.0, 0.0, 0.0]:
            menu.addAction("Remove Rotation", self.removeRotation)
        menu.addAction("Scale CSI", self.scaleSignal)
        
        if self.parentItem().getNextStep():
            if self.rotation != [0.0, 0.0, 0.0]:
                menu.addAction("Copy Rotation to next X CSIs...", lambda: self.copyRotationScaleToNextCSIs(True))
            if self.scaling != 1.0:
                menu.addAction("Copy Scaling to next X CSIs...", lambda: self.copyRotationScaleToNextCSIs(False))

        menu.addSeparator()
        arrowMenu = menu.addMenu("Select Part")
        for part in self.getPartList():
            text = "%s - %s" % (part.abstractPart.name, part.color.name)
            arrowMenu.addAction(text, lambda p = part: self.selectPart(p))
        arrowMenu.addAction("Select All", self.selectAllParts)

        menu.addAction("Add new Part", self.addNewPartSignal)
        
        menu.exec_(event.screenPos())
        
    def addNewPartSignal(self):
        formats = LicImporters.getFileTypesString()
        filename = unicode(QFileDialog.getOpenFileName(self.scene().activeWindow(), "Lic - Open Part", '.', formats))
        fn = os.path.basename(filename)
        if not fn:
            return

        part = Part(fn, LicHelpers.LicColor(), LicGLHelpers.IdentityMatrix(), False)
        part.initializeAbstractPart(self.getPage().instructions)

        if part.abstractPart.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            part.abstractPart.createGLDisplayList()
            glContext = self.getPage().instructions.glContext
            part.abstractPart.resetPixmap(glContext)

        self.scene().undoStack.push(AddRemovePartCommand(part, self.parentItem(), True))

    def removeRotation(self):
        step = self.parentItem()
        stack = self.scene().undoStack 
        if step.rotateIcon and not step.isInCallout():
            stack.beginMacro("remove CSI rotation")

        oldRotation = self.rotation
        self.rotation = [0.0, 0.0, 0.0]
        RotateScaleSignalItem.acceptRotation(self, oldRotation)

        if step.rotateIcon and not step.isInCallout():
            stack.push(AddRemoveRotateIconCommand(self.parentItem(), False))
            stack.endMacro()

    def acceptRotation(self, oldRotation):
        step = self.parentItem()
        stack = self.scene().undoStack 
        if not step.rotateIcon and not step.isInCallout():
            stack.beginMacro("CSI rotation")

        RotateScaleSignalItem.acceptRotation(self, oldRotation)

        if not step.rotateIcon and not step.isInCallout():
            stack.push(AddRemoveRotateIconCommand(self.parentItem(), True))
            stack.endMacro()

    def selectPart(self, part):
        self.scene().clearSelection()
        part.setSelected(True)
        self.scene().emit(SIGNAL("sceneClick"))
        
    def selectAllParts(self):
        self.scene().clearSelection()
        for part in self.getPartList():
            part.setSelected(True)
        self.scene().emit(SIGNAL("sceneClick"))

    def copyRotationScaleToNextCSIs(self, doRotation):

        # Build list of CSIs that need updating
        csiList = []
        step = self.parentItem().getNextStep()
        while step is not None:
            csiList.append(step.csi)
            step = step.getNextStep()

        # Get number of CSIs to update from user
        text = "Rotate" if doRotation else "Scale"
        parentWidget = self.scene().views()[0]
        i, ok = QInputDialog.getInteger(parentWidget, "CSI Count", text + " next CSIs:", 
                        1, 1, len(csiList), 1, Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        if not ok:
            return

        # Apply rotation | scaling to next chosen CSIs  
        self.scene().undoStack.beginMacro("%s next %d CSI%s" % (text, i, 's' if i > 1 else ''))
        for csi in csiList[0:i]:
            if doRotation:
                oldRotation = list(csi.rotation)
                csi.rotation = list(self.rotation)
                RotateScaleSignalItem.acceptRotation(csi, oldRotation)
            else:
                oldScaling = csi.scaling
                csi.scaling = self.scaling
                csi.acceptScale(oldScaling)

        self.scene().undoStack.endMacro()

class AbstractPart(object):
    """
    Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
    simple primitive, like stud.dat.  
    Used inside 'concrete' Part below. One AbstractPart instance will be shared across several Part instances.  
    In other words, AbstractPart represents everything that two 2x4 bricks have
    in common when present in a model; everything inside 3001.dat.
    """

    def __init__(self, filename = None):

        self.name = self.filename = filename
        self.invertNext = False
        self.winding = GL.GL_CCW
        self.parts = []
        self.primitives = []
        self.glDispID = LicGLHelpers.UNINIT_GL_DISPID
        self.isPrimitive = False  # primitive here means sub-part or part that's internal to another part
        self.isSubmodel = False
        self._boundingBox = None
        
        self.pliScale = 1.0
        self.pliRotation = [0.0, 0.0, 0.0]

        self.width = self.height = -1
        self.leftInset = self.bottomInset = -1
        self.center = QPointF()

    def duplicate(self):
        newPart = AbstractPart(self.filename)
        newPart.invertNext = self.invertNext
        newPart.winding = self.winding
        newPart.parts = list(self.parts)
        newPart.primitives = list(self.primitives)
        newPart.glDispID = self.glDispID
        newPart.isPrimitive = self.isPrimitive
        newPart.isSubmodel = self.isSubmodel
        newPart._boundingBox = self._boundingBox.duplicate() if self._boundingBox else None
        newPart.pliScale, newPart.pliRotation = self.pliScale, list(self.pliRotation)
        newPart.width, newPart.height = self.width, self.height
        newPart.leftInset, newPart.bottomInset = self.leftInset, self.bottomInset
        newPart.center = QPointF(self.center)
        return newPart

    def createGLDisplayList(self, skipPartInit = False):
        """ Initialize this part's display list."""

        # Ensure any parts in this part have been initialized
        if not skipPartInit:
            for part in self.parts:
                if part.abstractPart.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
                    part.abstractPart.createGLDisplayList()

        if self.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            self.glDispID = GL.glGenLists(1)
        GL.glNewList(self.glDispID, GL.GL_COMPILE)

        for part in self.parts:
            part.callGLDisplayList()

        for primitive in self.primitives:
            primitive.callGLDisplayList()

        GL.glEndList()

    def drawConditionalLines(self):
        for part in self.parts:
            part.abstractPart.drawConditionalLines()
            
        for primitive in self.primitives:
            primitive.drawConditionalLines()

    def buildSubAbstractPartDict(self, partDict):

        for part in self.parts:
            if part.abstractPart.filename not in partDict:
                part.abstractPart.buildSubAbstractPartDict(partDict)
        partDict[self.filename] = self

    def resetPixmap(self, glContext, extraRotation = None, extraScale = None, skipPartInit = False):

        glContext.makeCurrent()
        self.createGLDisplayList(skipPartInit)
        sizes = [128, 256, 512, 1024, 2048]
        self.width, self.height, self.center, self.leftInset, self.bottomInset = [0] * 5

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, LicGLHelpers.getGLFormat(), glContext)
            pBuffer.makeCurrent()

            rotation = extraRotation if extraRotation else self.pliRotation
            scaling = extraScale if extraScale else self.pliScale
            if self.initSize(size, pBuffer, rotation, scaling):
                break

        glContext.makeCurrent()

    def initSize(self, size, pBuffer, extraRotation = [0.0, 0.0, 0.0], extraScale = 1.0):
        """
        Initialize this part's display width, height, empty corner insets and center point.
        To do this, draw this part to the already initialized GL buffer.
        These dimensions are required to properly lay out PLIs and CSIs.

        Parameters:
            size: Width & height of GL buffer to render to, in pixels.  Note that buffer is assumed square

        Returns:
            True if part rendered successfully.
            False if the part has been rendered partially or wholly out of frame.
        """

        # TODO: If a part is rendered at a size > 256, draw it smaller in the PLI - this sounds like a great way to know when to shrink a PLI image...
        rotation = SubmodelPreview.defaultRotation if self.isSubmodel else PLI.defaultRotation
        scaling = SubmodelPreview.defaultScale if self.isSubmodel else PLI.defaultScale
        params = LicGLHelpers.initImgSize(size, self.glDispID, self.filename, scaling * extraScale, rotation, extraRotation)
        if params is None:
            return False

        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def paintGL(self, dx, dy, rotation = [0.0, 0.0, 0.0], scaling = 1.0, color = None):

        LicGLHelpers.pushAllGLMatrices()

        dr = SubmodelPreview.defaultRotation if self.isSubmodel else PLI.defaultRotation
        ds = SubmodelPreview.defaultScale if self.isSubmodel else PLI.defaultScale

        dx += self.center.x() * scaling
        dy += self.center.y() * scaling

        if color is not None:  # Color means we're drawing a PLIItem, so apply PLI specific scale & rotation
            ds *= self.pliScale

        LicGLHelpers.rotateToView(dr, ds * scaling, dx, dy, 0.0)
        LicGLHelpers.rotateView(*rotation)

        if color is not None:

            LicGLHelpers.rotateView(*self.pliRotation)
            
            if color is not None:
                GL.glColor4fv(color.rgba)

        GL.glCallList(self.glDispID)
        LicGLHelpers.popAllGLMatrices()

    def getBoundingBox(self):
        if self._boundingBox:
            return self._boundingBox
        
        box = None
        for primitive in self.primitives:
            p = primitive.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p)
                else:
                    box = p.duplicate()
            
        for part in self.parts:
            p = part.abstractPart.getBoundingBox()
            if p:
                if box:
                    box.growByBoudingBox(p, part.matrix)
                else:
                    box = p.duplicate(part.matrix)

        self._boundingBox = box
        return box

    def resetBoundingBox(self):
        for primitive in self.primitives:
            primitive.resetBoundingBox()
        for part in self.parts:
            part.abstractPart.resetBoundingBox()
        self._boundingBox = None

class BoundingBox(object):
    
    def __init__(self, x = 0.0, y = 0.0, z = 0.0):
        self.x1 = self.x2 = x
        self.y1 = self.y2 = y
        self.z1 = self.z2 = z

    def __str__(self):
        #return "x1: %.2f, x2: %.2f,  y1: %.2f, y2: %.2f,  z1: %.2f, z2: %.2f" % (self.x1, self.x2, self.y1, self.y2, self.z1, self.z2)
        return "%.0f %.0f | %.0f %.0f | %.0f %.0f" % (self.x1, self.x2, self.y1, self.y2, self.z1, self.z2)
    
    def duplicate(self, matrix = None):
        b = BoundingBox()
        if matrix:
            b.x1, b.y1, b.z1 = self.transformPoint(matrix,self.x1, self.y1, self.z1)
            b.x2, b.y2, b.z2 = self.transformPoint(matrix,self.x2, self.y2, self.z2)
            if b.y1 > b.y2:
                b.y1, b.y2 = b.y2, b.y1
        else:
            b.x1, b.y1, b.z1 = self.x1, self.y1, self.z1
            b.x2, b.y2, b.z2 = self.x2, self.y2, self.z2
        return b
        
    def vertices(self):
        yield (self.x1, self.y1, self.z1)
        yield (self.x1, self.y1, self.z2)
        yield (self.x1, self.y2, self.z1)
        yield (self.x1, self.y2, self.z2)
        yield (self.x2, self.y1, self.z1)
        yield (self.x2, self.y1, self.z2)
        yield (self.x2, self.y2, self.z1)
        yield (self.x2, self.y2, self.z2)
        
    def growByPoints(self, x, y, z):
        self.x1 = min(x, self.x1)
        self.x2 = max(x, self.x2)
        self.y1 = min(y, self.y1)
        self.y2 = max(y, self.y2)
        self.z1 = min(z, self.z1)
        self.z2 = max(z, self.z2)
        
    def growByBoudingBox(self, box, matrix = None):
        if matrix:
            if matrix[5] < 0:
                self.growByPoints(*self.transformPoint(matrix, box.x1, box.y2, box.z1))
                self.growByPoints(*self.transformPoint(matrix, box.x2, box.y1, box.z2))
            else:
                self.growByPoints(*self.transformPoint(matrix, box.x1, box.y1, box.z1))
                self.growByPoints(*self.transformPoint(matrix, box.x2, box.y2, box.z2))
        else:
            self.growByPoints(box.x1, box.y1, box.z1)
            self.growByPoints(box.x2, box.y2, box.z2)

    def transformPoint(self, matrix, x, y, z):
        x2 = (matrix[0] * x) + (matrix[4] * y) + (matrix[8] * z) + matrix[12]
        y2 = (matrix[1] * x) + (matrix[5] * y) + (matrix[9] * z) + matrix[13]
        z2 = (matrix[2] * x) + (matrix[6] * y) + (matrix[10] * z) + matrix[14]
        return (x2, y2, z2)
    
    def xSize(self):
        return abs(self.x2 - self.x1)

    def ySize(self):
        return abs(self.y2 - self.y1)

    def zSize(self):
        return abs(self.z2 - self.z1)

class Submodel(SubmodelTreeManager, AbstractPart):
    """ A Submodel is just an AbstractPart that also has pages & steps, and can be inserted into a tree. """
    itemClassName = "Submodel"

    def __init__(self, parent = None, instructions = None, filename = ""):
        AbstractPart.__init__(self, filename)

        self.instructions = instructions
        self.used = False

        self.pages = []
        self.submodels = []

        self._row = 0
        self._parent = parent
        self.isSubmodel = True
        self.isSubAssembly = False

    def getSimpleName(self):
        name = os.path.splitext(os.path.basename(self.name))[0]
        return name.replace('_', ' ')

    def createGLDisplayList(self, skipPartInit = False):
        for model in self.submodels:
            model.createGLDisplayList(skipPartInit)
        AbstractPart.createGLDisplayList(self, skipPartInit)

    def setSelected(self, selected):
        self.pages[0].setSelected(selected)

    def importModel(self):
        """ Reads in a model file and populates this submodel with the info.
            Chooses the correct Importer to used based on its filename's extension. 
        """

        # Set up dynamic module to be used for import 
        importerName = LicImporters.getImporter(os.path.splitext(self.filename)[1][1:])
        importModule = __import__("LicImporters.%s" % importerName, fromlist = ["LicImporters"])
        importModule.LDrawPath = config.LDrawPath
        importModule.importModel(self.filename, self.instructions.getProxy())

    def hasImportedSteps(self):
        if not self.pages:
            return False
        if (len(self.pages) > 1) or (len(self.pages[0].steps)) > 1:
            return True
        return False

    def deleteEmptyPagesSteps(self):
        for page in self.pages:
            for step in page.steps:
                if step.isEmpty():
                    page.removeStep(step)
            if page.isEmpty():
                self.deletePage(page)
    
    def addInitialPagesAndSteps(self):

        for submodel in self.submodels:
            submodel.addInitialPagesAndSteps()

        if self.hasImportedSteps():
            self.deleteEmptyPagesSteps()
            return

        # Add one step for every 5 parts, and one page per step
        # At this point, if model had no steps (assumed for now), we have one page per submodel
        PARTS_PER_STEP_MAX = 5
        
        csi  = self.pages[0].steps[0].csi
        while csi.partCount() > 0:
            
            partList = csi.getPartList()
            #partList.sort(key = lambda x: x.xyzSortOrder())
            partList.sort(cmp = LicHelpers.compareParts)
            
            part = partList[0]
            y, dy = part.by(), part.ySize()
            currentPartIndex = 1
            
            if len(partList) > 1:
                
                # Advance part list splice point forward until we find the next 'layer' of parts
                nextPart = partList[currentPartIndex]
                while y == nextPart.by() and abs(dy - nextPart.ySize()) <= 4.0:
                    currentPartIndex += 1
                    if currentPartIndex >= len(partList):
                        break
                    nextPart = partList[currentPartIndex]
                    
                # Here, currentPartIndex points to the next potential splice point
                if currentPartIndex > PARTS_PER_STEP_MAX:
                    
                    # Have lots of parts in this layer: keep most popular part here, bump rest to next step
                    partCounts = {}
                    for part in partList[:currentPartIndex]:
                        if part.abstractPart.name in partCounts:
                            partCounts[part.abstractPart.name] += 1
                        else:
                            partCounts[part.abstractPart.name] = 1
                    popularPartName = max(partCounts, key = partCounts.get)
                    partList = [x for x in partList[:currentPartIndex] if x.abstractPart.name != popularPartName] + partList[currentPartIndex:]
                    currentPartIndex = 0
                    
                elif currentPartIndex == 1 and not partList[0].isSubmodel():
                    
                    # Have only one part in this layer: search forward until we hit a layer with several parts
                    part = partList[0]
                    nextPart = partList[1]
                    while (abs(part.by2() - nextPart.by()) <= 4.0) and \
                          (currentPartIndex < PARTS_PER_STEP_MAX - 1) and \
                          (currentPartIndex < len(partList) - 1):
                        part = partList[currentPartIndex]
                        nextPart = partList[currentPartIndex + 1]
                        currentPartIndex += 1
                        
                    if currentPartIndex > 1:
                        # Add an up displacement to last part, if it's basically above previous part
                        p1 = partList[currentPartIndex - 1]
                        p2 = partList[currentPartIndex]
                        px1, pz1, px2, pz2 = p1.x(), p1.z(), p2.x(), p2.z()
                        if abs(px1 - px2) < 2 and abs(pz1 - pz2) < 2:
                            p2.addNewDisplacement(Qt.Key_PageUp)
                        currentPartIndex += 1
            
            if len(partList[currentPartIndex: ]) == 0:
                break  # All done

            # Create a new page, give it a step, then push all remaining parts to that step
            newPage = self.instructions.spawnNewPage(self, self.pages[-1]._number + 1, self.pages[-1]._row + 1)
            newPage.addBlankStep()
            self.addPage(newPage)

            # Want submodels to be inserted in their own Step, so split those off
            submodelList = [part for part in partList[:currentPartIndex] if part.isSubmodel()]
            if submodelList and len(submodelList) != currentPartIndex:
                partList = submodelList + partList[currentPartIndex:]
                currentPartIndex = 0
            
            # Want all identical submodels inserted in same step, so group them all
            if partList[0].isSubmodel() and currentPartIndex > 0:
                partList = [part for part in partList if part.filename != partList[0].filename]
                currentPartIndex = 0
            
            # Here, partList is all parts not yet allocated to a Step, and currentPartIndex is an index into  
            # that list; parts before currentPartIndex stay in this Step, parts after get bumped to next Step
            for part in partList[currentPartIndex: ]:  # Move all but the first x parts to next step
                currentStep = part.getStep()
                part.setParentItem(newPage)
                currentStep.removePart(part)
                newPage.steps[-1].addPart(part)

            csi = newPage.steps[-1].csi

    def mergeInitialPages(self):
        
        for submodel in self.submodels:
            submodel.mergeInitialPages()
        
        if len(self.pages) < 2:
            return
        
        currentPage = self.pages[0]
        nextPage = self.pages[1]
        
        while True:   # yeah yeah, nested infinite loops of nastiness
            while True:

                nextStep = nextPage.steps[0]
                partList = nextStep.csi.getPartList()
                submodelList = [p for p in partList if p.isSubmodel()]
                if submodelList:  # Check if next Step has any Submodels

                    if len(submodelList) == len(partList):  # Check if next Step is full of Submodels
                        nextStep.disablePLI()  # Leave Submodel steps as first on page, and hide their PLI.

                    nextPage.initLayout()
                    break

                nextStep.moveToPage(currentPage) # Move step on next page to current page

                currentLayout = currentPage.layout.orientation
                currentPage.useHorizontalLayout()  # Try horizontal layout
                if currentPage.checkForLayoutOverlaps(): 

                    currentPage.useVerticalLayout()  # Try vertical layout
                    if currentPage.checkForLayoutOverlaps():

                        currentPage.steps[-1].moveToPage(nextPage)  # move Step back & redo layouts
                        currentPage.layout.orientation = currentLayout
                        currentPage.initLayout()
                        nextPage.initLayout()
                        break  # This page is full: move on to the next
                    
                tmp = nextPage.nextPage()  # No overlap - delete empty page & move on
                self.deletePage(nextPage)
                if tmp is None:  # At last page - all done
                    return
                nextPage = tmp
                    
            currentPage = nextPage
            nextPage = nextPage.nextPage()
            if nextPage is None:  # At last page - all done
                return

    def reOrderSubmodelPages(self):
        """ Reorder the tree so a submodel is right before the page it's used on """
        for submodel in self.submodels:
            submodel.reOrderSubmodelPages()
            
        for submodel in self.submodels:
            page = self.findSubmodelStep(submodel).getPage()
            if page is None or submodel._row == page._row - 1:
                continue  # submodel not used or in right spot
            
            self.removeRow(submodel._row)
            newRow = page._row
            self.addRow(newRow)
            submodel._row = newRow

    def addRow(self, row):
        for page in [p for p in self.pages if p._row >= row]:
            page._row += 1
        for s in [p for p in self.submodels if p._row >= row]:
            s._row += 1
    
    def removeRow(self, row):
        for page in [p for p in self.pages if p._row > row]:
            page._row -= 1
        for s in [p for p in self.submodels if p._row > row]:
            s._row -= 1
    
    def addSubmodel(self, submodel):  # TODO: co-opt this so it's used by Importers to add new Submodels
        # Assume Submodel already exists as a Part on an appropriate Step

        step = self.findSubmodelStep(submodel)
        
        if step is None:  # Submodel doesn't live here - try existing submodels
            for model in self.submodels:
                model.addSubmodel(submodel)
        else:
            submodel._parent = self
            submodel._row = self.rowCount()
            self.submodels.append(submodel)
            self.reOrderSubmodelPages()
            self.instructions.mainModel.syncPageNumbers()
            for page in submodel.pages:
                if page.scene() is None:
                    self.instructions.scene.addItem(page)
    
    def removeSubmodel(self, submodel):
        self.removeRow(submodel._row)
        self.submodels.remove(submodel)
        for page in submodel.pages:
            page.scene().removeItem(page)
        self.instructions.mainModel.syncPageNumbers()
        submodel._parent = None

    def findSubmodelStep(self, submodel):
        for page in self.pages:
            for step in page.steps:
                if submodel in [part.abstractPart for part in step.csi.getPartList()]:
                    return step
        return None

    def syncStepNumbers(self):  # Assume all page.children are ordered correctly.  Fixup all step numbers, then resort all page.steps
        stepNumber = 1
        for page in self.pages:
            l = [c for c in page.children if isinstance(c, Step)]
            for step in l:
                step.number = stepNumber
                stepNumber += 1
                
        for page in self.pages:
            page.steps.sort(key = lambda x: x._number)
    
    def syncPageNumbers(self, firstPageNumber = 1):

        rowList = self.pages + self.submodels
        rowList.sort(key = lambda x: x._row)

        pageNumber = firstPageNumber
        for item in rowList:
            if isinstance(item, Submodel):
                pageNumber = item.syncPageNumbers(pageNumber)
            else: # have a Page
                item.number = pageNumber
                pageNumber += 1

        return pageNumber
    
    def appendBlankPage(self):

        if not self.pages and not self.submodels:
            row = 0
        else:
            row = 1 + max(self.pages[-1]._row if self.pages else 0, self.submodels[-1]._row if self.submodels else 0)
            
        pageNumber = self.pages[-1].number + 1 if self.pages else 1
        page = self.instructions.spawnNewPage(self, pageNumber, row)
        for p in self.pages[page._row : ]:
            p._row += 1
        self.pages.insert(page._row, page)
        page.addBlankStep()
        return page

    def addPage(self, page):

        for p in self.pages:
            if p._row >= page._row:
                p._row += 1

        for s in self.submodels:
            if s._row >= page._row: 
                s._row += 1

        page.submodel = self
        self.instructions.updatePageNumbers(page.number)

        index = len([p for p in self.pages if p._row < page._row])
        self.pages.insert(index, page)

        if page in self.instructions.scene.items():
            self.instructions.scene.removeItem(page)  # Need to re-add page to trigger scene page layout
        self.instructions.scene.addItem(page)

    def deletePage(self, page):

        for p in self.pages:
            if p._row > page._row:
                p._row -= 1

        for s in self.submodels:
            if s._row > page._row: 
                s._row -= 1

        page.scene().removeItem(page)
        self.pages.remove(page)
        self.instructions.updatePageNumbers(page.number, -1)

    def resetStepSet(self, minStepNum, maxStepNum):

        if minStepNum > maxStepNum:
            minStepNum, maxStepNum = maxStepNum, minStepNum

        step = self.getStepByNumber(minStepNum)
        stepsToReset = [step]

        while step is not None and step.number <= maxStepNum:
            stepsToReset.append(step)
            step = step.getNextStep()

        for step in stepsToReset:
            step.csi.isDirty = True
            step.initLayout()
            if step.isInCallout():
                step.parentItem().initLayout()

    def updateStepNumbers(self, newNumber, increment = 1):
        for p in self.pages:
            for s in p.steps:
                if s.number >= newNumber:
                    s.number += increment

    def updatePageNumbers(self, newNumber, increment = 1):
        
        for p in self.pages:
            if p.number >= newNumber:
                p.number += increment
                
        for submodel in self.submodels:
            submodel.updatePageNumbers(newNumber, increment)
        
    def deleteAllPages(self, scene):
        for page in self.pages:
            scene.removeItem(page)
            del(page)
        for submodel in self.submodels:
            submodel.deleteAllPages(scene)

    def getStepByNumber(self, stepNumber):
        for page in self.pages:
            for step in page.steps:
                if step.number == stepNumber:
                    return step
                
        for submodel in self.submodels:
            step = submodel.getStepByNumber(stepNumber)
            if step:
                return step
        return None

    def getPage(self, pageNumber):
        for page in self.pages:
            if page.number == pageNumber:
                return page
        for submodel in self.submodels:
            page = submodel.getPage(pageNumber)
            if page:
                return page
        return None

    def getFirstPLIItem(self):
        for page in self.pages:
            for step in page.steps:
                if step.pli.pliItems:
                    return step.pli.pliItems[0]

        for submodel in self.submodels:
            item = submodel.getFirstPLIItem()
            if item: 
                return item
            
        return None

    def createBlankPart(self):
        return Part(self.filename, matrix = LicGLHelpers.IdentityMatrix())

    def getCSIList(self):
        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)
                for callout in step.callouts:
                    for step2 in callout.steps:
                        csiList.append(step2.csi)

        for submodel in self.submodels:
            csiList += submodel.getCSIList()

        return csiList

    def showHidePLIs(self, show, doLayout = False):
        for page in self.pages:
            for step in page.steps:
                step.enablePLI() if show else step.disablePLI()
            if doLayout:
                page.initLayout()

    def initAllPLILayouts(self):
        for page in self.pages:
            for step in page.steps:
                if step.pli:
                    step.pli.initLayout()
            page.initLayout()

        for submodel in self.submodels:
            submodel.initAllPLILayouts()

    def initSubmodelImages(self):
        for page in self.pages:
            page.resetSubmodelImage()
            page.initLayout()

        for submodel in self.submodels:
            for page in submodel.pages:
                page.resetSubmodelImage()
                page.initLayout()

    def _genericIterator(self, attr, op):
        res = op(self.__getattribute__(attr))
        for submodel in self.submodels:
            res += submodel._genericIterator(attr, op)
        return res

    def submodelInstanceCount(self, submodelName):
        count = len([p for p in self.parts if p.filename == submodelName])
        for submodel in self.submodels:
            count += submodel.submodelInstanceCount(submodelName)
        return count

    def submodelCount(self):
        return self._genericIterator('submodels', len)

    def pageCount(self):
        return self._genericIterator('pages', len)

    def getPageList(self):
        return self._genericIterator('pages', list)

    def getFullPartList(self):
        partList = [] 
        for part in [p for p in self.parts if p.isSubmodel()]:
            partList += part.abstractPart.getFullPartList()
        partList += [p for p in self.parts if not p.isSubmodel()]
        return partList

    def addSubmodelImages(self):
        count = self.instructions.mainModel.submodelInstanceCount(self.filename)
        self.pages[0].addSubmodelImage(count)
        for submodel in self.submodels:
            submodel.addSubmodelImages()

    def initSubmodelImageGLDisplayList(self):
        item = self.pages[0].submodelItem
        if item and item.abstractPart.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            item.abstractPart.createGLDisplayList(False)
            if any(item.rotation):
                item.resetPixmap() 
        for submodel in self.submodels:
            submodel.initSubmodelImageGLDisplayList()

    def exportImagesToPov(self):
        for page in self.pages:
            page.renderFinalImageWithPov()

        for submodel in self.submodels:
            submodel.exportImagesToPov()

    def createPng(self):

        datFile = os.path.join(config.datCachePath(), self.filename)

        if not os.path.isfile(datFile):
            fh = open(datFile, 'w')
            for part in self.parts:
                part.exportToLDrawFile(fh)
            fh.close()

        povFile = LicL3PWrapper.createPovFromDat(datFile)
        pngFile = LicPovrayWrapper.createPngFromPov(povFile, self.width, self.height, self.center, PLI.defaultScale, PLI.defaultRotation)
        self.pngImage = QImage(pngFile)

    def exportToLDrawFile(self, fh):
        for line in LDrawImporter.createSubmodelLines(self.filename):
            fh.write(line)
        for page in self.pages:
            for step in page.steps:
                step.exportToLDrawFile(fh)
                for part in step.csi.getPartList():
                    part.exportToLDrawFile(fh)
        for submodel in self.submodels:
            submodel.exportToLDrawFile(fh)

    def contextMenuEvent(self, event):
        menu = QMenu()
        if self.isSubAssembly:
            menu.addAction("Change Sub Assembly to Callout", self.convertToCalloutSignal)
            menu.addAction("Change Sub Assembly to Submodel", self.convertFromSubAssemblySignal)
        else:
            menu.addAction("Change Submodel to Callout", self.convertToCalloutSignal)
            menu.addAction("Change Submodel to Sub Assembly", self.convertToSubAssemblySignal)
        menu.addAction("Remove all Pages & Steps", self.removeAllPagesAndSteps)

        selectedSubmodels = list(self.instructions.scene.selectedSubmodels)
        if len(selectedSubmodels) == 2 and self in selectedSubmodels:
            menu.addSeparator()
            selectedSubmodels.remove(self)
            names = (selectedSubmodels[0].getSimpleName(), self.getSimpleName())
            menu.addAction("Clone Steps from '%s' to '%s'" % names, lambda: self.cloneStepsFromSubmodel(selectedSubmodels[0]))

        menu.exec_(event.screenPos())

    def removeAllPagesAndSteps(self):
        self.instructions.scene.undoStack.beginMacro("remove all Pages and Steps")
        step = self.pages[0].steps[0]
        nextStep = step.getNextStep()
        while nextStep is not None:
            nextStep.mergeWithStepSignal(step)
            nextStep = step.getNextStep()
        self.instructions.scene.undoStack.endMacro()

    def cloneStepsFromSubmodel(self, submodel):
        action = ClonePageStepsFromSubmodel(submodel, self)
        self.instructions.scene.undoStack.push(action)

    def convertToCalloutSignal(self):
        self.pages[0].scene().undoStack.push(SubmodelToCalloutCommand(self))

    def convertToSubAssemblySignal(self):
        self.pages[0].scene().undoStack.push(SubmodelToFromSubAssembly(self, True))

    def convertFromSubAssemblySignal(self):
        self.pages[0].scene().undoStack.push(SubmodelToFromSubAssembly(self, False))

class Mainmodel(MainModelTreeManager, Submodel):
    """ A MainModel is a Submodel plus a template, title & part list pages. It's used as the root of a tree mdoel. """
    itemClassName = "Mainmodel"

    def __init__(self, parent = None, instructions = None, filename = ""):
        Submodel.__init__(self, parent, instructions, filename)

        self.template = None

        self._hasTitlePage = False
        self.titlePage = None

        self.hasPartListPages = False  # TODO: Implement mainModel.hasPartListPages so user can show / hide part list pages, like title pages
        self.partListPages = []

    def hasTitlePage(self):
        return self._hasTitlePage and self.titlePage is not None

    def createNewTitlePage(self, useSignal = True):
        self.titlePage = self.instructions.spawnNewTitlePage()
        self.titlePage.addInitialContent()

        if useSignal:
            self.addRemoveTitlePageSignal(True)
        else:
            self._hasTitlePage = True
            self.incrementRows(1)
            self.syncPageNumbers()

    def addRemoveTitlePageSignal(self, add = True):
        scene = self.instructions.scene
        scene.undoStack.push(AddRemoveTitlePageCommand(scene, self.titlePage, add))

    def getFullPageList(self):
        pages = [self.titlePage] if self.titlePage else []
        return pages + Submodel.getPageList(self) + self.partListPages

    def addPage(self, page):
        for p in self.partListPages:
            if p._row >= page._row: 
                p._row += 1
        Submodel.addPage(self, page)

    def deletePage(self, page):
        for p in self.partListPages:
            if p._row > page._row: 
                p._row -= 1
        Submodel.deletePage(self, page)

    def initAllPLILayouts(self):
        Submodel.initAllPLILayouts(self)
        for page in self.partListPages:
            page.initLayout()

    def updatePageNumbers(self, newNumber, increment = 1):
        for p in self.partListPages:
            if p.number >= newNumber:
                p.number += increment
        Submodel.updatePageNumbers(self, newNumber, increment)

    def updatePartList(self):
        p1 = self.partListPages[0]
        scene = p1.scene()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        if len(self.partListPages) > 1:
            for page in self.partListPages[1:]:
                scene.removeItem(page)
                del(page)
        self.partListPages = p1.updatePartList()
        scene.emit(SIGNAL("layoutChanged()"))
        
    def syncPageNumbers(self, firstPageNumber = 1):

        rowList = [self.titlePage] if self.hasTitlePage() else []
        rowList += self.pages + self.submodels
        rowList += self.partListPages
        rowList.sort(key = lambda x: x._row)

        pageNumber = firstPageNumber
        for item in rowList:
            if isinstance(item, Submodel):
                pageNumber = item.syncPageNumbers(pageNumber)
            else:  # have a Page
                item.number = pageNumber
                pageNumber += 1

        self.instructions.scene.sortPages()
        return pageNumber

class PartTreeItem(PartTreeItemTreeManager, QGraphicsRectItem):
    itemClassName = "Part Tree Item"

    def __init__(self, parent, name):
        QGraphicsRectItem.__init__(self, parent)
        self.name = name
        self.parts = []
        self._dataString = None  # Cache data string for tree
        self.setFlags(AllFlags)

    def setSelected(self, selected):
        for part in self.parts:
            part.setSelected(selected)

    def addPart(self, part):
        part.setParentItem(self)
        self._dataString = None
        self.parts.append(part)

    def removePart(self, part):
        if part in self.parts:
            self.parts.remove(part)
            self._dataString = None

    def getStep(self):
        return self.parentItem().parentItem()

    def contextMenuEvent(self, event):
        self.scene().clearSelection()
        self.setSelected(True)
        self.parts[0].contextMenuEvent(event)  # Pass right-click on to first part 

class Part(PartTreeManager, QGraphicsRectItem):
    """
    Represents one 'concrete' part, ie, an 'abstract' part (AbstractPart), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """

    itemClassName = "Part"

    def __init__(self, filename, color = None, matrix = None, invert = False):
        QGraphicsRectItem.__init__(self)

        self.filename = filename  # Needed for save / load
        self.color = color
        self.matrix = matrix
        self.inverted = invert
        self.abstractPart = None
        self._dataString = None  # Cache data string for tree
        self.isInPLI = True

        self.displacement = []
        self.displaceDirection = None

        # Links to track if this part is in a Callout, and the part it's tied to
        self.calloutPart = None
        self.originalPart = None
        self.arrows = []

        #self.setPos(0.0, 0.0)
        #self.setRect(0.0, 0.0, 30.0, 30.0)
        #self.setPen(QPen(Qt.black))
        self.setFlags(NoMoveFlags)

    def initializeAbstractPart(self, instructions):
        
        fn = self.filename
        pd = instructions.partDictionary

        if fn in pd:
            self.abstractPart = pd[fn]
        elif fn.upper() in pd:
            self.abstractPart = pd[fn.upper()]
        else:
            # Set up dynamic module to be used for import 
            importerName = LicImporters.getImporter(os.path.splitext(fn)[1][1:])
            importModule = __import__("LicImporters.%s" % importerName, fromlist = ["LicImporters"])
            importModule.LDrawPath = config.LDrawPath

            abstractPart = AbstractPart(fn)
            importModule.importPart(fn, instructions.getProxy(), abstractPart)
            self.abstractPart = pd[fn] = abstractPart

    def setInversion(self, invert):
        # Inversion is annoying as hell.  
        # Possible the containing part used a BFC INVERTNEXT (invert arg)
        # Possible this part's matrix implies an inversion (det < 0)
        det = LicHelpers.determinant3x3([self.matrix[0:3], self.matrix[4:7], self.matrix[8:11]])
        self.inverted = (True if det < 0 else False) ^ invert
        
    def xyzSortOrder(self):
        b = self.getPartBoundingBox()
        return (-b.y1, b.ySize(), -b.z1, b.x1)

    def getPartBoundingBox(self):
        m = list(self.matrix)
        if self.displacement:
            m[12] += self.displacement[0]
            m[13] += self.displacement[1]
            m[14] += self.displacement[2]

        return self.abstractPart.getBoundingBox().duplicate(m)
    
    def xyz(self):
        return [self.matrix[12], self.matrix[13], self.matrix[14]]
    
    def bx(self):
        return self.getPartBoundingBox().x1

    def by(self):
        return self.getPartBoundingBox().y2

    def bz(self):
        return self.getPartBoundingBox().z1

    def bx2(self):
        return self.getPartBoundingBox().x2

    def by2(self):
        return self.getPartBoundingBox().y1

    def bz2(self):
        return self.getPartBoundingBox().z2

    def x(self):
        return self.matrix[12]
    
    def y(self):
        return self.matrix[13]
    
    def z(self):
        return self.matrix[14]

    def xyzSize(self):
        return [self.xSize(), self.ySize(), self.zSize()]
    
    def xSize(self):
        return self.getPartBoundingBox().xSize()

    def ySize(self):
        return self.getPartBoundingBox().ySize()

    def zSize(self):
        return self.getPartBoundingBox().zSize()

    def xRotation(self):
        return math.degrees(math.atan2(-self.matrix[6], self.matrix[10]))
    
    def yRotation(self):
        return math.degrees(math.asin(self.matrix[2]))

    def zRotation(self):
        return math.degrees(math.atan2(-self.matrix[1], self.matrix[0]))

    def xyzRotation(self):
        return [self.xRotation(), self.yRotation(), self.zRotation()]
    
    def setXYZRotation(self, x, y, z):
        x, y, z = math.radians(x), math.radians(y), math.radians(z)

        sx, sy, sz = math.sin(x), math.sin(y), math.sin(z)
        cx, cy, cz = math.cos(x), math.cos(y), math.cos(z)
        
        self.matrix[0] = cy * cz
        self.matrix[1] = -cy * sz
        self.matrix[2] = sy

        self.matrix[4] = (sx * sy * cz) + (cx * sz)
        self.matrix[5] = (-sx * sy * sz) + (cx * cz)
        self.matrix[6] = -sx * cy

        self.matrix[8]  = (-cx * sy * cz) + (sx * sz)
        self.matrix[9]  = (cx * sy * sz) + (sx * cz)
        self.matrix[10] = cx * cy
    
    def getPositionMatch(self, part):
        score = 0
        for a, b in zip(self.xyz(), part.xyz()):
            score += 2 if a == b else (1.0 / abs(a-b))
        return score

    def getCSI(self):
        return self.parentItem().parentItem()

    def getStep(self):
        return self.getCSI().parentItem()

    def setSelected(self, selected, updatePixmap = True):
        QGraphicsRectItem.setSelected(self, selected)
        if updatePixmap:
            self.getCSI().createGLDisplayList()

    def addNewDisplacement(self, direction):
        self.displaceDirection = direction
        self.displacement = LicHelpers.getDisplacementOffset(direction, True, self.abstractPart.getBoundingBox())
        self.addNewArrow(direction)
        self._dataString = None

    def addNewArrow(self, direction):
        arrow = Arrow(direction, self)
        arrow.setPosition(*LicHelpers.GLMatrixToXYZ(self.matrix))
        arrow.setLength(arrow.getOffsetFromPart(self))
        self.arrows.append(arrow)

    def removeDisplacement(self):
        self.displaceDirection = None
        self.displacement = []
        self.arrows = []
        self._dataString = None

    def isSubmodel(self):
        return isinstance(self.abstractPart, Submodel)

    def toBlack(self):
        self.color = LicHelpers.LicColor.black()

    def callGLDisplayList(self, useDisplacement = False):

        # must be called inside a glNewList/EndList pair
        if self.color is not None:
            color = list(self.color.rgba)
            if useDisplacement and self.isSelected():
                color[3] = 0.5
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        if self.inverted:
            GL.glPushAttrib(GL.GL_POLYGON_BIT)
            GL.glFrontFace(GL.GL_CW)

        if self.matrix:
            matrix = list(self.matrix)
            if useDisplacement and self.displacement:
                matrix[12] += self.displacement[0]
                matrix[13] += self.displacement[1]
                matrix[14] += self.displacement[2]
            GL.glPushMatrix()
            GL.glMultMatrixf(matrix)

        if useDisplacement and (self.isSelected() or CSI.highlightNewParts):
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4f(1.0, 0.0, 0.0, 1.0)
            self.drawGLBoundingBox()
            GL.glPopAttrib()

        GL.glCallList(self.abstractPart.glDispID)
        #self.abstractPart.drawConditionalLines()

        if self.matrix:
            GL.glPopMatrix()

        if self.inverted:
            GL.glPopAttrib()

        if self.color is not None:
            GL.glPopAttrib()

        for arrow in self.arrows:
            arrow.callGLDisplayList(useDisplacement)

    def drawGLBoundingBox(self):
        b = self.abstractPart.getBoundingBox()
        GL.glBegin(GL.GL_LINE_LOOP)
        GL.glVertex3f(b.x1, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y2, b.z1)
        GL.glVertex3f(b.x1, b.y2, b.z1)
        GL.glEnd()

        GL.glBegin(GL.GL_LINE_LOOP)
        GL.glVertex3f(b.x1, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y2, b.z2)
        GL.glVertex3f(b.x1, b.y2, b.z2)
        GL.glEnd()

        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(b.x1, b.y1, b.z1)
        GL.glVertex3f(b.x1, b.y1, b.z2)
        GL.glVertex3f(b.x1, b.y2, b.z1)
        GL.glVertex3f(b.x1, b.y2, b.z2)
        GL.glVertex3f(b.x2, b.y1, b.z1)
        GL.glVertex3f(b.x2, b.y1, b.z2)
        GL.glVertex3f(b.x2, b.y2, b.z1)
        GL.glVertex3f(b.x2, b.y2, b.z2)
        GL.glEnd()

    def exportToLDrawFile(self, fh):
        line = LDrawImporter.createPartLine(self.color, self.matrix, self.abstractPart.filename)
        fh.write(line)

    def duplicate(self):
        p = Part(self.filename, self.color.duplicate(), list(self.matrix), self.inverted)
        p.abstractPart = self.abstractPart
        p.setParentItem(self.parentItem())
        p.displacement = list(self.displacement)
        p.displaceDirection = self.displaceDirection
        for arrow in self.arrows:
            p.arrows.append(arrow.duplicate(p))
        return p

    def contextMenuEvent(self, event):
        """ 
        This is called if any part is the target of a right click.  
        self is guaranteed to be selected.  Other stuff may be selected too, so deal.
        """

        stack = self.scene().undoStack
        step = self.getStep()
        menu = QMenu(self.scene().views()[0])

        if self.isInPLI:
            menu.addAction("Remove from PLI", lambda: stack.push(AddRemovePartToPLICommand(self, False)))
        else:
            menu.addAction("Add to PLI", lambda: stack.push(AddRemovePartToPLICommand(self, True)))

        if self.calloutPart:
            menu.addAction("Remove from Callout", self.removeFromCalloutSignal)
        else:
            menu.addAction("Create Callout from Parts", self.createCalloutSignal)

            if step.callouts:
                subMenu = menu.addMenu("Move Part to Callout")
                for callout in step.callouts:
                    subMenu.addAction("Callout %d" % callout.number, lambda x = callout: self.moveToCalloutSignal(x))
        
        menu.addSeparator()

        needSeparator = False
        if step.getPrevStep() and not self.calloutPart:
            menu.addAction("Move to &Previous Step", lambda: self.moveToStepSignal(step.getPrevStep()))
            needSeparator = True

        if step.getNextStep() and not self.calloutPart:
            menu.addAction("Move to &Next Step", lambda: self.moveToStepSignal(step.getNextStep()))
            needSeparator = True

        if needSeparator:
            menu.addSeparator()

        if self.displacement:
            #menu.addAction("&Increase displacement", lambda: self.displaceSignal(self.displaceDirection))
            #menu.addAction("&Decrease displacement", lambda: self.displaceSignal(LicHelpers.getOppositeDirection(self.displaceDirection)))
            menu.addAction("&Change displacement", self.adjustDisplaceSignal)
            menu.addAction("&Remove displacement", lambda: self.displaceSignal(None))
            menu.addAction("&Add Arrow", self.addArrowSignal)
        else:
            arrowMenu = menu.addMenu("Displace With &Arrow")
            arrowMenu.addAction("Move Up", lambda: self.displacePartsSignal(Qt.Key_PageUp))
            arrowMenu.addAction("Move Down", lambda: self.displacePartsSignal(Qt.Key_PageDown))
            arrowMenu.addAction("Move Forward", lambda: self.displacePartsSignal(Qt.Key_Down))
            arrowMenu.addAction("Move Back", lambda: self.displacePartsSignal(Qt.Key_Up))
            arrowMenu.addAction("Move Left", lambda: self.displacePartsSignal(Qt.Key_Left))
            arrowMenu.addAction("Move Right", lambda: self.displacePartsSignal(Qt.Key_Right))

        menu.addSeparator()
        if not self.originalPart:
            arrowMenu2 = menu.addMenu("Change Part")
            arrowMenu2.addAction("Change Color", self.changeColorSignal)
            arrowMenu2.addAction("Change to Different Part", self.changeBasePartSignal)
            arrowMenu2.addAction("Change Position && Rotation", self.changePartPositionSignal)
            arrowMenu2.addAction("Duplicate Part", self.duplicatePartSignal)
            arrowMenu2.addAction("Delete Part", self.deletePartSignal)
        
        menu.exec_(event.screenPos())

    def displacePartsSignal(self, direction):
        partList = [p for p in self.scene().selectedItems() if isinstance(p, Part)]
        stack = self.scene().undoStack
        stack.beginMacro("Displace Part%s" % ('s' if len(partList) > 1 else ''))
        for part in partList:
            stack.push(BeginEndDisplacementCommand(part, direction))
        stack.endMacro()

    def createCalloutSignal(self):
        stack = self.scene().undoStack
        step = self.getStep()
        page = step.getPage()

        stack.beginMacro("Create new Callout from Parts")
        callout = step.addBlankCalloutSignal(True, False)
        self.moveToCalloutSignal(callout)
        stack.push(LayoutItemCommand(page, page.getCurrentLayout()))
        stack.endMacro()

        self.scene().fullItemSelectionUpdate(callout)

    def moveToCalloutSignal(self, callout):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part) and not item.calloutPart:
                selectedParts.append(item)
        self.scene().undoStack.push(AddPartsToCalloutCommand(callout, selectedParts))

    def removeFromCalloutSignal(self):
        selectedParts = []
        for item in self.scene().selectedItems():
            if isinstance(item, Part) and item.calloutPart:
                selectedParts.append(item)
        callout = self.calloutPart.getStep().parentItem()
        self.scene().undoStack.push(RemovePartsFromCalloutCommand(callout, selectedParts))
    
    def keyReleaseEvent(self, event):
        direction = event.key()
        if direction == Qt.Key_Plus:
            return self.displaceSignal(self.displaceDirection)
        if direction == Qt.Key_Minus:
            return self.displaceSignal(LicHelpers.getOppositeDirection(self.displaceDirection))

    def displaceSignal(self, direction):
        stack = self.scene().undoStack
        if direction:
            displacement = LicHelpers.getDisplacementOffset(direction, False, self.abstractPart.getBoundingBox())
            if not displacement:
                return
            oldPos = self.displacement if self.displacement else [0.0, 0.0, 0.0]
            newPos = [oldPos[0] + displacement[0], oldPos[1] + displacement[1], oldPos[2] + displacement[2]]

            stack.beginMacro("Displace Part && Arrow")
            stack.push(DisplacePartCommand(self, oldPos, newPos))

            newLength = LicHelpers.displacementToDistance(newPos, self.displaceDirection)
            for arrow in self.arrows:
                stack.push(AdjustArrowLength(arrow, arrow.getLength(), newLength))

            stack.endMacro()
        else:
            # Remove any displacement
            stack.push(BeginEndDisplacementCommand(self, self.displaceDirection, end = True))

    def addArrowSignal(self):
        self.addNewArrow(self.displaceDirection)
        newArrow = self.arrows.pop()
        action = AddRemoveArrowCommand(self, newArrow, len(self.arrows), True)
        self.scene().undoStack.push(action)

    def adjustDisplaceSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.DisplaceDlg(parentWidget, self.displacement, self.displaceDirection)
        parentWidget.connect(dialog, SIGNAL("changeDisplacement"), self.changeDisplacement)
        parentWidget.connect(dialog, SIGNAL("acceptDisplacement"), self.acceptDisplacement)
        dialog.exec_()

    def changeDisplacement(self, displacement, changeArrow):
        self.displacement = displacement
        if changeArrow:
            length = LicHelpers.displacementToDistance(displacement, self.displaceDirection)
            for arrow in self.arrows:
                arrow.setLength(length)
        self.getCSI().resetPixmap()

    def acceptDisplacement(self, oldDisplacement, changeArrow):
        stack = self.scene().undoStack
        if changeArrow:
            stack.beginMacro("Displace Part && Arrow")

        stack.push(DisplacePartCommand(self, oldDisplacement, self.displacement))

        if changeArrow:
            oldLength = LicHelpers.displacementToDistance(oldDisplacement, self.displaceDirection)
            for arrow in self.arrows:
                self.scene().undoStack.push(AdjustArrowLength(arrow, oldLength, arrow.getLength()))
            stack.endMacro()

    def moveToStepSignal(self, destStep):
        scene = self.scene()
        stack = scene.undoStack
        selectedParts = []
        for item in scene.selectedItems():
            if isinstance(item, Part) and not item.calloutPart:
                selectedParts.append(item)

        stack.beginMacro("move Parts to Step")

        currentStep = self.getStep()
        scene.undoStack.push(MovePartsToStepCommand(selectedParts, destStep))

        currentPage = currentStep.getPage()
        if currentStep.isEmpty():
            scene.undoStack.push(AddRemoveStepCommand(currentStep, False))
            
        if currentPage.isEmpty():
            scene.undoStack.push(AddRemovePageCommand(scene, currentPage, False))
        stack.endMacro()
            
    def changeColorSignal(self):
        colorDict = self.getPage().instructions.colorDict
        self.scene().clearSelection()
        self.getCSI().isDirty = True
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.LDrawColorDialog(parentWidget, self.color, colorDict)
        parentWidget.connect(dialog, SIGNAL("changeColor"), self.changeColor)
        parentWidget.connect(dialog, SIGNAL("acceptColor"), self.acceptColor)
        dialog.exec_()

    def changeColor(self, newColor):
        self.color = newColor
        self.getCSI().isDirty = True
        self.getCSI().nextCSIIsDirty = True
        self._dataString = None
        if self.calloutPart:
            self.calloutPart.changeColor(newColor)
        self.update()
    
    def acceptColor(self, oldColor):
        action = ChangePartColorCommand(self, oldColor, self.color)
        self.scene().undoStack.push(action)

    def changeAbstractPart(self, filename):

        step = self.getStep()

        self.setParentItem(None) # Temporarily set part's parent, so it doesn't get deleted by Qt
        step.removePart(self)

        self.filename = filename
        self.initializeAbstractPart(step.getPage().instructions)

        if self.abstractPart.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            glContext = step.getPage().instructions.glContext
            self.abstractPart.createGLDisplayList()
            self.abstractPart.resetPixmap(glContext)

        if self.calloutPart:
            self.calloutPart.changeAbstractPart(filename)

        step.addPart(self)
        step.csi.isDirty = True
        step.csi.nextCSIIsDirty = True
        if self.originalPart:
            step.parentItem().initLayout()
        else:
            step.initLayout()

    def changeBasePartSignal(self):
        dir = os.path.dirname(self.filename) if self.filename is not None else "."
        formats = LicImporters.getFileTypesString()
        filename = unicode(QFileDialog.getOpenFileName(self.scene().activeWindow(), "Lic - Open Part", dir, formats))
        fn = os.path.basename(filename)
        if fn and fn != self.filename:
            self.scene().undoStack.push(ChangeAbstractPartCommand(self, fn))

    def duplicatePartSignal(self):
        part = self.duplicate()
        self.scene().undoStack.push(AddRemovePartCommand(part, self.getStep(), True))

    def deletePartSignal(self):
        self.scene().undoStack.push(AddRemovePartCommand(self, self.getStep(), False))

    def changePartPositionSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.PositionRotationDlg(parentWidget, self.xyz(), self.xyzRotation())
        parentWidget.connect(dialog, SIGNAL("change"), self.changePosRot)
        parentWidget.connect(dialog, SIGNAL("accept"), self.acceptPosRot)
        dialog.exec_()

    def changePosRot(self, newPosition, newRotation):
        self.matrix[12] = newPosition[0]
        self.matrix[13] = newPosition[1]
        self.matrix[14] = newPosition[2]

        self.setXYZRotation(*newRotation)

        self.getCSI().isDirty = True
        self.getCSI().nextCSIIsDirty = True
        self._dataString = None
        if self.calloutPart:
            self.calloutPart.changePosRot(newPosition, newRotation)
        self.update()

    def acceptPosRot(self, oldPos, oldRot):
        action = ChangePartPosRotCommand(self, oldPos, self.xyz(), oldRot, self.xyzRotation())
        self.scene().undoStack.push(action)

class Arrow(Part):
    itemClassName = "Arrow"

    def __init__(self, direction, parentPart = None):
        red = LicHelpers.LicColor.red
        Part.__init__(self, "arrow", red(), None, False)
        
        if parentPart:
            self.setParentItem(parentPart)
        self.displaceDirection = direction
        self.displacement = [0.0, 0.0, 0.0]
        self.axisRotation = 0.0
        
        self.abstractPart = AbstractPart("arrow")
        self.matrix = LicGLHelpers.IdentityMatrix()

        x = [0.0, 20.0, 25.0, 50.0]
        y = [-5.0, -1.0, 0.0, 1.0, 5.0]

        tip = [x[0], y[2], 0.0]
        topEnd = [x[2], y[0], 0.0]
        botEnd = [x[2], y[4], 0.0]
        joint = [x[1], y[2], 0.0]
        
        tl = [x[1], y[1], 0.0]
        tr = [x[3], y[1], 0.0]
        br = [x[3], y[3], 0.0]
        bl = [x[1], y[3], 0.0]
        
        tip1 = Primitive(red(), tip + topEnd + joint, GL.GL_TRIANGLES)
        tip2 = Primitive(red(), tip + joint + botEnd, GL.GL_TRIANGLES)
        base = Primitive(red(), tl + tr + br + bl, GL.GL_QUADS)

        self.abstractPart.primitives.append(tip1)
        self.abstractPart.primitives.append(tip2)
        self.abstractPart.primitives.append(base)
        self.abstractPart.createGLDisplayList()

    def data(self, index):
        x, y, z = LicHelpers.GLMatrixToXYZ(self.matrix)
        return "%s  (%.1f, %.1f, %.1f)" % (self.abstractPart.filename, x, y, z)

    def duplicate(self, parentPart = None):
        p = Arrow(self.displaceDirection, parentPart)
        p.matrix = list(self.matrix)
        p.displacement = list(self.displacement)
        p.axisRotation = self.axisRotation
        p.setLength(self.getLength())
        p.setParentItem(parentPart if parentPart else self.parentItem())
        return p

    def positionToBox(self, direction, box):
        y = box.getBottomOffset()
        self.addToPosition(0, y + self.length, 0)

    def addToPosition(self, x, y, z):
        self.matrix[12] += x
        self.matrix[13] += y
        self.matrix[14] += z
        
    def setPosition(self, x, y, z):
        self.matrix[12] = x
        self.matrix[13] = y
        self.matrix[14] = z
        
    def doGLRotation(self):
        
        d = self.displaceDirection
        if d == Qt.Key_PageUp:  # Up
            GL.glRotatef(-90, 0.0, 0.0, 1.0)
            GL.glRotatef(45, 1.0, 0.0, 0.0)
        elif d == Qt.Key_PageDown:  # Down
            GL.glRotatef(90, 0.0, 0.0, 1.0)
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        elif d == Qt.Key_Left:  # Left
            GL.glRotatef(90, 0.0, 1.0, 0.0)
            GL.glRotatef(225, 1.0, 0.0, 0.0)
        elif d == Qt.Key_Right:  # Right
            GL.glRotatef(-90, 0.0, 1.0, 0.0)
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        elif d == Qt.Key_Up:  # Back
            GL.glRotatef(180, 0.0, 0.0, 1.0)
            GL.glRotatef(45, 1.0, 0.0, 0.0)
        elif d == Qt.Key_Down:  # Forward
            GL.glRotatef(-45, 1.0, 0.0, 0.0)

        if self.axisRotation:
            GL.glRotatef(self.axisRotation, 1.0, 0.0, 0.0)

    def callGLDisplayList(self, useDisplacement = False):
        if not useDisplacement:
            return

        # Must be called inside a glNewList/EndList pair
        if self.color is not None:
            color = list(self.color.rgba)
            if self.isSelected():
                color[3] = 0.5
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(color)

        matrix = list(self.matrix)
        if self.displacement:
            matrix[12] += self.displacement[0]
            matrix[13] += self.displacement[1]
            matrix[14] += self.displacement[2]
        GL.glPushMatrix()
        GL.glMultMatrixf(matrix)

        #LicGLHelpers.drawCoordLines()
        self.doGLRotation()

        if self.isSelected():
            self.drawGLBoundingBox()

        GL.glCallList(self.abstractPart.glDispID)
        GL.glPopMatrix()

        if self.color is not None:
            GL.glPopAttrib()

    def getOffsetFromPart(self, part):
    
        direction = part.displaceDirection
    
        if direction == Qt.Key_Up:
            return self.x() - part.bx2()
        elif direction == Qt.Key_Down:
            return part.bx() - self.x()
    
        elif direction == Qt.Key_PageUp:
            return self.y() - part.by()
        elif direction == Qt.Key_PageDown:
            return part.by2() - self.y()
    
        elif direction == Qt.Key_Left:
            return self.z() - part.bz2() 
        elif direction == Qt.Key_Right:
            return part.bz() - self.z()

    def getCSI(self):
        return self.parentItem().parentItem().parentItem()  # Part->PartItem->CSI

    def getLength(self):
        p = self.abstractPart.primitives[-1]
        return p.points[3]

    def setLength(self, length):
        p = self.abstractPart.primitives[-1]
        p.points[3] = length
        p.points[6] = length
        self.abstractPart.resetBoundingBox()
        self.abstractPart.createGLDisplayList()
        self._dataString = None
    
    def adjustLength(self, offset):
        self.setLength(self.getLength() + offset)
        
    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        
        #stack = self.scene().undoStack
        #menu.addAction("Move &Forward", lambda: self.displaceSignal(LicHelpers.getOppositeDirection(self.displaceDirection)))
        #menu.addAction("Move &Back", lambda: self.displaceSignal(self.displaceDirection))
        #menu.addAction("&Longer", lambda: stack.push(AdjustArrowLength(self, 20)))
        #menu.addAction("&Shorter", lambda: stack.push(AdjustArrowLength(self, -20)))
        menu.addAction("&Change Position and Length", self.adjustDisplaceSignal)
        menu.addAction("&Remove", self.removeSignal)
        menu.exec_(event.screenPos())

    def removeSignal(self):
        part = self.parentItem()
        action = AddRemoveArrowCommand(part, self, part.arrows.index(self), False)
        self.scene().undoStack.push(action)

    def adjustDisplaceSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.ArrowDisplaceDlg(parentWidget, self)
        parentWidget.connect(dialog, SIGNAL("changeDisplacement"), self.changeDisplacement)
        parentWidget.connect(dialog, SIGNAL("changeLength"), self.changeLength)
        parentWidget.connect(dialog, SIGNAL("changeRotation"), self.changeRotation)
        parentWidget.connect(dialog, SIGNAL("accept"), self.accept)
        dialog.exec_()

    def changeDisplacement(self, displacement):
        self.displacement = displacement
        self.getCSI().resetPixmap()

    def changeLength(self, length):
        self.setLength(length)
        self.getCSI().resetPixmap()

    def changeRotation(self, rotation):
        self.axisRotation = rotation
        self.getCSI().resetPixmap()

    def accept(self, oldDisplacement, oldLength, oldRotation):
        stack = self.scene().undoStack
        stack.beginMacro("Change Arrow Position")
        self.scene().undoStack.push(DisplacePartCommand(self, oldDisplacement, self.displacement))
        self.scene().undoStack.push(AdjustArrowLength(self, oldLength, self.getLength()))
        self.scene().undoStack.push(AdjustArrowRotation(self, oldRotation, self.axisRotation))
        stack.endMacro()

class Primitive(object):
    """
    Not a primitive in the LDraw sense, just a single line/triangle/quad.
    Used mainly to construct a GL display list for a set of points.
    """

    def __init__(self, color, points, type, winding = GL.GL_CW):
        self.color = color
        self.type = type
        self.points = points
        self.winding = winding
        self._boundingBox = None

    def getBoundingBox(self):
        if self._boundingBox:
            return self._boundingBox
        
        p = self.points
        box = BoundingBox(p[0], p[1], p[2])
        box.growByPoints(p[3], p[4], p[5])
        if self.type != GL.GL_LINES:
            box.growByPoints(p[6], p[7], p[8])
            if self.type == GL.GL_QUADS:
                box.growByPoints(p[9], p[10], p[11])
                
        self._boundingBox = box
        return box

    def resetBoundingBox(self):
        self._boundingBox = None

    def addNormal(self, p1, p2, p3):
        Bx = p2[0] - p1[0]
        By = p2[1] - p1[1]
        Bz = p2[2] - p1[2]

        Cx = p3[0] - p1[0]
        Cy = p3[1] - p1[1]
        Cz = p3[2] - p1[2]

        Ax = (By * Cz) - (Bz * Cy)
        Ay = (Bz * Cx) - (Bx * Cz)
        Az = (Bx * Cy) - (By * Cx)
        l = math.sqrt((Ax*Ax)+(Ay*Ay)+(Az*Az))
        if l != 0:
            Ax /= l
            Ay /= l
            Az /= l
        return [Ax, Ay, Az]

    def pointWinding(self, p0, p1, p2):
        
        dx1 = p1[0] - p0[0]
        dy1 = p1[1] - p0[1]
        dx2 = p2[0] - p0[0]
        dy2 = p2[1] - p0[1]
        
        if (dx1*dy2 > dy1*dx2):
            return +1
        if (dx1*dy2 < dy1*dx2):
            return -1
        if ((dx1*dx2 < 0) or (dy1*dy2 < 0)):
            return -1
        if ((dx1*dx1 + dy1*dy1) < (dx2*dx2 + dy2*dy2)):
            return +1
        return 0
    
    def callGLDisplayList(self):

        # must be called inside a glNewList/EndList pair
        p = self.points
        if self.type == GL.GL_LINES:
            if len(self.points) > 6:  # This is a conditional line
                return

            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4f(0.0, 0.0, 0.0, 1.0)
            GL.glBegin(self.type)
            GL.glVertex3f(p[0], p[1], p[2])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glEnd()
            GL.glPopAttrib()
            return

        if self.color is not None:
            GL.glPushAttrib(GL.GL_CURRENT_BIT)
            GL.glColor4fv(self.color.rgba)

        if self.winding == GL.GL_CCW:
            normal = self.addNormal(p[0:3], p[3:6], p[6:9])
            #GL.glBegin( GL.GL_LINES )
            #GL.glVertex3f(p[3], p[4], p[5])
            #GL.glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #GL.glEnd()

            GL.glBegin(self.type)
            GL.glNormal3fv(normal)
            GL.glVertex3f(p[0], p[1], p[2])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glVertex3f(p[6], p[7], p[8])
            if self.type == GL.GL_QUADS:
                GL.glVertex3f(p[9], p[10], p[11])
            GL.glEnd()
            
        elif self.winding == GL.GL_CW:
            normal = self.addNormal(p[0:3], p[6:9], p[3:6])
            #GL.glBegin( GL.GL_LINES )
            #GL.glVertex3f(p[3], p[4], p[5])
            #GL.glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #GL.glEnd()

            GL.glBegin(self.type)
            GL.glNormal3fv(normal)
            GL.glVertex3f(p[0], p[1], p[2])
            if self.type == GL.GL_QUADS:
                GL.glVertex3f(p[9], p[10], p[11])
            GL.glVertex3f(p[6], p[7], p[8])
            GL.glVertex3f(p[3], p[4], p[5])
            GL.glEnd()

        if self.color is not None:
            GL.glPopAttrib()

    def drawConditionalLines(self):
        if self.type != GL.GL_LINES or len(self.points) != 12:
            return  # Not a conditional line
        
        p = self.points
        p0 = GLU.gluProject(p[0], p[1], p[2])
        p1 = GLU.gluProject(p[3], p[4], p[5])
        c0 = GLU.gluProject(p[6], p[7], p[8])
        c1 = GLU.gluProject(p[9], p[10], p[11])
        
        winding1 = self.pointWinding(p0, p1, c0)
        winding2 = self.pointWinding(p0, p1, c1)
        if winding1 != winding2:
            return
    
        GL.glPushAttrib(GL.GL_CURRENT_BIT)
        GL.glColor4f(1.0, 1.0, 0.0, 1.0)
        GL.glBegin(self.type)
        GL.glVertex3f(p[0], p[1], p[2])
        GL.glVertex3f(p[3], p[4], p[5])
        GL.glEnd()
        GL.glPopAttrib()
