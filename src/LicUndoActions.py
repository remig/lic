"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicUndoActions.py) is part of Lic.

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

from PyQt4.QtGui import QUndoCommand, QPixmap
from PyQt4.QtCore import SIGNAL, QSizeF

import LicHelpers
import LicGLHelpers

def resetGLItem(self, templateItem):
    instructions = templateItem.getPage().instructions
    templateItem.resetPixmap()
    templateItem.getPage().resetCallout()
    templateItem.getPage().initLayout()

    if templateItem.itemClassName == "CSI":
        for unused in instructions.initCSIDimensions(True):
            pass  # Don't care about yielded items here

    elif templateItem.itemClassName == "PLI":
        for unused in instructions.initPartDimensions(True):
            pass  # Don't care about yielded items here
        instructions.mainModel.initAllPLILayouts()

    elif templateItem.itemClassName == "SubmodelPreview":
        instructions.mainModel.initSubmodelImages()  # TODO: Template rotate Submodel Image is broken for nested submodels (viper.lic)

NextCommandID = 122
def getNewCommandID():
    global NextCommandID
    NextCommandID += 1
    return NextCommandID

QUndoCommand.id = lambda self: self._id
QUndoCommand.undo = lambda self: self.doAction(False)
QUndoCommand.redo = lambda self: self.doAction(True)
QUndoCommand.resetGLItem = resetGLItem

class MoveCommand(QUndoCommand):

    """
    MoveCommand stores a list of parts moved together:
    itemList[0] = (item, item.oldPos, item.newPos)
    """

    _id = getNewCommandID()
    
    def __init__(self, itemList):
        QUndoCommand.__init__(self, "move Page Object")

        self.itemList = []
        for item in itemList:
            self.itemList.append((item, item.oldPos, item.pos()))

    def doAction(self, redo):
        for item, oldPos, newPos in self.itemList:
            item.setPos(newPos if redo else oldPos)
            if hasattr(item, "resetArrow"):
                item.resetArrow()
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()

class ResizeCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, item, oldRect, newRect):
        QUndoCommand.__init__(self, "resize Item")

        self.item, self.oldRect, self.newRect = item, oldRect, newRect

    def doAction(self, redo):
        self.item.initLayout(self.newRect if redo else self.oldRect)

class LayoutItemCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target):
        QUndoCommand.__init__(self, "auto-layout")
        self.target = target

    def doAction(self, redo):
        self.target.initLayout()

class CalloutArrowMoveCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, arrow, oldPoint, newPoint):
        QUndoCommand.__init__(self, "move Callout Arrow")
        self.arrow, self.oldPoint, self.newPoint = arrow, oldPoint, newPoint

    # Need to invalidate scene because we don't actually move a part here, so scene doesn't redraw
    def doAction(self, redo):
        self.arrow.point = self.newPoint if redo else self.oldPoint
        self.arrow.parentItem().internalPoints = []
        self.arrow.update()

class CalloutBorderFitCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, label, oldText, newText):
        QUndoCommand.__init__(self, "Change Label Text")
        self.label, self.oldText, self.newText = label, oldText, newText

    def doAction(self, redo):
        text = self.newText if redo else self.oldText
        self.label.setText(text)
        self.label.data = lambda index: "Label: " + text

class SetTextCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, oldBorder, newBorder):
        QUndoCommand.__init__(self, "Callout Border fit")
        self.callout, self.oldBorder, self.newBorder = callout, oldBorder, newBorder

    def doAction(self, redo):
        self.callout.setBorderFit(self.newBorder if redo else self.oldBorder)
        self.callout.update()

class SetDefaultDiameterCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, circle, oldDiameter, newDiameter, doLayout):
        QUndoCommand.__init__(self, "circle Diameter")
        self.circle, self.oldDiameter, self.newDiameter, self.doLayout = circle, oldDiameter, newDiameter, doLayout

    def doAction(self, redo):
        diameter = self.newDiameter if redo else self.oldDiameter
        template = self.circle.getPage()
        self.circle.setDiameter(diameter)
        self.circle.update()
        if self.doLayout:
            template.initLayout()
        for page in template.instructions.getPageList():
            for child in page.getAllChildItems():
                if self.circle.itemClassName == child.itemClassName:
                    child.setDiameter(diameter)
                    child.update()
                    if self.doLayout:
                        child.getPage().initLayout()

class DisplacePartCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, oldDisp, newDisp):
        QUndoCommand.__init__(self, "Displace Part")
        self.part, self.oldDisp, self.newDisp = part, oldDisp, newDisp

    def doAction(self, redo):
        self.part.displacement = list(self.newDisp if redo else self.oldDisp)
        self.part.getCSI().resetPixmap()

