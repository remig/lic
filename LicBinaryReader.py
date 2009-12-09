from PyQt4.QtCore import *

from Model import *
from LicTemplate import *
from LicCustomPages import *
import Layout
import GLHelpers

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
QDataStream.readQSizeF = lambda self: ro(self, QSizeF)
QDataStream.readQSize = lambda self: ro(self, QSize)

def loadLicFile(filename, instructions):

    fh, stream = __createStream(filename)
    
    if stream.licFileVersion >= 6:
        template = __readTemplate(stream, instructions)
    else:
        if stream.readBool():  # have template
            template = __readTemplate(stream, instructions)

    __readInstructions(stream, instructions)

    if template:
        template.subModel = instructions.mainModel

    template.lockIcon.resetPosition()
    instructions.mainModel.template = template

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

    stream.licFileVersion = stream.readInt16()
    if stream.licFileVersion > FileVersion:
        raise IOError, "Cannot read file: %s was created with a newer version of Lic (%d) than you're using(%d)." % (filename, stream.licFileVersion, FileVersion)
    return fh, stream
    
def __readTemplate(stream, instructions):

    filename = str(stream.readQString())

    # Read in the entire partOGL dictionary
    global partDictionary, submodelDictionary
    partDictionary, submodelDictionary = {}, {}
    __readPartDictionary(stream, partDictionary)

    subModelPart = __readSubmodel(stream, None)
    template = __readPage(stream, instructions.mainModel, instructions, subModelPart)
    template.subModelPart = subModelPart

    for part in template.subModelPart.parts:
        part.partOGL = partDictionary[part.filename]

        template.steps[0].addPart(part)
        if hasattr(part, "displaceArrow"):
            template.steps[0].csi.addPart(part.displaceArrow)
            template.steps[0].csi.arrows.append(part.displaceArrow)

    for partOGL in partDictionary.values():
        if partOGL.oglDispID == GLHelpers.UNINIT_GL_DISPID:
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
    
    Page.PageSize = stream.readQSize()
    Page.Resolution = stream.readFloat()

    CSI.defaultScale = stream.readFloat()
    PLI.defaultScale = stream.readFloat()
    SubmodelPreview.defaultScale = stream.readFloat()
    
    CSI.defaultRotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    PLI.defaultRotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    SubmodelPreview.defaultRotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]

    __readPartDictionary(stream, partDictionary)
    
    submodelCount = stream.readInt32()
    for i in range(0, submodelCount):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions, True)

    if stream.licFileVersion >= 7:
        pageCount = stream.readInt32()
        for i in range(0, pageCount):
            newPage = __readPartListPage(stream, instructions)
            instructions.mainModel.partListPages.append(newPage)

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

def __readSubmodel(stream, instructions, createMainmodel = False):

    submodel = __readPartOGL(stream, True, createMainmodel)
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
    
    if stream.licFileVersion >= 3:
        submodel.isSubAssembly = stream.readBool()

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

def __readPartOGL(stream, createSubmodel = False, createMainmodel = False):

    if createMainmodel:
        part = Mainmodel()
    elif createSubmodel:
        part = Submodel()
    else:
        part = PartOGL()

    part.filename = str(stream.readQString())
    part.name = str(stream.readQString())

    part.isPrimitive = stream.readBool()
    part.width = stream.readInt32()
    part.height = stream.readInt32()
    part.leftInset = stream.readInt32()
    part.bottomInset = stream.readInt32()
    part.center = stream.readQPointF()

    part.pliScale = stream.readFloat()
    part.pliRotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    
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

    inCallout = stream.readBool() if stream.licFileVersion >= 4 else False

    if stream.licFileVersion >= 8:
        pageNumber = stream.readInt32()
        stepNumber = stream.readInt32()
    else:
        pageNumber = stepNumber = -1
    
    useDisplacement = stream.readBool()
    if useDisplacement:
        displacement = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        displaceDirection = stream.readInt32()
        if filename != 'arrow':
            displaceArrow = __readPart(stream)
        
    if filename == 'arrow':
        arrow = Arrow(displaceDirection)
        arrow.matrix = matrix
        arrow.displacement = displacement
        arrow.setLength(stream.readInt32())
        
        if stream.licFileVersion >= 2:
            arrow.axisRotation = stream.readFloat()
        
        return arrow
    
    part = Part(filename, color, matrix, invert)
    part.inCallout = inCallout
    part.pageNumber = pageNumber
    part.stepNumber = stepNumber
    
    if useDisplacement:
        part.displacement = displacement
        part.displaceDirection = displaceDirection
        part.displaceArrow = displaceArrow

    return part

def __readPage(stream, parent, instructions, templateModel = None):

    number = stream.readInt32()
    row = stream.readInt32()
    
    if templateModel:
        page = TemplatePage(parent, instructions)
        if page.subModel is None:
            page.subModel = templateModel
    else:
        page = Page(parent, instructions, number, row)

    if stream.licFileVersion >= 5:
        __readRoundedRectItem(stream, page)
        page.color = stream.readQColor()
    else:
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
        page.submodelItem = __readSubmodelItem(stream, page)
        page.addChild(page.submodelItem._row, page.submodelItem)

    # Read in any page separator lines
    borderCount = stream.readInt32()
    for i in range(0, borderCount):
        border = page.addStepSeparator(stream.readInt32())
        border.setPos(stream.readQPointF())
        border.setRect(stream.readQRectF())
        border.setPen(stream.readQPen())

    return page

