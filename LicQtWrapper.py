from PyQt4.QtCore import *
from PyQt4.QtGui import *

def genericDrawSelectionRect(self, rect, cornerRadius = 0):
    self.save()
    pen = QPen(Qt.DashLine)
    pen.setWidth(2)
    self.setPen(pen)
    self.setBrush(Qt.NoBrush)
    if cornerRadius:
        self.drawRoundedRect(rect, cornerRadius, cornerRadius)
    else:
        self.drawRect(rect)
    self.restore()

QPainter.drawSelectionRect = genericDrawSelectionRect

class GraphicsRoundRectItem(QGraphicsRectItem):
    
    defaultPen = QPen(Qt.black)
    defaultBrush = QBrush(Qt.white)
    
    def __init__(self, parent):
        QGraphicsRectItem.__init__(self, parent)
        self.cornerRadius = 10
        self.setPen(self.defaultPen)
        self.setBrush(self.defaultBrush)
       
    def paint(self, painter, option, widget = None):
        
        if self.cornerRadius:
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            painter.drawRoundedRect(self.rect(), self.cornerRadius, self.cornerRadius)
            if self.isSelected():
                painter.drawSelectionRect(self.rect(), self.cornerRadius)
        else:
            QGraphicsRectItem.paint(self, painter, option, widget)
    
    def pen(self):
        pen = QGraphicsRectItem.pen(self)
        pen.cornerRadius = self.cornerRadius
        return pen

    def setPen(self, newPen):
        QGraphicsRectItem.setPen(self, newPen)
        if hasattr(newPen, "cornerRadius"):  # Need this check because some setPen() calls come from Qt directly
            self.cornerRadius = newPen.cornerRadius

class GraphicsCircleLabelItem(QGraphicsEllipseItem):

    itemClassName = "GraphicsCircleLabelItem"
    defaultPen = QPen(Qt.black)
    defaultBrush = QBrush(Qt.white)
    defaultFont = QFont("Arial", 8)
    defaultDiameter = 18

    def __init__(self, parent, length = "10"):
        QGraphicsEllipseItem.__init__(self, 0, 0, self.defaultDiameter, self.defaultDiameter, parent)
        self.setPen(self.defaultPen)
        self.setBrush(self.defaultBrush)

        self._row = 1
        self.setFont(self.defaultFont)
        self.lengthText = length
        self.labelColor = QColor(Qt.black)  # TODO: implement this
        self.dataText = "Length Indicator (%s)" % length

    def paint(self, painter, option, widget = None):
        QGraphicsEllipseItem.paint(self, painter, option, widget)
        painter.setPen(QPen(self.labelColor))
        painter.setFont(self.font())
        textRect = painter.boundingRect(self.rect(), Qt.AlignCenter, self.lengthText)
        painter.drawText(textRect, Qt.AlignCenter, self.lengthText)

    def setDiameter(self, diameter):
        self.setRect(0, 0, diameter, diameter)

    def diameter(self):
        return self.rect().width()

    def setFont(self, font):
        self._font = font
        
    def font(self):
        return self._font

