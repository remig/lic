import math
from PyQt4.QtCore import *

class GridLayout(QRectF):
    # Assumes any item added inside this class is the correct size
    # Stores a margin and row & column count, and provides layout algorithms given a list of stuff to layout
    # Can layout any objects as long as they define initLayout(QRectF)
    
    def __init__(self, rowCount = -1, colCount = -1, margin = 15):
        QRectF.__init__(self)
        self.colCount = rowCount
        self.rowCount = colCount
        self.margin = margin
        
    def setRect(self, rect):
        QRectF.setRect(self, rect.x(), rect.y(), rect.width(), rect.height())

    def initRowColCount(self, memberList):
        
        itemCount = len(memberList)
        self.colCount = int(math.ceil(math.sqrt(itemCount)))
        self.rowCount = itemCount // self.colCount  # This needs to be integer division
        if itemCount % self.colCount:
            self.rowCount += 1
            
    def getActualRowColCount(self, memberList):
        if self.rowCount == -1 or self.colCount == -1:
            self.initRowColCount(memberList)
        
        cols = min(len(memberList), self.colCount)
        rows = min(len(memberList), self.rowCount)
        
        return (rows, cols)
        
    def initLayoutInsideOut(self, memberList):
        # Assumes each member in list is right width & height
        # Sets position of each member into a grid

        rows, cols = self.getActualRowColCount(memberList)
        maxWidth = maxHeight = 0.0

        # Find tallest entry in each row:
        rowHeights = []
        for i in range(0, rows):
            for member in memberList[i::rows]:
                maxHeight = max(maxHeight, member.rect().height())
            rowHeights.append(maxHeight)
            maxHeight = 0.0

        # Find widest entry in each column
        colWidths = []
        for i in range(0, rows):
            offset = i * rows
            for member in memberList[offset: offset + rows]:
                maxWidth = max(maxWidth, member.rect().width())
            colWidths.append(maxWidth)
            maxWidth = 0.0
        
        # Build a box that will fit all members, then lay it out grid-style
        box = QRectF(0.0, 0.0, sum(colWidths), sum(rowHeights))
        self.initLayoutFromRect(box, memberList, True)
        
        # Now, all members are in top left corner of their cell; move to center of cell
        for i, member in enumerate(memberList):
            dx = (colWidths[i // rows] - member.rect().width()) / 2.0
            dy = (rowHeights[i % rows] - member.rect().height()) / 2.0
            if dx > 0 or dy > 0:
                member.moveBy(dx, dy)
    
    def initLayoutFromRect(self, rect, memberList, setPositionOnly = False):
        # Assumes the QRectF position, width & height of this layout has already been set
        # If row / col count are -1 (unset), will be set to something appropriate
        
        rows, cols = self.getActualRowColCount(memberList)
        
        colWidth = rect.width() / cols
        rowHeight = rect.height() / rows
        x = -colWidth
        y = 0.0
        
        for i, member in enumerate(memberList):
            
            if i % rows:  # Add to bottom of current row
                y += rowHeight
            else:  # Start a new Column
                y = 0.0
                x += colWidth

            if setPositionOnly:
                member.setPos(x + self.margin, y + self.margin)
            else:
                tmpRect = QRectF(x, y, colWidth, rowHeight)
                tmpRect.translate(rect.x(), rect.y())
                tmpRect.adjust(self.margin, self.margin, -self.margin, -self.margin)
                member.initLayout(tmpRect)
