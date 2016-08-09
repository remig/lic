"""
    LIC - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne
    Copyright (C) 2015 Jeremy Czajkowski

    This file (LicGraphicsScene.py) is part of LIC.

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

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from LicAssistantWidget import LicPlacementAssistant
from LicCustomPages import *
from LicDialogs import MessageDlg
import LicGLHelpers
import LicLayout
from LicModel import *
from LicTemplate import TemplateCSI, TemplatePLIItem, TemplateLineItem
import LicUndoActions


class LicGraphicsView(QGraphicsView):
    def __init__(self, parent):
        QGraphicsView.__init__(self, parent)

        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setCacheMode(QGraphicsView.CacheNone)
        self.setAcceptDrops(True)
        self.setOptimizationFlag(8, True)
        self.viewport().setAttribute(Qt.WA_StyledBackground, True)

    def scaleView(self, scaleFactor):
        if self.scene().items().__len__() > 2:
            if scaleFactor == 1.0:
                self.scene().scaleFactor = scaleFactor
                self.resetTransform()
            else:
                factor = self.matrix().scale(scaleFactor, scaleFactor).mapRect(QRectF(0, 0, 1, 1)).width()
                if factor >= 0.15 and factor <= 5:
                    self.scene().scaleFactor = factor
                    self.scale(scaleFactor, scaleFactor)

        return self.scene().scaleFactor

    def scaleToFit(self):
        vw, vh = self.geometry().size() - QSize(20, 20)
        pw, ph = Page.PageSize * self.scene().scaleFactor
        
        if (pw > vw) or (ph > pw) or ((pw < (vw - 50)) and (ph < (vh - 50))):  # Ensure we should scale
            if vw - pw < vh - ph:
                self.scaleView(float(vw) / pw)  # Scale to fit width
            else:
                self.scaleView(float(vh) / ph)  # Scale to fit height
                          
        if self.verticalScrollBar().isVisible() and not self.horizontalScrollBar().isVisible():
            self.scaleView( float(vh) / ph )
                    
        return self.scene().scaleFactor
        
    def dragEnterEvent(self, event):
        self.parentWidget().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        pass  # Necessary for file drag & drop to work on the graphicsView

    def dropEvent(self, event):
        self.parentWidget().dropEvent(event)
        

class LicGraphicsScene(QGraphicsScene):

    PageViewContinuous = -1
    PageViewContinuousFacing = -2
    hasMargins = False
    
    _staticGuides = []
    _crossGuides = []
    _selected = []
    
    _catchTheMouse = False
    # For LicDialogs.MessageDlg single instance
    dialog = None
    # For LicAssistantWidget.LicPlacementAssistant single instance
    assist = None
    
        
    def __init__(self, parent):
        QGraphicsScene.__init__(self, parent)
        self.setBackgroundBrush(Qt.gray)
        self.reset()
                
    def __getCatchTheMouse(self):
        return self._catchTheMouse
    
    def __setCatchTheMouse(self, state):
        self._catchTheMouse = state
        if state:
            self.saveSelection()
        else:
            self.restoreSelection()
        
    catchTheMouse = property(__getCatchTheMouse, __setCatchTheMouse)    
        
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
        
        self.renderMode = 'full'  # Or "background" or "foreground"

        self.guide1v = None
        self.guide2v = None
        self.guide1h = None
        self.guide2h = None        

    def markToMove(self, part=None):       
        if self.assist is None: 
            self.assist = LicPlacementAssistant(self.views()[0])
        self.assist.setItemtoMove(part)
        
    def createSnapLine(self):
        snapLine = QGraphicsLineItem()
        pen = QPen(Qt.darkCyan)
        pen.setWidth(2)
        snapLine.setPen(pen)
        snapLine.setZValue(10000)  # Put on top of everything else
        snapLine.hide()
        self.addItem(snapLine)
        return snapLine

    def saveSelection(self):  
        self._selected = list(self.selectedItems())

    def restoreSelection(self):
        if [] != self._selected:
            for item in self._selected:
                item.setSelected(True)
            
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
        if self.views().__len__() > 0:
            self.views()[0].resetTransform()
            self.update()        
            
    def drawForeground(self, painter, rect):
        """
        In general, you should, and in fact mostly cannot paint outside paint events 
        (if you really really need this, you have to enable painting outside of the paintEvent 
        by setting the flag Qt::WA_PaintOutsidePaintEvent. This is highly discouraged, though!).
        If you want to paint in the QGraphiscView, You should reimplement QGraphicsView::paintEvent().
        
        However, the correct solution is to use one of the two dedicated functions in QGraphicsView 
        that allow you to paint behind all items in the background, or as overlay on top of all items:
            virtual void drawBackground ( QPainter * painter, const QRectF & rect )
            virtual void drawForeground ( QPainter * painter, const QRectF & rect )
        
        Please look in the Qt Assistant documentation in QGraphicsView for further details.
        """
        if self.items().__len__() > 2:
            return QGraphicsScene.drawForeground(self, painter, rect)
        else:
            painter.fillRect(rect, Qt.gray)
            pt = rect.bottomRight()
            painter.drawPixmap(pt[0] - 512, pt[1] - 64, QPixmap(":/emmet"))
        
    def drawOneItem(self, painter, item, option, widget):
        painter.save()
        painter.setMatrix(item.sceneMatrix(), True)
        try:
            item.paint(painter, option, widget)
        except:
            pass
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

    def pageCount(self):
        """ 
            Return only the number of pages with Construction Step Image [CSI].
            Exclude template page, title page and part list pages.  
        """
        count = 0
        for page in self.pages:
            if page.data(Qt.WhatsThisRole) == "Page":
                count += 1
        return count
        
    def selectFirstPage(self):
        if self.pages:
            self.selectPageFullUpdate(1)

    def selectLastPage(self):
        if self.pages:
            self.selectPageFullUpdate(self.pages[-1]._number)

    def selectCurrentPage(self):
        if self.currentPage:
            self.selectPageFullUpdate(self.currentPage._number)
            
    def selectNextPart(self):
        """ Focus on next|first sibling part """
        choosen = csi = None
        for item in self.selectedItems():
            if isinstance(item, (Step, CSI, Part)):
                choosen = item
                 
        if isinstance(choosen, Step):
            csi = choosen.csi
            choosen = csi.getPartList()[0]
        if isinstance(choosen, CSI):
            csi = choosen
            choosen = csi.getPartList()[0]
        if isinstance(choosen, Part):
            csi = choosen.getCSI()
            lst = csi.getPartList()
            try:
                idx = lst.index(choosen)
            except ValueError:
                idx = 0
            else:
                idx += 1
                if idx > lst.__len__() - 1:
                    idx = 0
                    
            choosen = lst[idx]
        
        if csi and choosen:
            csi.selectPart(choosen)
            self.emit(SIGNAL("sceneClick")) 

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
            self.pages.sort(key=lambda x: x._number)
            self.setPagesToDisplay(self.pagesToDisplay)

    def sortPages(self):
        self.pages.sort(key=lambda x: x._number)
                
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

    def removeBlankPages(self):
        stack = self.undoStack
        stack.beginMacro("Remove blank pages")
        for page in self.pages:
            if page.isEmpty():
                stack.push(AddRemovePageCommand(page.scene() , page , False))
        stack.endMacro()

    def removeAllGuides(self):
        self.undoStack.beginMacro("Remove all guides")
        for guide in list(self.guides):
            self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, guide, False))
        self.undoStack.endMacro()

    def removeSelectedGuides(self):
        self.undoStack.beginMacro("Remove selected guides")
        for guide in list(self.guides):
            if guide.isSelected():
                self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, guide, False))
        self.undoStack.endMacro()

    def addGuide(self, orientation, pos):
        guide = Guide(orientation, self)
        guide.setPos(pos)
        self.guides.append(guide)
        self.addItem(guide)

    def addNewGuide(self, orientation):
        self.undoStack.push(LicUndoActions.AddRemoveGuideCommand(self, Guide(orientation, self), True))

    def showHideMargins(self):
        if not isinstance(self.guide1v, FixedGuide):
            self.guide1v = FixedGuide(LicLayout.Vertical, self)
        if not isinstance(self.guide2v, FixedGuide):
            self.guide2v = FixedGuide(LicLayout.Vertical, self)
        if not isinstance(self.guide1h, FixedGuide):
            self.guide1h = FixedGuide(LicLayout.Horizontal, self)
        if not isinstance(self.guide2h, FixedGuide):
            self.guide2h = FixedGuide(LicLayout.Horizontal, self)
        self._staticGuides = [self.guide1v, self.guide2h, self.guide2v, self.guide1h]
        
        if self.hasMargins:
            for g in self._staticGuides:
                g.hide()
        
        if not self.hasMargins:
            self.guide1v.setPos(QPointF(LicLayout.PageDefaultMargin , LicLayout.PageDefaultMargin))
            self.guide2v.setPos(QPointF(self.width() - LicLayout.PageDefaultMargin , LicLayout.PageDefaultMargin))
        
            self.guide1h.setPos(QPointF(LicLayout.PageDefaultMargin , LicLayout.PageDefaultMargin))
            self.guide2h.setPos(QPointF(LicLayout.PageDefaultMargin , self.height() - LicLayout.PageDefaultMargin))
            for g in self._staticGuides:
                g.show()
            
        self.hasMargins = not self.hasMargins           
            
    def maximizeGuides(self, width, height):
        for guide in self.guides:
            if guide.orientation == LicLayout.Vertical and height > 0:
                guide.setLength(height)
            elif guide.orientation == LicLayout.Horizontal and width > 0:
                guide.setLength(width)

    def snap(self, item):
        if not self.snapToGuides and not self.snapToItems:
            return  # User disabled snap
         
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

        if self.snapToItems and isinstance(item.getPage(), (Page ,PartListPage ,TitlePage)):
            
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

            nearestX, dx, x, newXItem = snapX(left, tl.x())  # Compare left edges
            nearestX, dx, x, newXItem = snapX(right, br.x())  # Compare right edges
                
            nearestY, dy, y, newYItem = snapY(top, tl.y())  # Compare top edges
            nearestY, dy, y, newYItem = snapY(bottom, br.y())  # Compare bottom edges
            
            if not isinstance(pageItem, Page):
                
                # Check if two items line up horizontally / vertically.  Snap with margin on opposite sides if so
                if (top < tl.y() and bottom > br.y()) or (top > tl.y() and bottom < br.y()):
                    nearestX, dx, x, newXItem = snapX(right + margin, tl.x())  # Snap item's left edge to right w. margin
                    nearestX, dx, x, newXItem = snapX(left - margin, br.x())  # Snap item's right edge to left

                if (left < tl.x() and right > br.x()) or (left > tl.x() and right < br.x()):
                    nearestY, dy, y, newYItem = snapY(bottom + margin, tl.y())  # Snap item's bottom edge to top w. margin
                    nearestY, dy, y, newYItem = snapY(top - margin, br.y())  # Snap item's top edge to bottom 

        # Snap item into position
        if nearestX < snapDistance:
            item.moveBy(dx, 0)
        if nearestY < snapDistance:
            item.moveBy(0, dy)

        tl, br = item.getSceneCorners()  # Get top-left & bottom-right corners of newly positioned item
    
        # Position a little snap guide line between item & snapped-to item
        if nearestX < snapDistance:
            if isinstance(newXItem, Guide):
                top, bottom = tl.y() + 10, br.y() - 10
            else:
                left, top, right, bottom = itemDict[newXItem]  # Look up item points to snap to
                
            self.xSnapLine.setLine(x, min(top, tl.y()), x, max((bottom, br.y())))  # Position  snap guide line
            self.xSnapLine.show()

        if nearestY < snapDistance:
            if isinstance(newYItem, Guide):
                left, right = tl.x() + 10, br.x() - 10
            else:
                left, top, right, bottom = itemDict[newYItem]  # Look up item points to snap to
                
            self.ySnapLine.setLine(min(left, tl.x()), y, max((right, br.x())), y)  # Position  snap guide line
            self.ySnapLine.show()   
      
    def lockApp(self, state):  
        if self.dialog is None:
            self.dialog = MessageDlg(self.views()[0])
            
        self.dialog.setText(LicHelpers.SUBWINDOW_LOCKAPP_TEXT)
        if state:
            self.dialog.show()
        else:
            self.dialog.close()
        
        QCoreApplication.processEvents()
      
    def mouseReleaseEvent(self, event):
        if self.catchTheMouse:
            self.emit(SIGNAL("sceneClick"), event) 
            return
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
        
    def mouseMoveEvent(self, event):
        eventPos = event.scenePos()
        if self.catchTheMouse:
            if [] == self._crossGuides:
                hor = FixedGuide(LicLayout.Horizontal , self)
                ver = FixedGuide(LicLayout.Vertical , self)
                hor_2 = FixedGuide(LicLayout.Horizontal , self)
                ver_2 = FixedGuide(LicLayout.Vertical , self)
                self._crossGuides.append(hor)
                self._crossGuides.append(ver)
                self._crossGuides.append(hor_2)
                self._crossGuides.append(ver_2)
            self._crossGuides[0].setPos(eventPos)    
            self._crossGuides[1].setPos(eventPos)    
            self._crossGuides[2].setPos(LicLayout.PageDefaultMargin , eventPos.y())    
            self._crossGuides[3].setPos(eventPos.x(), LicLayout.PageDefaultMargin)    
            return
        elif [] != self._crossGuides:
            for guide in self._crossGuides:
                self.removeItem(guide)
            self._crossGuides = []
            
        return QGraphicsScene.mouseMoveEvent(self, event)    
        
    def mousePressEvent(self, event):
        if self.catchTheMouse:
            # Need to correctly handling sceneClick signal on release event
            return
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
            # On Template Page, igNOre event so all page elements can't move
            if isinstance(item, (QGraphicsSimpleTextItem, TemplateLineItem, TemplatePLIItem, TemplateCSI)):
                if item.flags().__int__() == NoMoveFlags.__int__ ():
                    return
            # Part class haVE own event
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
        offset = 20 if event.modifiers() & Qt.ShiftModifier else 1
        if event.modifiers() & Qt.ControlModifier:
            offset = 5
        
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

class FixedGuide(QGraphicsLineItem):
    
    def __init__(self, orientation, scene):
        QGraphicsItem.__init__(self, None, scene)
        self.orientation = orientation
        self.setFlags(NoFlags)
        
        sceneRect = scene.sceneRect()        
        length = sceneRect.width() if orientation == LicLayout.Horizontal else sceneRect.height()
        if orientation == LicLayout.Vertical:
            self.setLine(1, 1, 1, length - 1)
        if orientation == LicLayout.Horizontal:
            self.setLine(1, 1, length - 1, 1)
        
        self.setPen(QPen(QBrush(QColor(Qt.black) , Qt.CrossPattern), 3.0))  # Black , 2.0 thick ,Cross pattern
        self.setZValue(10000)  # Put on top of everything else
        
    def setPos(self, *args, **kwargs):
        if self.scene():
            x = args[0][0] if isinstance(args[0], (QPoint, QPointF)) else args[0]
            y = args[0][1] if isinstance(args[0], (QPoint, QPointF)) else args[1]
            line = self.line()
            length = self.scene().width() if self.orientation == LicLayout.Horizontal else self.scene().height()
            cord = x if self.orientation == LicLayout.Horizontal else y
            
            line.setLength(length - cord - LicLayout.PageDefaultMargin)
            self.setLine(line)
        return QGraphicsLineItem.setPos(self, *args, **kwargs)
                

class Guide(QGraphicsLineItem):
    
    extends = 500
    
    def __init__(self, orientation, scene):
        QGraphicsLineItem.__init__(self)
        
        self.orientation = orientation
        self.setFlags(AllFlags)
        self.setPen(QPen(QBrush(QColor(0, 0, 255, 128)), 1.5))  # Blue 1/2 transparent, 1.5 thick
        self.setZValue(10000)  # Put on top of everything else

        dx = scene.views()[0].horizontalScrollBar().value()
        dy = scene.views()[0].verticalScrollBar().value()
        viewRect = scene.views()[0].geometry()
        sceneRect = scene.sceneRect()

        length = scene.sceneRect().width() if orientation == LicLayout.Horizontal else scene.sceneRect().height()
        x, y = (min(viewRect.width(), sceneRect.width()) / 2.0) + dx, (min(viewRect.height(), sceneRect.height()) / 2.0) + dy

        if orientation == LicLayout.Horizontal:
            self.setCursor(Qt.SplitVCursor)
            self.setPos(1, y)
            self.setLine(-Guide.extends, 1, length + Guide.extends, 1)
        else:
            self.setCursor(Qt.SplitHCursor)
            self.setPos(x, 1)
            self.setLine(1, -Guide.extends, 1, length + Guide.extends)

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
            
            
