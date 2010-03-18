"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicGradientDialog.py) is part of Lic.

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
from PyQt4.QtOpenGL import *

class HoverPoints(QObject):
    
    CircleShape = 1
    RectangleShape = 2

    LockToLeft   = 0x01
    LockToRight  = 0x02
    LockToTop    = 0x04
    LockToBottom = 0x08

    NoSort = 0
    XSort = 1
    YSort = 2

    NoConnection = 0
    LineConnection = 1
    CurveConnection = 2

    def __init__(self, parent, shape):
        QObject.__init__(self, parent)
        
        self.m_widget = parent
        self.m_widget.installEventFilter(self)
    
        self.m_points = []
        self.m_bounds = QRectF()
        self.m_shape = shape
        self.m_sortType = HoverPoints.NoSort
        self.m_connectionType = HoverPoints.CurveConnection
    
        self.m_locks = []
    
        self.m_pointPen = QPen(QColor(255, 255, 255, 191), 1)
        self.m_connectionPen = QPen(QColor(255, 255, 255, 127), 2)
        self.m_pointBrush = QBrush(QColor(191, 191, 191, 127))
        self.m_pointSize = QSize(11, 11)
        self.m_currentIndex = -1
        self.m_editable = True
        self.m_enabled = True
    
    def eventFilter(self, object, event):
        if (object != self.m_widget or not self.m_enabled):
            return False
    
        if (event.type() == QEvent.MouseButtonPress):

            clickPos = QPointF(event.pos())
            index = -1
            for i, point in enumerate(self.m_points):
                path = QPainterPath()
                if (self.m_shape == HoverPoints.CircleShape):
                    path.addEllipse(self.pointBoundingRect(point))
                else:
                    path.addRect(self.pointBoundingRect(point))

                if (path.contains(clickPos)):
                    index = i
                    break

            if (event.button() == Qt.LeftButton):
                if (index == -1):
                    if (not self.m_editable):
                        return False
                    pos = 0
                    if (self.m_sortType == HoverPoints.XSort):
                        for i, p in enumerate(self.m_points):
                            if (p.x() > clickPos.x()):
                                pos = i
                                break
                    elif (self.m_sortType == HoverPoints.YSort):
                        for i, p in enumerate(self.m_points):
                            if (p.y() > clickPos.y()):
                                pos = i
                                break

                    self.m_points.insert(pos, clickPos)
                    self.m_locks.insert(pos, 0)
                    self.m_currentIndex = pos
                    self.firePointChange()
                else:
                    self.m_currentIndex = index
                return True

            elif (event.button() == Qt.RightButton):
                if (index >= 0 and self.m_editable):
                    if (self.m_locks[index] == 0):
                        self.m_locks.pop(index)
                        self.m_points.pop(index)
                    self.firePointChange()
                    return True

        elif (event.type() == QEvent.MouseButtonRelease):
            self.m_currentIndex = -1

        elif (event.type() == QEvent.MouseMove):
            if (self.m_currentIndex >= 0):
                self.movePoint(self.m_currentIndex, QPointF(event.pos()))

        elif (event.type() == QEvent.Resize):
            if (event.oldSize().width() > 0 and event.oldSize().height() > 0):
                stretch_x = event.size().width() / float(event.oldSize().width())
                stretch_y = event.size().height() / float(event.oldSize().height())
                for i, p in enumerate(self.m_points):
                    self.movePoint(i, QPointF(p.x() * stretch_x, p.y() * stretch_y), False)
    
                self.firePointChange()

        elif (event.type() == QEvent.Paint):
            that_widget = self.m_widget
            self.m_widget = 0
            QApplication.sendEvent(object, event)
            self.m_widget = that_widget
            self.paintPoints()
            return True
        
        return False

    def bound_point(self, p, bounds, lock):
        left = bounds.left();
        right = bounds.right();
        top = bounds.top();
        bottom = bounds.bottom();
    
        if (p.x() < left or (lock & HoverPoints.LockToLeft)):
            p.setX(left)
        elif (p.x() > right or (lock & HoverPoints.LockToRight)):
            p.setX(right)
    
        if (p.y() < top or (lock & HoverPoints.LockToTop)):
            p.setY(top)
        elif (p.y() > bottom or (lock & HoverPoints.LockToBottom)):
            p.setY(bottom)
        return p

    def paintPoints(self):
        p = QPainter()
        p.begin(self.m_widget)
    
        p.setRenderHint(QPainter.Antialiasing)
    
        if (self.m_connectionPen.style() != Qt.NoPen and self.m_connectionType != HoverPoints.NoConnection):
            p.setPen(self.m_connectionPen)
    
            if (self.m_connectionType == HoverPoints.CurveConnection):
                path = QPainterPath()
                path.moveTo(self.m_points[0])
                for p1, p2 in zip(self.m_points[:-1], self.m_points[1:]):
                    distance = p2.x() - p1.x()
    
                    path.cubicTo(p1.x() + distance / 2, p1.y(),
                                 p1.x() + distance / 2, p2.y(),
                                 p2.x(), p2.y())
                p.drawPath(path)
            else:
                p.drawPolyline(self.m_points)
    
        p.setPen(self.m_pointPen)
        p.setBrush(self.m_pointBrush)
    
        for point in self.m_points:
            bounds = self.pointBoundingRect(point)
            if (self.m_shape == HoverPoints.CircleShape):
                p.drawEllipse(bounds)
            else:
                p.drawRect(bounds)

    def pointBoundingRect(self, p):
        w = self.m_pointSize.width()
        h = self.m_pointSize.height()
        x = p.x() - w / 2.0
        y = p.y() - h / 2.0
        return QRectF(x, y, w, h)

    def setBoundingRect(self, boundingRect):
        self.m_bounds = boundingRect

    def points(self):
        return self.m_points
    
    def setPoints(self, points):
        self.m_points = []
        for point in points:
            self.m_points.append(self.bound_point(point, self.boundingRect(), 0))
        self.m_locks = [0] * len(self.m_points)

    def pointSize(self):
        return self.m_pointSize
    
    def setPointSize(self, size):
        self.m_pointSize = size

    def sortType(self):
        return self.m_sortType
    
    def setSortType(self, sortType):
        self.m_sortType = sortType

    def connectionType(self):
        return self.m_connectionType
    
    def setConnectionType(self, connectionType):
        self.m_connectionType = connectionType

    def setConnectionPen(self, pen):
        self.m_connectionPen = pen
        
    def setShapePen(self, pen):
        self.m_pointPen = pen
        
    def setShapeBrush(self, brush):
        self.m_pointBrush = brush

    def setPointLock(self, pos, lock):
        self.m_locks[pos] = lock

    def setEditable(self, editable):
        self.m_editable = editable
        
    def editable(self):
        return self.m_editable

    def setEnabled(self, enabled):
        if (self.m_enabled != enabled):
            self.m_enabled = enabled
            self.m_widget.update()
    
    def setDisabled(self, disabled):
        self.setEnabled(not disabled)

    def firePointChange(self):
        if (self.m_sortType != HoverPoints.NoSort):
    
            oldCurrent = QPointF()
            if (self.m_currentIndex != -1):
                oldCurrent = self.m_points[self.m_currentIndex]

            if (self.m_sortType == HoverPoints.XSort):
                self.m_points.sort(key = lambda p: p.x())
            elif (self.m_sortType == HoverPoints.YSort):
                self.m_points.sort(key = lambda p: p.y())
    
            if (self.m_currentIndex != -1):
                for i in range(0, len(self.m_points)):
                    if (self.m_points[i] == oldCurrent):
                        self.m_currentIndex = i
                        break
    
        self.emit(SIGNAL("pointsChanged"), self.m_points)
        self.m_widget.update()
    
    def boundingRect(self):
        if (self.m_bounds.isEmpty()):
            return self.m_widget.rect()
        else:
            return self.m_bounds

    def movePoint(self, index, point, emitUpdate = True):
        self.m_points[index] = self.bound_point(point, self.boundingRect(), self.m_locks[index])
        if emitUpdate:
            self.firePointChange()

