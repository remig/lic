from PyQt4.QtGui import QUndoCommand
from PyQt4.QtCore import SIGNAL

import Helpers

NextCommandID = 122
def getNewCommandID():
    global NextCommandID
    NextCommandID += 1
    return NextCommandID

QUndoCommand.id = lambda self: self._id

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

    def undo(self):
        for item, oldPos, newPos in self.itemList:
            item.setPos(oldPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()

    def redo(self):
        for item, oldPos, newPos in self.itemList:
            item.setPos(newPos)
            if hasattr(item.parentItem(), "resetRect"):
                item.parentItem().resetRect()

class DisplacePartCommand(QUndoCommand):

    """
    DisplacePartCommand stores a tuple of part and old & new displacement:
    displaceCommand = (part, oldDisplacement, newDisplacement)
    """

    _id = getNewCommandID()

    def __init__(self, part, oldDisp, newDisp):
        QUndoCommand.__init__(self, "Part displacement")
        self.part, self.oldDisp, self.newDisp = part, oldDisp, newDisp

    def undo(self):
        self.part.displacement = list(self.oldDisp)
        self.part.csi().resetPixmap()

    def redo(self):
        self.part.displacement = list(self.newDisp)
        self.part.csi().resetPixmap()

class BeginDisplacement(QUndoCommand):
    
    """
    BeginDisplaceCommand stores a (part, direction, arrow) tuple to displace
    """

    _id = getNewCommandID()

    def __init__(self, part, direction, arrow):
        QUndoCommand.__init__(self, "Begin Part displacement")
        self.part = part 
        self.direction = direction
        self.arrow = arrow

    def undo(self):
        part = self.part
        part.displaceDirection = None
        part.displacement = []
        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        part.csi().removeArrow(self.arrow)
        part.scene().emit(SIGNAL("layoutChanged()"))
        part.csi().resetPixmap()

    def redo(self):
        part = self.part
        part.displaceDirection = self.direction
        part.displacement = Helpers.getDisplacementOffset(self.direction)
        self.arrow.setPosition(*Helpers.GLMatrixToXYZ(part.matrix))
        part.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        part.csi().addArrow(self.arrow)
        part.scene().emit(SIGNAL("layoutChanged()"))
        part.csi().resetPixmap()
    
class ResizeCSIPLICommand(QUndoCommand):

    """
    ResizeCSIPLICommand stores a list of old / new image size pairs:
    sizes = ((oldCSISize, newCSISize), (oldPLISize, newPLISize))
    """

    _id = getNewCommandID()

    def __init__(self, instructions, sizes):
        QUndoCommand.__init__(self, "CSI | PLI resize")
        
        self.instructions = instructions
        csiSizes, pliSizes = sizes
        self.oldCSISize, self.newCSISize = csiSizes
        self.oldPLISize, self.newPLISize = pliSizes
        
    def undo(self):
        self.instructions.setCSIPLISize(self.oldCSISize, self.oldPLISize)
    
    def redo(self):
        self.instructions.setCSIPLISize(self.newCSISize, self.newPLISize)
    
    def mergeWith(self, command):
        
        if command.id() != self.id():
            return False
        
        self.newCSISize = command.newCSISize
        self.newPLISize = command.newPLISize
        return True

class MoveStepToPageCommand(QUndoCommand):

    """
    stepSet stores a list of (step, oldPage, newPage) tuples:
    stepSet = [(step1, oldPage1, newPage1), (step2, oldPage2, newPage2)]
    """

    _id = getNewCommandID()

    def __init__(self, stepSet):
        QUndoCommand.__init__(self, "move Step to Page")
        self.stepSet = stepSet

    def undo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(oldPage)
            oldPage.initLayout()
            newPage.initLayout()

    def redo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage)
            newPage.initLayout()
            oldPage.initLayout()

class AddRemoveStepCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, step, addStep):
        QUndoCommand.__init__(self, "%s Step" % ("add" if addStep else "delete"))
            
        self.step = step
        self.parent = step.parentItem()
        self.addStep = addStep

    def doAction(self, redo):
        parent = self.parent
        if (redo and self.addStep) or (not redo and not self.addStep):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.insertStep(self.step)
            parent.scene().emit(SIGNAL("layoutChanged()"))
            self.step.setSelected(True)
        else:
            self.step.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.deleteStep(self.step)                
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

    def undo(self):
        self.doAction(False)

    def redo(self):
        self.doAction(True)

class AddRemoveCalloutCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, callout, addCallout):
        QUndoCommand.__init__(self, "%s Callout" % ("add" if addCallout else "delete"))
            
        self.callout = callout
        self.parent = callout.parentItem()
        self.addCallout = addCallout

    def doAction(self, redo):
        parent = self.parent
        if (redo and self.addCallout) or (not redo and not self.addCallout):
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.addCallout(self.callout)
            parent.scene().emit(SIGNAL("layoutChanged()"))
            self.callout.setSelected(True)
        else:
            self.callout.setSelected(False)
            parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            parent.removeCallout(self.callout)                
            parent.scene().emit(SIGNAL("layoutChanged()"))
        parent.initLayout()

    def undo(self):
        self.doAction(False)

    def redo(self):
        self.doAction(True)

class AddRemovePageCommand(QUndoCommand):

    _id = getNewCommandID()

    def __init__(self, page, addPage):
        QUndoCommand.__init__(self, "%s Page" % ("add" if addPage else "delete"))
        self.page = page
        self.addPage = addPage

    def doAction(self, redo):
        page = self.page
        page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))

        if (redo and self.addPage) or (not redo and not self.addPage):
            page.parent().addPage(page)
            number = page.number
        else:
            page.parent().deletePage(page)
            number = page.number - 1

        page.instructions.emit(SIGNAL("layoutChanged()"))
        page.instructions.selectPage(number)

    def undo(self):
        self.doAction(False)

    def redo(self):
        self.doAction(True)

class MovePartsToStepCommand(QUndoCommand):

    """
    MovePartToStepCommand stores a part list, original step and step moved to
    (partList, oldStep, newStep)
    """

    _id = getNewCommandID()

    def __init__(self, partSet):
        QUndoCommand.__init__(self, "move Part to Step")
        self.partList, self.oldStep, self.newStep = partSet

    def moveFromStepToStep(self, oldStep, newStep):
        oldStep.scene().clearSelection()
        oldStep.scene().emit(SIGNAL("layoutAboutToBeChanged()"))

        for part in self.partList:
            oldStep.removePart(part)
            newStep.addPart(part)

        oldStep.scene().emit(SIGNAL("layoutChanged()"))

        oldStep.csi.resetPixmap()
        newStep.csi.resetPixmap()
        oldStep.parent().initLayout()
        newStep.parent().initLayout()
            
    def undo(self):
        self.moveFromStepToStep(self.newStep, self.oldStep)

    def redo(self):
        self.moveFromStepToStep(self.oldStep, self.newStep)

class AddPartsToCalloutCommand(QUndoCommand):

    """
    AddPartsToCalloutCommand stores a part list and destination callout
    """

    _id = getNewCommandID()

    def __init__(self, partSet):
        QUndoCommand.__init__(self, "add Part to Callout")
        self.partList, self.callout = partSet

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
        
    def undo(self):
        self.doAction(False)

    def redo(self):
        self.doAction(True)

class AdjustArrowLength(QUndoCommand):

    """
    AdjustArrowLength stores an arrow and offset to add / remove to length
    (arrow, offset)
    """

    _id = getNewCommandID()

    def __init__(self, arrowSet):
        QUndoCommand.__init__(self, "arrow length change")
        self.arrow, self.offset = arrowSet

    def undo(self):
        self.arrow.adjustLength(-self.offset)

    def redo(self):
        self.arrow.adjustLength(self.offset)
