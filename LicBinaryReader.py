from PyQt4.QtCore import *

from Model import *
from LicTemplate import *
import Layout

def ro(self, targetType):
    c = targetType()
    x = self >> c
    return c

QDataStream.readQColor = lambda self: ro(self, QColor)
QDataStream.readQBrush = lambda self: ro(self, QBrush)
QDataStream.readQFont = lambda self: ro(self, QFont)
QDataStream.readQPen = lambda self: ro(self, QPen)
QDataStream.readQRectF = lambda self: ro(self, QRectF)
QDataStream.readQPointF = lambda self: ro(self, QPointF)
QDataStream.readQString = lambda self: ro(self, QString)

def loadLicFile(filename, instructions, treeModel):

    fh, stream = __createStream(filename)
    
    if stream.readBool():  # have template
        treeModel.templatePage = __readTemplate(stream, instructions)
    
    __readInstructions(stream, instructions)

    if treeModel.templatePage:
        treeModel.templatePage.subModel = instructions.mainModel

    treeModel.templatePage.applyDefaults()
    instructions.scene.selectPage(1)

    if fh is not None:
        fh.close()

def loadLicTemplate(filename, instructions):

    fh, stream = __createStream(filename, True)
    template = __readTemplate(stream, instructions)
    if fh is not None:
        fh.close()

    return template

def __createStream(filename, template = False):
    global FileVersion, MagicNumber

    fh = QFile(filename)
    if not fh.open(QIODevice.ReadOnly):
        raise IOError, unicode(fh.errorString())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)

    ext = ".lit" if template else ".lic"
    magic = stream.readInt32()
    if magic != MagicNumber:
        raise IOError, "not a valid " + ext + " file"

    fileVersion = stream.readInt16()
    if fileVersion != FileVersion:
        raise IOError, "unrecognized " + ext + " version"
    return fh, stream
    
def __readTemplate(stream, instructions):

    filename = str(stream.readQString())

    # Read in the entire partOGL dictionary
    global partDictionary, submodelDictionary
    partDictionary, submodelDictionary = {}, {}
    __readPartDictionary(stream, partDictionary)

    template = __readPage(stream, instructions.mainModel, instructions, True)
    template.subModelPart = __readSubmodel(stream, None)

    for part in template.steps[0].csi.getPartList():
        part.partOGL = partDictionary[part.filename]

    for part in template.subModelPart.parts:
        part.partOGL = partDictionary[part.filename]

    for partOGL in partDictionary.values():
        if partOGL.oglDispID == UNINIT_GL_DISPID:
            partOGL.createOGLDisplayList()
       
    for glItem in template.glItemIterator():
        if hasattr(glItem, 'createOGLDisplayList'):
            glItem.createOGLDisplayList()

    template.subModelPart.createOGLDisplayList()
    template.submodelItem.setPartOGL(template.subModelPart)
    template.postLoadInit(filename)
    return template

def __readInstructions(stream, instructions):
    global partDictionary, submodelDictionary

    partDictionary = instructions.getPartDictionary()
    submodelDictionary = instructions.getSubmodelDictionary()
    
    filename = str(stream.readQString())
    instructions.filename = filename

    CSI.scale = stream.readFloat()
    PLI.scale = stream.readFloat()

    __readPartDictionary(stream, partDictionary)
    
    partCount = stream.readInt32()
    for i in range(0, partCount):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions)

    guideCount = stream.readInt32()
    for i in range(0, guideCount):
        pos = stream.readQPointF()
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

def __readSubmodel(stream, instructions):

    submodel = __readPartOGL(stream, True)
    submodel.instructions = instructions

    pageCount = stream.readInt32()
    for i in range(0, pageCount):
        page = __readPage(stream, submodel, instructions)
        submodel.pages.append(page)

    submodelCount = stream.readInt32()
    for i in range(0, submodelCount):
        filename = str(stream.readQString())
        model = submodelDictionary[filename]
        model.used = True
        submodel.submodels.append(model)

    submodel._row = stream.readInt32()
    submodel._parent = str(stream.readQString())
    return submodel

def __readPartDictionary(stream, partDictionary):

    partCount = stream.readInt32()
    for i in range(0, partCount):
        partOGL = __readPartOGL(stream)
        partDictionary[partOGL.filename] = partOGL

    # Each partOGL can contain several parts, but those parts do
    # not have valid sub-partOGLs.  Create those now.
    for partOGL in partDictionary.values():
        for part in partOGL.parts:
            part.partOGL = partDictionary[part.filename]

