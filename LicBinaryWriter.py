from PyQt4.QtCore import *

from Model import *
import Layout

def saveLicFile(filename, instructions, template):

    fh, stream = __createStream(filename)

    # Need to explicitly de-select parts so they refresh the CSI pixmap
    instructions.scene.clearSelectedParts()

    __writeTemplate(stream, template)
    __writeInstructions(stream, instructions)

    if fh is not None:
        fh.close()
        
def saveLicTemplate(template):
    
    fh, stream = __createStream(template.filename)

    __writeTemplate(stream, template)

    if fh is not None:
        fh.close()

def __createStream(filename):
    global FileVersion, MagicNumber
    
    fh = QFile(filename)
    if not fh.open(QIODevice.WriteOnly):
        raise IOError, unicode(fh.errorStriong())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)
    stream.writeInt32(MagicNumber)
    stream.writeInt16(FileVersion)
    return fh, stream

def __writeTemplate(stream, template):

    # Build part dictionary, since it's not implicitly stored anywhere
    partDictionary = {}
    for part in template.steps[0].csi.getPartList():
        if part.partOGL.filename not in partDictionary:
            part.partOGL.buildSubPartOGLDict(partDictionary)

    stream << QString(template.filename)
    __writePartDictionary(stream, partDictionary)
    __writeSubmodel(stream, template.subModelPart)
    __writePage(stream, template)

def __writeInstructions(stream, instructions):

    stream << QString(instructions.mainModel.filename)
    stream << Page.PageSize
    stream.writeFloat(Page.Resolution)

    stream.writeFloat(CSI.defaultScale)
    stream.writeFloat(PLI.defaultScale)
    stream.writeFloat(SubmodelPreview.defaultScale)
    
    stream.writeFloat(CSI.defaultRotation[0])
    stream.writeFloat(CSI.defaultRotation[1])
    stream.writeFloat(CSI.defaultRotation[2])
        
    stream.writeFloat(PLI.defaultRotation[0])
    stream.writeFloat(PLI.defaultRotation[1])
    stream.writeFloat(PLI.defaultRotation[2])

    stream.writeFloat(SubmodelPreview.defaultRotation[0])
    stream.writeFloat(SubmodelPreview.defaultRotation[1])
    stream.writeFloat(SubmodelPreview.defaultRotation[2])

    partDictionary = instructions.getPartDictionary()
    __writePartDictionary(stream, partDictionary)

    submodelDictionary = instructions.getSubmodelDictionary()
    stream.writeInt32(len(submodelDictionary))

    # Need to write a submodel's submodels before the submodel,
    # So mark all submodels as unwritten, then recursively write away
    for submodel in submodelDictionary.values():
        submodel.writtenToFile = False

    for submodel in submodelDictionary.values():
        if not submodel.writtenToFile:
            __writeSubmodel(stream, submodel)
            submodel.writtenToFile = True

    __writeSubmodel(stream, instructions.mainModel)

    stream.writeInt32(len(instructions.mainModel.partListPages))
    for page in instructions.mainModel.partListPages:
        __writePartListPage(stream, page)

    stream.writeInt32(len(instructions.scene.guides))
    for guide in instructions.scene.guides:
        stream << guide.pos()
        stream.writeBool(True if guide.orientation == Layout.Horizontal else False)

def __writeSubmodel(stream, submodel):

    for model in submodel.submodels:
        if not model.writtenToFile:
            __writeSubmodel(stream, model)
            model.writtenToFile = True

    __writePartOGL(stream, submodel)

    stream.writeInt32(len(submodel.pages))
    for page in submodel.pages:
        __writePage(stream, page)

    stream.writeInt32(len(submodel.submodels))
    for model in submodel.submodels:
        stream << QString(model.filename)

    stream.writeInt32(submodel._row)
    name = submodel._parent.filename if hasattr(submodel._parent, 'filename') else ""
    stream << QString(name)

    stream.writeBool(submodel.isSubAssembly)

def __writePartDictionary(stream, partDictionary):

    stream.writeInt32(len(partDictionary))
    for partOGL in partDictionary.values():
        __writePartOGL(stream, partOGL)

def __writePartOGL(stream, partOGL):

    stream << QString(partOGL.filename) << QString(partOGL.name)
    stream.writeBool(partOGL.isPrimitive)
    stream.writeInt32(partOGL.width)
    stream.writeInt32(partOGL.height)
    stream.writeInt32(partOGL.leftInset)
    stream.writeInt32(partOGL.bottomInset)
    stream << partOGL.center

    stream.writeFloat(partOGL.pliScale)
    stream.writeFloat(partOGL.pliRotation[0])
    stream.writeFloat(partOGL.pliRotation[1])
    stream.writeFloat(partOGL.pliRotation[2])
    
    stream.writeInt32(len(partOGL.primitives))
    for primitive in partOGL.primitives:
        __writePrimitive(stream, primitive)
        
    stream.writeInt32(len(partOGL.parts))
    for part in partOGL.parts:
        __writePart(stream, part)

