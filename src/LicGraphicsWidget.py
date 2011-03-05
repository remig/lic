"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicGraphicsScene.py) is part of Lic.

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
from LicCustomPages import Page
import LicUndoActions
import LicLayout
import LicGLHelpers
import LicQtWrapper

class LicGraphicsView(QGraphicsView):
    def __init__(self, parent):
        QGraphicsView.__init__(self,  parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setCacheMode(QGraphicsView.CacheNone)
        self.setAcceptDrops(True)
        self.setOptimizationFlag(8, True)  # TODO: When PyQt is fixed, this 8 should be QGraphicsView.IndirectPainting

    def scaleView(self, scaleFactor):
        
        if scaleFactor == 1.0:
            self.scene().scaleFactor = scaleFactor
            self.resetTransform()
        else:
            factor = self.matrix().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()
            if factor >= 0.15 and factor <= 5:
                self.scene().scaleFactor = factor
                self.scale(scaleFactor, scaleFactor)

    def scaleToFit(self):
        vw, vh = self.geometry().size() - QSize(20, 20)
        pw, ph = Page.PageSize * self.scene().scaleFactor
        
        if (pw > vw) or (ph > pw) or ((pw < (vw-50)) and (ph < (vh-50))):  # Ensure we should scale
            if vw - pw < vh - ph:
                self.scaleView(float(vw) / pw)  # Scale to fit width
            else:
                self.scaleView(float(vh) / ph)  # Scale to fit height
        
    def dragEnterEvent(self, event):
        self.parentWidget().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        pass  # Necessary for file drag & drop to work on the graphicsView

    def dropEvent(self, event):
        self.parentWidget().dropEvent(event)

class LicGraphicsScene(QGraphicsScene):

    PageViewContinuous = -1
    PageViewContinuousFacing = -2
        
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)
        self.setBackgroundBrush(Qt.gray)
        self.reset()

    def reset(self):
        self.scaleFactor = 1.0
        self.pagesToDisplay = 1
        self.currentPage = None
        self.pages = []
        self.selectedSubmodels = []
        self.guides = []
        self.xSnapLine = self.createSnapLine()
        self.ySnapLine = self.createSnapLine()
        self.snapToGuides = True
        self.snapToItems = True
        self.renderMode = 'full' # Or "background" or "foreground"

    def createSnapLine(self):
        snapLine = QGraphicsLineItem()
        pen = QPen(Qt.darkCyan)
        pen.setWidth(2)
        snapLine.setPen(pen)
        snapLine.setZValue(10000)  # Put on top of everything else
        snapLine.hide()
        self.addItem(snapLine)
        return snapLine

    def saveSelection(self):  # TODO: implement this, so we can save & restore selections on image export
        #self.savedSelection = list(self.selectedItems())
        pass

    def restoreSelection(self):
        pass
            
    def clearSelection(self):
        self.clearSelectedParts()
        self.selectedSubmodels = []
        QGraphicsScene.clearSelection(self)
        
    def clearSelectedParts(self):
        partList = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                partList.append(item)
        if partList:
            for part in partList[:-1]:
                part.setSelected(False, False)
            partList[-1].setSelected(False, True)

    def clear(self):
        QGraphicsScene.clear(self)
        self.reset()

    def drawOneItem(self, painter, item, option, widget):
        painter.save()
        painter.setMatrix(item.sceneMatrix(), True)
        item.paint(painter, option, widget)
        painter.restore()

    def drawItems(self, painter, items, options, widget):

        LicGLHelpers.clear([0.62, 0.62, 0.65, 1.0])

        # First draw all items that are not annotations
        if self.renderMode == 'full' or self.renderMode == 'background':
            for i, item in enumerate(items):
                if item.isVisible() and (not hasattr(item, 'isAnnotation') or not item.isAnnotation):
                    self.drawOneItem(painter, item, options[i], widget)

        if widget and self.renderMode == 'full':

            # Build list of pages to be drawn (if any)
            rect = QRectF(self.views()[0].mapToScene(QPoint()), QSizeF(widget.size()) / self.scaleFactor)
            pagesToDraw = []
            for page in self.pages:
                if page.isVisible() and rect.intersects(page.rect().translated(page.pos())):
                    pagesToDraw.append(page)

            if pagesToDraw:
                # Setup the GL items to be drawn & the necessary context
                painter.beginNativePainting()
                LicGLHelpers.initFreshContext(False)
    
                # Draw all GL items
                for page in pagesToDraw:
                    page.drawGLItems(rect)
    
                LicGLHelpers.setupForQtPainter()  # Reset all GL lighting, so that subsequent drawing is not affected
                painter.endNativePainting()
            
        # Draw all annotation
        if self.renderMode == 'full' or self.renderMode == 'foreground':
            for i, item in enumerate(items):
                if item.isVisible() and (hasattr(item, 'isAnnotation') and item.isAnnotation):
                    self.drawOneItem(painter, item, options[i], widget)

    def pageUp(self):
        self.clearSelection()
        if self.pages and self.currentPage:
            self.selectPageFullUpdate(max(self.currentPage._number - 1, self.pages[0]._number))

    def pageDown(self):
        self.clearSelection()
        if self.pages and self.currentPage:
            self.selectPageFullUpdate(min(self.pages[-1]._number, self.currentPage._number + 1))

    def selectFirstPage(self):
        if self.pages:
            self.selectPageFullUpdate(1)

    def selectLastPage(self):
        if self.pages:
            self.selectPageFullUpdate(self.pages[-1]._number)

    def selectCurrentPage(self):
        if self.currentPage:
            self.selectPageFullUpdate(self.currentPage._number)

    def selectPageFullUpdate(self, pageNumber):
        self.selectPage(pageNumber)
        self.currentPage.setSelected(True)
        self.emit(SIGNAL("sceneClick"))

    def refreshView(self):
        self.setPagesToDisplay(self.pagesToDisplay)
        
    def selectPage(self, pageNumber):
        # Don't call currentPage.setSelected() from here!  Must be done later
        for page in self.pages:
            if self.pagesToDisplay == 1 and page._number == pageNumber:
                page.setPos(0, 0)
                page.show()
                self.currentPage = page
            elif self.pagesToDisplay == 2:
                if pageNumber % 2:  # draw odd pages on right
                    if page._number == pageNumber:
                        page.setPos(Page.PageSize.width() + 20, 0)
                        page.show()
                        self.currentPage = page
                    elif page._number == pageNumber - 1:
                        page.show()
                        page.setPos(10, 0)
                    else:
                        page.hide()
                        page.setPos(0, 0)
                else:  # draw even pages on left
                    if page._number == pageNumber:
                        page.setPos(10, 0)
                        page.show()
                        self.currentPage = page
                    elif page._number == pageNumber + 1:
                        page.setPos(Page.PageSize.width() + 20, 0)
                        page.show()
                    else:
                        page.hide()
                        page.setPos(0, 0)
            elif self.pagesToDisplay == self.PageViewContinuous or self.pagesToDisplay == self.PageViewContinuousFacing:
                if page._number == pageNumber:
                    self.currentPage = page
            else:
                page.hide()
                page.setPos(0, 0)

        self.scrollToPage(self.currentPage)

    def selectionChangedHandler(self):
        selList = self.selectedItems()
        if self.pagesToDisplay == 1 or not selList or isinstance(selList[-1], Guide):
            return
        self.scrollToPage(selList[-1].getPage())
    
    def fullItemSelectionUpdate(self, *itemList):
        self.clearSelection()
        for item in itemList:
            item.setSelected(True)
        self.emit(SIGNAL("sceneClick"))

    def scrollToPage(self, page):
        if page is None:
            return
        view = self.views()[0]
        view.setInteractive(False)
        view.centerOn(page)
        view.setInteractive(True)
        self.currentPage = page
        
    def showOnePage(self):
        self.pagesToDisplay = 1
        self.setSceneRect(0, 0, Page.PageSize.width(), Page.PageSize.height())
        self.maximizeGuides(Page.PageSize.width(), Page.PageSize.height())
        for page in self.pages:
            page.hide()
            page.setPos(0.0, 0.0)
        self.selectCurrentPage()
    
    def showTwoPages(self):
        if len(self.pages) < 2:
            return self.showOnePage()

        self.pagesToDisplay = 2
        self.setSceneRect(0, 0, (Page.PageSize.width() * 2) + 30, Page.PageSize.height() + 20)
        self.maximizeGuides(Page.PageSize.width() * 2, Page.PageSize.height())

        for page in self.pages:
            page.hide()
            page.setPos(0, 0)

        index = self.pages.index(self.currentPage)
        if self.currentPage == self.pages[-1]:
            p1 = self.pages[index - 1]
            p2 = self.currentPage
        else:
            p1 = self.currentPage
            p2 = self.pages[index + 1]
        
        p1.setPos(10, 0)
        p1.show()
        p2.setPos(Page.PageSize.width() + 20, 0)
        p2.show()
        self.selectCurrentPage()

    def continuous(self):
        self.pagesToDisplay = self.PageViewContinuous
        pc = max(len(self.pages), 1)
        ph = Page.PageSize.height()
        height = (10 * (pc + 1)) + (ph * pc)
        self.setSceneRect(0, 0, Page.PageSize.width() + 20, height)
        self.maximizeGuides(0, height)
                
        for i, page in enumerate(self.pages):
            page.setPos(10, (10 * (i + 1)) + (ph * i))
            page.show()
        self.selectCurrentPage()

    def continuousFacing(self):
        if len(self.pages) < 3:
            return self.continuous()
        self.pagesToDisplay = self.PageViewContinuousFacing
        pw = Page.PageSize.width()
        ph = Page.PageSize.height()
        rows = sum(divmod(len(self.pages) - 1, 2)) + 1
        width = pw + pw + 30
        height = (10 * (rows + 1)) + (ph * rows)
        self.setSceneRect(0, 0, width, height)
        self.maximizeGuides(width, height)
            
        self.pages[0].setPos(10, 10)  # Template page first
        self.pages[0].show()
        
        for i, page in enumerate(self.pages[1:]):
            i += 2
            x = 10 + ((pw + 10) * (i % 2))
            y = (10 * ((i // 2) + 1)) + (ph * (i // 2))
            page.setPos(x, y)
            page.show()
        self.selectCurrentPage()

    def setPagesToDisplay(self, pagesToDisplay):
        if pagesToDisplay == self.PageViewContinuous:
            return self.continuous()
        if pagesToDisplay == self.PageViewContinuousFacing:
            return self.continuousFacing()
        if pagesToDisplay == 2:
            return self.showTwoPages()
        return self.showOnePage()

    def addItem(self, item):
        QGraphicsScene.addItem(self, item)
        if isinstance(item, Page):
            self.pages.append(item)
            self.pages.sort(key = lambda x: x._number)
            self.setPagesToDisplay(self.pagesToDisplay)

    def sortPages(self):
        self.pages.sort(key = lambda x: x._number)
                
    def removeItem(self, item):
        self.emit(SIGNAL("itemDeleted"), item)
        QGraphicsScene.removeItem(self, item)
        if not isinstance(item, Page):
            return
        if isinstance(item, Page) and item in self.pages:
            self.pages.remove(item)
            if self.pagesToDisplay == self.PageViewContinuous:
                self.continuous()
            elif self.pagesToDisplay == self.PageViewContinuousFacing:
                self.continuousFacing()

    def removeAllGuides(self):
        self.undoStack.beginMacro("Remove all guides")
        for guide in list(self.guides):
            self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, guide, False))
        self.undoStack.endMacro()

    def addGuide(self, orientation, pos):
        guide = Guide(orientation, self)
        guide.setPos(pos)
        self.guides.append(guide)
        self.addItem(guide)

    def addNewGuide(self, orientation):
        self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, Guide(orientation, self), True))

    def maximizeGuides(self, width, height):
        for guide in self.guides:
            if guide.orientation == LicLayout.Vertical and height > 0:
                guide.setLength(height)
            elif guide.orientation == LicLayout.Horizontal and width > 0:
                guide.setLength(width)

    def snap(self, item):
        if not self.snapToGuides and not self.snapToItems:
            return # User disabled snap
         
        snapDistance = 20
        margin = 20

        # Hide any existing snap guide lines
        self.xSnapLine.hide()
        self.ySnapLine.hide()
        
        # Build dict of all guides and page items and their [left, right, top, bottom] points
        itemDict = {}
        
        if self.snapToGuides:
            for guide in self.guides:
                guidePt = guide.mapToScene(guide.line().p1())
                itemDict[guide] = [guidePt.x(), guidePt.y()]

        if self.snapToItems:
            for pageItem in item.getPage().getAllChildItems():
                if isinstance(pageItem, Step):
                    continue
                if item.isAncestorOf(pageItem):
                    continue
                if pageItem is item:
                    continue
                itemDict[pageItem] = pageItem.getSceneCornerList()
                
                if isinstance(pageItem, Page):  # Bump page points inwards so we snap to margin, not outside edge
                    itemDict[pageItem][0] += margin
                    itemDict[pageItem][1] += margin
                    itemDict[pageItem][2] -= margin
                    itemDict[pageItem][3] -= margin

        if not itemDict:
            return  # Nothing to snap to
        
        # Get top-left & bottom-right corners of target item
        tl, br = item.getSceneCorners()
        
        # Placeholders for current nearest corner & item
        nearestX = dx = x = nearestY = dy = y = 100
        newXItem = newYItem = None
        
        def snapEdge(targetEdge, itemEdge, nearest, dt, t, currentItem, newItem):
            i = targetEdge - itemEdge
            if abs(i) < nearest:
                return abs(i), i, targetEdge, newItem
            return nearest, dt, t, currentItem
            
        def snapX(targetEdge, itemEdge):
            return snapEdge(targetEdge, itemEdge, nearestX, dx, x, newXItem, pageItem)

        def snapY(targetEdge, itemEdge):
            return snapEdge(targetEdge, itemEdge, nearestY, dy, y, newYItem, pageItem)

        for pageItem, pts in itemDict.items():

            if isinstance(pageItem, Guide):
                left, top = pts
                right, bottom = pts
            else:
                left, top, right, bottom = pts

            nearestX, dx, x, newXItem = snapX(left, tl.x())   # Compare left edges
            nearestX, dx, x, newXItem = snapX(right, br.x())  # Compare right edges
                
            nearestY, dy, y, newYItem = snapY(top, tl.y())     # Compare top edges
            nearestY, dy, y, newYItem = snapY(bottom, br.y())  # Compare bottom edges
            
            if not isinstance(pageItem, Page):
                
                # Check if two items line up horizontally / vertically.  Snap with margin on opposite sides if so
                if (top < tl.y() and bottom > br.y()) or (top > tl.y() and bottom < br.y()):
                    nearestX, dx, x, newXItem = snapX(right + margin, tl.x())  # Snap item's left edge to right w. margin
                    nearestX, dx, x, newXItem = snapX(left - margin, br.x())   # Snap item's right edge to left

                if (left < tl.x() and right > br.x()) or (left > tl.x() and right < br.x()):
                    nearestY, dy, y, newYItem = snapY(bottom + margin, tl.y()) # Snap item's bottom edge to top w. margin
                    nearestY, dy, y, newYItem = snapY(top - margin, br.y())    # Snap item's top edge to bottom 

        # Snap item into position
        if nearestX < snapDistance:
            item.moveBy(dx, 0)
        if nearestY < snapDistance:
            item.moveBy(0, dy)

        tl, br = item.getSceneCorners() # Get top-left & bottom-right corners of newly positioned item
    
        # Position a little snap guide line between item & snapped-to item
        if nearestX < snapDistance:
            if isinstance(newXItem, Guide):
                top, bottom = tl.y() + 10, br.y() - 10
            else:
                left, top, right, bottom = itemDict[newXItem]  # Look up item points to snap to
                
            self.xSnapLine.setLine(x, min(top, tl.y()), x, max((bottom, br.y()))) # Position  snap guide line
            self.xSnapLine.show()

        if nearestY < snapDistance:
            if isinstance(newYItem, Guide):
                left, right = tl.x() + 10, br.x() - 10
            else:
                left, top, right, bottom = itemDict[newYItem]  # Look up item points to snap to
                
            self.ySnapLine.setLine(min(left, tl.x()), y, max((right, br.x())), y) # Position  snap guide line
            self.ySnapLine.show()
    
    def mouseReleaseEvent(self, event):

        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)

        QGraphicsScene.mouseReleaseEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

        self.emit(SIGNAL("sceneClick"))
        
    def mousePressEvent(self, event):
        
        # Need to compare the selection list before and after selection, to deselect any selected parts
        parts = []
        for item in self.selectedItems():
            if isinstance(item, Part):
                parts.append(item)

        QGraphicsScene.mousePressEvent(self, event)

        selItems = self.selectedItems()
        for part in parts:
            if not part in selItems:
                part.setSelected(False)

    def contextMenuEvent(self, event):

        # We can't use the default handler at all because it calls the menu of the 
        # item that was *right-clicked on*, not the menu of the selected items.
        # So check if clicked item is selected.
        clickedItem = self.itemAt(event.scenePos())
        if clickedItem and clickedItem.isSelected():
            return clickedItem.contextMenuEvent(event)
        
        selList = self.selectedItems()
        if selList:
            return selList[-1].contextMenuEvent(event)
        event.ignore()

    def keyPressEvent(self, event):
        pass  # Need this to properly ignore built-in press events
    
    def keyReleaseEvent(self, event):
        if not self.pages:
            return  # No pages = nothing to do here

        for item in self.selectedItems():
            if isinstance(item, Part):
                item.keyReleaseEvent(event)
                return

        key = event.key()
        if key == Qt.Key_PageUp:
            return self.pageUp()
        if key == Qt.Key_PageDown:
            return self.pageDown()
        if key == Qt.Key_Home:
            return self.selectFirstPage()
        if key == Qt.Key_End:
            return self.selectLastPage()

        x = y = 0
        offset = 1
        if event.modifiers() & Qt.ShiftModifier:
            offset = 20 if event.modifiers() & Qt.ControlModifier else 5

        if key == Qt.Key_Left:
            x = -offset
        elif key == Qt.Key_Right:
            x = offset
        elif key == Qt.Key_Up:
            y = -offset
        elif key == Qt.Key_Down:
            y = offset
        else:
            event.ignore()  # We do not handle this key stroke here - pass it on and return
            return

        movedItems = []
        for item in self.selectedItems():
            if isinstance(item, Page):
                continue  # Pages cannot be moved

            item.oldPos = item.pos()
            item.moveBy(x, y)
            if not isinstance(item, CalloutArrowEndItem):
                movedItems.append(item)

        if movedItems:
            self.emit(SIGNAL("itemsMoved"), movedItems)
        event.accept()

