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

class Page(PageTreeManager, GraphicsRoundRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """

    itemClassName = "Page"

    PageSize = QSize(800, 600)  # Always pixels
    Resolution = 72.0           # Always pixels / inch
    NumberPos = 'right'         # One of 'left', 'right', 'oddRight', 'evenRight'

    defaultPageSize = QSize(800, 600)
    defaultResolution = 72.0

    margin = QPointF(15, 15)
    defaultFillColor = QColor(Qt.white)
    defaultBrush = QBrush(Qt.NoBrush)
    defaultPen = QPen(Qt.NoPen)

    def __init__(self, submodel, instructions, number, row):
        if not hasattr(Page.defaultPen, "cornerRadius"):
            Page.defaultPen.cornerRadius = 0

        GraphicsRoundRectItem.__init__(self, None)

        self.setPos(0, 0)
        self.setRect(0, 0, self.PageSize.width(), self.PageSize.height())
        self.setFlags(NoMoveFlags)

        self.instructions = instructions
        self.submodel = submodel
        self._number = number
        self._row = row
        self.steps = []
        self.separators = []
        self.children = []
        self.annotations = []
        self.submodelItem = None
        self.layout = GridLayout()
        self.color = Page.defaultFillColor

        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self._number), self)
        self.numberItem.setFont(QFont("Arial", 15))
        self.numberItem.setFlags(AllFlags)
        self.numberItem.data = lambda index: "Page Number Label"
        self.numberItem.itemClassName = "Page Number"
        self.children.append(self.numberItem)
        
        # Setup this page's layout lock icon
        self.lockIcon = LockIcon(self)

        # Position page number in bottom right page corner
        self.resetPageNumberPosition()
        
        # Need to explicitly add this page to scene, since it has no parent
        instructions.scene.addItem(self)

    def insetRect(self):
        r = QGraphicsRectItem.rect(self)
        inset = self.pen().width()
        if inset:
            r.adjust(inset, inset, -inset, -inset)
        return r

    def _setNumber(self, number):
        self._number = number
        self.numberItem.setText("%d" % self._number)

    def _getNumber(self):
        return self._number

    number = property(_getNumber, _setNumber)

    def getAllChildItems(self):

        items = [self, self.numberItem]

        for step in self.steps:
            items.append(step)
            items.append(step.csi)
            if step.numberItem:
                items.append(step.numberItem)
            if step.hasPLI():
                items.append(step.pli)
                for pliItem in step.pli.pliItems:
                    items.append(pliItem)
                    items.append(pliItem.numberItem)
                    if pliItem.lengthIndicator:
                        items.append(pliItem.lengthIndicator)
            if step.rotateIcon:
                items.append(step.rotateIcon)
            for callout in step.callouts:
                items.append(callout)
                items.append(callout.arrow)
                items.append(callout.arrow.tipRect)
                items.append(callout.arrow.baseRect)
                if callout.qtyLabel:
                    items.append(callout.qtyLabel)
                for step in callout.steps:
                    items.append(step)
                    items.append(step.csi)
                    if step.numberItem:
                        items.append(step.numberItem)

        for separator in self.separators:
            items.append(separator)

        if self.submodelItem:
            items.append(self.submodelItem)

        items += self.annotations
        return items

    def getExportFilename(self):
        return os.path.join(config.finalImageCachePath(), "Page_%d.png" % self._number)
    
    def getGLImageFilename(self):
        return os.path.join(config.glImageCachePath(), "Page_%d.png" % self._number)

    def getPage(self):
        return self
    
    def prevPage(self):
        i = self.submodel.pages.index(self)
        if i == 0:
            return None
        return self.submodel.pages[i - 1]

    def nextPage(self):
        i = self.submodel.pages.index(self)
        if i == len(self.submodel.pages) - 1:
            return None
        return self.submodel.pages[i + 1]
        
    def getStep(self, number):
        return self.submodel.getStep(number)

    def addStep(self, step):

        self.steps.append(step)
        self.steps.sort(key = lambda x: x._number)
        step.setParentItem(self)

        i = 0
        for i in range(len(self.children) - 1, -1, -1):
            item = self.children[i]
            if isinstance(item, Step):
                if item._number < step._number:
                    break
        self.addChild(i + 1, step)

    def getNextStepNumber(self):

        if self.steps:
            return self.steps[-1].number + 1
        
        for page in self.submodel.pages:  # Look forward through pages
            if page._number > self._number and page.steps:
                return page.steps[0].number

        for page in reversed(self.submodel.pages):  # Look back
            if page._number < self._number and page.steps:
                return page.steps[-1].number + 1

        return 1
        
    def addBlankStep(self):
        self.insertStep(Step(self, self.getNextStepNumber()))
    
    def insertStep(self, step):
        self.submodel.updateStepNumbers(step.number)
        self.addStep(step)

    def removeStep(self, step):
        self.scene().removeItem(step)
        self.steps.remove(step)
        self.children.remove(step)
        self.submodel.updateStepNumbers(step.number, -1)

    def isEmpty(self):
        return len(self.steps) == 0 and self.submodelItem is None

    def isLocked(self):
        return self.lockIcon.isLocked

    def lock(self, isLocked):
        for child in self.getAllChildItems():
            child.setFlags(NoMoveFlags if isLocked else AllFlags)
        self.setFlags(NoMoveFlags)

    def show(self):
        GraphicsRoundRectItem.show(self)
        for step in self.steps:
            if step.hasPLI():
                step.pli.show()

    def addChild(self, index, child):

        self.children.insert(index, child)

        # Adjust the z-order of all children: first child has highest z value
        length = len(self.children)
        for i, item in enumerate(self.children):
            item.setZValue(length - i)
        self.lockIcon.setZValue(length + 1)
        for i, item in enumerate(self.annotations):  # Annotations on top
            item.setZValue(length + i + 1)

    def addStepSeparator(self, index, rect = None):
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        s = QGraphicsRectItem(self)
        s.setRect(rect if rect else QRectF(0, 0, 1, 1))
        s.setFlags(AllFlags)
        s.setPen(QPen(Qt.black))
        s.setBrush(QBrush(Qt.black))
        s.itemClassName = "Separator"
        s.data = lambda index: "Step Separator"
        self.separators.append(s)
        self.addChild(index, s)
        self.scene().emit(SIGNAL("layoutChanged()"))
        return s

    def removeAllSeparators(self):
        if not self.separators:
            return
        self.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        for separator in self.separators:
            self.scene().removeItem(separator)
            self.children.remove(separator)
        del self.separators[:]
        self.scene().emit(SIGNAL("layoutChanged()"))
    
    def showSeparators(self):
        for s in self.separators:
            s.show()
    
    def hideSeparators(self):
        for s in self.separators:
            s.hide()
    
    def addSubmodelImage(self, count = 0):
        self.submodelItem = SubmodelPreview(self, self.submodel)
        self.submodelItem.setPos(Page.margin)
        self.addChild(1, self.submodelItem)
        if count > 1:
            self.submodelItem.addQuantityLabel(count)
        
    def resetSubmodelImage(self):
        if self.submodelItem:
            self.submodelItem.resetPixmap()

    def checkForLayoutOverlaps(self):
        for step in self.steps:
            if step.checkForLayoutOverlaps():
                return True
        return False
    
    def resetPageNumberPosition(self):
        rect = self.numberItem.rect()
        pos = Page.NumberPos
        isOdd = self.number % 2
        onRight = pos == 'right' or (isOdd and pos == 'oddRight') or (not isOdd and pos == 'evenRight')

        if onRight:
            rect.moveBottomRight(self.insetRect().bottomRight() - Page.margin)
        else:
            rect.moveBottomLeft(QPointF(Page.margin.x(), self.insetRect().bottom() - Page.margin.y()))
        self.numberItem.setPos(rect.topLeft())

    def initLayout(self):

        self.lockIcon.resetPosition()
        if self.lockIcon.isLocked:
            return  # Don't make any layout changes to locked pages

        self.resetPageNumberPosition()
        if self.submodelItem:
            self.submodelItem.initLayout()

        # Remove any separators; we'll re-add them in the appropriate place later
        self.removeAllSeparators()

        pageRect = self.insetRect()

        label = "Initializing Page: %d" % self._number
        if len(self.steps) <= 0:
            return label # No steps - nothing more to do here

        members = [self.submodelItem] if self.submodelItem else []
        self.layout.initGridLayout(pageRect, members + self.steps)
        for index, rect in self.layout.separators:
            self.addStepSeparator(index, rect)

        return label

    def updateSubmodel(self):
        if self.submodel and self.submodel.pages and self.submodel.pages[0].submodelItem:
            self.submodel.pages[0].submodelItem.resetPixmap()

    def adjustSubmodelImages(self):

        # Check if we should shrink submodel image
        if self.submodelItem and self.submodelItem.scaling > 0.5 and self.checkForLayoutOverlaps():
            
            # Scale submodel down and try again
            newScale = self.submodelItem.scaling - 0.2
            self.submodelItem.changeScale(newScale)
            print "scaling page %d submodel down to %.2f" % (self._number, newScale)
            self.initLayout()
            self.adjustSubmodelImages()
    
    def scaleImages(self):
        for step in self.steps:
            if step.hasPLI():
                step.pli.initLayout()
            
        if self.submodelItem:
            self.resetSubmodelImage()

    def renderFinalImageWithPov(self):

        for step in self.steps:
            step.csi.createPng()
            
            for callout in step.callouts:
                for s in callout.steps:
                    s.csi.createPng()
                    
            if step.hasPLI():
                for item in step.pli.pliItems:
                    item.createPng()

        oldPos = self.pos()
        self.setPos(0, 0)
        image = QImage(self.rect().width(), self.rect().height(), QImage.Format_ARGB32)
        painter = QPainter()
        painter.begin(image)

        items = self.getAllChildItems()
        options = QStyleOptionGraphicsItem()
        optionList = [options] * len(items)
        self.scene().drawItems(painter, items, optionList)

        for step in self.steps:
            painter.drawImage(step.csi.scenePos(), step.csi.pngImage)
                
            for callout in step.callouts:
                for s in callout.steps:
                    painter.drawImage(s.csi.scenePos(), s.csi.pngImage)
            
            if step.hasPLI():
                for item in step.pli.pliItems:
                    painter.drawImage(item.scenePos(), item.pngImage)

        if self.submodelItem:
            painter.drawImage(self.submodelItem.pos() + PLI.margin, self.submodel.pngImage)

        painter.end()
        image.save(self.getExportFilename())
        self.setPos(oldPos)

    def paint(self, painter, option, widget = None):

        # Draw a slightly down-right translated black rectangle, for the page shadow effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.rect().translated(3, 3))

        # Draw the full page in the border color
        painter.setBrush(QBrush(self.pen().color()))
        painter.drawRect(self.rect())
        
        # Draw the page itself in the chosen fill, with the correctly inset rounded rect 
        painter.setBrush(QBrush(self.color))
        painter.drawRoundedRect(self.insetRect(), self.cornerRadius, self.cornerRadius)
        
        # Draw any images or gradients this page may have
        painter.setBrush(self.brush())
        painter.drawRoundedRect(self.insetRect(), self.cornerRadius, self.cornerRadius)

    def drawGLItems(self, rect):
        
        LicGLHelpers.pushAllGLMatrices()
        vx = self.pos().x() - rect.x()
        vy = rect.height() + rect.y() - Page.PageSize.height() - self.pos().y()
        f = self.scene().scaleFactor
        LicGLHelpers.adjustGLViewport(vx, vy, Page.PageSize.width(), Page.PageSize.height(), f, True)
        
        for glItem in self.glItemIterator():
            if rect.intersects(glItem.mapToScene(glItem.rect()).boundingRect()):
                glItem.paintGL(f)
            elif hasattr(glItem, "isDirty") and glItem.isDirty:
                glItem.paintGL(f)

        LicGLHelpers.popAllGLMatrices()

    def drawGLItemsOffscreen(self, rect, f):
        
        LicGLHelpers.pushAllGLMatrices()
        LicGLHelpers.adjustGLViewport(0, 0, rect.width(), rect.height(), 1.0, True)
        
        for glItem in self.glItemIterator():
            glItem.paintGL(f)
            
        LicGLHelpers.popAllGLMatrices()

    def glItemIterator(self):
        if self.submodelItem:
            if self.submodelItem.isSubAssembly:
                for pliItem in self.submodelItem.pli.pliItems:
                    yield pliItem
            else:
                yield self.submodelItem
        for step in self.steps:
            for glItem in step.glItemIterator():
                yield glItem

    def acceptDragAndDropList(self, dragItems, row):

        steps = [s for s in dragItems if isinstance(s, Step)]
        if not steps:
            return False

        print "Dropping steps: %d"  %len(steps)
        return True

    def contextMenuEvent(self, event):

        menu = QMenu(self.scene().views()[0])
        if not self.isLocked():
            menu.addAction("Auto Layout", self.initLayout)

        if not self.isLocked() and ((len(self.steps) > 1) or (self.steps and self.submodelItem)):
            if self.layout.orientation == Horizontal:
                menu.addAction("Use Vertical layout", self.useVerticalLayout)
            else:
                menu.addAction("Use Horizontal layout", self.useHorizontalLayout)
        #menu.addAction("Check for Overlaps", self.checkForLayoutOverlaps)

        menu.addSeparator()

        menu.addAction("Prepend blank Page", lambda: self.addPageSignal(self.number, self._row))
        menu.addAction("Append blank Page", lambda: self.addPageSignal(self.number + 1, self._row + 1))

        menu.addSeparator()
        if self.separators:
            if [x for x in self.separators if x.isVisible()]:
                menu.addAction("Hide Step Separators", self.hideSeparators)
            else:
                menu.addAction("Show Step Separators", self.showSeparators)

        menu.addAction("Add blank Step", self.addBlankStepSignal)
        menu.addAction("Add Annotation", lambda: self.addAnnotationSignal(event.scenePos()))
        menu.addSeparator()
        if not self.steps:
            menu.addAction("Delete Page", lambda: self.scene().undoStack.push(AddRemovePageCommand(self.scene(), self, False)))
        menu.exec_(event.screenPos())
    
    def useVerticalLayout(self):
        self.layout.orientation = Vertical
        self.initLayout()
        
    def useHorizontalLayout(self):
        self.layout.orientation = Horizontal
        self.initLayout()
        
    def addBlankStepSignal(self):
        step = Step(self, self.getNextStepNumber())
        self.scene().undoStack.push(AddRemoveStepCommand(step, True))
        self.scene().fullItemSelectionUpdate(step)

    def addPageSignal(self, number, row):
        scene = self.scene()
        newPage = Page(self.submodel, self.instructions, number, row)
        scene.undoStack.push(AddRemovePageCommand(scene, newPage, True))
        scene.fullItemSelectionUpdate(newPage)

    def addAnnotationSignal(self, pos = None):
        filename = unicode(QFileDialog.getOpenFileName(self.scene().activeWindow(), "Lic - Open Annotation Image", "", "Images (*.png *.jpg)"))
        if filename:
            pixmap = QPixmap(filename)
            if pixmap.isNull():
                QMessageBox.information(self.scene().views()[0], "Lic", "Cannot load " + filename)
            else:
                item = PageAnnotation(self, pixmap, filename, pos)
                self.scene().undoStack.push(AddRemoveAnnotationCommand(self, item, True))

class PageAnnotation(QGraphicsPixmapItem):

    def __init__(self, parent, pixmap, filename, pos = None):
        QGraphicsPixmapItem.__init__(self, pixmap, parent)
        self.filename = filename
        self.setFlags(AllFlags)
        self.itemClassName = "Annotation"
        self.isAnnotation = True
        if pos:
            self.setPos(pos)

    def data(self, index):
        return "Annotation: " + os.path.basename(self.filename)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        stack = self.scene().undoStack
        menu.addAction("Change Picture", self.changePicture)
        menu.addAction("Remove Annotation", lambda: stack.push(AddRemoveAnnotationCommand(self.parentItem(), self, False)))
        if self.isAnnotation:
            menu.addAction("Move to Background", lambda: stack.push(ToggleAnnotationOrderCommand(self, False)))
        else:
            menu.addAction("Move to Foreground", lambda: stack.push(ToggleAnnotationOrderCommand(self, True)))
        menu.exec_(event.screenPos())

    def changePicture(self):
        filename = unicode(QFileDialog.getOpenFileName(self.scene().activeWindow(), "Lic - Open Annotation Image", "", "Images (*.png *.jpg)"))
        if filename:
            self.scene().undoStack.push(ChangeAnnotationPixmap(self, self.filename, filename))
            self.filename = filename

    def changeOrder(self, moveForward):
        z = 1200 if moveForward else -1200
        self.setZValue(z)
        self.isAnnotation = moveForward

class LockIcon(QGraphicsPixmapItem):

    loaded = False
    activeOpenIcon = None
    activeCloseIcon = None
    deactiveOpenIcon = None
    deactiveCloseIcon = None
    
    def __init__(self, parent):
        QGraphicsPixmapItem.__init__(self, parent)
        
        if not LockIcon.loaded:
            LockIcon.activeOpenIcon = QPixmap(":/lock_open")
            LockIcon.activeCloseIcon = QPixmap(":/lock_close")
            LockIcon.deactiveOpenIcon = QPixmap(":/lock_grey_open")
            LockIcon.deactiveCloseIcon = QPixmap(":/lock_grey_close")
            LockIcon.loaded = True

        self.setPixmap(LockIcon.deactiveOpenIcon)
        self.resetPosition()
        self.setFlags(NoMoveFlags)
        self.setAcceptHoverEvents(True)
        self.hoverEnterEvent = lambda event: self.changeIcon(True)
        self.hoverLeaveEvent = lambda event: self.changeIcon(False)
        
        self.isLocked = False
    
    def resetPosition(self):
        self.setPos(5, Page.PageSize.height() - self.rect().height() - 5)
    
    def changeIcon(self, active):
        if active:
            self.setPixmap(LockIcon.activeCloseIcon if self.isLocked else LockIcon.activeOpenIcon)
        else:
            self.setPixmap(LockIcon.deactiveCloseIcon if self.isLocked else LockIcon.deactiveOpenIcon)
            
    def mousePressEvent(self, event):
        self.isLocked = not self.isLocked
        self.parentItem().lock(self.isLocked)
        self.changeIcon(True)
        event.ignore()
    
class PartListPLI(PLI):
    itemClassName = "PartListPLI"

    def __init__(self, parent):
        PLI.__init__(self, parent)
        self.data = lambda index: "Part List PLI"
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
        partList.sort(key = lambda x: (x.color.sortKey(), x.rect().width()))
        
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
        for part in self.submodel.getFullPartList():
            self.pli.addPart(part)

    def initPartialItemList(self, itemList):
        self.pli.pliItems = itemList
        for item in itemList:
            item.setParentItem(self.pli)

    def initLayout(self):
        self.lockIcon.resetPosition()
        if self.lockIcon.isLocked:
            return  # Don't make any layout changes to locked pages
        self.resetPageNumberPosition()
        self.pli.doOverflowLayout()
        # TODO: Need to handle bumping items from page to page, so can do post-loaded auto-layouts

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
        return items + self.annotations

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Add Annotation", lambda: self.addAnnotationSignal(event.scenePos()))
        menu.exec_(event.screenPos())

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
        self.setFont(QFont("Arial", 15))

    def data(self, index):
        return "Label: " + self.text()
        
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

    def addInitialContent(self):  # TODO: shrink title page submodel image so it fits on the page along with the different titles.

        self.addSubmodelImage()
        si = self.submodelItem
        si._row = 0
        si.setPen(QPen(Qt.NoPen))
        si.setBrush(QBrush(Qt.NoBrush))
        si.itemClassName = "TitleSubmodelPreview"  # Override regular name so we don't set this in any template action

        self.addNewLabel(None, QFont("Arial", 25), self.submodel.getSimpleName())
        self.addNewLabel(Page.margin * 2, None, "1001")
        self.addPartCountLabel(False)
        self.addPageCountLabel(False)
        self.initLayout()

    def initLayout(self):

        self.lockIcon.resetPosition()
        if self.lockIcon.isLocked:
            return  # Don't make any layout changes to locked pages

        pw2, ph2 = Page.PageSize.width() / 2.0, Page.PageSize.height() / 2.0
        pmy = Page.margin.y()
        titleRect = self.labels[0].rect() if self.labels else QRectF()

        if self.submodelItem:
            x = pw2 - (self.submodelItem.rect().width() / 2.0)
            y = ph2 - (self.submodelItem.rect().height() / 2.0) + (titleRect.height() / 2.0) + (pmy * 2)
            self.submodelItem.setPos(x, y)

        # TODO: Auto-shrink submodelImage if it is too big

        if self.labels:
            x = pw2 - (titleRect.width() / 2.0)
            if self.submodelItem:
                y = self.submodelItem.pos().y() - titleRect.height() - (pmy * 3)
            else:
                y = ph2 - (titleRect.height() / 2.0)
            self.labels[0].setPos(x, y)

        if self.getPartCountLabel():
            self.setPartCountLabelPos(self.getPartCountLabel())
        if self.getPageCountLabel():
            self.setPageCountLabelPos(self.getPageCountLabel())

    def getPartCountLabel(self):
        for label in reversed(self.labels):
            if label.text().count(" pcs.") > 0:
                return label
        return None

    def getPageCountLabel(self):
        for label in reversed(self.labels):
            if label.text().count(" Pages") > 0:
                return label
        return None

    def setPartCountLabelPos(self, label):
        label.setPos(self.rect().bottomLeft())
        label.moveBy(0, -label.rect().height())
        label.moveBy(Page.margin.x(), -Page.margin.y())

    def setPageCountLabelPos(self, label):
        label.setPos(self.rect().bottomRight())
        label.moveBy(-label.rect().width(), -label.rect().height())
        label.moveBy(-Page.margin.x(), -Page.margin.y())

    def getAllChildItems(self):
        return [self] + [self.submodelItem] if self.submodelItem else [] + self.labels + self.annotations

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Auto Layout", self.initLayout)
        menu.addSeparator()
        menu.addAction("Add Annotation", lambda: self.addAnnotationSignal(event.scenePos()))
        menu.addAction("Add Label", lambda: self.addNewLabel(event.scenePos(), useUndo = True))
        if self.getPartCountLabel() is None:
            menu.addAction("Add Part Count Label", lambda: self.addPartCountLabel(True))
        if self.getPageCountLabel() is None:
            menu.addAction("Add Page Count Label", lambda: self.addPageCountLabel(True))
        if self.submodelItem is None:
            menu.addAction("Add Model Preview - NYI", lambda: True)  # TODO: Allow user to add / remove title page model preview
            
        menu.addSeparator()
        menu.addAction("Remove Title Page", lambda: self.submodel.addRemoveTitlePageSignal(False))
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
        text = "%d pcs." % len(self.submodel.getFullPartList())
        self.addNewLabel(None, None, text, useUndo)
        self.setPartCountLabelPos(self.labels[-1])

    def addPageCountLabel(self, useUndo = False):
        text = "%d Pages" % len(self.submodel.getFullPageList())
        self.addNewLabel(None, None, text, useUndo)
        self.setPageCountLabelPos(self.labels[-1])
