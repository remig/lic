from PyQt4.QtCore import *

from Model import *

def loadLicFile(filename, instructions):
    global FileVersion, MagicNumber

    fh = QFile(filename)
    if not fh.open(QIODevice.ReadOnly):
        raise IOError, unicode(fh.errorString())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)

    magic = stream.readInt32()
    if magic != MagicNumber:
        raise IOError, "not a valid .lic file"

    fileVersion = stream.readInt16()
    if fileVersion != FileVersion:
        raise IOError, "unrecognized .lic file version"

    __readInstructions(stream, instructions)
    instructions.mainModel.selectPage(1)

    if fh is not None:
        fh.close()

def __readInstructions(stream, instructions):
    global partDictionary, submodelDictionary

    instructions.emit(SIGNAL("layoutAboutToBeChanged"))
    partDictionary = instructions.getPartDictionary()
    submodelDictionary = instructions.getSubmodelDictionary()
    
    filename = QString()
    stream >> filename
    instructions.filename = str(filename)

    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPartOGL(stream)
        partDictionary[part.filename] = part

    partCount = stream.readInt32()
    for i in range(0, partCount):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions)
    
    for csi in instructions.mainModel.getCSIList():
        __linkPrevCSI(csi, instructions.mainModel)

    for submodel in submodelDictionary.values():
        if submodel._parent == "":
            submodel._parent = instructions
        elif submodel._parent == filename:
            submodel._parent = instructions.mainModel
        else:
            submodel._parent = submodelDictionary[submodel._parent]

    instructions.emit(SIGNAL("layoutChanged()"))

def __readSubmodel(stream, instructions):

    submodel = __readPartOGL(stream, True)
    submodel.instructions = instructions

    pageCount = stream.readInt32()
    for i in range(0, pageCount):
        page = __readPage(stream, submodel, instructions)
        submodel.pages.append(page)

    filename = QString()
    submodelCount = stream.readInt32()
    for i in range(0, submodelCount):
        stream >> filename
        model = submodelDictionary[str(filename)]
        submodel.submodels.append(model)

    submodel._row = stream.readInt32()
    stream >> filename
    submodel._parent = str(filename)
    return submodel

def __readPartOGL(stream, createSubmodel = False):
    filename = QString()
    name = QString()
    stream >> filename >> name

    part = Submodel() if createSubmodel else PartOGL()
    part.filename = str(filename)
    part.name = str(name)

    part.isPrimitive = stream.readBool()
    part.width = stream.readInt32()
    part.height = stream.readInt32()
    part.leftInset = stream.readInt32()
    part.bottomInset = stream.readInt32()
    stream >> part.center
    
    primitiveCount = stream.readInt32()
    for i in range(0, primitiveCount):
        p = __readPrimitive(stream)
        part.primitives.append(p)
        
    partCount = stream.readInt32()
    for i in range(0, partCount):
        p = __readPart(stream)
        p.partOGL = part
        part.parts.append(p)
    return part

def __readPrimitive(stream):
    invert = stream.readBool()
    color = stream.readInt32()
    type = stream.readInt16()
    count = 9 if type == GL_TRIANGLES else 12
    points = []
    for i in range(0, count):
        points.append(stream.readFloat())
    return Primitive(color, points, type, invert)

def __readPart(stream):
    filename = QString()
    stream >> filename
    invert = stream.readBool()
    color = stream.readInt32()
    matrix = []
    for i in range(0, 16):
        matrix.append(stream.readFloat())
    return Part(str(filename), color, matrix, invert, False)

def __readPage(stream, parent, instructions):
    pos = QPointF()
    rect = QRectF()
    font = QFont()

    stream >> pos >> rect
    number = stream.readInt32()
    page = Page(parent, instructions, number)
    page.setPos(pos)
    page.setRect(rect)

    page._row = stream.readInt32()

    stream >> pos >> font
    page.numberItem.setPos(pos)
    page.numberItem.setFont(font)
    
    hasSubmodelItem = stream.readBool()
    if hasSubmodelItem:
        pen = QPen()
        pixmap = QPixmap()
        stream >> pos >> rect >> pen
        stream >> pixmap
        
        page.addSubmodelImage(parent)
        page.submodelItem.setPos(pos)
        page.submodelItem.setRect(rect)
        page.submodelItem.setPen(pen)
        page.submodelItem.children()[0].setPixmap(pixmap)

    stepCount = stream.readInt32()
    step = None
    for i in range(0, stepCount):
        step = __readStep(stream, page)
        page.steps.append(step)
    return page