class ShadeWidget(QWidget):
    
    RedShade = 1
    GreenShade = 2
    BlueShade = 3
    ARGBShade = 4
    
    def __init__(self, type, parent):
        QWidget.__init__(self, parent)
        
        self.m_shade_type = type
        self.m_shade = QImage()
        self.m_alpha_gradient = QLinearGradient(0, 0, 0, 0)

        if (self.m_shade_type == self.ARGBShade):
            pm = QPixmap(20, 20)
            pmp = QPainter(pm)
            pmp.fillRect(0, 0, 10, 10, Qt.lightGray)
            pmp.fillRect(10, 10, 10, 10, Qt.lightGray)
            pmp.fillRect(0, 10, 10, 10, Qt.darkGray)
            pmp.fillRect(10, 0, 10, 10, Qt.darkGray)
            pmp.end()
            pal = self.palette()
            pal.setBrush(self.backgroundRole(), QBrush(pm))
            self.setAutoFillBackground(True)
            self.setPalette(pal)
        else:
            self.setAttribute(Qt.WA_OpaquePaintEvent)
    
        points = [QPointF(0, self.sizeHint().height()), QPointF(self.sizeHint().width(), 0)]
    
        self.m_hoverPoints = HoverPoints(self, HoverPoints.CircleShape)
        self.m_hoverPoints.setPoints(points)
        self.m_hoverPoints.setPointLock(0, HoverPoints.LockToLeft)
        self.m_hoverPoints.setPointLock(1, HoverPoints.LockToRight)
        self.m_hoverPoints.setSortType(HoverPoints.XSort)
    
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    
        self.connect(self.m_hoverPoints, SIGNAL("pointsChanged"), self, SIGNAL("colorsChanged()"))

    def points(self):
        return self.m_hoverPoints.points()

    def colorAt(self, x):
        self.generateShade()
        pts = self.m_hoverPoints.points()
        for p1, p2 in zip(pts[:-1], pts[1:]):
            if p1.x() <= x and p2.x() >= x:
                l = QLineF(p1, p2)
                l.setLength(l.length() * ((x - l.x1()) / max(l.dx(), 0.1)))
                return self.m_shade.pixel(round(min(l.x2(), (float(self.m_shade.width() - 1)))),
                                      round(min(l.y2(), float(self.m_shade.height() - 1))))
        return 0

    def setGradientStops(self, stops):
        if (self.m_shade_type != self.ARGBShade):
            return
        
        self.m_alpha_gradient = QLinearGradient(0, 0, self.width(), 0)

        for position, color in stops:
            self.m_alpha_gradient.setColorAt(position, color)

        self.m_shade = QImage()
        self.generateShade()
        self.update()

    def paintEvent(self, event):
        self.generateShade()
    
        p = QPainter(self)
        p.drawImage(0, 0, self.m_shade)
        p.setPen(QColor(146, 146, 146))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

    def sizeHint(self):
        return QSize(150, 40)
    
    def hoverPoints(self):
        return self.m_hoverPoints
    
    def generateShade(self):
        if (not self.m_shade.isNull() and self.m_shade.size() == self.size()):
            return
    
        if (self.m_shade_type == self.ARGBShade):
            self.m_shade = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
            self.m_shade.fill(0)

            p = QPainter(self.m_shade)
            p.fillRect(self.rect(), self.m_alpha_gradient)

            p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            fade = QLinearGradient(0, 0, 0, self.height())
            fade.setColorAt(0, QColor(0, 0, 0, 255))
            fade.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), fade)

        else:
            self.m_shade = QImage(self.size(), QImage.Format_RGB32)
            shade = QLinearGradient(0, 0, 0, self.height())
            shade.setColorAt(1, Qt.black)

            if (self.m_shade_type == self.RedShade):
                shade.setColorAt(0, Qt.red)
            elif (self.m_shade_type == self.GreenShade):
                shade.setColorAt(0, Qt.green)
            else:
                shade.setColorAt(0, Qt.blue)

            p = QPainter(self.m_shade)
            p.fillRect(self.rect(), shade)
    
