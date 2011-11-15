"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicBinaryWriter.py) is part of Lic.

    Lic is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Lic is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/
"""

from LicCommonImports import *

from LicCustomPages import Page
from LicTemplate import TemplatePage, TemplatePLI
from LicModel import Arrow, CSI, PLI, SubmodelPreview

def saveLicFile(filename, instructions, FileVersion, MagicNumber):

    fh, stream = __createStream(filename, FileVersion, MagicNumber)

    # Need to explicitly de-select parts so they refresh the CSI pixmap
    instructions.scene.clearSelectedParts()

    stream.writeInt32(instructions.getQuantitativeSizeMeasure())

    __writeTemplate(stream, instructions.template)
    __writeInstructions(stream, instructions)

    if fh is not None:
        fh.close()
        
def saveLicTemplate(template, FileVersion, MagicNumber):
    
    fh, stream = __createStream(template.filename, FileVersion, MagicNumber)

    __writeTemplate(stream, template)

    if fh is not None:
        fh.close()

def __createStream(filename, FileVersion, MagicNumber):
    
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
        if part.abstractPart.filename not in partDictionary:
            part.abstractPart.buildSubAbstractPartDict(partDictionary)

    stream << QString(os.path.basename(template.filename))
    stream.writeBool(TemplatePage.separatorsVisible)
    stream.writeBool(TemplatePLI.includeSubmodels)
    __writePartDictionary(stream, partDictionary)
    __writeSubmodel(stream, template.submodelPart)
    __writePage(stream, template)

    __writeStaticInfo(stream)  # Need to save PageSize, PLI|CSI size, etc, so we can apply these on template load

    values = LicGLHelpers.getLightParameters()
    stream.writeInt32(len(values))
    for v in values:
        stream.writeFloat(v)

def __writeStaticInfo(stream):
    stream << Page.PageSize
    stream.writeFloat(Page.Resolution)
    stream << QString(Page.NumberPos)

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

def __writeInstructions(stream, instructions):

    stream << QString(instructions.mainModel.filename)

    __writeStaticInfo(stream)

    partDictionary = instructions.partDictionary
    __writePartDictionary(stream, partDictionary)

    __writeSubmodel(stream, instructions.mainModel)

    __writeTitlePage(stream, instructions.mainModel.titlePage)

    stream.writeInt32(len(instructions.mainModel.partListPages))
    for page in instructions.mainModel.partListPages:
        __writePartListPage(stream, page)

    stream.writeInt32(len(instructions.scene.guides))
    for guide in instructions.scene.guides:
        stream.writeInt32(guide.orientation)
        stream << guide.pos()

def __writeSubmodel(stream, submodel):

    __writeAbstractPart(stream, submodel)

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

def __writeLicColor(stream, licColor):
    if licColor is not None:
        stream.writeBool(True)
        for v in licColor.rgba:
            stream.writeFloat(v)
        stream << QString(licColor.name)
    else:
        stream.writeBool(False)

def __writePartDictionary(stream, partDictionary):

    partList = [p for p in partDictionary.values() if not p.isSubmodel]
    stream.writeInt32(len(partList))
    for part in partList:
        __writeAbstractPart(stream, part)

    submodelList = [p for p in partDictionary.values() if p.isSubmodel]
    stream.writeInt32(len(submodelList))
    for model in submodelList:
        __writeSubmodel(stream, model)

def __writeAbstractPart(stream, part):

    stream << QString(part.filename) << QString(part.name)
    stream.writeBool(part.isPrimitive)
    stream.writeInt32(part.width)
    stream.writeInt32(part.height)
    stream.writeInt32(part.leftInset)
    stream.writeInt32(part.bottomInset)
    stream << part.center

    stream.writeFloat(part.pliScale)
    stream.writeFloat(part.pliRotation[0])
    stream.writeFloat(part.pliRotation[1])
    stream.writeFloat(part.pliRotation[2])
    
    stream.writeInt32(len(part.primitives))
    for primitive in part.primitives:
        __writePrimitive(stream, primitive)
        
    stream.writeInt32(len(part.parts))
    for part in part.parts:
        __writePart(stream, part)

def __writePrimitive(stream, primitive):
    __writeLicColor(stream, primitive.color)
    stream.writeInt16(primitive.type)
    stream.writeInt32(primitive.winding)

    for point in primitive.points:
        stream.writeFloat(point)

def __writePart(stream, part):
    stream << QString(part.abstractPart.filename)
    stream.writeBool(part.inverted)
    __writeLicColor(stream, part.color)

    for point in part.matrix:
        stream.writeFloat(point)

    stream.writeBool(part.calloutPart != None)

    pageNumber = stepNumber = -1
    if part.parentItem() and part.getCSI():
        pageNumber, stepNumber = part.getCSI().getPageStepNumberPair()
    stream.writeInt32(pageNumber)
    stream.writeInt32(stepNumber)
    stream.writeBool(part.isInPLI)

    if part.displacement and part.displaceDirection:
        stream.writeBool(True)
        stream.writeFloat(part.displacement[0])
        stream.writeFloat(part.displacement[1])
        stream.writeFloat(part.displacement[2])
        stream.writeInt32(part.displaceDirection)
        if part.filename != "arrow":
            stream.writeInt32(len(part.arrows))
            for arrow in part.arrows:
                __writePart(stream, arrow)
    else:
        stream.writeBool(False)

    if isinstance(part, Arrow):
        stream.writeInt32(part.getLength())
        stream.writeFloat(part.axisRotation)

def __writeAnnotationSet(stream, page):
    stream.writeInt32(len(page.annotations))
    for annotation in page.annotations:
        stream << annotation.pixmap()
        stream << QString(annotation.filename)
        stream << annotation.pos()
        stream.writeBool(annotation.isAnnotation)
        stream.writeInt32(annotation.zValue())

def __writePage(stream, page):
    stream.writeInt32(page.number)
    stream.writeInt32(page._row)
    
    __writeRoundedRectItem(stream, page)
    stream << page.color

    stream.writeInt32(page.layout.orientation)
    stream << page.numberItem.pos() << page.numberItem.font()

    if page.numberItem and page.numberItem._customNumber:
        stream.writeBool(True)
        stream.writeInt32(page.numberItem._customNumber)
    else:
        stream.writeBool(False)

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
    for separator in page.separators:
        stream.writeInt32(separator.row())
        stream << separator.pos() << separator.rect() << separator.pen()
        stream.writeBool(separator.enabled)

    __writeAnnotationSet(stream, page)

def __writeTitlePage(stream, page):
    
    if page is None:
        stream.writeBool(False)
        return
    
    stream.writeBool(True)
    __writeRoundedRectItem(stream, page)
    stream << page.color

    if page.submodelItem:
        stream.writeBool(True)
        __writeSubmodelItem(stream, page.submodelItem)
    else:
        stream.writeBool(False)
        
    stream.writeInt32(len(page.labels))
    for label in page.labels:
        stream << label.pos() << label.font() << label.text()

    __writeAnnotationSet(stream, page)

def __writePartListPage(stream, page):
    stream.writeInt32(page.number)
    stream.writeInt32(page._row)

    __writeRoundedRectItem(stream, page)
    stream << page.color

    stream << page.numberItem.pos() << page.numberItem.font()

    __writePLI(stream, page.pli)
    __writeAnnotationSet(stream, page)

def __writeStep(stream, step):
    
    stream.writeInt32(step.number)
    stream.writeBool(True if step.pli else False)
    stream.writeBool(True if step.numberItem else False)
    
    assert(step.maxRect is not None)
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

    if step.rotateIcon:
        stream.writeBool(True)
        __writeRoundedRectItem(stream, step.rotateIcon)
        stream << step.rotateIcon.arrowPen
    else:
        stream.writeBool(False)
        
    if step.numberItem and step.numberItem._customNumber:
        stream.writeBool(True)
        stream.writeInt32(step.numberItem._customNumber)
    else:
        stream.writeBool(False)

def __writeCallout(stream, callout):
    stream.writeInt32(callout.number)
    stream.writeBool(callout.showStepNumbers)
    stream.writeInt32(callout.borderFit)

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

    partList = callout.getPartList()
    stream.writeInt32(len(partList))
    for part in partList:
        __writePart(stream, part)

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

    if submodelItem.numberItem:
        stream.writeBool(True)
        stream.writeInt32(submodelItem.quantity)
        stream << submodelItem.numberItem.pos() << submodelItem.numberItem.font()
    else:
        stream.writeBool(False)
        
    stream.writeInt32(submodelItem.abstractPart.width)
    stream.writeInt32(submodelItem.abstractPart.height)
    stream.writeInt32(submodelItem.abstractPart.center.x())
    stream.writeInt32(submodelItem.abstractPart.center.y())

def __writeCSI(stream, csi):
    stream << csi.pos()
    stream.writeInt32(csi.rect().width())
    stream.writeInt32(csi.rect().height())
    stream << csi.center

    stream.writeFloat(csi.scaling)
    stream.writeFloat(csi.rotation[0])
    stream.writeFloat(csi.rotation[1])
    stream.writeFloat(csi.rotation[2])

def __writePLI(stream, pli):
    __writeRoundedRectItem(stream, pli)
    stream.writeInt32(len(pli.pliItems))
    for item in pli.pliItems:
        __writePLIItem(stream, item)

def __writePLIItem(stream, pliItem):
    stream << QString(pliItem.abstractPart.filename)
    __writeLicColor(stream, pliItem.color)
    stream.writeInt32(pliItem.quantity)
    stream << pliItem.pos() << pliItem.rect()
    stream << pliItem.numberItem.pos() << pliItem.numberItem.font()

    if pliItem.lengthIndicator:
        stream.writeBool(True)
        li = pliItem.lengthIndicator
        stream << li.pos() << li.rect() << li.font() << QString(li.lengthText) << li.labelColor << li.pen() << li.brush()
    else:
        stream.writeBool(False)

def __writeRoundedRectItem(stream, parent):
    stream << parent.pos() << parent.rect() << parent.pen() << parent.brush()
    stream.writeInt16(parent.cornerRadius)