def __writePrimitive(stream, primitive):
    stream.writeInt32(primitive.color)
    stream.writeInt16(primitive.type)
    stream.writeInt32(primitive.winding)

    for point in primitive.points:
        stream.writeFloat(point)

def __writePart(stream, part):
    stream << QString(part.partOGL.filename)
    stream.writeBool(part.inverted)
    stream.writeInt32(part.color)
    for point in part.matrix:
        stream.writeFloat(point)
        
    stream.writeBool(part.inCallout)

    if part.displacement and part.displaceDirection:
        stream.writeBool(True)
        stream.writeFloat(part.displacement[0])
        stream.writeFloat(part.displacement[1])
        stream.writeFloat(part.displacement[2])
        stream.writeInt32(part.displaceDirection)
        if part.filename != "arrow":
            __writePart(stream, part.displaceArrow)
    else:
        stream.writeBool(False)
        
    if isinstance(part, Arrow):
        stream.writeInt32(part.getLength())
        stream.writeFloat(part.axisRotation)

def __writePage(stream, page):
    stream.writeInt32(page.number)
    stream.writeInt32(page._row)
    
    __writeRoundedRectItem(stream, page)
    stream << page.color
    
    stream << page.numberItem.pos() << page.numberItem.font()

    # Write out each step in this page
    stream.writeInt32(len(page.steps))
    for step in page.steps:
        __writeStep(stream, step)

    # Write out the optional submodel preview image
    if page.submodelItem:
        stream.writeBool(True)
        __writeSubmodelItem(stream, page.submodelItem)
    else:
        stream.writeBool(False)

    # Write out any page separator lines
    stream.writeInt32(len(page.separators))
    for border in page.separators:
        stream.writeInt32(border.row())
        stream << border.pos() << border.rect() << border.pen()

def __writePartListPage(stream, page):
    stream.writeInt32(page.number)
    stream.writeInt32(page._row)

    __writeRoundedRectItem(stream, page)
    stream << page.color

    stream << page.numberItem.pos() << page.numberItem.font()

    __writePLI(stream, page.pli)

def __writeStep(stream, step):
    
    stream.writeInt32(step.number)
    stream.writeBool(True if step.pli else False)
    stream.writeBool(True if step.numberItem else False)
    
    stream << step.pos() << step.rect() << step.maxRect
    
    __writeCSI(stream, step.csi)
    
    if step.pli:
        __writePLI(stream, step.pli)
    stream.writeBool(step._hasPLI)

    if step.numberItem:
        stream << step.numberItem.pos() << step.numberItem.font()

    stream.writeInt32(len(step.callouts))
    for callout in step.callouts:
        __writeCallout(stream, callout)

def __writeCallout(stream, callout):
    stream.writeInt32(callout.number)
    stream.writeBool(callout.showStepNumbers)

    __writeRoundedRectItem(stream, callout)
    stream << callout.arrow.tipRect.point
    stream << callout.arrow.baseRect.point
    stream << callout.arrow.pen() << callout.arrow.brush()
    
    stream.writeBool(True if callout.qtyLabel else False)
    if callout.qtyLabel:
        stream << callout.qtyLabel.pos() << callout.qtyLabel.font()
        stream.writeInt32(int(callout.qtyLabel.text()[:-1]))
        
    stream.writeInt32(len(callout.steps))
    for step in callout.steps:
        __writeStep(stream, step)
    
def __writeSubmodelItem(stream, submodelItem):
    stream.writeInt32(submodelItem.row())
    __writeRoundedRectItem(stream, submodelItem)
    
    stream.writeFloat(submodelItem.scaling)
    stream.writeFloat(submodelItem.rotation[0])
    stream.writeFloat(submodelItem.rotation[1])
    stream.writeFloat(submodelItem.rotation[2])

    stream.writeBool(submodelItem.isSubAssembly)
    if submodelItem.isSubAssembly:
        __writePLI(stream, submodelItem.pli)

def __writeCSI(stream, csi):
    stream << csi.pos()
    stream.writeInt32(csi.rect().width())
    stream.writeInt32(csi.rect().height())
    stream << csi.center
    
    stream.writeFloat(csi.scaling)
    stream.writeFloat(csi.rotation[0])
    stream.writeFloat(csi.rotation[1])
    stream.writeFloat(csi.rotation[2])

    stream.writeInt32(csi.partCount() - len(csi.arrows))
    for partItem in csi.parts:
        for part in partItem.parts:
            if part.filename != 'arrow':
                __writePart(stream, part)

def __writePLI(stream, pli):
    __writeRoundedRectItem(stream, pli)
    stream.writeInt32(len(pli.pliItems))
    for item in pli.pliItems:
        __writePLIItem(stream, item)

def __writePLIItem(stream, pliItem):
    stream << QString(pliItem.partOGL.filename)
    stream.writeInt32(pliItem.color)
    stream.writeInt32(pliItem.quantity)
    stream << pliItem.pos() << pliItem.rect()
    stream << pliItem.numberItem.pos() << pliItem.numberItem.font()

def __writeRoundedRectItem(stream, parent):
    stream << parent.pos() << parent.rect() << parent.pen() << parent.brush()
    stream.writeInt16(parent.cornerRadius)