class GradientRenderer(QWidget):

    def __init__(self, parent, pageSize):
        QWidget.__init__(self, parent)

        self.pageSize = pageSize
        self.m_tile = QPixmap(128, 128)
        self.m_tile.fill(Qt.white)

        pt = QPainter(self.m_tile)
        color = QColor (230, 230, 230)
        pt.fillRect(0, 0, 64, 64, color)
        pt.fillRect(64, 64, 64, 64, color)
        pt.end()
        
        self.static_image = None
        
        self.m_hoverPoints = HoverPoints(self, HoverPoints.CircleShape)
        self.m_hoverPoints.setPointSize(QSize(20, 20))
        self.m_hoverPoints.setConnectionType(HoverPoints.NoConnection)
        self.m_hoverPoints.setEditable(False)
        self.m_hoverPoints.setPoints([QPointF(100, 100), QPointF(200, 200)])
        
        self.m_spread = QGradient.PadSpread
        self.m_gradientType = QGradient.LinearGradient
        self.m_stops = []
        self.setMaximumSize(self.pageSize)
        self.setMinimumSize(self.pageSize)

    def sizeHint(self):
        return self.pageSize
    
    def setGradientStops(self, stops):
        self.m_stops = list(stops)
        self.update()

    def hoverPoints(self):
        return self.m_hoverPoints
    
    def setSpread(self, spread):
        self.m_spread = spread
        self.update()
        
    def setGradientType(self, gradientType):
        self.m_gradientType = gradientType
        self.update()

    def getGradient(self):

        pts = self.m_hoverPoints.points()
        g = None

        if (self.m_gradientType == QGradient.LinearGradient):
            g = QLinearGradient(pts[0], pts[1])
        elif (self.m_gradientType == QGradient.RadialGradient):
            line = QLineF(pts[0], pts[1])
            if (line.length() > 132):
                line.setLength(132)
            g = QRadialGradient(line.p1(), min(self.pageSize.width(), self.pageSize.height()) / 3.0, line.p2())
        else:
            l = QLineF (pts[0], pts[1])
            angle = l.angle(QLineF(0, 0, 1, 0))
            if (l.dy() > 0):
                angle = 360 - angle
            g = QConicalGradient(pts[0], angle)

        for pos, color in self.m_stops:
            g.setColorAt(pos, color)
            
        g.setSpread(self.m_spread)
        return g
    
    def paintEvent(self, e):

        painter = QPainter();
            
        if (not self.static_image or self.static_image.size() != self.size()):
            self.static_image = QPixmap(self.size())
            
        painter.begin(self.static_image);

        o = 10;

        bg = self.palette().brush(QPalette.Background)
        painter.fillRect(0, 0, o, o, bg);
        painter.fillRect(self.width() - o, 0, o, o, bg)
        painter.fillRect(0, self.height() - o, o, o, bg)
        painter.fillRect(self.width() - o, self.height() - o, o, o, bg)
    
        painter.setClipRect(e.rect())
        painter.setRenderHint(QPainter.Antialiasing)
    
        clipPath = QPainterPath()
    
        r = self.rect()
        left = r.x() + 1
        top = r.y() + 1
        right = r.right()
        bottom = r.bottom()
        radius2 = 8 * 2
    
        clipPath.moveTo(right - radius2, top)
        clipPath.arcTo(right - radius2, top, radius2, radius2, 90, -90)
        clipPath.arcTo(right - radius2, bottom - radius2, radius2, radius2, 0, -90)
        clipPath.arcTo(left, bottom - radius2, radius2, radius2, 270, -90)
        clipPath.arcTo(left, top, radius2, radius2, 180, -90)
        clipPath.closeSubpath()
    
        painter.save()
        painter.setClipPath(clipPath, Qt.IntersectClip)
        painter.drawTiledPixmap(self.rect(), self.m_tile)

        g = self.getGradient()
        painter.setBrush(g)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
    
        painter.restore()
    
        level = 180
        painter.setPen(QPen(QColor(level, level, level), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(clipPath)
    
        painter.end()
        painter.begin(self)
        painter.drawPixmap(e.rect(), self.static_image, e.rect())

class GradientEditor(QWidget):

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        vbox = QVBoxLayout(self)
        vbox.setSpacing(1)
        vbox.setMargin(1)
    
        self.m_red_shade = ShadeWidget(ShadeWidget.RedShade, self)
        self.m_green_shade = ShadeWidget(ShadeWidget.GreenShade, self)
        self.m_blue_shade = ShadeWidget(ShadeWidget.BlueShade, self)
        self.m_alpha_shade = ShadeWidget(ShadeWidget.ARGBShade, self)
    
        vbox.addWidget(self.m_red_shade)
        vbox.addWidget(self.m_green_shade)
        vbox.addWidget(self.m_blue_shade)
        vbox.addWidget(self.m_alpha_shade)
    
        self.connect(self.m_red_shade, SIGNAL("colorsChanged()"), self.pointsUpdated)
        self.connect(self.m_green_shade, SIGNAL("colorsChanged()"), self.pointsUpdated)
        self.connect(self.m_blue_shade, SIGNAL("colorsChanged()"), self.pointsUpdated)
        self.connect(self.m_alpha_shade, SIGNAL("colorsChanged()"), self.pointsUpdated)

    def pointsUpdated(self):
        
        w = self.m_alpha_shade.width()
        stops = []
        points = []

        points += self.m_red_shade.points()
        points += self.m_green_shade.points()
        points += self.m_blue_shade.points()
        points += self.m_alpha_shade.points()

        points.sort(key = lambda p: p.x())

        for i in range(0, len(points)):
            x = points[i].x()
            if (i < len(points) - 1 and x == points[i+1].x()):
                continue
            color = QColor((0x00ff0000 & self.m_red_shade.colorAt(x)) >> 16,
                           (0x0000ff00 & self.m_green_shade.colorAt(x)) >> 8,
                           (0x000000ff & self.m_blue_shade.colorAt(x)),
                           (0xff000000 & self.m_alpha_shade.colorAt(x)) >> 24)
    
            if (x / w > 1):
                return
    
            stops.append((x / w, color))

        self.m_alpha_shade.setGradientStops(stops)
        self.emit(SIGNAL("gradientStopsChanged"), stops)

    def setGradientStops(self, stops):
        def set_shade_points(points, shade):
            shade.hoverPoints().setPoints(points)
            shade.hoverPoints().setPointLock(0, HoverPoints.LockToLeft)
            shade.hoverPoints().setPointLock(len(points) - 1, HoverPoints.LockToRight)
            shade.update()

        pts_red, pts_green, pts_blue, pts_alpha = [], [], [], []

        h_red = self.m_red_shade.height()
        h_green = self.m_green_shade.height()
        h_blue = self.m_blue_shade.height()
        h_alpha = self.m_alpha_shade.height()

        for pos, color in stops:
            color = color.rgba()
            pts_red.append(QPointF(pos * self.m_red_shade.width(), h_red - qRed(color) * h_red / 255))
            pts_green.append(QPointF(pos * self.m_green_shade.width(), h_green - qGreen(color) * h_green / 255))
            pts_blue.append(QPointF(pos * self.m_blue_shade.width(), h_blue - qBlue(color) * h_blue / 255))
            pts_alpha.append(QPointF(pos * self.m_alpha_shade.width(), h_alpha - qAlpha(color) * h_alpha / 255))

        set_shade_points(pts_red, self.m_red_shade)
        set_shade_points(pts_green, self.m_green_shade)
        set_shade_points(pts_blue, self.m_blue_shade)
        set_shade_points(pts_alpha, self.m_alpha_shade)

class GradientDialog(QDialog):

    def __init__(self, parent, pageSize, initialGradient = None):
        QDialog.__init__(self, parent)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setWindowTitle("Gradient Editor")
        self.m_renderer = GradientRenderer(self, pageSize)
    
        mainGroup = QGroupBox(self)
        mainGroup.setTitle("Gradients")
    
        editorGroup = QGroupBox(mainGroup)
        editorGroup.setTitle("Color Editor")
        self.m_editor = GradientEditor(editorGroup)
    
        typeGroup = QGroupBox(mainGroup)
        typeGroup.setTitle("Gradient Type")
        self.m_linearButton = QRadioButton("Linear Gradient", typeGroup)
        self.m_radialButton = QRadioButton("Radial Gradient", typeGroup)
        self.m_conicalButton = QRadioButton("Conical Gradient", typeGroup)
    
        spreadGroup = QGroupBox(mainGroup)
        spreadGroup.setTitle("Spread Method")
        self.m_padSpreadButton = QRadioButton("Pad Spread", spreadGroup)
        self.m_reflectSpreadButton = QRadioButton("Reflect Spread", spreadGroup)
        self.m_repeatSpreadButton = QRadioButton("Repeat Spread", spreadGroup)
    
        defaultsGroup = QGroupBox(mainGroup)
        defaultsGroup.setTitle("Defaults")
        default1Button = QPushButton("1", defaultsGroup)
        default2Button = QPushButton("2", defaultsGroup)
        default3Button = QPushButton("3", defaultsGroup)
        default4Button = QPushButton("Reset", editorGroup)
    
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal)
    
        mainLayout = QHBoxLayout(self)
        mainLayout.addWidget(self.m_renderer)
        mainLayout.addWidget(mainGroup)
    
        mainGroup.setFixedWidth(180)
        mainGroupLayout = QVBoxLayout(mainGroup)
        mainGroupLayout.addWidget(editorGroup)
        mainGroupLayout.addWidget(typeGroup)
        mainGroupLayout.addWidget(spreadGroup)
        mainGroupLayout.addWidget(defaultsGroup)
        mainGroupLayout.addStretch(1)
        mainGroupLayout.addWidget(buttonBox)
    
        editorGroupLayout = QVBoxLayout(editorGroup)
        editorGroupLayout.addWidget(self.m_editor)
    
        typeGroupLayout = QVBoxLayout(typeGroup)
        typeGroupLayout.addWidget(self.m_linearButton)
        typeGroupLayout.addWidget(self.m_radialButton)
        typeGroupLayout.addWidget(self.m_conicalButton)
    
        spreadGroupLayout = QVBoxLayout(spreadGroup)
        spreadGroupLayout.addWidget(self.m_padSpreadButton)
        spreadGroupLayout.addWidget(self.m_repeatSpreadButton)
        spreadGroupLayout.addWidget(self.m_reflectSpreadButton)
    
        defaultsGroupLayout = QHBoxLayout(defaultsGroup)
        defaultsGroupLayout.addWidget(default1Button)
        defaultsGroupLayout.addWidget(default2Button)
        defaultsGroupLayout.addWidget(default3Button)
        editorGroupLayout.addWidget(default4Button)
    
        self.connect(self.m_editor, SIGNAL("gradientStopsChanged"), self.m_renderer.setGradientStops)
    
        self.connect(self.m_linearButton, SIGNAL("clicked()"), lambda: self.m_renderer.setGradientType(QGradient.LinearGradient))
        self.connect(self.m_radialButton, SIGNAL("clicked()"), lambda: self.m_renderer.setGradientType(QGradient.RadialGradient))
        self.connect(self.m_conicalButton, SIGNAL("clicked()"), lambda: self.m_renderer.setGradientType(QGradient.ConicalGradient))
    
        self.connect(self.m_padSpreadButton, SIGNAL("clicked()"), lambda: self.m_renderer.setSpread(QGradient.PadSpread))
        self.connect(self.m_reflectSpreadButton, SIGNAL("clicked()"), lambda: self.m_renderer.setSpread(QGradient.ReflectSpread))
        self.connect(self.m_repeatSpreadButton, SIGNAL("clicked()"), lambda: self.m_renderer.setSpread(QGradient.RepeatSpread))
    
        self.connect(default1Button, SIGNAL("clicked()"), lambda: self.setDefault(1))
        self.connect(default2Button, SIGNAL("clicked()"), lambda: self.setDefault(2))
        self.connect(default3Button, SIGNAL("clicked()"), lambda: self.setDefault(3))
        self.connect(default4Button, SIGNAL("clicked()"), lambda: self.setDefault(4))
    
        self.connect(buttonBox, SIGNAL("accepted()"), self, SLOT("accept()"))
        self.connect(buttonBox, SIGNAL("rejected()"), self, SLOT("reject()"))
        
        if initialGradient:
            QTimer.singleShot(50, lambda: self.setGradient(initialGradient))
        else:
            QTimer.singleShot(50, lambda: self.setDefault(1))

    def getGradient(self):
        return self.m_renderer.getGradient()

    def setGradient(self, g):

        pts = None
        if g.type() == QGradient.LinearGradient:
            g.__class__ = QLinearGradient
            pts = [g.start(), g.finalStop()]
            self.m_linearButton.animateClick()
        elif g.type() == QGradient.RadialGradient:
            g.__class__ = QRadialGradient
            pts = [g.center(), g.focalPoint()]
            self.m_radialButton.animateClick()
        elif g.type() == QGradient.ConicalGradient:
            g.__class__ = QConicalGradient
            l = QLineF(g.center(), QPointF(0, 0))
            l.setAngle(g.angle())
            l.setLength(120)
            pts = [g.center(), l.p2()]
            self.m_conicalButton.animateClick()

        if g.spread() == QGradient.PadSpread:
            self.m_padSpreadButton.animateClick()
        elif g.spread() == QGradient.RepeatSpread:
            self.m_repeatSpreadButton.animateClick()
        elif g.spread() == QGradient.ReflectSpread:
            self.m_reflectSpreadButton.animateClick()

        self.m_editor.setGradientStops(g.stops())
        self.m_renderer.hoverPoints().setPoints(pts)
        self.m_renderer.setGradientStops(g.stops())
    
    def setDefault(self, config):
        stops = []
        if config == 1:
            stops.append((0.00, QColor.fromRgba(0)))
            stops.append((0.04, QColor.fromRgba(0xff131360)))
            stops.append((0.08, QColor.fromRgba(0xff202ccc)))
            stops.append((0.42, QColor.fromRgba(0xff93d3f9)))
            stops.append((0.51, QColor.fromRgba(0xffb3e6ff)))
            stops.append((0.73, QColor.fromRgba(0xffffffec)))
            stops.append((0.92, QColor.fromRgba(0xff5353d9)))
            stops.append((0.96, QColor.fromRgba(0xff262666)))
            stops.append((1.00, QColor.fromRgba(0)))
            self.m_linearButton.animateClick()
            self.m_repeatSpreadButton.animateClick()

        elif config == 2:
            stops.append((0.00, QColor.fromRgba(0xffffffff)))
            stops.append((0.11, QColor.fromRgba(0xfff9ffa0)))
            stops.append((0.13, QColor.fromRgba(0xfff9ff99)))
            stops.append((0.14, QColor.fromRgba(0xfff3ff86)))
            stops.append((0.49, QColor.fromRgba(0xff93b353)))
            stops.append((0.87, QColor.fromRgba(0xff264619)))
            stops.append((0.96, QColor.fromRgba(0xff0c1306)))
            stops.append((1.00, QColor.fromRgba(0)))
            self.m_radialButton.animateClick()
            self.m_padSpreadButton.animateClick()

        elif config == 3:
            stops.append((0.00, QColor.fromRgba(0)))
            stops.append((0.10, QColor.fromRgba(0xffe0cc73)))
            stops.append((0.17, QColor.fromRgba(0xffc6a006)))
            stops.append((0.46, QColor.fromRgba(0xff600659)))
            stops.append((0.72, QColor.fromRgba(0xff0680ac)))
            stops.append((0.92, QColor.fromRgba(0xffb9d9e6)))
            stops.append((1.00, QColor.fromRgba(0)))
            self.m_conicalButton.animateClick()
            self.m_padSpreadButton.animateClick()

        elif config == 4:
            stops.append((0.00, QColor.fromRgba(0xff000000)))
            stops.append((1.00, QColor.fromRgba(0xffffffff)))
            
        else:
            qWarning("bad default: %d\n", config)

        h_off = self.m_renderer.width() / 10
        v_off = self.m_renderer.height() / 8
        pts = [QPointF(self.m_renderer.width() / 2, self.m_renderer.height() / 2),
               QPointF(self.m_renderer.width() / 2 - h_off, self.m_renderer.height() / 2 - v_off)]
    
        self.m_editor.setGradientStops(stops)
        self.m_renderer.hoverPoints().setPoints(pts)
        self.m_renderer.setGradientStops(stops)
