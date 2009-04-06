import math
from PyQt4.QtCore import *

Horizontal = 0
Vertical = 1
    
def maxSafe(s):
    return max(s) if s else 0.0

class GridLayout(QRectF):
    # Assumes any item added inside this class is the correct size
    # Stores a margin and row & column count, and provides layout algorithms given a list of stuff to layout
    # Can layout any objects as long as they define initLayout(QRectF)
    
    def __init__(self, rowCount = -1, colCount = -1, margin = 15, orientation = Vertical):
        QRectF.__init__(self)
        self.colCount = rowCount
        self.rowCount = colCount
        self.margin = margin
        self.orientation = orientation

    def setRect(self, rect):
        QRectF.setRect(self, rect.x(), rect.y(), rect.width(), rect.height())

    def initRowColCount(self, memberList):
        
        itemCount = len(memberList)
        x = int(math.ceil(math.sqrt(itemCount)))
        y = itemCount // x  # This needs to be integer division
        if itemCount % x:
            y += 1
            
        if self.orientation == Horizontal:
            self.rowCount, self.colCount = y, x
        else:
            self.rowCount, self.colCount = x, y
            
    def getActualRowColCount(self, memberList):
        if self.rowCount == -1 or self.colCount == -1:
            self.initRowColCount(memberList)
        
        cols = min(len(memberList), self.colCount)
        rows = min(len(memberList), self.rowCount)
        
        return (rows, cols)
        
    def initLayoutInsideOut(self, memberList):
        # Assumes each member in list is right width & height
        # Sets position of each member into a grid
        # MemberList is a list of any objects that have rect(), setPos() and moveBy() methods

        rows, cols = self.getActualRowColCount(memberList)
        rowHeights, colWidths = [], []
        
        # Build a table of each row's height and column's width
        for i in range(0, rows):
            if self.orientation == Horizontal:
                maxSize = maxSafe([x.rect().width() for x in memberList[i::rows]])  # 0, 3, 6...
                colWidths.append(maxSize)
            else:
                maxSize = maxSafe([x.rect().height() for x in memberList[i::rows]])
                rowHeights.append(maxSize)

        for i in range(0, rows):
            if self.orientation == Horizontal:
                maxSize = maxSafe([x.rect().height() for x in memberList[i * rows: (i * rows) + rows]])  # 0, 1, 2...
                rowHeights.append(maxSize)
            else:
                maxSize = maxSafe([x.rect().width() for x in memberList[i * rows: (i * rows) + rows]])
                colWidths.append(maxSize)
        
        # Position each member in the center of its cell
        for i, member in enumerate(memberList):
            row, col = i % rows, i // rows
            if self.orientation == Horizontal:
                row, col = col, row
                
            # Position at top left of cell
            width = sum(colWidths[:col]) + (self.margin * (col + 1)) 
            height = sum(rowHeights[:row]) + (self.margin * (row + 1))
            member.setPos(width, height)
            
            # Move to center of cell, if necessary
            dx = (colWidths[col] - member.rect().width()) / 2.0
            dy = (rowHeights[row] - member.rect().height()) / 2.0
            if dx > 0 or dy > 0:
                member.moveBy(dx, dy)
    
    def initGridLayout(self, rect, memberList):
        # Assumes the QRectF position, width & height of this layout has already been set
        # Divides rect into equally sized rows & columns, and sizes each member to fit inside
        # If row / col count are -1 (unset), will be set to something appropriate
        # MemberList is a list of any objects that have an initLayout(rect) method
        
        rows, cols = self.getActualRowColCount(memberList)
        
        colWidth = rect.width() / cols
        rowHeight = rect.height() / rows

        if self.orientation == Horizontal:
            x, y = 0.0, -rowHeight
        else:
            x, y = -colWidth, 0.0
        
        for i, member in enumerate(memberList):
            
            if self.orientation == Horizontal:
                if i % cols:  # Add to right of current column
                    x += colWidth
                else:  # Start a new row
                    x = 0.0
                    y += rowHeight
            else:
                if i % rows:  # Add to bottom of current row
                    y += rowHeight
                else:  # Start a new column
                    y = 0.0
                    x += colWidth

            tmpRect = QRectF(x, y, colWidth, rowHeight)
            tmpRect.translate(rect.x(), rect.y())
            tmpRect.adjust(self.margin, self.margin, -self.margin, -self.margin)
            member.initLayout(tmpRect)
