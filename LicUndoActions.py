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
        QUndoCommand.__init__(self, "Undo the last Page element movement")

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
    DisplacePartCommand stores a list of parts moved together:
    partList[0] = (part, oldDisplacement, newDisplacement)
    """

    _id = getNewCommandID()

    def __init__(self, partList):
        QUndoCommand.__init__(self, "Undo the last Part displacement")
        self.partList = list(partList)

    def undo(self):
        for part, oldPos, newPos in self.partList:
            part.displacement = list(oldPos)
            part._parentCSI.updatePixmap()

    def redo(self):
        for part, oldPos, newPos in self.partList:
            part.displacement = list(newPos)
            part._parentCSI.updatePixmap()

class ResizeCSIPLICommand(QUndoCommand):

    """
    ResizeCSIPLICommand stores a list of old / new image size pairs:
    sizes = ((oldCSISize, newCSISize), (oldPLISize, newPLISize))
    """

    _id = getNewCommandID()

    def __init__(self, instructions, sizes):
        QUndoCommand.__init__(self, "Undo the last CSI | PLI image resize")
        
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
        QUndoCommand.__init__(self, "Undo the last Step-to-Page Move")
        self.stepSet = stepSet

    def undo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(oldPage, relayout = True)

    def redo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage, relayout = True)

class DeleteStepCommand(QUndoCommand):

    """
    DeleteStepCommand stores a step that was deleted and the page it was on
    """

    _id = getNewCommandID()

    def __init__(self, step):
        QUndoCommand.__init__(self, "Undo the last Step deletion")
        self.step = step
        self.page = step.parentItem()

    def undo(self):
        # Need to emit layout change here because addStep doesn't - TODO: make this consistent with deleteStep
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.addStep(self.step, True)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))

    def redo(self):
        self.page.deleteStep(self.step, True)

class DeletePageCommand(QUndoCommand):

    """
    DeletePageCommand stores a page that was deleted
    """

    _id = getNewCommandID()

    def __init__(self, page):
        QUndoCommand.__init__(self, "Undo the last Page deletion")
        self.page = page

    def undo(self):
        # Need to emit layout change here because addStep doesn't - TODO: make this consistent with deleteStep
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.addStep(self.step, True)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))

    def redo(self):
        self.page.deleteStep(self.step, True)