class Guide(QGraphicsLineItem):
    
    extends = 500
    
    def __init__(self, orientation, scene):
        QGraphicsLineItem.__init__(self)
        
        self.orientation = orientation
        self.setFlags(LicQtWrapper.AllFlags)
        self.setPen(QPen(QColor(0, 0, 255, 128)))  # Blue 1/2 transparent
        #self.setPen(QPen(QBrush(QColor(0, 0, 255, 128)), 1.5))  # Blue 1/2 transparent, 1.5 thick
        self.setZValue(10000)  # Put on top of everything else

        dx = scene.views()[0].horizontalScrollBar().value()
        dy = scene.views()[0].verticalScrollBar().value()
        viewRect = scene.views()[0].geometry()
        sceneRect = scene.sceneRect()

        length = scene.sceneRect().width() if orientation == LicLayout.Horizontal else scene.sceneRect().height()
        x, y = (min(viewRect.width(), sceneRect.width()) / 2.0) + dx, (min(viewRect.height(), sceneRect.height()) / 2.0) + dy

        if orientation == LicLayout.Horizontal:
            self.setCursor(Qt.SplitVCursor)
            self.setPos(0, y)
            self.setLine(-Guide.extends, 0, length + Guide.extends, 0)
        else:
            self.setCursor(Qt.SplitHCursor)
            self.setPos(x, 0)
            self.setLine(0, -Guide.extends, 0, length + Guide.extends)

    def setLength(self, length):
        line = self.line()
        line.setLength(length + Guide.extends + Guide.extends)
        self.setLine(line)

    def mouseMoveEvent(self, event):
        if self.orientation == LicLayout.Horizontal:
            x = self.pos().x()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(x, self.pos().y())
        else:
            y = self.pos().y()
            QGraphicsLineItem.mouseMoveEvent(self, event)
            self.setPos(self.pos().x(), y)
