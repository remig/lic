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