def __readPartOGL(stream, createSubmodel = False):

    part = Submodel() if createSubmodel else PartOGL()
    part.filename = str(stream.readQString())
    part.name = str(stream.readQString())

    part.isPrimitive = stream.readBool()
    part.width = stream.readInt32()
    part.height = stream.readInt32()
    part.leftInset = stream.readInt32()
    part.bottomInset = stream.readInt32()
    part.center = stream.readQPointF()
    
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
    
    filename = str(stream.readQString())
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

def __readPage(stream, parent, instructions, isTemplatePage = False):

    number = stream.readInt32()
    row = stream.readInt32()
    
    if isTemplatePage:
        page = TemplatePage(parent, instructions)
    else:
        page = Page(parent, instructions, number, row)

    page.setPos(stream.readQPointF())
    page.setRect(stream.readQRectF())
    page.color = stream.readQColor()
    hasBrush = stream.readBool()
    if hasBrush:
        page.brush = stream.readQBrush()
    
    page.numberItem.setPos(stream.readQPointF())
    page.numberItem.setFont(stream.readQFont())
    
    # Read in each step in this page
    stepCount = stream.readInt32()
    for i in range(0, stepCount):
        page.addStep(__readStep(stream, page))

    # Read in the optional submodel preview image
    hasSubmodelItem = stream.readBool()
    if hasSubmodelItem:
        page.submodelItem = SubmodelPreview(page, page.subModel)
        page.addChild(stream.readInt32(), page.submodelItem)
        page.submodelItem.setPos(stream.readQPointF())
        page.submodelItem.setRect(stream.readQRectF())
        page.submodelItem.setPen(stream.readQPen())

    # Read in any page separator lines
    borderCount = stream.readInt32()
    for i in range(0, borderCount):
        border = page.addStepSeparator(stream.readInt32())
        border.setPos(stream.readQPointF())
        border.setRect(stream.readQRectF())
        border.setPen(stream.readQPen())

    return page

def __readStep(stream, parent):
    
    stepNumber = stream.readInt32()
    hasPLI = stream.readBool()
    hasNumberItem = stream.readBool()
    
    step = Step(parent, stepNumber, hasPLI, hasNumberItem)
    
    step.setPos(stream.readQPointF())
    step.setRect(stream.readQRectF())
    step.maxRect = stream.readQRectF()

    step.csi = __readCSI(stream, step)
    
    if hasPLI:
        step.pli = __readPLI(stream, step)
    
    if hasNumberItem:
        step.numberItem.setPos(stream.readQPointF())
        step.numberItem.setFont(stream.readQFont())

    calloutCount = stream.readInt32()
    for i in range(0, calloutCount):
        callout = __readCallout(stream, step)
        step.callouts.append(callout)
    
    return step

def __readCallout(stream, parent):
    
    callout = Callout(parent, stream.readInt32(), stream.readBool())
    __readRoundedRectItem(stream, callout)
    
    callout.arrow.tipRect.point = stream.readQPointF()
    callout.arrow.baseRect.point = stream.readQPointF()

    if stream.readBool():  # has quantity label
        callout.addQuantityLabel(stream.readQPointF(), stream.readQFont())
        callout.setQuantity(stream.readInt32())
        
    stepCount = stream.readInt32()
    for i in range(0, stepCount):
        step = __readStep(stream, callout)
        callout.steps.append(step)

    return callout

def __readCSI(stream, step):

    csi = CSI(step)
    csi.setPos(stream.readQPointF())

    csi.setRect(0.0, 0.0, stream.readInt32(), stream.readInt32())
    csi.center = stream.readQPointF()

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

    pli = PLI(parentStep)
    __readRoundedRectItem(stream, pli)
    
    itemCount = stream.readInt32()
    for i in range(0, itemCount):
        pliItem = __readPLIItem(stream, pli)
        pli.pliItems.append(pliItem)

    return pli

def __readPLIItem(stream, pli):
    
    filename = str(stream.readQString())

    global partDictionary, submodelDictionary
    if filename in partDictionary:
        partOGL = partDictionary[filename]
    elif filename in submodelDictionary:
        partOGL = submodelDictionary[filename]
    else:
        print "LOAD ERROR: Could not find part in part dict: " + filename

    pliItem = PLIItem(pli, partOGL, stream.readInt32(), stream.readInt32())
    pliItem.setPos(stream.readQPointF())
    pliItem.setRect(stream.readQRectF())

    pliItem.numberItem.setPos(stream.readQPointF())
    pliItem.numberItem.setFont(stream.readQFont())
    return pliItem

def __readRoundedRectItem(stream, parent):
    parent.setPos(stream.readQPointF())
    parent.setRect(stream.readQRectF())
    parent.setPen(stream.readQPen())
    parent.setBrush(stream.readQBrush())
    parent.cornerRadius = stream.readInt16()

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
