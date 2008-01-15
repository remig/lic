from PyQt4.QtCore import *

from Model_qt import *

MagicNumber = 0x14768126
FileVersion = 1
partDictionary = {}

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

    __readInstructions(stream, filename, instructions)
    instructions.selectPage(1)

    if fh is not None:
        fh.close()

def saveLicFile(filename, instructions):
    global FileVersion, MagicNumber
    
    fh = QFile(filename)
    if not fh.open(QIODevice.WriteOnly):
        raise IOError, unicode(fh.errorStriong())
    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)
    stream.writeInt32(MagicNumber)
    stream.writeInt16(FileVersion)
    __writeInstructions(stream, instructions)

    if fh is not None:
        fh.close()

def __readInstructions(stream, filename, instructions):
    global partDictionary

    instructions.emit(SIGNAL("layoutAboutToBeChanged"))
    instructions.filename = os.path.splitext(os.path.basename(filename))[0]
    partDictionary = instructions.getPartDictionary()
    
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPartOGL(stream)
        partDictionary[part.filename] = part

    pageCount = stream.readInt32()
    for i in range(0, pageCount):
        page = __readPage(stream, instructions)
        instructions.addPage(page)
    
    __linkAllPrevCSIs(instructions)
    instructions.emit(SIGNAL("layoutChanged()"))

def __linkAllPrevCSIs(instructions):
    
    for page in instructions.pages:
        for step in page.steps:
            __linkPrevCSI(step.csi, instructions)

def __linkPrevCSI(csi, instructions):

    if not isinstance(csi.prevCSI, tuple) or len(csi.prevCSI) != 2:
        print "Error linking prev CSIs - prevCSI isn't a tuple, it's a %s" % str(type(csi.prevCSI))
        return
    
    prevPageNumber, prevStepNumber = csi.prevCSI
    
    csi.prevCSI = None
    if prevPageNumber == 0 and prevStepNumber == 0:
        return  # prevPageNumber == 0 means this is the first CSI; its previous is expected to be None
        
    prevPage = instructions.pages[prevPageNumber - 1]
    prevStep = None
    for step in prevPage.steps:
        if step.number == prevStepNumber:
            prevStep = step
            break
        
    if not prevStep:
        print "Error linking prev CSI: could not find step %d on page %d" % (prevStepNumber, prevPageNumber)
        return

    csi.prevCSI = step.csi
    
def __readPartOGL(stream):
    filename = QString()
    name = QString()
    stream >> filename >> name

    part = PartOGL()
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

def __readPage(stream, instructions):
    pos = QPointF()
    rect = QRectF()
    font = QFont()

    stream >> pos >> rect
    number = stream.readInt32()
    page = Page(instructions, number)
    page.setPos(pos)
    page.setRect(rect)

    stream >> pos >> font
    page.numberItem.setPos(pos)
    page.numberItem.setFont(font)

    stepCount = stream.readInt32()
    step = None
    for i in range(0, stepCount):
        step = __readStep(stream, page)
        page.steps.append(step)
    return page

def __readStep(stream, parentPage):
    global partDictionary
    
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
    
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPart(stream)
        part.partOGL = partDictionary[part.filename]
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
    global partDictionary
    
    filename = QString()
    pos = QPointF()
    rect = QRectF()
    stream >> filename >> pos >> rect
    filename = str(filename)

    color = stream.readInt32()
    count = stream.readInt32()

    if filename in partDictionary:
        partOGL = partDictionary[filename]
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

def __writeInstructions(stream, instructions):
    global partDictionary

    partDictionary = instructions.getPartDictionary()
    stream.writeInt32(len(partDictionary))
    for partOGL in partDictionary.values():
        __writePartOGL(stream, partOGL)

    stream.writeInt32(len(instructions.pages))
    for page in instructions.pages:
        __writePage(stream, page)
    instructions.dirty = False

def __writePartOGL(stream, partOGL):

    stream << QString(partOGL.filename) << QString(partOGL.name)
    stream.writeBool(partOGL.isPrimitive)
    stream.writeInt32(partOGL.width)
    stream.writeInt32(partOGL.height)
    stream.writeInt32(partOGL.leftInset)
    stream.writeInt32(partOGL.bottomInset)
    stream << partOGL.center
    
    stream.writeInt32(len(partOGL.primitives))
    for primitive in partOGL.primitives:
        __writePrimitive(stream, primitive)
        
    stream.writeInt32(len(partOGL.parts))
    for part in partOGL.parts:
        __writePart(stream, part)

def __writePrimitive(stream, primitive):
    stream.writeBool(primitive.inverted)
    stream.writeInt32(primitive.color)
    stream.writeInt16(primitive.type)

    if primitive.type == GL_QUADS:
        assert len(primitive.points) == 12
    elif primitive.type == GL_TRIANGLES:
        assert len(primitive.points) == 9

    for point in primitive.points:
        stream.writeFloat(point)

def __writePart(stream, part):
    stream << QString(part.partOGL.filename)
    stream.writeBool(part.inverted)
    stream.writeInt32(part.color)
    assert len(part.matrix) == 16
    for point in part.matrix:
        stream.writeFloat(point)
        
def __writePage(stream, page):    
    stream << page.pos() << page.rect()
    stream.writeInt32(page.number)
    stream << page.numberItem.pos() << page.numberItem.font()
    
    stream.writeInt32(len(page.steps))
    for step in page.steps:
        __writeStep(stream, step)

def __writeStep(stream, step):
    stream << step.pos() << step.rect()
    stream.writeInt32(step.number)
    stream << step.numberItem.pos() << step.numberItem.font()

    __writeCSI(stream, step.csi)
    __writePLI(stream, step.pli)
    
def __writeCSI(stream, csi):
    stream << csi.pos()
    stream.writeInt32(csi.width)
    stream.writeInt32(csi.height)
    stream << csi.center
    stream << csi.pixmap()
    
    prevPageNumber, prevStepNumber = csi.getPrevPageStepNumberPair()
    stream.writeInt32(prevPageNumber)
    stream.writeInt32(prevStepNumber)

    stream.writeInt32(len(csi.parts))
    for part in csi.parts:
        __writePart(stream, part)

def __writePLI(stream, pli):
    stream << pli.pos() << pli.rect() << pli.pen()
    stream.writeInt32(len(pli.pliItems))
    for item in pli.pliItems:
        __writePLIItem(stream, item)

def __writePLIItem(stream, pliItem):
    stream << QString(pliItem.partOGL.filename) << pliItem.pos() << pliItem.rect()
    stream.writeInt32(pliItem.color)
    stream.writeInt32(pliItem.count)
    stream << pliItem.numberItem.pos() << pliItem.numberItem.font() << pliItem.pixmapItem.pixmap()