def __readPartListPage(stream, instructions):

    number = stream.readInt32()
    row = stream.readInt32()

    page = PartListPage(instructions, number, row)

    __readRoundedRectItem(stream, page)
    page.color = stream.readQColor()

    page.numberItem.setPos(stream.readQPointF())
    page.numberItem.setFont(stream.readQFont())

    page.pli = __readPLI(stream, page, True)

    return page

def __readStep(stream, parent):
    
    stepNumber = stream.readInt32()
    pliExists = stream.readBool()
    hasNumberItem = stream.readBool()
    
    step = Step(parent, stepNumber, pliExists, hasNumberItem)
    
    step.setPos(stream.readQPointF())
    step.setRect(stream.readQRectF())
    step.maxRect = stream.readQRectF()

    step.csi = __readCSI(stream, step)
    
    if pliExists:
        step.pli = __readPLI(stream, step)
    
    if stream.licFileVersion >= 3:
        step._hasPLI = stream.readBool()
        if not step._hasPLI and step.pli:
            step.disablePLI()
        
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
    if stream.licFileVersion >= 10:
        callout.borderFit = stream.readInt32()
    __readRoundedRectItem(stream, callout)
    
    callout.arrow.tipRect.point = stream.readQPointF()
    callout.arrow.baseRect.point = stream.readQPointF()
    callout.arrow.setPen(stream.readQPen())
    callout.arrow.setBrush(stream.readQBrush())

    if stream.readBool():  # has quantity label
        callout.addQuantityLabel(stream.readQPointF(), stream.readQFont())
        callout.setQuantity(stream.readInt32())
        
    stepCount = stream.readInt32()
    for i in range(0, stepCount):
        step = __readStep(stream, callout)
        callout.steps.append(step)

    if stream.licFileVersion >= 9:
        partCount = stream.readInt32()
        for i in range(0, partCount):
            part = __readPart(stream)
            part.partOGL = partDictionary[part.filename]
            step = callout.getStep(part.stepNumber)
            step.addPart(part)
            if hasattr(part, "displaceArrow"):
                step.csi.addPart(part.displaceArrow)
                step.csi.arrows.append(part.displaceArrow)

    return callout

def __readSubmodelItem(stream, page):
    
    submodelItem = SubmodelPreview(page, page.subModel)
    submodelItem._row = stream.readInt32()
    __readRoundedRectItem(stream, submodelItem)
    submodelItem.scaling = stream.readFloat()
    submodelItem.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    
    if stream.licFileVersion >= 3:
        submodelItem.isSubAssembly = stream.readBool()
        if submodelItem.isSubAssembly:
            submodelItem.pli = __readPLI(stream, submodelItem)

    return submodelItem

def __readCSI(stream, step):

    csi = CSI(step)
    csi.setPos(stream.readQPointF())

    csi.setRect(0.0, 0.0, stream.readInt32(), stream.readInt32())
    csi.center = stream.readQPointF()

    csi.scaling = stream.readFloat()
    csi.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]

    if stream.licFileVersion < 8:
        global partDictionary, submodelDictionary
        partCount = stream.readInt32()
        for i in range(0, partCount):
            part = __readPart(stream)
            if part.filename in partDictionary:
                part.partOGL = partDictionary[part.filename]
            elif part.filename in submodelDictionary:
                part.partOGL = submodelDictionary[part.filename]
                part.partOGL.used = True
            else:
                print "LOAD ERROR: could not find a partOGL for part: " + part.filename
    
            csi.addPart(part)
            if hasattr(part, "displaceArrow"):
                csi.addPart(part.displaceArrow)
                csi.arrows.append(part.displaceArrow)

    return csi

def __readPLI(stream, parent, makePartListPLI = False):

    if makePartListPLI:
        pli = PartListPLI(parent)
    else:
        pli = PLI(parent)
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
            
    for part in model.parts:
        if part.pageNumber >= 0 and part.stepNumber >= 0:
            page = model.getPage(part.pageNumber)
            step = page.getStep(part.stepNumber)
            step.addPart(part)
            if hasattr(part, "displaceArrow"):
                step.csi.addPart(part.displaceArrow)
                step.csi.arrows.append(part.displaceArrow)

    # Associate each part that has a matching part in a callout to that matching part, and vice versa
    for part in [p for p in model.parts if p.inCallout]:
        for callout in part.getStep().callouts:
            for calloutPart in callout.getPartList():
                if (calloutPart.filename == part.filename) and (calloutPart.matrix == part.matrix) and (calloutPart.color == part.color):
                    part.calloutPart = calloutPart
                    calloutPart.originalPart = part
                    break

