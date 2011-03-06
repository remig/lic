"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicLayout.py) is part of Lic.

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
    
    margin = 15
    
    def __init__(self, rowCount = -1, colCount = -1, orientation = Vertical):
        self.colCount = rowCount
        self.rowCount = colCount
        self.orientation = orientation
        self.separators = []  # List of (index, QRectF) tuples that encode all separator info

    def addHSeparator(self, x, y, width, index):
        b = QRectF(x + self.margin, y, width - (self.margin * 2), 1.0)
        self.separators.append((index, b))
        
    def addVSeparator(self, x, y, height, index):
        b = QRectF(x, y + self.margin, 1.0, height - (self.margin * 2))
        self.separators.append((index, b))

    def addSeparator(self, x, y, size, index):
        if self.orientation == Horizontal:
            self.addHSeparator(x, y, size, index)
        else:
            self.addVSeparator(x, y, size, index)

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
            
        return (y, x) if self.orientation == Horizontal else (x, y)
    
    @staticmethod
    def initCrossLayout(rect, memberList):
        # Assumes each member in list is right width & height.  Max 9 items in memberList (beyond are ignored)
        # MemberList is a list of any objects that have rect(), setPos() and moveBy() methods
        # Sets position of each member into a cross, which fits inside rect:
        # -5- -3- -6-
        # -2- -0- -1-
        # -7- -4- -8-
        
        indices = [(1,1), (1,2), (1,0), (0,1), (2,1), (0,0), (0,2), (2,0), (2,2)]
        rowHeights, colWidths = [[], [], []], [[], [], []]
        
        # Store the size of each memeber in the appropriate row col spot
        for i, member in enumerate(memberList):
            row, col = indices[i]
            r, m2 = member.rect(), GridLayout.margin * 2
            rowHeights[row].append(r.height() + m2)
            colWidths[col].append(r.width() + m2)
            
        # Use only the max row / col value for a given cell
        rowHeights = [maxSafe(row) for row in rowHeights]
        colWidths = [maxSafe(col) for col in colWidths]

        # Find difference in size between current cross and passed in rect
        dx = (rect.width() - sum(colWidths)) / 3.0
        dy = (rect.height() - sum(rowHeights)) / 3.0

        # Enlarge each row / col so overall cross fits tight inside passed in rect
        colWidths = [x + dx for x in colWidths]
        rowHeights = [y + dy for y in rowHeights]

        # Position each member in the right cell in the cross
        for i, member in enumerate(memberList):
            row, col = indices[i]
            width = sum(colWidths[:col]) + rect.x()
            height = sum(rowHeights[:row]) + rect.y()
            member.setPos(width, height)

            # Move to center of cell, if necessary
            dx = (colWidths[col] - member.rect().width()) / 2.0
            dy = (rowHeights[row] - member.rect().height()) / 2.0
            if dx > 0 or dy > 0:
                member.moveBy(dx, dy)

    def initLayoutInsideOut(self, memberList):
        # Assumes each member in list is right width & height
        # Sets position of each member into a grid
        # MemberList is a list of any objects that have rect(), setPos() and moveBy() methods

        rows, cols = self.getRowColCount(memberList)
        rowHeights, colWidths = [], []

        # Build a table of each row's height and column's width
        for i in range(0, rows):
            maxSize = maxSafe([x.rect().height() for x in memberList[i::rows]])
            rowHeights.append(maxSize)

        for i in range(0, cols):
            maxSize = maxSafe([x.rect().width() for x in memberList[i * rows: (i * rows) + rows]])
            colWidths.append(maxSize)

        # Position each member in the center of its cell
        for i, member in enumerate(memberList):
            row, col = i % rows, i // rows

            # Position at top left of cell
            width = sum(colWidths[:col]) + (self.margin * (col + 1)) 
            height = sum(rowHeights[:row]) + (self.margin * (row + 1))
            member.setPos(width, height)

            # Move to center of cell, if necessary
            dx = (colWidths[col] - member.rect().width()) / 2.0
            dy = (rowHeights[row] - member.rect().height()) / 2.0
            if dx > 0 or dy > 0:
                member.moveBy(dx, dy)

    def _adjustRow(self, rowMembers, length, size, startPoint):

        fixedCount = 0
        for member in [m for m in rowMembers if m.fixedSize]:
            length -= member.rect().getOrientedSize(self.orientation) + (self.margin * 2)
            fixedCount += 1;

        length = length / (len(rowMembers) - fixedCount)

        if self.orientation == Vertical:
            length, size = size, length

        destRects = []

        # First, set each member's width & height and position it in top left corner of destRect
        for member in rowMembers:
            if member.fixedSize:
                destRects.append(member.rect().adjusted(0, 0, self.margin * 2, self.margin * 2))
                destRects[-1].setTopLeft(startPoint)
            else:
                destRects.append(QRectF(startPoint.x(), startPoint.y(), length, size))

        # Move each rect over so it's beside its predecessor
        for i, member in enumerate(rowMembers[1:]):
            if self.orientation == Horizontal:
                destRects[i+1].moveLeft(destRects[i].right())
            else:
                destRects[i+1].moveTop(destRects[i].bottom())

        # Now, shrink each member by margin, then do layout
        for i, member in enumerate(rowMembers):
            rect = destRects[i].adjusted(self.margin, self.margin, -self.margin, -self.margin)
            member.initLayout(rect)

    def _getSizeList(self, memberList, interval, intervalCount, maxRect):
        sizeList = []
        oID = not self.orientation
        for i in range(0, len(memberList), interval):
            rowMembers = memberList[i : i + interval]
            maxFixedSize = maxSafe([(m.rect().getOrientedSize(oID) + self.margin * 2) for m in rowMembers if m.fixedSize])
            sizeList.append(maxFixedSize)

        eachRowHeight = maxRect.getOrientedSize(oID) / intervalCount  # size if no members are fixed
        if any(i == 0 for i in sizeList):  # Have fixed members
            nonFixedHeight = (maxRect.getOrientedSize(oID) - sum(sizeList)) / sizeList.count(0)  # size of non-fixed rows
            eachRowHeight = min(eachRowHeight, nonFixedHeight)

        for i in range(len(sizeList)):
            sizeList[i] = max(sizeList[i], eachRowHeight)

        return sizeList

    def initGridLayout(self, rect, memberList):
        # Divides rect into equally sized rows & columns, and sizes each member to fit inside.
        # If row / col count are -1 (unset), will be set to something appropriate.
        # MemberList is a list of any objects that have an initLayout(rect) method

        rows, cols = self.getRowColCount(memberList)
        startPoint = rect.topLeft()
        self.separators = []

        oID = self.orientation
        if oID == Vertical:
            cols, rows = rows, cols

        sizeList = self._getSizeList(memberList, cols, rows, rect)

        for i in range(0, len(memberList), cols):  # Adjust each row

            rowMembers = memberList[i : i + cols]
            size = sizeList[i // cols]

            self._adjustRow(rowMembers, rect.getOrientedSize(oID), size, startPoint)  # Position each member in this row
            childRow = rowMembers[-1].row() + len(self.separators) + 1  # Figure out where step separator should be inserted in tree

            startPoint = QPointF(rect.left(), startPoint.y() + size) if oID == Horizontal else QPointF(startPoint.x() + size, rect.top())

            if rowMembers[-1] != memberList[-1]:
                self.addSeparator(startPoint.x(), startPoint.y(), rect.getOrientedSize(oID), childRow)
