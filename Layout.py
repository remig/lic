import math
from PyQt4.QtCore import *

Horizontal = 0
Vertical = 1
    
def maxSafe(s):
    return max(s) if s else 0.0

class GridLayout(object):
    # Assumes any item added inside this class is the correct size
    # Stores a margin and row & column count, and provides layout algorithms given a list of stuff to layout
    # Stores a set of separators that separate each member.
    
    def __init__(self, rowCount = -1, colCount = -1, margin = 15, orientation = Vertical):
        self.colCount = rowCount
        self.rowCount = colCount
        self.margin = margin
        self.orientation = orientation
        self.separators = []  # List of (index, QRectF) tuples that encode all separator info

    def addHSeparator(self, x, y, width, index):
        b = QRectF(x + self.margin, y, width - (self.margin * 2), 1.0)
        self.separators.append((index, b))
        
    def addVSeparator(self, x, y, height, index):
        b = QRectF(x, y + self.margin, 1.0, height - (self.margin * 2))
        self.separators.append((index, b))

    def getRowColCount(self, memberList):
        
        if self.rowCount != -1 and self.colCount != -1:
            rows = min(len(memberList), self.rowCount)
            cols = min(len(memberList), self.colCount)
            return (rows, cols)

        itemCount = len(memberList)
        x = int(math.ceil(math.sqrt(itemCount)))
        y = itemCount // x  # This needs to be integer division
        if itemCount % x:
            y += 1
            
        if self.orientation == Horizontal:
            return (y, x)
        else:
            return (x, y)
            
    def initLayoutInsideOut(self, memberList):
        # Assumes each member in list is right width & height
        # Sets position of each member into a grid
        # MemberList is a list of any objects that have rect(), setPos() and moveBy() methods

        rows, cols = self.getRowColCount(memberList)
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
        # Assumes the QRectF position, width & height of this layout has already been set.
        # Divides rect into equally sized rows & columns, and sizes each member to fit inside.
        # If row / col count are -1 (unset), will be set to something appropriate.
        # MemberList is a list of any objects that have an initLayout(rect) method
        
        rows, cols = self.getRowColCount(memberList)
        self.separators = []
        
        colWidth = rect.width() / cols
        rowHeight = rect.height() / rows
        x, y, = rect.x(), rect.y()
        
        for i, member in enumerate(memberList):
            
            if i > 0:
                if self.orientation == Horizontal:
                    if i % cols:  # Add to right of current column
                        x += colWidth
                    else:  # Start a new row
                        x = rect.x()
                        y += rowHeight
                        self.addHSeparator(x, y, rect.width(), i + 1)
                else:
                    if i % rows:  # Add to bottom of current row
                        y += rowHeight
                    else:  # Start a new column
                        y = rect.y()
                        x += colWidth
                        self.addVSeparator(x, y, rect.height(), i + 1)
                        
            tmpRect = QRectF(x, y, colWidth, rowHeight)
            tmpRect.adjust(self.margin, self.margin, -self.margin, -self.margin)
            member.initLayout(tmpRect)
            
