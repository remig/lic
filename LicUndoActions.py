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
        self.part.parentCSI.maximizePixmap()
        self.part.parentCSI.resetPixmap()

    def redo(self):
        self.part.displacement = list(self.newDisp)
        self.part.parentCSI.maximizePixmap()
        self.part.parentCSI.resetPixmap()

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
            step.moveToPage(oldPage, relayout = True)

    def redo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage, relayout = True)

class InsertStepCommand(QUndoCommand):

    """
    AddStepCommand stores a step that was added and the page it was added to
    """

    _id = getNewCommandID()

    def __init__(self, step):
        QUndoCommand.__init__(self, "add Step")
        self.step = step
        self.page = step.parentItem()

    def undo(self):
        self.step.setSelected(False)
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.deleteStep(self.step)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))

    def redo(self):
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.insertStep(self.step)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))
        self.step.setSelected(True)

class DeleteStepCommand(QUndoCommand):

    """
    DeleteStepCommand stores a step that was deleted and the page it was on
    """

    _id = getNewCommandID()

    def __init__(self, step):
        QUndoCommand.__init__(self, "delete Step")
        self.step = step
        self.page = step.parentItem()

    def undo(self):
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.insertStep(self.step)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))
        self.step.setSelected(True)

    def redo(self):
        self.step.setSelected(False)
        self.page.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        self.page.deleteStep(self.step)
        self.page.instructions.emit(SIGNAL("layoutChanged()"))

class AddPageCommand(QUndoCommand):

    """
    AddPageCommand stores a page that was added
    """

    _id = getNewCommandID()

    def __init__(self, page):
        QUndoCommand.__init__(self, "add Page")
        self.page = page

    def undo(self):
        p = self.page
        p.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        p.parent().deletePage(p)
        p.instructions.emit(SIGNAL("layoutChanged()"))
        p.instructions.selectPage(p.number - 1)

    def redo(self):
        p = self.page
        p.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        p.parent().addPage(p)
        p.instructions.emit(SIGNAL("layoutChanged()"))
        p.instructions.selectPage(p.number)

class DeletePageCommand(QUndoCommand):

    """
    DeletePageCommand stores a page that was deleted
    """

    _id = getNewCommandID()

    def __init__(self, page):
        QUndoCommand.__init__(self, "delete Page")
        self.page = page

    def undo(self):
        p = self.page
        p.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        p.parent().addPage(p)
        p.instructions.emit(SIGNAL("layoutChanged()"))
        p.instructions.selectPage(p.number)

    def redo(self):
        p = self.page
        p.scene().clearSelection()
        p.instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
        p.parent().deletePage(p)
        p.instructions.emit(SIGNAL("layoutChanged()"))
        p.instructions.selectPage(p.number - 1)

class MovePartToStepCommand(QUndoCommand):

    """
    MovePartToStepCommand stores a part, step it was from and step it was moved to
    (part, oldStep, newStep)
    """

    _id = getNewCommandID()

    def __init__(self, partSet):
        QUndoCommand.__init__(self, "move Part to Step")
        self.part, self.oldStep, self.newStep = partSet

    def undo(self):
        self.part.moveToStep(self.oldStep)

    def redo(self):
        self.part.moveToStep(self.newStep)

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
