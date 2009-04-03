from PyQt4.QtCore import *

from Model import *

def saveLicFile(filename, instructions):
    global FileVersion, MagicNumber
    
    fh = QFile(filename)
    if not fh.open(QIODevice.WriteOnly):
        raise IOError, unicode(fh.errorStriong())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)
    stream.writeInt32(MagicNumber)
    stream.writeInt16(FileVersion)

    # Need to explicitly de-select parts so they refresh the CSI pixmap
    instructions.clearSelectedParts()

    __writeInstructions(stream, instructions)

    if fh is not None:
        fh.close()

def __writeInstructions(stream, instructions):

    stream << QString(instructions.mainModel.filename)

    stream.writeFloat(CSI.scale)
    stream.writeFloat(PLI.scale)

    partDictionary = instructions.getPartDictionary()
    stream.writeInt32(len(partDictionary))
    for partOGL in partDictionary.values():
        __writePartOGL(stream, partOGL)

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

    if primitive.type == GL.GL_QUADS:
        assert len(primitive.points) == 12
    elif primitive.type == GL.GL_TRIANGLES:
        assert len(primitive.points) == 9

    for point in primitive.points:
        stream.writeFloat(point)

def __writePart(stream, part):
    stream << QString(part.partOGL.filename)
    stream.writeBool(part.inverted)
    stream.writeInt32(part.color)
    for point in part.matrix:
        stream.writeFloat(point)
        
    if part.displacement:
        stream.writeBool(True)
        stream.writeFloat(part.displacement[0])
        stream.writeFloat(part.displacement[1])
        stream.writeFloat(part.displacement[2])
        stream.writeInt32(part.displaceDirection)
    else:
        stream.writeBool(False)
        
def __writePage(stream, page):
    stream << page.pos() << page.rect()
    stream.writeInt32(page.number)
    stream.writeInt32(page._row)
    stream << page.numberItem.pos() << page.numberItem.font()

    # Write out each step in this page
    stream.writeInt32(len(page.steps))
    for step in page.steps:
        __writeStep(stream, step)

    # Write out the optional submodel preview image
    if page.submodelItem:
        stream.writeBool(True)
        item = page.submodelItem
        stream.writeInt32(item.row())
        stream << item.pos() << item.rect() << item.pen() 
        stream << item.children()[0].pixmap()
    else:
        stream.writeBool(False)

    # Write out any page separator lines
    stream.writeInt32(len(page.borders))
    for border in page.borders:
        stream.writeInt32(border.row())
        stream << border.pos() << border.rect() << border.pen()

def __writeStep(stream, step):
    
    stream.writeInt32(step.number)
    stream.writeBool(True if step.pli else False)
    stream.writeBool(True if step.numberItem else False)
    
    stream << step.pos() << step.rect() << step.maxRect
    
    __writeCSI(stream, step.csi)
    
    if step.pli:
        __writePLI(stream, step.pli)

    if step.numberItem:
        stream << step.numberItem.pos() << step.numberItem.font()

    stream.writeInt32(len(step.callouts))
    for callout in step.callouts:
        __writeCallout(stream, callout)

def __writeCallout(stream, callout):
    stream << callout.pos() << callout.rect() << callout.pen()

    stream.writeInt32(len(callout.steps))
    for step in callout.steps:
        __writeStep(stream, step)
    
def __writeCSI(stream, csi):
    stream << csi.pos()
    stream.writeInt32(csi.width)
    stream.writeInt32(csi.height)
    stream << csi.center
    stream << csi.pixmap()
    
    stream.writeInt32(len(csi.parts))
    for part in csi.parts:
        __writePart(stream, part)

def __writePLI(stream, pli):
    stream << pli.pos() << pli.rect() << pli.pen()
    stream.writeInt32(len(pli.pliItems))
    for item in pli.pliItems:
        __writePLIItem(stream, item)

def __writePLIItem(stream, pliItem):
    stream << QString(pliItem.partOGL.filename) << pliItem.pos() << pliItem.rect() << pliItem.transform()
    stream.writeInt32(pliItem.color)
    stream.writeInt32(pliItem.quantity)
    stream << pliItem.numberItem.pos() << pliItem.numberItem.font() << pliItem.pixmapItem.pixmap()
