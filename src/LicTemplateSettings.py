"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicTemplateSettings.py) is part of Lic.

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

__all__ = ["TemplateSettings"]

class TemplateSettings(object):
    def __init__(self):
        self.filename = ""
        self.Page = PageSettings()
        self.SubmodelPreview = TransformAndBorder()
        self.TitleSubmodelPreview = PenAndBrush()
        self.CSI = RotateAndScale()
        self.PLI = TransformAndBorder()
        self.PLI.rotation = [20.0, -45.0, 0.0]
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
    def __init__(self, pen = Qt.black):
        self.pen = QPen(pen)
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
        
class RotateAndScale(object):
    def __init__(self):
        self.rotation = [20.0, 45.0, 0.0]
        self.scale = 1.0

    def writeToStream(self, stream):
        stream.writeFloat(self.rotation[0])
        stream.writeFloat(self.rotation[1])
        stream.writeFloat(self.rotation[2])
        stream.writeFloat(self.scale)
        
    def readFromStream(self, stream):
        self.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        self.scale = stream.readFloat()
        
class TransformAndBorder(PenAndBrush, RotateAndScale):
    def __init__(self):
        PenAndBrush.__init__(self)
        RotateAndScale.__init__(self)
        
    def writeToStream(self, stream):
        PenAndBrush.writeToStream(self, stream)
        RotateAndScale.writeToStream(self, stream)
        
    def readFromStream(self, stream):
        PenAndBrush.readFromStream(self, stream)
        RotateAndScale.readFromStream(self, stream)

class PageSettings(PenAndBrush):
    def __init__(self):
        PenAndBrush.__init__(self, Qt.NoPen)
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