def __readStep(stream, parentPage):
    
    pos = QPointF()
    rect = QRectF()
    font = QFont()
    stream >> pos >> rect

    number = stream.readInt32()
    step = Step(parentPage, number, None)
    step.setPos(pos)
    step.setRect(rect)

    stream >> pos >> font
    step.numberItem.setPos(pos)
    step.numberItem.setFont(font)

    step.csi = __readCSI(stream, step)
    step.pli = __readPLI(stream, step)
    return step

def __readCSI(stream, step):
    csi = CSI(step)
    pos = QPointF()
    stream >> pos
    csi.setPos(pos)

    csi.width = stream.readInt32()
    csi.height = stream.readInt32()
    stream >> csi.center

    pixmap = QPixmap()
    stream >> pixmap
    csi.setPixmap(pixmap)
    
    prevPageNumber = stream.readInt32()
    prevStepNumber = stream.readInt32()    
    csi.prevCSI = (prevPageNumber, prevStepNumber)
    
    global partDictionary, submodelDictionary
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPart(stream)
        if part.filename in partDictionary:
            part.partOGL = partDictionary[part.filename]
        elif part.filename in submodelDictionary:
            part.partOGL = submodelDictionary[part.filename]
        else:
            print "LOAD ERROR: could not find a partOGL for part: " + part.filename

        csi.parts.append(part)
    return csi

def __readPLI(stream, parentStep):
    pos = QPointF()
    rect = QRectF()
    pen = QPen()
    stream >> pos >> rect >> pen

    pli = PLI(parentStep)
    pli.setPos(pos)
    pli.setPen(pen)
    pli.setRect(rect)

    itemCount = stream.readInt32()
    for i in range(0, itemCount):
        pliItem = __readPLIItem(stream, pli)
        pli.pliItems.append(pliItem)
    return pli

def __readPLIItem(stream, pli):
    
    filename = QString()
    pos = QPointF()
    rect = QRectF()
    stream >> filename >> pos >> rect
    filename = str(filename)

    color = stream.readInt32()
    count = stream.readInt32()

    global partDictionary, submodelDictionary
    if filename in partDictionary:
        partOGL = partDictionary[filename]
    elif filename in submodelDictionary:
        partOGL = submodelDictionary[filename]
    else:
        print "LOAD ERROR: Could not find part in part dict: " + filename

    pliItem = PLIItem(pli, partOGL, color)
    pliItem.count = count
    pliItem.setPos(pos)
    pliItem.setRect(rect)

    font = QFont()
    pixmap = QPixmap()
    stream >> pos >> font >> pixmap

    pliItem.numberItem.setPos(pos)
    pliItem.numberItem.setFont(font)
    pliItem.pixmapItem.setPixmap(pixmap)
    pliItem.numberItem.setZValue(pliItem.pixmapItem.zValue() + 1)
    return pliItem

def __linkPrevCSI(csi, mainModel):

    if not isinstance(csi.prevCSI, tuple) or len(csi.prevCSI) != 2:
        print "LOAD ERROR: linking prev CSIs - prevCSI isn't a tuple, it's a %s" % str(type(csi.prevCSI))
        return
    
    prevPageNumber, prevStepNumber = csi.prevCSI
    
    csi.prevCSI = None
    if prevPageNumber == 0 and prevStepNumber == 0:
        return  # This is the first CSI; its previous is expected to be None
        
    prevPage = mainModel.getPage(prevPageNumber)
    prevStep = None
    for step in prevPage.steps:
        if step.number == prevStepNumber:
            prevStep = step
            break
        
    if not prevStep:
        print "LOAD ERROR: linking prev CSI: could not find step %d on page %d" % (prevStepNumber, prevPageNumber)
        return

    csi.prevCSI = step.csi
