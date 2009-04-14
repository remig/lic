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
    
def genericMouseReleaseEvent(className):
    
    def _tmp(self, event):

        if event.button() == Qt.RightButton:
            return
        className.mouseReleaseEvent(self, event)
        if hasattr(self, 'oldPos') and self.pos() != self.oldPos:
            self.scene().emit(SIGNAL("itemsMoved"), self.scene().selectedItems())

    return _tmp
                
def genericItemParent(self):
    return self.parentItem()

def genericItemData(self, index):
    return self.dataText

def genericRow(self):
    if hasattr(self, '_row'):
        return self._row
    if hasattr(self, 'parentItem'):
        parent = self.parentItem()
        if hasattr(parent, 'getChildRow'):
            return parent.getChildRow(self)
    return 0

QGraphicsRectItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsRectItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsRectItem.parent = genericItemParent
QGraphicsRectItem.data = genericItemData
QGraphicsRectItem.row = genericRow

QGraphicsPolygonItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsPolygonItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsPolygonItem.parent = genericItemParent
QGraphicsPolygonItem.data = genericItemData
QGraphicsPolygonItem.row = genericRow

QGraphicsSimpleTextItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.parent = genericItemParent
QGraphicsSimpleTextItem.data = genericItemData
QGraphicsSimpleTextItem.row = genericRow

QGraphicsPixmapItem.mousePressEvent = genericMousePressEvent(QGraphicsItem)
QGraphicsPixmapItem.mouseReleaseEvent = genericMouseReleaseEvent(QGraphicsItem)

QGraphicsPixmapItem.parent = genericItemParent
QGraphicsPixmapItem.data = genericItemData
QGraphicsPixmapItem.row = genericRow

def printRect(rect, text = ""):
    print text + ", l: %f, r: %f, t: %f, b: %f" % (rect.left(), rect.right(), rect.top(), rect.bottom())