class BeginEndDisplacementCommand(QUndoCommand):
    
    _id = getNewCommandID()

    def __init__(self, part, direction, end = False):
        if end:
            QUndoCommand.__init__(self, "Remove Part displacement")
            self.undo, self.redo = self.redo, self.undo
        else:
            QUndoCommand.__init__(self, "Begin Part displacement")
        self.part, self.direction = part, direction

    def doAction(self, redo):
        part = self.part
        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        part.addNewDisplacement(self.direction) if redo else part.removeDisplacement()
        part.scene().emit(SIGNAL("layoutChanged()"))
        part.getCSI().resetPixmap()
        if part.originalPart: # Part is in Callout - resize Callout
            part.getStep().resetRect()

class ResizePageCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, oldPageSize, newPageSize, oldResolution, newResolution, doRescale):
        QUndoCommand.__init__(self, "Page Resize")

        self.template = template
        self.oldPageSize, self.newPageSize = oldPageSize, newPageSize
        self.oldResolution, self.newResolution = oldResolution, newResolution
        self.doRescale = doRescale
        self.oldScale = 1.0
        self.newScale = float(newPageSize.width()) / float(oldPageSize.width())

    def undo(self):
        self.template.setGlobalPageSize(self.oldPageSize, self.oldResolution, self.doRescale, self.oldScale)

    def redo(self):
        self.template.setGlobalPageSize(self.newPageSize, self.newResolution, self.doRescale, self.newScale)

class MoveStepToPageCommand(QUndoCommand):

    """
    stepSet stores a list of (step, oldPage, newPage) tuples:
    stepSet = [(step1, oldPage1, newPage1), (step2, oldPage2, newPage2)]
    """

    _id = getNewCommandID()

    def __init__(self, stepSet):
        QUndoCommand.__init__(self, "move Step to Page")
        self.stepSet = stepSet

    def doAction(self, redo):
        self.stepSet[0][0].scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage if redo else oldPage)
            if step.csi.containsSubmodel():
                model = newPage.instructions.mainModel 
                model.reOrderSubmodelPages()
                model.syncPageNumbers()
            newPage.initLayout()
            oldPage.initLayout()
        self.stepSet[0][0].scene().emit(SIGNAL("layoutChanged()"))

class SwapStepsCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, step1, step2):
        QUndoCommand.__init__(self, "Swap Steps")
        self.step1, self.step2 = step1, step2

    def doAction(self, redo):
        s1, s2 = self.step1, self.step2
        p1, p2 = s1.parentItem(), s2.parentItem()

        p1.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        if not s1.isInCallout():
            i1, i2 = s1.row(), s2.row()
            p1.children[i1], p2.children[i2] = p2.children[i2], p1.children[i1]

        i1, i2 = p1.steps.index(s1), p2.steps.index(s2)
        p1.steps[i1], p2.steps[i2] = p2.steps[i2], p1.steps[i1]

        s1.number, s2.number = s2.number, s1.number
        s1.csi.isDirty, s2.csi.isDirty = True, True

        if p1 != p2:
            s1.setParentItem(p2)
            s2.setParentItem(p1)

        if s1.csi.containsSubmodel() or s2.csi.containsSubmodel():
            model = p1.instructions.mainModel 
            model.reOrderSubmodelPages()
            model.syncPageNumbers()

        p1.initLayout()
        if p1 != p2:
            p2.initLayout()
        p1.scene().emit(SIGNAL("layoutChanged()"))

class AddRemovePartCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, step, addPart):
        QUndoCommand.__init__(self, "%s Part" % ("add" if addPart else "delete"))
        self.part, self.step, self.addPart = part, step, addPart

    def doAction(self, redo):
        step = self.step
        page = step.getPage()
        submodel = page.submodel

        step.scene().clearSelection()
        step.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.addPart) or (not redo and not self.addPart):
            step.addPart(self.part)
            submodel.parts.append(self.part)
        else:
            self.part.setParentItem(None)
            step.removePart(self.part)
            submodel.parts.remove(self.part)

        step.scene().emit(SIGNAL("layoutChanged()"))

        page.instructions.updateMainModel()
        page.updateSubmodel()

        step.csi.isDirty = True
        page.initLayout()

class AddRemoveArrowCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, arrow, index, addArrow):
        QUndoCommand.__init__(self, "%s Arrow" % ("add" if addArrow else "delete"))
        self.part, self.arrow, self.index, self.addArrow = part, arrow, index, addArrow

    def doAction(self, redo):
        self.part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.addArrow) or (not redo and not self.addArrow):
            self.arrow.setParentItem(self.part)
            self.part.arrows.insert(self.index, self.arrow)
        else:
            self.part.scene().removeItem(self.arrow)
            self.part.arrows.remove(self.arrow)
            self.arrow.setParentItem(None)
        self.part.getCSI().isDirty = True
        self.part.scene().emit(SIGNAL("layoutChanged()"))

class AddRemoveLabelCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, page, label, index, addLabel):
        QUndoCommand.__init__(self, "%s Label" % ("add" if addLabel else "delete"))
        self.page, self.label, self.index, self.addLabel = page, label, index, addLabel

    def doAction(self, redo):
        self.page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.addLabel) or (not redo and not self.addLabel):
            self.label.setParentItem(self.page)
            self.page.labels.insert(self.index, self.label)
        else:
            self.page.scene().removeItem(self.label)
            self.page.labels.remove(self.label)
            self.label.setParentItem(None)
        self.page.scene().emit(SIGNAL("layoutChanged()"))

class AddRemoveRotateIconCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, step, addIcon):
        QUndoCommand.__init__(self, "%s Rotation Icon" % ("add" if addIcon else "delete"))
        self.step, self.addIcon = step, addIcon

    def doAction(self, redo):
        self.step.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.addIcon) or (not redo and not self.addIcon):
            self.step.addRotateIcon()
            self.step.positionRotateIcon()
        else:
            self.step.removeRotateIcon()
        self.step.scene().emit(SIGNAL("layoutChanged()"))

class AddRemoveStepCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, step, addStep):
        QUndoCommand.__init__(self, "%s Step" % ("add" if addStep else "delete"))
            
        self.step, self.addStep = step, addStep
        self.parent = step.parentItem()

    def doAction(self, redo):
        parent = self.parent
        parent.scene().clearSelection()
        if (redo and self.addStep) or (not redo and not self.addStep):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.insertStep(self.step)
            parent.scene().emit(SIGNAL("layoutChanged()"))
            self.step.setSelected(True)
        else:
            self.step.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.removeStep(self.step)                
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

class AddRemoveCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, addCallout):
        QUndoCommand.__init__(self, "%s Callout" % ("add" if addCallout else "delete"))

        self.callout, self.addCallout = callout, addCallout
        self.parent = callout.parentItem()

    def doAction(self, redo):
        parent = self.parent
        if (redo and self.addCallout) or (not redo and not self.addCallout):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.addCallout(self.callout)
            parent.scene().emit(SIGNAL("layoutChanged()"))
        else:
            self.callout.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.removeCallout(self.callout)
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

class AddRemovePageCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, scene, page, addPage):
        QUndoCommand.__init__(self, "%s Page" % ("add" if addPage else "delete"))
        self.scene, self.page, self.addPage = scene, page, addPage

    def doAction(self, redo):
        page = self.page
        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.addPage) or (not redo and not self.addPage):
            page.submodel.addPage(page)
            number = page.number
        else:
            page.submodel.deletePage(page)
            number = page.number - 1

        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(number)
        
class AddRemoveTitlePageCommand(QUndoCommand):
    
    _id = getNewCommandID()

    def __init__(self, scene, page, addPage):
        QUndoCommand.__init__(self, "%s Title Page" % ("add" if addPage else "delete"))
        self.scene, self.page, self.addPage = scene, page, addPage

    def doAction(self, redo):

        page = self.page
        model = page.submodel

        self.scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.addPage) or (not redo and not self.addPage):
            model._hasTitlePage = True
            model.titlePage = page
            if page.scene() is None:
                self.scene.addItem(page)
            model.updatePageNumbers(1, 1)
            model.incrementRows(1)
        else:
            model._hasTitlePage = False
            model.titlePage = None
            self.scene.removeItem(page)
            model.updatePageNumbers(1, -1)
            model.incrementRows(-1)

        self.scene.emit(SIGNAL("layoutChanged()"))
        self.scene.selectPage(1)

class AddRemoveGuideCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, scene, guide, addGuide):
        QUndoCommand.__init__(self, "%s Guide" % ("add" if addGuide else "remove"))
        self.scene, self.guide, self.addGuide = scene, guide, addGuide

    def doAction(self, redo):

        if (redo and self.addGuide) or (not redo and not self.addGuide):
            self.scene.guides.append(self.guide)
            self.scene.addItem(self.guide)
        else:
            self.scene.removeItem(self.guide)
            self.scene.guides.remove(self.guide)

class AddRemoveAnnotationCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, page, annotation, addAnnotation):
        QUndoCommand.__init__(self, "%s Annotation" % ("add" if addAnnotation else "remove"))
        self.page, self.annotation, self.addAnnotation = page, annotation, addAnnotation

    def doAction(self, redo):

        page, item = self.page, self.annotation
        page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.addAnnotation) or (not redo and not self.addAnnotation):
            item.setParentItem(page)
            page.annotations.append(item)
            page.addChild(len(page.children), item)
        else:
            page.scene().removeItem(item)
            page.annotations.remove(item)
            page.children.remove(item)
        page.scene().emit(SIGNAL("layoutChanged()"))

class AddRemovePartToPLICommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, addPart):
        QUndoCommand.__init__(self, "%s Part %s PLI" % (("add", "to") if addPart else ("remove", "from")))
        self.part, self.addPart = part, addPart

    def doAction(self, redo):

        part, step = self.part, self.part.getStep()
        pli = step.pli

        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.addPart) or (not redo and not self.addPart):
            step.enablePLI()
            pli.addPart(part)
        else:
            pli.removePart(part)
            if pli.isEmpty():
                step.disablePLI()
            part.isInPLI = False

        step.initLayout()
        part.scene().emit(SIGNAL("layoutChanged()"))

class MovePartsToStepCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, partList, newStep):
        QUndoCommand.__init__(self, "move Part to Step")
        self.newStep = newStep
        self.partListStepPairs = [(p, p.getStep()) for p in partList]

    def doAction(self, redo):
        self.newStep.scene().clearSelection()
        self.newStep.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        redoSubmodelOrder = False
        stepsToReset = set([self.newStep])
        
        for part, oldStep in self.partListStepPairs:
            if part.filename == 'arrow':
                continue
            startStep = oldStep if redo else self.newStep
            endStep = self.newStep if redo else oldStep
            
            part.setParentItem(None) # Temporarily set part's parent, so it doesn't get deleted by Qt
            startStep.removePart(part)
            endStep.addPart(part)
                
            if part.isSubmodel():
                redoSubmodelOrder = True
            stepsToReset.add(oldStep)

        if redoSubmodelOrder:
            mainModel = self.newStep.getPage().instructions.mainModel
            mainModel.reOrderSubmodelPages()
            mainModel.syncPageNumbers()
        
        self.newStep.scene().emit(SIGNAL("layoutChanged()"))

        # Need to refresh each step between the lowest and highest numbers
        minStep = min(stepsToReset, key = lambda step: step.number)
        maxStep = max(stepsToReset, key = lambda step: step.number)

        nextStep = minStep.getNextStep()
        while (nextStep is not None and nextStep.number < maxStep.number):
            stepsToReset.add(nextStep)
            nextStep = nextStep.getNextStep()
            
        for step in stepsToReset:
            step.csi.isDirty = True
            step.initLayout()
            if step.isInCallout():
                step.parentItem().initLayout()
    
class AddPartsToCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, partList):
        QUndoCommand.__init__(self, "Add Parts to Callout")
        self.callout, self.partList = callout, partList

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        for part in self.partList:
            if redo:
                self.callout.addPart(part)
            else:
                self.callout.removePart(part)

        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.steps[-1].csi.resetPixmap()
        self.callout.initLayout()

class RemovePartsFromCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, partList):
        QUndoCommand.__init__(self, "Remove Parts from Callout")
        self.callout = callout
        self.partStepList = [(part, part.calloutPart.getStep()) for part in partList]

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        for part, step in self.partStepList:
            if redo:
                self.callout.removePart(part)
            else:
                self.callout.addPart(part, step)

        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        for step in self.callout.steps:
            step.csi.resetPixmap()
        self.callout.initLayout()

class MergeCalloutsCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, mainCallout, calloutList, mergeCallouts):
        QUndoCommand.__init__(self, "%s Callouts" % ("Merge" if mergeCallouts else "Split"))
        self.mainCallout, self.mergeCallouts = mainCallout, mergeCallouts

        # Store the original {callout: merged callouts} configuration
        self.calloutConfig = dict([(callout, tuple(callout.mergedCallouts)) for callout in calloutList])
        self.originalMergedCallouts = tuple(self.mainCallout.mergedCallouts)
        self.parent = mainCallout.parentItem()

    def doAction(self, redo):
        parent = self.parent
        parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.mergeCallouts) or (not redo and not self.mergeCallouts):
            for callout in self.calloutConfig.keys():
                parent.removeCallout(callout)
                self.mainCallout.mergeCallout(callout)
        else:
            for callout, mergeList in self.calloutConfig.items():
                parent.addCallout(callout)
                self.mainCallout.removeMergedCallout(callout)
                callout.setMergedCallouts(list(mergeList))
            self.mainCallout.setMergedCallouts(list(self.originalMergedCallouts))

        parent.initLayout()
        parent.scene().emit(SIGNAL("layoutChanged()"))

class SwitchToNextCalloutBase(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, doSwitch):
        QUndoCommand.__init__(self, "Switch to next Callout base")
        self.callout, self.doSwitch = callout, doSwitch
        self.parent = callout.parentItem()

    def doAction(self, redo):
        parent = self.parent
        parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.doSwitch) or (not redo and not self.doSwitch):
            newCallout = self.callout.mergedCallouts.pop(0)
            parent.addCallout(newCallout)
            newCallout.mergeCallout(self.callout, append = True)
        else:
            newCallout = self.callout.mergedCallouts.pop()
            parent.addCallout(newCallout)
            newCallout.mergeCallout(self.callout)
                
        parent.removeCallout(self.callout)
        self.callout.mergedCallouts = []
        self.callout = newCallout
        parent.initLayout()
        parent.scene().emit(SIGNAL("layoutChanged()"))

class ChangeAnnotationPixmap(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, annotation, oldFilename, newFilename):
        QUndoCommand.__init__(self, "change Annotation picture")
        self.annotation, self.oldFilename, self.newFilename = annotation, oldFilename, newFilename

    def doAction(self, redo):
        filename = self.newFilename if redo else self.oldFilename
        self.annotation.setPixmap(QPixmap(filename))

class ToggleAnnotationOrderCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, annotation, moveForward):
        QUndoCommand.__init__(self, "move Annotation to %s" % ("Foreground" if moveForward else "Background"))
        self.annotation, self.moveForward = annotation, moveForward

    def doAction(self, redo):
        moveForward = (redo and self.moveForward) or (not redo and not self.moveForward)
        self.annotation.changeOrder(moveForward)

class ToggleStepNumbersCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, enableNumbers):
        QUndoCommand.__init__(self, "%s Step Numbers" % ("show" if enableNumbers else "hide"))
        self.callout, self.enableNumbers = callout, enableNumbers

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.enableNumbers) or (not redo and not self.enableNumbers):
            self.callout.enableStepNumbers()
        else:
            self.callout.disableStepNumbers()
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.initLayout()

class ToggleCalloutQtyCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, enableQty):
        QUndoCommand.__init__(self, "%s Callout Quantity" % ("Show" if enableQty else "Hide"))
        self.callout, self.enableQty = callout, enableQty

    def doAction(self, redo):
        self.callout.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.enableQty) or (not redo and not self.enableQty):
            self.callout.setMergedQuantity()
        else:
            self.callout.removeQuantityLabel()
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        self.callout.initLayout()

class AdjustArrowLength(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, arrow, oldLength, newLength):
        QUndoCommand.__init__(self, "change arrow length")
        self.arrow, self.oldLength, self.newLength = arrow, oldLength, newLength

    def doAction(self, redo):
        length = self.newLength if redo else self.oldLength
        self.arrow.setLength(length)
        self.arrow.getCSI().resetPixmap()

class AdjustArrowRotation(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, arrow, oldRotation, newRotation):
        QUndoCommand.__init__(self, "change arrow rotation")
        self.arrow, self.oldRotation, self.newRotation = arrow, oldRotation, newRotation

    def doAction(self, redo):
        self.arrow.axisRotation = self.newRotation if redo else self.oldRotation
        self.arrow.getCSI().resetPixmap()

class ScaleItemCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, oldScale, newScale):
        QUndoCommand.__init__(self, "Item Scale")
        self.target, self.oldScale, self.newScale = target, oldScale, newScale

    def doAction(self, redo):
        self.target.scaling = self.newScale if redo else self.oldScale
        self.target.resetPixmap() 
        self.target.getPage().initLayout()

class RotateItemCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, oldRotation, newRotation):
        QUndoCommand.__init__(self, "Item rotation")
        self.target, self.oldRotation, self.newRotation = target, oldRotation, newRotation

    def doAction(self, redo):
        self.target.rotation = list(self.newRotation) if redo else list(self.oldRotation)
        self.target.resetPixmap() 
        self.target.getPage().initLayout()

class ScaleDefaultItemCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, templateItem, oldScale, newScale):
        QUndoCommand.__init__(self, "Change default %s Scale" % templateItem.itemClassName)
        self.target, self.templateItem = target, templateItem
        self.oldScale, self.newScale = oldScale, newScale

    def doAction(self, redo):
        self.target.defaultScale = self.newScale if redo else self.oldScale
        self.resetGLItem(self.templateItem)
        self.templateItem.update()  # Need this to force full redraw
            
class RotateDefaultItemCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, templateItem, oldRotation, newRotation):
        QUndoCommand.__init__(self, "Change default %s rotation" % templateItem.itemClassName)
        self.target, self.templateItem = target, templateItem
        self.oldRotation, self.newRotation = oldRotation, newRotation

    def doAction(self, redo):
        self.target.defaultRotation = list(self.newRotation) if redo else list(self.oldRotation)
        self.resetGLItem(self.templateItem)

class SetPageNumberPosCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, oldPos, newPos):
        QUndoCommand.__init__(self, "change Page Number position")
        self.template, self.oldPos, self.newPos = template, oldPos, newPos

    def doAction(self, redo):
        pos = self.newPos if redo else self.oldPos
        self.template.setNumberItemPos(pos)
        for page in self.template.instructions.getPageList():
            page.resetPageNumberPosition()

class SetPageBackgroundColorCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, oldColor, newColor):
        QUndoCommand.__init__(self, "change Page background")
        self.template, self.oldColor, self.newColor = template, oldColor, newColor

    def doAction(self, redo):
        color = self.newColor if redo else self.oldColor
        self.template.setColor(color)
        self.template.update()
        for page in self.template.instructions.getPageList():
            page.color = color
            page.update()

class SetPageBackgroundBrushCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, oldBrush, newBrush):
        QUndoCommand.__init__(self, "change Page background")
        self.template, self.oldBrush, self.newBrush = template, oldBrush, newBrush

    def doAction(self, redo):
        brush = self.newBrush if redo else self.oldBrush
        self.template.setBrush(brush)
        self.template.update()
        for page in self.template.instructions.getPageList():
            page.setBrush(brush)
            page.update()

class SetPenCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, oldPen, newPen = None, penSetter = "setPen"):
        QUndoCommand.__init__(self, "change Border")
        self.target, self.oldPen, self.penSetter = target, oldPen, penSetter
        self.newPen = newPen if newPen else target.pen()
        self.template = target.getPage()

    def doAction(self, redo):
        pen = self.newPen if redo else self.oldPen
        self.target.__getattribute__(self.penSetter)(pen)
        self.target.update()
        for page in self.template.instructions.getPageList():
            for child in page.getAllChildItems():
                if self.target.itemClassName == child.itemClassName:
                    child.__getattribute__(self.penSetter)(pen)
                    child.update()

class SetBrushCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, target, oldBrush, newBrush = None, text = "change Fill"):
        QUndoCommand.__init__(self, text)
        self.target, self.oldBrush = target, oldBrush
        self.newBrush = newBrush if newBrush else target.brush()
        self.template = target.getPage()

    def doAction(self, redo):
        brush = self.newBrush if redo else self.oldBrush
        self.target.setBrush(brush)
        self.target.update()
        for page in self.template.instructions.getPageList():
            for child in page.getAllChildItems():
                if self.target.itemClassName == child.itemClassName:
                    child.setBrush(brush)
                    child.update()
    
class SetItemFontsCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, oldFont, newFont, target):
        QUndoCommand.__init__(self, "change " + target + " font")
        self.template, self.oldFont, self.newFont, self.target = template, oldFont, newFont, target

    def doAction(self, redo):
        font = self.newFont if redo else self.oldFont
        if self.target == 'Page':
            self.template.numberItem.setFont(font)
            for page in self.template.instructions.getPageList():
                page.numberItem.setFont(font)
                
        elif self.target == 'Step':
            self.template.steps[0].numberItem.setFont(font)
            for page in self.template.instructions.getPageList():
                for step in page.steps:
                    step.numberItem.setFont(font)
                    
        elif self.target == 'PLIItem':
            for item in self.template.steps[0].pli.pliItems:
                item.numberItem.setFont(font)
            for page in self.template.instructions.getPageList():
                for child in page.getAllChildItems():
                    if self.target == child.itemClassName:
                        child.numberItem.setFont(font)

        elif self.target == 'GraphicsCircleLabelItem':
            for item in self.template.steps[0].pli.pliItems:
                if item.lengthIndicator:
                    item.lengthIndicator.setFont(font)
            for page in self.template.instructions.getPageList():
                for child in page.getAllChildItems():
                    if self.target == child.itemClassName:
                        child.setFont(font)

class TogglePLIs(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, template, enablePLIs):
        QUndoCommand.__init__(self, "%s PLIs" % ("Enable" if enablePLIs else "Remove"))
        self.template, self.enablePLIs = template, enablePLIs

    def doAction(self, redo):
        self.template.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        if (redo and self.enablePLIs) or (not redo and not self.enablePLIs):
            self.template.steps[0].enablePLI()
            self.template.instructions.mainModel.showHidePLIs(True, True)
        else:
            self.template.steps[0].disablePLI()
            self.template.instructions.mainModel.showHidePLIs(False, True)
        self.template.scene().emit(SIGNAL("layoutChanged()"))
        self.template.initLayout()

class ToggleCSIPartHighlightCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, state, target, templateCSI):
        QUndoCommand.__init__(self, "Highlight Parts")
        self.state, self.target, self.templateCSI = state, target, templateCSI

    def doAction(self, redo):
        self.target.highlightNewParts = redo and self.state
        self.templateCSI.isDirty = True
        self.templateCSI.getPage().instructions.setAllCSIDirty()
        self.templateCSI.scene().update()

class ChangePartColorCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, oldColor, newColor):
        QUndoCommand.__init__(self, "Change Part color")
        self.part, self.oldColor, self.newColor = part, oldColor, newColor

    def doAction(self, redo):
        self.part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        oldColor, newColor = (self.oldColor, self.newColor) if redo else (self.newColor, self.oldColor)
        self.part.changeColor(newColor)
        if self.part.getStep().pli:
            self.part.getStep().pli.changePartColor(self.part, oldColor, newColor)

        page = self.part.getPage()
        page.instructions.updateMainModel()
        page.updateSubmodel()

        self.part.scene().emit(SIGNAL("layoutChanged()"))

class ChangeAbstractPartCommand(QUndoCommand):
    
    _id = getNewCommandID()
    
    def __init__(self, part, newFilename):
        QUndoCommand.__init__(self, "Change Part")
        self.part, self.newFilename = part, newFilename
        self.oldFilename = self.part.filename

    def doAction(self, redo):
        scene = self.part.scene()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        scene.clearSelection()

        self.part.changeAbstractPart(self.newFilename if redo else self.oldFilename)

        page = self.part.getPage()
        page.instructions.updateMainModel()
        page.updateSubmodel()

        scene.emit(SIGNAL("layoutChanged()"))

        page.initLayout()
        scene.update()

class ChangePartPosRotCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, part, oldPos, newPos, oldRot, newRot):
        QUndoCommand.__init__(self, "Change Part position")
        self.part, self.oldPos, self.newPos = part, oldPos, newPos
        self.oldRot, self.newRot = oldRot, newRot

    def doAction(self, redo):
        self.part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        pos = self.newPos if redo else self.oldPos
        rot = self.newRot if redo else self.oldRot
        self.part.changePosRot(pos, rot)
        self.part.scene().emit(SIGNAL("layoutChanged()"))

        page = self.part.getPage() 
        page.instructions.updateMainModel(False)
        page.updateSubmodel()

class SubmodelToCalloutCommand(QUndoCommand):
    
    _id = getNewCommandID()
    
    def __init__(self, submodel):
        QUndoCommand.__init__(self, "Submodel To Callout")
        self.submodel = submodel
        self.parentModel = submodel._parent
        
    def redo(self):
        # Convert a Submodel into a Callout

        self.targetStep = self.parentModel.findSubmodelStep(self.submodel)
        scene = self.targetStep.scene()
        scene.clearSelection()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        
        self.targetCallout = self.targetStep.addBlankCalloutSignal(False, False)

        # Find each instance of this submodel on the target page
        self.submodelInstanceList = []
        self.addedParts = []
        for part in self.targetStep.csi.getPartList():
            if part.abstractPart == self.submodel:
                self.targetStep.removePart(part)
                self.submodelInstanceList.append(part)

        calloutDone = False
        for submodelPart in self.submodelInstanceList:
            for page in self.submodel.pages:
                for step in page.steps:
                    for part in step.csi.getPartList():
                        newPart = part.duplicate()
                        newPart.matrix = LicHelpers.multiplyMatrices(newPart.matrix, submodelPart.matrix)
                        self.addedParts.append(newPart)
                        
                        self.targetStep.addPart(newPart)
                        if not calloutDone:
                            self.targetCallout.addPart(newPart.duplicate())

                    if step != page.steps[-1] and not calloutDone:
                        self.targetCallout.addBlankStep(False)
                            
            calloutDone = True
        
        if len(self.submodelInstanceList) > 1:
            self.targetCallout.setQuantity(len(self.submodelInstanceList))
            
        for step in self.targetCallout.steps:
            step.csi.resetPixmap()
        self.targetStep.initLayout()
        self.targetCallout.initLayout()
                    
        self.parentModel.removeSubmodel(self.submodel)
        scene.emit(SIGNAL("layoutChanged()"))
        scene.selectPage(self.targetStep.parentItem().number)
        self.targetCallout.setSelected(True)
        scene.emit(SIGNAL("sceneClick"))
        
    def undo(self):
        # Convert a Callout into a Submodel
        # For now, assume this really is an undo, and we have a fully defined self.submodel, targetStep and targetCallout 
        
        scene = self.targetStep.scene()
        scene.clearSelection()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))
        
        for part in self.addedParts:
            self.targetStep.removePart(part)

        for submodel in self.submodelInstanceList:
            self.targetStep.addPart(submodel)

        self.parentModel.addSubmodel(self.submodel)
        
        self.targetStep.removeCallout(self.targetCallout)
        self.targetStep.initLayout()
        scene.emit(SIGNAL("layoutChanged()"))

        scene.selectPage(self.submodel.pages[0].number)
        self.submodel.pages[0].setSelected(True)
        scene.emit(SIGNAL("sceneClick"))

class CalloutToSubmodelCommand(SubmodelToCalloutCommand):

    _id = getNewCommandID()
    
    def __init__(self, callout):
        QUndoCommand.__init__(self, "Callout To Submodel")
        self.callout = callout
        
    def redo(self):
        callout = self.callout
        scene = callout.scene()
        scene.clearSelection()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        partList = callout.getOriginalPartList()
        self.targetStep = callout.parentItem()
        self.parentModel = callout.getPage().parent()
        submodel = callout.createBlankSubmodel()
        submodel.appendBlankPage()
        
        for part in partList:
            submodel.parts.append(part)
            submodel.pages[0].steps[0].addPart(part)
            self.targetStep.removePart(part)

        submodel.addInitialPagesAndSteps()
        submodel.mergeInitialPages()
        if submodel.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            submodel.createGLDisplayList()
        submodel.resetPixmap()

        self.newPart = submodel.createBlankPart()
        self.newPart.abstractPart = submodel
        self.targetStep.addPart(self.newPart)
        
        self.parentModel.addSubmodel(submodel)

        self.targetStep.removeCallout(callout)
        self.targetStep.initLayout()
        self.submodel = submodel

        scene.emit(SIGNAL("layoutChanged()"))

        scene.selectPage(submodel.pages[0].number)
        submodel.pages[0].setSelected(True)
        scene.emit(SIGNAL("sceneClick"))

    def undo(self):
        scene = self.targetStep.scene()
        scene.clearSelection()
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        self.targetStep.removePart(self.newPart)
        self.parentModel.removeSubmodel(self.submodel)
        for part in self.submodel.parts:
            self.targetStep.addPart(part)

        self.targetStep.addCallout(self.callout)
        self.targetStep.initLayout()
        self.callout.initLayout()

        scene.emit(SIGNAL("layoutChanged()"))
        scene.selectPage(self.targetStep.parentItem().number)
        self.callout.setSelected(True)
        scene.emit(SIGNAL("sceneClick"))

