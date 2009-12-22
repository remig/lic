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

# To check file version:
#    if stream.licFileVersion >= 6:
#        do whatever

def loadLicFile(filename, instructions):

    fh, stream = __createStream(filename)

    template = __readTemplate(stream, instructions)

    __readInstructions(stream, instructions)
    instructions.licFileVersion = stream.licFileVersion

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

        template.steps[0].csi.addPart(part)

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

    for i in range(stream.readInt32()):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions, True)

    instructions.mainModel.addTitlePage(__readTitlePage(stream, instructions))

    for i in range(stream.readInt32()):
        newPage = __readPartListPage(stream, instructions)
        instructions.mainModel.partListPages.append(newPage)

    for i in range(stream.readInt32()):
        instructions.scene.addGuide(stream.readInt32(), stream.readQPointF())

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

    for i in range(stream.readInt32()):
        page = __readPage(stream, submodel, instructions)
        submodel.pages.append(page)

    for i in range(stream.readInt32()):
        filename = str(stream.readQString())
        model = submodelDictionary[filename]
        model.used = True
        submodel.submodels.append(model)

    submodel._row = stream.readInt32()
    submodel._parent = str(stream.readQString())
    submodel.isSubAssembly = stream.readBool()

    return submodel

def __readPartDictionary(stream, partDictionary):

    for i in range(stream.readInt32()):
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

    for i in range(stream.readInt32()):
        p = __readPrimitive(stream)
        part.primitives.append(p)

    for i in range(stream.readInt32()):
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
    for i in range(count):
        points.append(stream.readFloat())
    return Primitive(color, points, type, winding)

def __readPart(stream):
    
    filename = str(stream.readQString())
    invert = stream.readBool()
    color = stream.readInt32()
    matrix = []

    for i in range(0, 16):
        matrix.append(stream.readFloat())

    inCallout = stream.readBool()
    pageNumber = stream.readInt32()
    stepNumber = stream.readInt32()

    useDisplacement = stream.readBool()
    if useDisplacement:
        displacement = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        displaceDirection = stream.readInt32()
        if filename != 'arrow':
            arrows = []
            if stream.licFileVersion >= 4:
                for i in range(stream.readInt32()):
                    arrows.append(__readPart(stream))
            else:
                arrows.append(__readPart(stream))
        
    if filename == 'arrow':
        arrow = Arrow(displaceDirection)
        arrow.matrix = matrix
        arrow.displacement = displacement
        arrow.setLength(stream.readInt32())
        arrow.axisRotation = stream.readFloat()
        return arrow
    
    part = Part(filename, color, matrix, invert)
    part.inCallout = inCallout
    part.pageNumber = pageNumber
    part.stepNumber = stepNumber
    
    if useDisplacement:
        part.displacement = displacement
        part.displaceDirection = displaceDirection
        for arrow in arrows:
            arrow.setParentItem(part)
        part.arrows = arrows

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

    __readRoundedRectItem(stream, page)
    page.color = stream.readQColor()
    page.layout.orientation = stream.readInt32()
    page.numberItem.setPos(stream.readQPointF())
    page.numberItem.setFont(stream.readQFont())

    # Read in each step in this page
    for i in range(stream.readInt32()):
        page.addStep(__readStep(stream, page))

    # Read in the optional submodel preview image
    if stream.readBool():
        page.submodelItem = __readSubmodelItem(stream, page)
        page.addChild(page.submodelItem._row, page.submodelItem)

    # Read in any page separator lines
    for i in range(stream.readInt32()):
        border = page.addStepSeparator(stream.readInt32())
        border.setPos(stream.readQPointF())
        border.setRect(stream.readQRectF())
        border.setPen(stream.readQPen())

    return page

def __readTitlePage(stream, instructions):
    if not stream.readBool():
        return None

    page = TitlePage(instructions)

    __readRoundedRectItem(stream, page)
    page.color = stream.readQColor()

    if stream.readBool():
        page.submodelItem = __readSubmodelItem(stream, page)
        page.submodelItem.itemClassName = "TitleSubmodelPreview"  # Override regular name so we don't set this in any template action

    for i in range(stream.readInt32()):
        page.addNewLabel(stream.readQPointF(), stream.readQFont(), str(stream.readQString()))

    return page

def __readPartListPage(stream, instructions):

    page = PartListPage(instructions, stream.readInt32(), stream.readInt32())

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

    step._hasPLI = stream.readBool()
    if not step._hasPLI and step.pli:
        step.disablePLI()

    if hasNumberItem:
        step.numberItem.setPos(stream.readQPointF())
        step.numberItem.setFont(stream.readQFont())

    for i in range(stream.readInt32()):
        callout = __readCallout(stream, step)
        step.callouts.append(callout)

    if stream.licFileVersion >= 3:
        if stream.readBool():
            step.addRotateIcon()
            __readRoundedRectItem(stream, step.rotateIcon)
            step.rotateIcon.arrowPen = stream.readQPen()

    return step

def __readCallout(stream, parent):
    
    callout = Callout(parent, stream.readInt32(), stream.readBool())
    callout.borderFit = stream.readInt32()
    __readRoundedRectItem(stream, callout)
    
    callout.arrow.tipRect.point = stream.readQPointF()
    callout.arrow.baseRect.point = stream.readQPointF()
    callout.arrow.setPen(stream.readQPen())
    callout.arrow.setBrush(stream.readQBrush())

    if stream.readBool():  # has quantity label
        callout.addQuantityLabel(stream.readQPointF(), stream.readQFont())
        callout.setQuantity(stream.readInt32())

    for i in range(stream.readInt32()):
        step = __readStep(stream, callout)
        callout.steps.append(step)

    for i in range(stream.readInt32()):
        part = __readPart(stream)
        part.partOGL = partDictionary[part.filename]
        step = callout.getStep(part.stepNumber)
        step.addPart(part)

    return callout

def __readSubmodelItem(stream, page):
    
    submodelItem = SubmodelPreview(page, page.subModel)
    submodelItem._row = stream.readInt32()
    __readRoundedRectItem(stream, submodelItem)
    submodelItem.scaling = stream.readFloat()
    submodelItem.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
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

    return csi

def __readPLI(stream, parent, makePartListPLI = False):

    if makePartListPLI:
        pli = PartListPLI(parent)
    else:
        pli = PLI(parent)
    __readRoundedRectItem(stream, pli)

    for i in range(stream.readInt32()):
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

    if stream.licFileVersion >= 2:
        if stream.readBool():  # Have a length indicator
            li = pliItem.lengthIndicator
            li.setPos(stream.readQPointF())
            li.setRect(stream.readQRectF())
            li.setFont(stream.readQFont())
            li.lengthText = str(stream.readQString())
            li.labelColor = stream.readQColor()
            li.setPen(stream.readQPen())
            li.setBrush(stream.readQBrush())

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
            csi = page.getStep(part.stepNumber).csi
            csi.addPart(part)

    # Associate each part that has a matching part in a callout to that matching part, and vice versa
    for part in [p for p in model.parts if p.inCallout]:
        for callout in part.getStep().callouts:
            for calloutPart in callout.getPartList():
                if (calloutPart.filename == part.filename) and (calloutPart.matrix == part.matrix) and (calloutPart.color == part.color):
                    part.calloutPart = calloutPart
                    calloutPart.originalPart = part
                    break

