from PyQt4.QtCore import *
from PyQt4.QtGui import *

# lambda is bound dynamically to the last variable used, so we can't 
# use it in a loop for creating menu actions.  Use this instead.
# usage: menu.addAction("menu text", makeFunc(self.moveToCallout, callout))
def makeFunc(func, arg):
    def f(): func(arg)
    return f

def determinant3x3(m):
    # m must be in the form [[00, 01, 02], [10, 11, 12], [20, 21, 22]]
    d1 = m[0][0] * ((m[1][1] * m[2][2]) - (m[1][2] * m[2][1]))
    d2 = m[0][1] * ((m[1][0] * m[2][2]) - (m[1][2] * m[2][0]))
    d3 = m[0][2] * ((m[1][0] * m[2][1]) - (m[1][1] * m[2][0]))
    return d1 - d2 + d3

def GLMatrixToXYZ(matrix):
    return [matrix[12], matrix[13], matrix[14]]

def compareParts(p1, p2):
    b1 = p1.getPartBoundingBox()
    b2 = p2.getPartBoundingBox()
    
    if abs(b1.y1 - b2.y1) < 6.0:  # tops equal enough - 6 to handle technic pins in holes
        
        if abs(b1.y2 - b2.y2) < 4.0:  # bottoms equal enough too
            return cmp((-b1.z1, b1.x1), (-b2.z1, b2.x1))  # back to front, left to right
        
        if b1.y2 < b2.y2:  # compare bottoms
            return 1
        return -1
        
    if b1.y1 < b2.y1:  # compare tops
        return 1
    return -1

def getOffsetFromBox(direction, box):

    if direction == Qt.Key_Up or direction == Qt.Key_Down:
        return box.xSize()
    elif direction == Qt.Key_PageUp or direction == Qt.Key_PageDown:
        return box.ySize()
    elif direction == Qt.Key_Left or direction == Qt.Key_Right:
        return box.zSize()

def getOffsetFromPart(part):

    direction = part.displaceDirection
    arrow = part.displaceArrow
    
    if direction == Qt.Key_Up:
        return arrow.x() - part.bx2()
    elif direction == Qt.Key_Down:
        return part.bx() - arrow.x()
    
    elif direction == Qt.Key_PageUp:
        return arrow.y() - part.by()
    elif direction == Qt.Key_PageDown:
        return part.by2() - arrow.y()
    
    elif direction == Qt.Key_Left:
        return arrow.z() - part.bz2() 
    elif direction == Qt.Key_Right:
        return part.bz() - arrow.z()

def displacementToDistance(displacement, direction):

    if direction == Qt.Key_Up:
        return -displacement[0]
    elif direction == Qt.Key_Down:
        return displacement[0]
        
    elif direction == Qt.Key_PageUp:
        return -displacement[1]
    elif direction == Qt.Key_PageDown:
        return displacement[1]
        
    elif direction == Qt.Key_Left:
        return -displacement[2]
    elif direction == Qt.Key_Right:
        return displacement[2]
    return None

def distanceToDisplacement(distance, direction):

    displacement = [0.0, 0.0, 0.0]

    if direction == Qt.Key_Up:
        displacement[0] = -distance
    elif direction == Qt.Key_Down:
        displacement[0] = distance
        
    elif direction == Qt.Key_PageUp:
        displacement[1] = -distance
    elif direction == Qt.Key_PageDown:
        displacement[1] = distance
        
    elif direction == Qt.Key_Left:
        displacement[2] = -distance
    elif direction == Qt.Key_Right:
        displacement[2] = distance
    else:
        return None

    return displacement


def getDisplacementOffset(direction, initialOffset, box):

    offset = 80.0 if initialOffset else 50.0
    displacement = [0.0, 0.0, 0.0]

    if direction == Qt.Key_Up:
        displacement[0] -= offset + box.xSize()
    elif direction == Qt.Key_Down:
        displacement[0] += offset + box.xSize()
        
    elif direction == Qt.Key_PageUp:
        displacement[1] -= offset + box.ySize()
    elif direction == Qt.Key_PageDown:
        displacement[1] += offset + box.ySize()
        
    elif direction == Qt.Key_Left:
        displacement[2] -= offset + box.zSize()
    elif direction == Qt.Key_Right:
        displacement[2] += offset + box.zSize()
    else:
        return None

    return displacement
        
def getOppositeDirection(direction):
    if direction == Qt.Key_Up:
        return Qt.Key_Down
    if direction == Qt.Key_Down:
        return Qt.Key_Up
    if direction == Qt.Key_PageUp:
        return Qt.Key_PageDown
    if direction == Qt.Key_PageDown:
        return Qt.Key_PageUp
    if direction == Qt.Key_Left:
        return Qt.Key_Right
    if direction == Qt.Key_Right:
        return Qt.Key_Left

def genericMousePressEvent(className):
    def _tmp(self, event):

        if event.button() == Qt.RightButton:
            return
        className.mousePressEvent(self, event)
        for item in self.scene().selectedItems():
            item.oldPos = item.pos()

    return _tmp
    
def snapToGrid(item):
    gridSpacing = 50
    x = gridSpacing * int(item.pos().x() / gridSpacing)
    y = gridSpacing * int(item.pos().y() / gridSpacing)
    item.setPos(x, y)

def genericMouseMoveEvent(className):
    
    def _tmp(self, event):
        className.mouseMoveEvent(self, event)
        self.scene().snapToGuides(self)
        #snapToGrid(self)
    return _tmp
    
def genericMouseReleaseEvent(className):
    
    def _tmp(self, event):

        if event.button() == Qt.RightButton:
            return
        className.mouseReleaseEvent(self, event)
        if hasattr(self, 'oldPos') and self.pos() != self.oldPos:
            self.scene().emit(SIGNAL("itemsMoved"), self.scene().selectedItems())

    return _tmp
                
def genericGetPage(self):
    return self.parentItem().getPage()

# This is necessary because Qt distinguishes between QContextMenuEvent and 
# QGraphicsSceneContextMenuEvent.  I guess its a C++ thing.  bleh
# Python is perfectly happy simply accepting event.  Be sure to convert the appropriate event
# parameters when passing one where another is expected though (like TreeView.contextMenuEvent)
QGraphicsItem.contextMenuEvent = lambda self, event: event.ignore()

QGraphicsLineItem.mousePressEvent = genericMousePressEvent(QGraphicsItem)
QGraphicsLineItem.mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsItem)

QGraphicsRectItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsRectItem.mouseMoveEvent = genericMouseMoveEvent(QAbstractGraphicsShapeItem)
QGraphicsRectItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsRectItem.getPage = genericGetPage

QGraphicsSimpleTextItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseMoveEvent = genericMouseMoveEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.getPage = genericGetPage
