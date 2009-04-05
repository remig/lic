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
            
    def initLayoutInsideOut(self, memberList):
        pass
    
    def initLayoutFromRect(self, rect, memberList):
        # Assumes the QRectF position, width & height of this layout has already been set
        # If row / col count are -1 (unset), will be set to something appropriate
        
        if self.rowCount == -1 or self.colCount == -1:
            self.initRowColCount(memberList)
        
        cols = min(len(memberList), self.colCount)
        rows = min(len(memberList), self.rowCount)
        
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
                
            tmpRect = QRectF(x, y, colWidth, rowHeight)
            tmpRect.translate(rect.x(), rect.y())
            tmpRect.adjust(self.margin, self.margin, -self.margin, -self.margin)
            member.initLayout(tmpRect)
            