class GraphicsRotateArrowItem(GraphicsRoundRectItem):

    itemClassName = "GraphicsRotateArrowItem"

    defaultArrowPen = QPen(Qt.blue, 0, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
    arrowTipLength = 9.0
    arrowTipHeight = 4.0
    ArrowHead = QPolygonF([QPointF(),
                           QPointF(arrowTipLength + 2.5, -arrowTipHeight),
                           QPointF(arrowTipLength, 0.0),
                           QPointF(arrowTipLength + 2.5, arrowTipHeight)])

    def __init__(self, parent, length = "10"):
        GraphicsRoundRectItem.__init__(self, parent)
        self.cornerRadius = 6

        self.arrowPen = self.defaultArrowPen
        self.dataText = "Rotation Icon"
        self.setRect(0, 0, 50, 50)

    def changeArrowPen(self, newPen):
        self.arrowPen = newPen
        self.update()

    def paint(self, painter, option, widget = None):
        GraphicsRoundRectItem.paint(self, painter, option, widget)
        painter.setPen(self.arrowPen)
        painter.setBrush(QBrush(Qt.transparent))
        
        w, h2 = self.rect().width(), self.rect().height() / 2.0
        inset = 6.0
                
        start = QPointF(inset, h2 - inset)
        end = QPointF(w - inset, h2 - inset)
        
        ix, iy = inset * 1.8, inset * 2.5  # 1.8 & 2.5 entirely qualitative, for a 'nice' curve
        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(start + QPointF(ix, -iy), end + QPointF(-ix, -iy), end)

        start += QPointF(0, inset + inset)
        end += QPointF(0, inset + inset)
        path.moveTo(end)
        path.cubicTo(end + QPointF(-ix, iy), start + QPointF(ix, iy), start)

        painter.drawPath(path)

        painter.setBrush(QBrush(self.arrowPen.color()))
        painter.save()
        painter.translate(w - inset, h2 - inset)
        painter.rotate(-135)
        painter.drawPolygon(self.ArrowHead)
        painter.restore()

        painter.save()
        painter.translate(inset, h2 + inset)
        painter.rotate(45)
        painter.drawPolygon(self.ArrowHead)
        painter.restore()

def genericMousePressEvent(className):
    def _tmp(self, event):
        if event.button() == Qt.RightButton:
            return
        className.mousePressEvent(self, event)
        for item in self.scene().selectedItems():
            item.oldPos = item.pos()

    return _tmp
    
def genericMouseMoveEvent(className):
    
    def _tmp(self, event):
        if event.buttons() == Qt.RightButton or self.oldPos is None:
            return
        className.mouseMoveEvent(self, event)
        if (self.flags() & QGraphicsItem.ItemIsMovable) == QGraphicsItem.ItemIsMovable:
            self.scene().snap(self)
        #snapToGrid(self)
    return _tmp
    
def genericMouseReleaseEvent(className):
    
    def _tmp(self, event):
        if event.button() == Qt.RightButton:
            return
        scene = self.scene()
        className.mouseReleaseEvent(self, event)
        if self.oldPos and self.pos() != self.oldPos:
            scene.emit(SIGNAL("itemsMoved"), scene.selectedItems())
        self.oldPos = None
        scene.xSnapLine.hide()
        scene.ySnapLine.hide()

    return _tmp

# Make QPointF iterable: p[0] is p.x, p[1] is p.y.  Useful for unpacking x & y easily
def pointIterator(self, index):
    if index == 0:
        return self.x()
    if index == 1:
        return self.y()
    raise IndexError
QPointF.__getitem__ = pointIterator

def genericGetSceneCorners(self):
    topLeft = self.mapToScene(self.mapFromParent(self.pos())) # pos is in item.parent coordinates
    bottomRight = topLeft + QPointF(self.boundingRect().width(), self.boundingRect().height())
    return topLeft, bottomRight

def genericGetSceneCornerList(self):
    tl, br = self.getSceneCorners()
    return [tl.x(), tl.y(), br.x(), br.y()]

def genericGetOrderedCornerList(self, margin = None):
    r, pos = self.rect(), self.pos()
    if margin:
        r.adjust(-margin.x(), -margin.y(), margin.x(), margin.y())
    return [r.topLeft() + pos, r.topRight() + pos, r.bottomRight() + pos, r.bottomLeft() + pos]

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
QGraphicsRectItem.getSceneCorners = genericGetSceneCorners
QGraphicsRectItem.getSceneCornerList = genericGetSceneCornerList
QGraphicsRectItem.getOrderedCorners = genericGetOrderedCornerList

QGraphicsEllipseItem.getPage = genericGetPage
QGraphicsEllipseItem.getSceneCorners = genericGetSceneCorners
QGraphicsEllipseItem.getSceneCornerList = genericGetSceneCornerList
QGraphicsEllipseItem.getOrderedCorners = genericGetOrderedCornerList

QGraphicsEllipseItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsEllipseItem.mouseMoveEvent = genericMouseMoveEvent(QAbstractGraphicsShapeItem)
QGraphicsEllipseItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.mousePressEvent = genericMousePressEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseMoveEvent = genericMouseMoveEvent(QAbstractGraphicsShapeItem)
QGraphicsSimpleTextItem.mouseReleaseEvent = genericMouseReleaseEvent(QAbstractGraphicsShapeItem)

QGraphicsSimpleTextItem.getPage = genericGetPage
QGraphicsSimpleTextItem.getSceneCorners = genericGetSceneCorners
QGraphicsSimpleTextItem.getSceneCornerList = genericGetSceneCornerList
