#from __future__ import division
import random
import sys
import math
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

from Model_qt import *

try:
    from OpenGL.GL import *
except ImportError:
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Lic 0.1",
                            "PyOpenGL must be installed to run Lic.",
                            QMessageBox.Ok | QMessageBox.Default,
                            QMessageBox.NoButton)
    sys.exit(1)

PageSize = QSize(800, 600)

class InstructionViewWidget(QGraphicsView):
    def __init__(self,  parent = None):
        QGLWidget.__init__(self,  parent)
        
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(Qt.gray))
        
    def resizeEvent(self, event = None):
        pass

class LicWindow(QMainWindow):

    pageInset = 41
    
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)

        self.glWidget = QGLWidget(self)
        self.filename = QString()
        
        self.view = InstructionViewWidget(self)
        self.tree = QTreeWidget(self)
        
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(0, 0, PageSize.width() + LicWindow.pageInset, PageSize.height() + LicWindow.pageInset)
        self.view.setScene(self.scene)
    
        self.mainSplitter = QSplitter(Qt.Horizontal)
        
        if (0):
            self.glWidget = GLPreviewWidget(self)
            self.glSplitter = QSplitter(Qt.Horizontal)
            self.glSplitter.addWidget(self.glWidget)
            self.glSplitter.addWidget(self.view)
        
            self.mainSplitter.addWidget(self.tree)
            self.mainSplitter.addWidget(self.glSplitter)
            self.setCentralWidget(self.mainSplitter)
        else:
            self.mainSplitter.addWidget(self.tree)
            self.mainSplitter.addWidget(self.view)
            self.setCentralWidget(self.mainSplitter)

        self.setWindowTitle(self.tr("Lic 0.1"))
        
        Page.pageInset = LicWindow.pageInset / 2.0
        
        #modelName = None
        modelName = "pyramid_orig.dat"
        #modelName = "Blaster.mpd"
        #modelName = "3001.DAT"
        
        if modelName:
            self.load_model("c:\\ldrawparts\\models\\" + modelName)

    def position(self):
        point = self.mapFromGlobal(QCursor.pos())
        if not self.view.geometry().contains(point):
            point = QPoint(20, 20)
        else:
            if point == self.prevPoint:
                point += QPoint(self.addOffset, self.addOffset)
                self.addOffset += 5
            else:
                self.addOffset = 5
                self.prevPoint = point
        return self.view.mapToScene(point)

    def addPixmap(self):
        path = QFileInfo(self.filename).path() if not self.filename.isEmpty() else "."
        fname = QFileDialog.getOpenFileName(self,
                            "Page Designer - Add Pixmap", path,
                            "Pixmap Files (*.bmp *.jpg *.png *.xpm)")
        if fname.isEmpty():
            return
        self.createPixmapItem(QPixmap(fname), self.position())

    def createPixmapItem(self, pixmap, position, matrix=QMatrix()):
        item = QGraphicsPixmapItem(pixmap)
        item.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        item.setPos(position)
        item.setMatrix(matrix)
        self.scene.clearSelection()
        self.scene.addItem(item)
        item.setSelected(True)
        global Dirty
        Dirty = True

    def load_model(self, filename):
    
        try:
            self.instructions = Instructions(filename, self.scene, self.glWidget)
        except IOError:
            print "Could not find file %s" % (filename)
            return

        self.update()

