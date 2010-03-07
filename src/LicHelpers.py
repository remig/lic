from PyQt4.QtCore import Qt, QPointF
from PyQt4.QtGui import QPainterPath

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

def multiplyMatrices(matrix1, matrix2):
    # m1 & m2 must be in the form [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    # ie, matrix list straigth from a Part
    m1 = listToMatrix(matrix1)
    m2 = listToMatrix(matrix2)
    m = [[0]*4, [0]*4, [0]*4, [0]*4]
    
    for i in range(4):
        for j in range(4):
            for k in range(4):
                m[i][j] += m1[i][k] * m2[k][j]
        
    return matrixToList(m)

def listToMatrix(l):
    return [l[0:4], l[4:8], l[8:12], l[12:16]]

def matrixToList(m):
    return m[0] + m[1] + m[2] + m[3]

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

    offset = 60.0 if initialOffset else 35.0
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

def snapToGrid(item):
    gridSpacing = 50
    x = gridSpacing * int(item.pos().x() / gridSpacing)
    y = gridSpacing * int(item.pos().y() / gridSpacing)
    item.setPos(x, y)

def polygonToCurvedPath(polygon, radius):
    
    path = QPainterPath()
    for i, pt in enumerate(polygon):
        
        # TODO: if two points are too close to draw the desired radius, either remove those points or draw at smaller radius
        px, py = polygon[i-1] if i > 0 else polygon[-1]
        nx, ny = polygon[i+1] if i < len(polygon) - 1 else polygon[0]
        x, y = pt
        
        if px == x:
            dy = y - py
            r = radius if dy < 0 else -radius
            p1 = QPointF(x, y + r)
        else:
            dx = x - px
            r = radius if dx < 0 else -radius
            p1 = QPointF(x + r, y)
        
        if x == nx:
            dy = y - ny
            r = radius if dy < 0 else -radius
            p2 = QPointF(x, y + r)
        else:
            dx = x - nx
            r = radius if dx < 0 else -radius
            p2 = QPointF(x + r, y)
        
        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.cubicTo(pt, pt, p2)

    path.closeSubpath()
    return path