class SubmodelToFromSubAssembly(QUndoCommand):
    
    _id = getNewCommandID()
    
    def __init__(self, submodel, submodelToAssembly):
        text = "Submodel to Sub Assembly" if submodelToAssembly else "Sub Assembly to Submodel"
        QUndoCommand.__init__(self, text)
        self.submodel, self.submodelToAssembly = submodel, submodelToAssembly
    
    def doAction(self, redo):
        
        self.submodel.isSubAssembly = not self.submodel.isSubAssembly
        do = (redo and self.submodelToAssembly) or (not redo and not self.submodelToAssembly)
        self.submodel.showHidePLIs(not do)
        submodelItem = self.submodel.pages[0].submodelItem
        submodelItem.convertToSubAssembly() if do else submodelItem.convertToSubmodel()

class ClonePageStepsFromSubmodel(QUndoCommand):

    _id = getNewCommandID()
    
    def __init__(self, targetSubmodel, destinationSubmodel):
        QUndoCommand.__init__(self, "clone Submodel Pages and Steps")
        self.target, self.destination = targetSubmodel, destinationSubmodel

        self.originalPageList = []
        for page in self.destination.pages:
            self.originalPageList.append((page, page._row, page._number))

        self.partPageStepList = []
        for part in self.destination.parts:
            pageNumber, stepNumber = part.getCSI().getPageStepNumberPair()
            self.partPageStepList.append((part, pageNumber, stepNumber))

    def redo(self):

        dest = self.destination
        scene = dest.instructions.scene
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        # Remove all Pages and Steps from destination submodel
        for page in list(dest.pages):
            dest.deletePage(page)

        # Now have toally empty dest, and submodel with lots of pages & steps
        # Add the right number of blank pages and steps
        for page in self.target.pages:
            dest.appendBlankPage()
            dest.pages[-1].layout.orientation = page.layout.orientation
            for step in page.steps[1:]:  # skip first Step because appendBlankPage() adds one Step automatically
                dest.pages[-1].addBlankStep()

        currentStep = dest.pages[0].steps[0]
        nextStep = currentStep.getNextStep()

        # Copy all parts in dest submodel to its first CSI
        for part in dest.parts:
            currentStep.addPart(part)

        for page in self.target.pages:
            for step in page.steps:

                if step is self.target.pages[-1].steps[-1]:
                    break  # At last step: done

                # Remove all parts in submodel's current Step from the list of parts to be moved to next step
                partList = currentStep.csi.getPartList()
                for part in step.csi.getPartList():
                    matchList = [(p.getPositionMatch(part),  p) for p in partList if p.color == part.color and p.filename == part.filename]
                    if matchList:
                        partList.remove(max(matchList)[1])
                    else:  # Try finding a match by ignoring color 
                        matchList = [(p.getPositionMatch(part),  p) for p in partList if p.filename == part.filename]
                        if matchList:
                            partList.remove(max(matchList)[1])  # no match list means submodel has part not in dest, which we ignore utterly, which is fine

                for part in partList:  # Move all parts to the next step
                    part.setParentItem(nextStep)
                    currentStep.removePart(part)
                    nextStep.addPart(part)

                if currentStep.isEmpty():  # Check if any part are left
                    currentStep.parentItem().removeStep(currentStep)

                currentStep = nextStep
                nextStep = nextStep.getNextStep()

        if self.target.pages[0].submodelItem:
            dest.pages[0].addSubmodelImage()

        for page in dest.pages:
            for step in page.steps:
                step.csi.isDirty = True
            page.initLayout()

        dest.instructions.mainModel.syncPageNumbers()
        scene.emit(SIGNAL("layoutChanged()"))

    def undo(self):
        dest = self.destination
        scene = dest.instructions.scene
        scene.emit(SIGNAL("layoutAboutToBeChanged()"))

        for part in dest.parts:
            part.setParentItem(None)  # About to delete the pages these parts live on, so change parents so Qt doesn't delete them

        for page in list(dest.pages):
            dest.deletePage(page)

        for page, row, number in self.originalPageList:
            page._row, page.number = row, number
            dest.addPage(page)

        for part, pageNumber, stepNumber in self.partPageStepList:
            page = dest.getPage(pageNumber)
            csi = page.getStep(stepNumber).csi
            csi.addPart(part)

        scene.fullItemSelectionUpdate(dest.pages[0])
        scene.emit(SIGNAL("layoutChanged()"))

class ChangeLightingCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, scene, oldValues):
        QUndoCommand.__init__(self, "Change 3D Lighting")
        self.scene, self.oldValues = scene, oldValues
        self.newValues = LicGLHelpers.getLightParameters()

    def doAction(self, redo):
        values = self.newValues if redo else self.oldValues
        LicGLHelpers.setLightParameters(*values)
        if self.scene.currentPage:
            self.scene.currentPage.update()
