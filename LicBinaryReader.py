from PyQt4.QtCore import *

from Model import *
import Layout

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
    instructions.scene.selectPage(1)

    if fh is not None:
        fh.close()

def __readInstructions(stream, instructions):
    global partDictionary, submodelDictionary

    instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
    partDictionary = instructions.getPartDictionary()
    submodelDictionary = instructions.getSubmodelDictionary()
    
    filename = QString()
    stream >> filename
    instructions.filename = str(filename)

    CSI.scale = stream.readFloat()
    PLI.scale = stream.readFloat()

    # Read in the entire partOGL dictionary
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPartOGL(stream)
        partDictionary[part.filename] = part

    # Each partOGL can contain several parts, but those parts do
    # not have valid sub-partOGLs.  Create those now.
    for partOGL in partDictionary.values():
        for part in partOGL.parts:
            part.partOGL = partDictionary[part.filename]

    partCount = stream.readInt32()
    for i in range(0, partCount):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions)

    guideCount = stream.readInt32()
    for i in range(0, guideCount):
        pos = QPointF()
        stream >> pos
        orientation = Layout.Horizontal if stream.readBool() else Layout.Vertical
        instructions.scene.addGuide(orientation, pos)

    for model in submodelDictionary.values():
        __linkModelPartNames(model)

    __linkModelPartNames(instructions.mainModel)

    for submodel in submodelDictionary.values():
        if submodel._parent == "":
            submodel._parent = instructions
        elif submodel._parent == filename:
            submodel._parent = instructions.mainModel
        else:
            submodel._parent = submodelDictionary[submodel._parent]

    instructions.initGLDisplayLists()
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
        model.used = True
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
        part.parts.append(p)
    return part

def __readPrimitive(stream):
    color = stream.readInt32()
    type = stream.readInt16()
    winding = stream.readInt32()
    
    if type == GL.GL_LINES:
        count = 6
    elif type == GL.GL_TRIANGLES:
        count = 9 
    elif type == GL.GL_QUADS:
        count = 12
    
    points = []
    for i in range(0, count):
        points.append(stream.readFloat())
    return Primitive(color, points, type, winding)

def __readPart(stream):
    filename = QString()
    stream >> filename
    filename = str(filename)
    
    invert = stream.readBool()
    color = stream.readInt32()
    matrix = []

    for i in range(0, 16):
        matrix.append(stream.readFloat())
    
    useDisplacement = stream.readBool()
    if useDisplacement:
        displacement = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        displaceDirection = stream.readInt32()
        
    if filename == 'arrow':
        arrow = Arrow(displaceDirection)
        arrow.matrix = matrix
        arrow.displacement = displacement
        arrow.setLength(stream.readInt32())
        return arrow
    
    part = Part(filename, color, matrix, invert)
    
    if useDisplacement:
        part.displacement = displacement
        part.displaceDirection = displaceDirection

    return part

def __readPage(stream, parent, instructions):
    pos = QPointF()
    rect = QRectF()
    font = QFont()
    pen = QPen()

    stream >> pos >> rect
    number = stream.readInt32()
    row = stream.readInt32()

    page = Page(parent, instructions, number, row)
    page.setPos(pos)
    page.setRect(rect)

    stream >> pos >> font
    page.numberItem.setPos(pos)
    page.numberItem.setFont(font)
    
    # Read in each step in this page
    stepCount = stream.readInt32()
    step = None
    for i in range(0, stepCount):
        step = __readStep(stream, page)
        page.addStep(step)

    # Read in the optional submodel preview image
    hasSubmodelItem = stream.readBool()
    if hasSubmodelItem:
        pixmap = QPixmap()
        childRow = stream.readInt32()
        stream >> pos >> rect >> pen
        stream >> pixmap
        
        page.addSubmodelImage(childRow)
        page.submodelItem.setPos(pos)
        page.submodelItem.setRect(rect)
        page.submodelItem.setPen(pen)
        page.submodelItem.children()[0].setPixmap(pixmap)

    # Read in any page separator lines
    borderCount = stream.readInt32()
    for i in range(0, borderCount):
        childRow = stream.readInt32()
        stream >> pos >> rect >> pen
        border = page.addStepSeparator(childRow)
        border.setPos(pos)
        border.setRect(rect)
        border.setPen(pen)

    return page

def __readStep(stream, parent):
    
    stepNumber = stream.readInt32()
    hasPLI = stream.readBool()
    hasNumberItem = stream.readBool()
    
    step = Step(parent, stepNumber, hasPLI, hasNumberItem)

    pos = QPointF()
    rect = QRectF()
    maxRect = QRectF()
    
    stream >> pos >> rect >> maxRect
    step.setPos(pos)
    step.setRect(rect)
    step.maxRect = maxRect

    step.csi = __readCSI(stream, step)
    
    if hasPLI:
        step.pli = __readPLI(stream, step)
    
    if hasNumberItem:
        font = QFont()
        stream >> pos >> font
        step.numberItem.setPos(pos)
        step.numberItem.setFont(font)

    calloutCount = stream.readInt32()
    for i in range(0, calloutCount):
        callout = __readCallout(stream, step)
        step.callouts.append(callout)
    
    return step

def __readCallout(stream, parent):
    
    pos = QPointF()
    rect = QRectF()
    pen = QPen()
    stream >> pos >> rect >> pen
    
    number = stream.readInt32()
    showStepNumbers = stream.readBool()

    callout = Callout(parent, number, showStepNumbers)
    callout.setPos(pos)
    callout.setPen(pen)
    callout.setRect(rect)
    
    stream >> pos
    callout.arrow.tipRect.point = QPointF(pos)
    stream >> pos
    callout.arrow.baseRect.point = QPointF(pos)

    if stream.readBool():  # has quantity label
        font = QFont()
        stream >> pos >> font
        callout.addQuantityLabel(pos, font)
        callout.setQuantity(stream.readInt32())
        
    stepCount = stream.readInt32()
    for i in range(0, stepCount):
        step = __readStep(stream, callout)
        callout.steps.append(step)

    return callout

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

    x, y, z = stream.readFloat(), stream.readFloat(), stream.readFloat()
    if (x != 0.0) and (y != 0.0) and (z != 0.0):
        csi.rotation = [x, y, z]

    global partDictionary, submodelDictionary
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPart(stream)
        if part.filename in partDictionary:
            part.partOGL = partDictionary[part.filename]
        elif part.filename in submodelDictionary:
            part.partOGL = submodelDictionary[part.filename]
            part.partOGL.used = True
        elif part.filename != 'arrow':
            print "LOAD ERROR: could not find a partOGL for part: " + part.filename

        csi.addPart(part)
        if part.filename == 'arrow':
            csi.arrows.append(part)

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
    quantity = stream.readInt32()

    global partDictionary, submodelDictionary
    if filename in partDictionary:
        partOGL = partDictionary[filename]
    elif filename in submodelDictionary:
        partOGL = submodelDictionary[filename]
    else:
        print "LOAD ERROR: Could not find part in part dict: " + filename

    pliItem = PLIItem(pli, partOGL, color, quantity)
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

def __linkModelPartNames(model):

    global partDictionary, submodelDictionary

    for m in model.submodels:
        __linkModelPartNames(m)

    for part in model.parts:
        if part.filename in partDictionary:
            part.partOGL = partDictionary[part.filename]
        elif part.filename in submodelDictionary:
            part.partOGL = submodelDictionary[part.filename]
            part.partOGL.used = True
        else:
            print "LOAD ERROR: could not find a partOGL for part: " + part.filename
