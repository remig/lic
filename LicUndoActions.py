from PyQt4.QtGui import QUndoCommand

QUndoCommand.id = lambda self: self._id

class MoveCommand(QUndoCommand):

    """
    MoveCommand stores a list of parts moved together:
    itemList[0] = (item, item.oldPos, item.newPos)
    """

    _id = 123
    
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

    _id = MoveCommand._id + 1

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

    _id = DisplacePartCommand._id + 1

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

    _id = ResizeCSIPLICommand._id + 1

    def __init__(self, stepSet):
        QUndoCommand.__init__(self, "Undo the last Step-to-Page Move")
        self.stepSet = stepSet

    def undo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(oldPage, relayout = True)

    def redo(self):
        for step, oldPage, newPage in self.stepSet:
            step.moveToPage(newPage, relayout = True)
