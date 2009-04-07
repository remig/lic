try:
    from OpenGL.GL import *
except ImportError:
    app = QApplication(sys.argv)
    QMessageBox.critical(None, "Lic 0.1",
                         "PyOpenGL must be installed to run Lic.",
                         QMessageBox.Ok | QMessageBox.Default,
                         QMessageBox.NoButton)
    sys.exit(1)

def paint(self, painter, option, widget = None):
    global GlobalGLContext
    GlobalGLContext.makeCurrent()
    
    minX = minY = 20.0
    maxX = maxY = 0.0

    GLHelpers.initFreshContext()
    GLHelpers.adjustGLViewport(0, 0, 80, 80)
    GLHelpers.rotateToDefaultView(100.0, 100.0, 0.0, PLI.scale)
    
    b = self.partOGL.getBoundingBox()
    
    for v in b.vertices():
        res = GLU.gluProject(v[0], v[1], v[2])
        maxX = max(res[0], maxX)
        maxY = max(res[1], maxY)
        minX = min(res[0], minX)
        minY = min(res[1], minY)
        
    self.setPos(minX, minY)
    self.setRect(0.0, 0.0, maxX-minX, maxY-minY)
    QGraphicsRectItem.paint(self, painter, option, widget)

    """
    aX, aY, aZ = GLU.gluUnProject(minX, minY, 0.0)
    bX, bY, bZ = GLU.gluUnProject(minX, maxY, 0.0)
    cX, cY, cZ = GLU.gluUnProject(maxX, maxY, 0.0)
    dX, dY, dZ = GLU.gluUnProject(maxX, minY, 0.0)
    
    GL.glPushAttrib(GL.GL_CURRENT_BIT)
    GL.glColor4fv([1.0, 1.0, 1.0, 1.0])
    
    GL.glBegin(GL.GL_LINE_LOOP)
    GL.glVertex3f(aX, aY, aZ)
    GL.glVertex3f(bX, bY, bZ)
    GL.glVertex3f(cX, cY, cZ)
    GL.glVertex3f(dX, dY, dZ)
    GL.glEnd()

    GL.glPopAttrib()
    """
        
def displaceManySelectedParts():
    partList = []
    for item in self.scene().selectedItems():
        if isinstance(item, Part):
            oldPos = item.displacement if item.displacement else [0.0, 0.0, 0.0]
            newPos = [0, 0, 0]
            newPos[0] = oldPos[0] + displacement[0]
            newPos[1] = oldPos[1] + displacement[1]
            newPos[2] = oldPos[2] + displacement[2]
            partList.append((item, oldPos, newPos))
                
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

def createGLTrackballWidget():
    if (0):
        self.glSplitter = QSplitter(Qt.Horizontal)
        self.glSplitter.addWidget(self.glWidget)
        self.glSplitter.addWidget(self.view)
    
        self.mainSplitter.addWidget(self.tree)
        self.mainSplitter.addWidget(self.glSplitter)
        self.setCentralWidget(self.mainSplitter)
    else:
        pass

class LicTree(QAbstractItemModel):

    def __init__(self):
        QAbstractItemModel.__init__(self)
        
    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        if role != Qt.DisplayRole:
            return QVariant()        
        
    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
    
    def headerData(self, section, orientation, role):
        if (orientation == Qt.Horizontal) and ( role == Qt.DisplayRole):
            return 0
        return QVariant()
    
    def index(self, row, column, parent):
        return QModelIndex()
    
    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        return QModelIndex()
    
    def rowCount(self, parent):
        return 0
    
    def initTree(self, instructions):        
        for page in instructions:
            pass

class LicNodeTypes(object):
    InstructionNode, \
                   PageNode, \
                   PageNumberNode, \
                   StepNode,  \
                   StepNumberNode, \
                   PLINode, \
                   PLIItemNode, \
                   PLIItemLabelNode, \
                   CSINode \
                   = range(QTreeWidgetItem.UserType + 1, QTreeWidgetItem.UserType + 10)

def initTree(self, instructions):
    """
    self.instructions = instructions
    root = QTreeWidgetItem(self, LicNodeTypes.InstructionNode)
    root.setText(0, instructions.filename)
    self.addTopLevelItem(root)

    for page in instructions.pages:
        pageNode = QTreeWidgetItem(root, LicNodeTypes.PageNode)
        pageNode.setText(0, "Page %d" % page.number)

        pageNumberNode = QTreeWidgetItem(pageNode, QStringList("Page Number Label"), LicNodeTypes.PageNumberNode)
        pageNode.addChild(pageNumberNode)

        for step in page.steps:
            stepNode = QTreeWidgetItem(pageNode)
            stepNode.setText(0, "Step %d" % step.number)
            stepNode.addChild(QTreeWidgetItem(stepNode, QStringList("Step Number Label")))

            pliNode = QTreeWidgetItem(stepNode)
            pliNode.setText(0, "PLI")

            for item in step.pli.layout.values():
                itemNode = QTreeWidgetItem(pliNode)
                itemNode.setText(0, item.partOGL.name)

            stepNode.addChild(QTreeWidgetItem(stepNode, QStringList("CSI")))

    """
    return

def drawBuffer(self):
    global GlobalGLContext

    size = 300
    pBuffer = QGLPixelBuffer(size,  size, QGLFormat(), GlobalGLContext)
    pBuffer.makeCurrent()

    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glShadeModel(GL_SMOOTH)

    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    lightPos = [100.0, 500.0, -500.0]
    ambient = [0.2, 0.2, 0.2]
    diffuse = [0.8, 0.8, 0.8]
    specular = [0.5, 0.5, 0.5]

    glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
    glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
    glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
    glLightfv(GL_LIGHT0, GL_SPECULAR, specular)

    glEnable(GL_DEPTH_TEST)
    glClearColor(1.0, 1.0, 1.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    GLHelpers.adjustGLViewport(0, 0, size, size)
    GLHelpers.rotateToPLIView()

    self.mainModel.draw()

    image = pBuffer.toImage()
    if image:
        print "have image"
        image.save("C:\\ldraw\\first_render.png", None)

    GlobalGLContext.makeCurrent()

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
