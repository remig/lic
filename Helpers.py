from PyQt4.QtCore import *

# lambda is bound dynamically to the last variable used, so we can't 
#  use it in a loop for creating menu actions.  Use this instead.
# usage: menu.addAction("menu text", makeFunc(self.moveToCallout, callout))
def makeFunc(func, arg):
    def f(): func(arg)
    return f

def getOppositeDirection(direction):
    if direction == Qt.Key_Up:
        return Qt.Key_Down
    if direction == Qt.Key_Down:
        return Qt.Key_Up
    if direction == Qt.Key_PageUp:
        return Qt.Key_PageDown
    if direction == Qt.Key_PageDown:
        return Qt.Key_PageUp
    if direction == Qt.Key_Left:
        return Qt.Key_Right
    if direction == Qt.Key_Right:
        return Qt.Key_Left
            