class GLPreviewWidget(QGLWidget):
    def __init__(self, parent = None):
        QGLWidget.__init__(self, parent)

        self.object = self.bufObject = 0
        self.xRot = self.yRot = self.zRot = 0

        self.lastPos = QPoint()

        self.green = QColor.fromCmykF(0.40, 0.0, 1.0, 0.0)
        self.purple = QColor.fromCmykF(0.39, 0.39, 0.0, 0.0)

    def xRotation(self):
        return self.xRot

    def yRotation(self):
        return self.yRot

    def zRotation(self):
        return self.zRot

    def minimumSizeHint(self):
        return QSize(50, 50)

    def sizeHint(self):
        return QSize(512, 512)

    def setXRotation(self, angle):
        angle = self.normalizeAngle(angle)
        if angle != self.xRot:
            self.xRot = angle
            self.emit(SIGNAL("xRotationChanged(int)"), angle)
            self.updateGL()

    def setYRotation(self, angle):
        angle = self.normalizeAngle(angle)
        if angle != self.yRot:
            self.yRot = angle
            self.emit(SIGNAL("yRotationChanged(int)"), angle)
            self.updateGL()

    def setZRotation(self, angle):
        angle = self.normalizeAngle(angle)
        if angle != self.zRot:
            self.zRot = angle
            self.emit(SIGNAL("zRotationChanged(int)"), angle)
            self.updateGL()

    def initializeGL(self):
    
        self.qglClearColor(self.purple.dark())
        self.object = self.makeObject()
        glShadeModel(GL_SMOOTH)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        
        self.drawBuffer()

    def drawBuffer(self):
        
        size = 600
        pBuffer = QGLPixelBuffer(size,  size, QGLFormat(), self)
        pBuffer.makeCurrent()

        painter = QPainter()
        painter.begin(pBuffer)
        painter.setRenderHint(QPainter.Antialiasing)
        
        glPushAttrib(GL_ALL_ATTRIB_BITS)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        self.qglClearColor(self.purple.dark())
        glShadeModel(GL_SMOOTH)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        
        lightPosition = ( 0.5, 5.0, 7.0, 1.0 )
        glLightfv(GL_LIGHT0, GL_POSITION, lightPosition)
        
        self.resizeGL(self.width(), self.height())
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glLoadIdentity()
        glTranslated(0.0, 0.0, -10.0)
        glRotated(self.xRot / 16.0, 1.0, 0.0, 0.0)
        glRotated(self.yRot / 16.0, 0.0, 1.0, 0.0)
        glRotated(self.zRot / 16.0, 0.0, 0.0, 1.0)
        glCallList(self.object)
        
        glDisable(GL_LIGHT0)
        glPopAttrib()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()

        glDisable(GL_CULL_FACE)
        painter.end()

        image = pBuffer.toImage()
        if image:
            image.save("C:\\ldraw\\pixbuf_x.png", None)

        self.makeCurrent()

    def paintGL(self):        
    
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setPen(QPen())
        painter.setBrush(QBrush())
        
        glPushAttrib(GL_ALL_ATTRIB_BITS)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        self.qglClearColor(self.purple.dark())
        glShadeModel(GL_SMOOTH)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        
        lightPosition = ( 0.5, 5.0, 7.0, 1.0 )
        glLightfv(GL_LIGHT0, GL_POSITION, lightPosition)
        
        self.resizeGL(self.width(), self.height())
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glLoadIdentity()
        glTranslated(0.0, 0.0, -10.0)
        glRotated(self.xRot / 16.0, 1.0, 0.0, 0.0)
        glRotated(self.yRot / 16.0, 0.0, 1.0, 0.0)
        glRotated(self.zRot / 16.0, 0.0, 0.0, 1.0)
        glCallList(self.object)
        
        glDisable(GL_LIGHT0)
        glPopAttrib()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()

        glDisable(GL_CULL_FACE)
        
        painter.drawRect(QRect(3,  5,  10,  12))
        painter.end()

    def resizeGL(self, width, height):
        side = min(width, height)
        glViewport((width - side) / 2, (height - side) / 2, side, side)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-0.5, +0.5, +0.5, -0.5, 4.0, 15.0)
        glMatrixMode(GL_MODELVIEW)

    def mousePressEvent(self, event):
        self.lastPos = QPoint(event.pos())

    def mouseMoveEvent(self, event):
        dx = event.x() - self.lastPos.x()
        dy = event.y() - self.lastPos.y()

        if event.buttons() & Qt.LeftButton:
            self.setXRotation(self.xRot + 8 * dy)
            self.setYRotation(self.yRot + 8 * dx)
        elif event.buttons() & Qt.RightButton:
            self.setXRotation(self.xRot + 8 * dy)
            self.setZRotation(self.zRot + 8 * dx)

        self.lastPos = QPoint(event.pos())

    def makeObject(self):
        genList = glGenLists(1)
        glNewList(genList, GL_COMPILE)

        glEnable(GL_NORMALIZE)
        glBegin(GL_QUADS)

        logoDiffuseColor = (self.green.red()/255.0, self.green.green()/255.0, self.green.blue()/255.0, 1.0)
        glMaterialfv(GL_FRONT, GL_DIFFUSE, logoDiffuseColor)
        
        x1 = +0.06
        y1 = -0.14
        x2 = +0.14
        y2 = -0.06
        x3 = +0.08
        y3 = +0.00
        x4 = +0.30
        y4 = +0.22

        self.quad(x1, y1, x2, y2, y2, x2, y1, x1)
        self.quad(x3, y3, x4, y4, y4, x4, y3, x3)

        self.extrude(x1, y1, x2, y2)
        self.extrude(x2, y2, y2, x2)
        self.extrude(y2, x2, y1, x1)
        self.extrude(y1, x1, x1, y1)
        self.extrude(x3, y3, x4, y4)
        self.extrude(x4, y4, y4, x4)
        self.extrude(y4, x4, y3, x3)

        Pi = 3.14159265358979323846
        NumSectors = 200

        for i in range(NumSectors):
            angle1 = (i * 2 * Pi) / NumSectors
            x5 = 0.30 * math.sin(angle1)
            y5 = 0.30 * math.cos(angle1)
            x6 = 0.20 * math.sin(angle1)
            y6 = 0.20 * math.cos(angle1)

            angle2 = ((i + 1) * 2 * Pi) / NumSectors
            x7 = 0.20 * math.sin(angle2)
            y7 = 0.20 * math.cos(angle2)
            x8 = 0.30 * math.sin(angle2)
            y8 = 0.30 * math.cos(angle2)

            self.quad(x5, y5, x6, y6, x7, y7, x8, y8)

            self.extrude(x6, y6, x7, y7)
            self.extrude(x8, y8, x5, y5)

        glEnd()
        glEndList()

        return genList

    def quad(self, x1, y1, x2, y2, x3, y3, x4, y4):

        glNormal3d(0.0, 0.0, -1.0)
        glVertex3d(x1, y1, -0.05)
        glVertex3d(x2, y2, -0.05)
        glVertex3d(x3, y3, -0.05)
        glVertex3d(x4, y4, -0.05)

        glNormal3d(0.0, 0.0, 1.0)
        glVertex3d(x4, y4, +0.05)
        glVertex3d(x3, y3, +0.05)
        glVertex3d(x2, y2, +0.05)
        glVertex3d(x1, y1, +0.05)

    def extrude(self, x1, y1, x2, y2):
        self.qglColor(self.green.dark(250 + int(100 * x1)))

        glNormal3d((x1 + x2)/2.0, (y1 + y2)/2.0, 0.0)
        glVertex3d(x1, y1, +0.05)
        glVertex3d(x2, y2, +0.05)
        glVertex3d(x2, y2, -0.05)
        glVertex3d(x1, y1, -0.05)

    def normalizeAngle(self, angle):
        while angle < 0:
            angle += 360 * 16
        while angle > 360 * 16:
            angle -= 360 * 16
        return angle

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LicWindow()
    window.show()
    sys.exit(app.exec_())
