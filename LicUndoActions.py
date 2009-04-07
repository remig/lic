from PyQt4.QtGui import QUndoCommand
from PyQt4.QtCore import SIGNAL

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

    def __init__(self, displaceCommand):
        QUndoCommand.__init__(self, "Part displacement")
        self.part, self.oldDisp, self.newDisp = displaceCommand

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

    def __init__(self, beginCommand):
        QUndoCommand.__init__(self, "Begin Part displacement")
        self.part, self.direction, arrow = beginCommand
        self.part.arrow = arrow

    def undo(self):
        self.part.stopDisplacement()

    def redo(self):
        self.part.startDisplacement(self.direction)
    
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

    """
    AddRemoveStepCommand stores a step to add / delete and the page it was on
    """

    _id = getNewCommandID()

    def __init__(self, step, addStep = True):
        QUndoCommand.__init__(self, "%s Step" % ("add" if addStep else "delete"))
            
        self.step = step
        self.parent = step.parentItem()
        self.addStep = addStep

    def doAction(self, redo = True):
        if (redo and self.addStep) or (not redo and not self.addStep):
            self.parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            self.parent.insertStep(self.step)
            self.parent.scene().emit(SIGNAL("layoutChanged()"))
            self.step.setSelected(True)
        else:
            self.step.setSelected(False)
            self.parent.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
            self.parent.deleteStep(self.step)                
            self.parent.scene().emit(SIGNAL("layoutChanged()"))
        self.parent.initLayout()

    def undo(self):
        self.doAction(False)

    def redo(self):
        self.doAction(True)

class AddPageCommand(QUndoCommand):

    """
    AddPageCommand stores a page that was added
    """

    _id = getNewCommandID()

    def __init__(self, page):
        QUndoCommand.__init__(self, "add Page")
        self.page = page

    def undo(self):
        page = self.page
        page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        page.parent().deletePage(page)
        page.scene().emit(SIGNAL("layoutChanged()"))
        page.instructions.selectPage(page.number - 1)

    def redo(self):
        page = self.page
        page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        page.parent().addPage(page)
        page.scene().emit(SIGNAL("layoutChanged()"))
        page.instructions.selectPage(page.number)

class DeletePageCommand(QUndoCommand):

    """
    DeletePageCommand stores a page that was deleted
    """

    _id = getNewCommandID()

    def __init__(self, page):
        QUndoCommand.__init__(self, "delete Page")
        self.page = page

    def undo(self):
        page = self.page
        page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        page.parent().addPage(page)
        page.scene().emit(SIGNAL("layoutChanged()"))
        page.instructions.selectPage(page.number)

    def redo(self):
        page = self.page
        page.scene().clearSelection()
        page.scene().emit(SIGNAL("layoutAboutToBeChanged()"))
        page.parent().deletePage(page)
        page.scene().emit(SIGNAL("layoutChanged()"))
        page.instructions.selectPage(page.number - 1)

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
        self.callout.steps[-1].csi.resetPixmap()
        self.callout.initLayout()
        self.callout.scene().emit(SIGNAL("layoutChanged()"))
        
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
