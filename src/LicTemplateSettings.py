
from LicCommonImports import *

__all__ = ["TemplateSettings"]

class TemplateSettings(object):
    def __init__(self):
        self.Page = PageSettings()
        self.SubmodelPreview = PenAndBrush()
        self.TitleSubmodelPreview = PenAndBrush()
        self.PLI = PenAndBrush()
        self.PartListPLI = PenAndBrush()
        self.Callout = CalloutSettings()
        self.GraphicsRotateArrowItem = RotateIconSettings()

    def writeToStream(self, stream):
        self.Page.writeToStream(stream)
        self.SubmodelPreview.writeToStream(stream)
        self.TitleSubmodelPreview.writeToStream(stream)
        self.PLI.writeToStream(stream)
        self.PartListPLI.writeToStream(stream)
        self.Callout.writeToStream(stream)
        self.GraphicsRotateArrowItem.writeToStream(stream)

    def readFromStream(self, stream):
        self.Page.readFromStream(stream)
        self.SubmodelPreview.readFromStream(stream)
        self.TitleSubmodelPreview.readFromStream(stream)
        self.PLI.readFromStream(stream)
        self.PartListPLI.readFromStream(stream)
        self.Callout.readFromStream(stream)
        self.GraphicsRotateArrowItem.readFromStream(stream)

class PenAndBrush(object):
    def __init__(self):
        self.pen = QPen(Qt.NoPen)
        self.pen.cornerRadius = 0
        self.brush = QBrush(Qt.NoBrush)
        
    def writeToStream(self, stream):
        stream << self.pen
        stream.writeInt16(self.pen.cornerRadius)
        stream << self.brush
        
    def readFromStream(self, stream):
        self.pen = stream.readQPen()
        self.pen.cornerRadius = stream.readInt16()
        self.brush = stream.readQBrush()

class PageSettings(PenAndBrush):
    def __init__(self):
        PenAndBrush.__init__(self)
        self.backgroundColor = QColor(Qt.white)
    
    def writeToStream(self, stream):
        PenAndBrush.writeToStream(self, stream)
        stream << self.backgroundColor

    def readFromStream(self, stream):
        PenAndBrush.readFromStream(self, stream)
        self.backgroundColor = stream.readQColor()
        
class CalloutSettings(PenAndBrush):
    def __init__(self):
        PenAndBrush.__init__(self)
        self.arrow = PenAndBrush()
        
    def writeToStream(self, stream):
        PenAndBrush.writeToStream(self, stream)
        self.arrow.writeToStream(stream)
        
    def readFromStream(self, stream):
        PenAndBrush.readFromStream(self, stream)
        self.arrow.readFromStream(stream)
        
class RotateIconSettings(PenAndBrush):
    def __init__(self):
        PenAndBrush.__init__(self)
        self.arrowPen = QPen(Qt.blue, 0, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
        
    def writeToStream(self, stream):
        PenAndBrush.writeToStream(self, stream)
        stream << self.arrowPen
        
    def readFromStream(self, stream):
        PenAndBrush.readFromStream(self, stream)
        self.arrowPen = stream.readQPen()
