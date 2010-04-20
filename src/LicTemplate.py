"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicTemplate.py) is part of Lic.

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

from LicModel import *
from LicUndoActions import *
from LicGradientDialog import GradientDialog
from LicQtWrapper import *

import LicDialogs
import LicGLHelpers

class TemplateLineItem(object):

    def formatBorder(self, fillColor = None):
        
        self.setSelected(False)  # Deselect to better see new border changes
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.PenDlg(parentWidget, self.pen(), hasattr(self, 'cornerRadius'), fillColor)

        parentWidget.connect(dialog, SIGNAL("changePen"), self.changePen)
        parentWidget.connect(dialog, SIGNAL("acceptPen"), self.acceptPen)

        dialog.exec_()

    def changePen(self, newPen, newBrush):
        self.setPen(newPen)
        if newBrush:
            self.setBrush(newBrush)
        self.update()

    def acceptPen(self, oldPen, oldBrush):
        stack = self.scene().undoStack
        if oldBrush:
            stack.beginMacro("format Callout Arrow")
        stack.push(SetPenCommand(self, oldPen, self.pen()))
        if oldBrush:
            stack.push(SetBrushCommand(self, oldBrush, self.brush()))
            stack.endMacro()

class TemplateRectItem(TemplateLineItem):
    """ Encapsulates functionality common to all template GraphicItems, like formatting border & fill""" 

    def postLoadInit(self, dataText):
        self.data = lambda index: dataText
        self.setFlags(NoMoveFlags)
    
    def getContextMenu(self, prependActions = []):
        menu = QMenu(self.scene().views()[0])
        for text, action in prependActions:
            menu.addAction(text, action)
        if prependActions:
            menu.addSeparator()
        menu.addAction("Format Border", self.formatBorder)
        menu.addAction("Background Color", self.setBackgroundColor)
        menu.addAction("Background Gradient", self.setBackgroundGradient)
        menu.addAction("Background None", self.setBackgroundNone)
        return menu
        
    def contextMenuEvent(self, event):
        menu = self.getContextMenu()
        menu.exec_(event.screenPos())

    def setBackgroundColor(self):
        color, result = QColorDialog.getRgba(self.brush().color().rgba(), self.scene().views()[0])
        color = QColor.fromRgba(color)
        if result and color.isValid():
            self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(color), "fill Color"))
    
    def setBackgroundNone(self):
        self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(Qt.transparent), "remove fill"))
        
    def setBackgroundGradient(self):
        g = self.brush().gradient()
        dialog = GradientDialog(self.scene().views()[0], self.rect().size().toSize(), g)
        if dialog.exec_():
            self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(dialog.getGradient()), "fill Gradient"))

class TemplateRotateScaleSignalItem(QObject):

    def rotateDefaultSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.RotationDialog(parentWidget, self.target.defaultRotation)
        parentWidget.connect(dialog, SIGNAL("changeRotation"), self.changeDefaultRotation)
        parentWidget.connect(dialog, SIGNAL("acceptRotation"), self.acceptDefaultRotation)
        dialog.exec_()

    def changeDefaultRotation(self, rotation):
        self.target.defaultRotation = list(rotation)
        self.resetPixmap()

    def acceptDefaultRotation(self, oldRotation):
        action = RotateDefaultItemCommand(self.target, self.name, self, oldRotation, self.target.defaultRotation)
        self.scene().undoStack.push(action)

    def scaleDefaultSignal(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.ScaleDlg(parentWidget, self.target.defaultScale)
        parentWidget.connect(dialog, SIGNAL("changeScale"), self.changeDefaultScale)
        parentWidget.connect(dialog, SIGNAL("acceptScale"), self.acceptDefaultScale)
        dialog.exec_()
    
    def changeDefaultScale(self, newScale):
        self.target.defaultScale = newScale
        self.resetPixmap()
    
    def acceptDefaultScale(self, originalScale):
        action = ScaleDefaultItemCommand(self.target, self.name, self, originalScale, self.target.defaultScale)
        self.scene().undoStack.push(action)

class TemplatePage(TemplateRectItem, Page):

    def __init__(self, submodel, instructions):
        Page.__init__(self, submodel, instructions, 0, 0)
        self.__filename = None
        self.dataText = "Template Page"
        self.submodelPart = None

    def __getFilename(self):
        return self.__filename
        
    def __setFilename(self, filename):
        self.__filename = filename
        self.dataText = "Template - " + os.path.basename(self.filename)
        
    filename = property(__getFilename, __setFilename)

    def postLoadInit(self, filename):
        # TemplatePages are rarely instantiated directly - instead, they're regular Page
        # instances promoted to TemplatePages by changing their __class__.  Doing that does
        # *not* call TemplatePage.__init__, so, can explicitly call postLoadInit instead. 

        self.filename = filename
        self.prevPage = lambda: None
        self.nextPage = lambda: None
        self.data = lambda index: self.dataText

        # Promote page members to appropriate Template subclasses, and initialize if necessary
        step = self.steps[0]
        step.__class__ = TemplateStep
        step.postLoadInit()
        step.csi.__class__ = TemplateCSI
        step.csi.target, step.csi.name = CSI, "CSI"

        if step.pli:
            step.pli.__class__ = TemplatePLI
            step.pli.target, step.pli.name = PLI, "PLI"
        if self.submodelItem:
            self.submodelItem.__class__ = TemplateSubmodelPreview
            self.submodelItem.target, self.submodelItem.name = SubmodelPreview, "Submodel"
        if step.callouts:
            step.callouts[0].__class__ = TemplateCallout
            step.callouts[0].arrow.__class__ = TemplateCalloutArrow
            step.callouts[0].steps[0].csi.__class__ = TemplateCSI
            step.callouts[0].steps[0].csi.target, step.callouts[0].steps[0].csi.name = CSI, "CSI"
        if step.rotateIcon:
            step.rotateIcon.__class__ = TemplateRotateIcon

        self.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Page'))
        step.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Step'))
        self.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, self.numberItem)
        step.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, step.numberItem)

        if step.hasPLI():
            for item in step.pli.pliItems:
                item.__class__ = TemplatePLIItem
                item.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'PLIItem'))
                item.numberItem.contextMenuEvent = lambda event, i = item: self.fontMenuEvent(event, i.numberItem)
                if item.lengthIndicator:
                    item.lengthIndicator.__class__ = TemplateCircleLabel

        # Set all page elements so they can't move
        for item in self.getAllChildItems():
            item.setFlags(NoMoveFlags)

        if step.callouts:
            step.callouts[0].arrow.tipRect.setFlags(NoFlags)
            step.callouts[0].arrow.baseRect.setFlags(NoFlags)

    def createBlankTemplate(self, glContext):
        step = Step(self, 0)
        step.data = lambda index: "Template Step"
        self.addStep(step)
        
        self.submodelPart = Submodel()
        for part in self.submodel.parts[:5]:
            newPart = part.duplicate()
            step.addPart(newPart)
            self.submodelPart.parts.append(newPart)

        self.submodelPart.createOGLDisplayList()
        self.initOGLDimension(self.submodelPart, glContext)
        
        step.csi.createOGLDisplayList()
        self.initOGLDimension(step.csi, glContext)

        step.addBlankCalloutSignal(False)
        if len(self.submodel.parts) >= 2:
            step.callouts[0].addPart(self.submodel.parts[1].duplicate())
        elif len(self.submodel.parts) >= 1:
            step.callouts[0].addPart(self.submodel.parts[0].duplicate())
        if len(self.submodel.parts) >= 3:
            step.callouts[0].addPart(self.submodel.parts[2].duplicate())

        step.callouts[0].steps[0].csi.resetPixmap()
        
        self.addSubmodelImage()
        self.submodelItem.setAbstractPart(self.submodelPart)

        step.addRotateIcon()

        self.initLayout()
        self.postLoadInit("test_template.lit")

    def initOGLDimension(self, part, glContext):

        glContext.makeCurrent()
        for size in [512, 1024, 2048]:
            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, LicGLHelpers.getGLFormat(), glContext)
            pBuffer.makeCurrent()

            # Render CSI and calculate its size
            if part.initSize(size, pBuffer):
                break
        glContext.makeCurrent()
        
    def applyFullTemplate(self, useUndo = True):
        
        originalPage = self.instructions.mainModel.pages[0]
        
        if useUndo:
            stack = self.scene().undoStack
            stack.beginMacro("Apply Template")
        else:
            class NoOp():
                def push(self, x):
                    x.redo()
            
            stack = NoOp()

        stack.push(SetPageBackgroundColorCommand(self, originalPage.color, self.color))
        stack.push(SetPageBackgroundBrushCommand(self, originalPage.brush(), self.brush()))

        stack.push(SetItemFontsCommand(self, originalPage.numberItem.font(), self.numberItem.font(), 'Page'))
        stack.push(SetItemFontsCommand(self, originalPage.steps[0].numberItem.font(), self.steps[0].numberItem.font(), 'Step'))
        pliItem = self.instructions.mainModel.getFirstPLIItem()
        if pliItem:
            stack.push(SetItemFontsCommand(self, pliItem.numberItem.font(), self.steps[0].pli.pliItems[0].numberItem.font(), 'PLIItem'))

        step = self.steps[0]
        if step.pli:
            stack.push(SetPenCommand(step.pli, PLI.defaultPen))
            stack.push(SetBrushCommand(step.pli, PLI.defaultBrush))

            for item in step.pli.pliItems:
                if item.lengthIndicator:
                    icon = item.lengthIndicator
                    stack.push(SetPenCommand(icon, GraphicsCircleLabelItem.defaultPen))
                    stack.push(SetBrushCommand(icon, GraphicsCircleLabelItem.defaultBrush))
                    stack.push(SetItemFontsCommand(icon.getPage(), GraphicsCircleLabelItem.defaultFont, icon.font(), 'GraphicsCircleLabelItem'))
                    stack.push(SetDefaultDiameterCommand(icon, GraphicsCircleLabelItem.defaultDiameter, icon.diameter(), False))
                    break

        if self.submodelItem:
            stack.push(SetPenCommand(self.submodelItem, SubmodelPreview.defaultPen))
            stack.push(SetBrushCommand(self.submodelItem, SubmodelPreview.defaultBrush))

        if step.callouts:
            callout = step.callouts[0]
            stack.push(SetPenCommand(callout, Callout.defaultPen))
            stack.push(SetBrushCommand(callout, Callout.defaultBrush))

            arrow = callout.arrow
            stack.push(SetPenCommand(arrow, CalloutArrow.defaultPen))
            stack.push(SetBrushCommand(arrow, CalloutArrow.defaultBrush))

        if step.rotateIcon:
            icon = step.rotateIcon
            stack.push(SetPenCommand(icon, GraphicsRotateArrowItem.defaultPen))
            stack.push(SetBrushCommand(icon, GraphicsRotateArrowItem.defaultBrush))
            stack.push(SetPenCommand(icon, GraphicsRotateArrowItem.defaultArrowPen, icon.arrowPen, "changeArrowPen"))

        if useUndo:
            stack.endMacro()

    def getStep(self, number):
        return self.steps[0] if number == 0 else None

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Format Border", self.formatBorder)
        menu.addAction("Background Color", self.setBackgroundColor)
        arrowMenu = menu.addMenu("Background Fill Effect")
        arrowMenu.addAction("Gradient", self.setBackgroundGradient)
        arrowMenu.addAction("Image", self.setBackgroundImage)
        arrowMenu.addAction("None", self.setBackgroundNone)
        if not self.instructions.mainModel.hasTitlePage():
            menu.addSeparator()
            menu.addAction("Add Title Page", self.instructions.mainModel.showTitlePage)

        menu.addSeparator()
        menu.addAction("Change 3D model Lighting", self.changeLighting)
        menu.exec_(event.screenPos())
        
    def setColor(self, color):
        Page.defaultFillColor = color
        self.color = color
        
    def setBrush(self, brush):
        Page.setBrush(self, brush)
        Page.defaultBrush = brush
        
    def setPen(self, newPen):
        Page.setPen(self, newPen)
        Page.defaultPen = newPen

    def setBackgroundColor(self):
        color = QColorDialog.getColor(self.color, self.scene().views()[0])
        if color.isValid(): 
            self.scene().undoStack.push(SetPageBackgroundColorCommand(self, self.color, color))
    
    def setBackgroundNone(self):
        self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush(), QBrush(Qt.NoBrush)))
        
    def setBackgroundGradient(self):
        g = self.brush().gradient()
        dialog = GradientDialog(self.scene().views()[0], Page.PageSize, g)
        if dialog.exec_():
            self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush(), QBrush(dialog.getGradient())))
    
    def setBackgroundImage(self):
        
        parentWidget = self.scene().views()[0]
        filename = QFileDialog.getOpenFileName(parentWidget, "Open Background Image", QDir.currentPath())
        if filename.isEmpty():
            return
        
        image = QImage(filename)
        if image.isNull():
            QMessageBox.information(self, "Lic", "Cannot load " + filename)
            return

        stack = self.scene().undoStack
        dialog = LicDialogs.BackgroundImagePropertiesDlg(parentWidget, image, self.color, self.brush(), Page.PageSize)
        action = lambda image: stack.push(SetPageBackgroundBrushCommand(self, self.brush(), QBrush(image) if image else None))
        parentWidget.connect(dialog, SIGNAL("changed"), action)

        stack.beginMacro("change Page background")
        dialog.exec_()
        stack.endMacro()

    def fontMenuEvent(self, event, item):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Set Font", lambda: self.setItemFont(item))
        menu.exec_(event.screenPos())
        
    def setItemFont(self, item):
        oldFont = item.font()
        newFont, ok = QFontDialog.getFont(oldFont)
        if ok:
            item.setAllFonts(oldFont, newFont)
            
    def resetCallout(self):
        for callout in self.steps[0].callouts:
            for step in callout.steps:
                step.csi.resetPixmap()

    def scaleAllItems(self, newScale):
        if not self.steps[0].pli:
            print "NO TEMPLATE PLI TO SCALE"
            return
        
        if not self.submodelItem:
            print "NO SUBMODEL ITEM TO SCALE"
            return
        
        oldScale = CSI.defaultScale
        self.steps[0].csi.changeDefaultScale(newScale)
        self.steps[0].csi.acceptDefaultScale(oldScale)

        oldScale = PLI.defaultScale
        self.steps[0].pli.changeDefaultScale(newScale)
        self.steps[0].pli.acceptDefaultScale(oldScale)

        oldScale = SubmodelPreview.defaultScale
        self.submodelItem.changeDefaultScale(newScale)
        self.submodelItem.acceptDefaultScale(oldScale)

    def changeLighting(self):
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.LightingDialog(parentWidget, *LicGLHelpers.getLightParameters())
        parentWidget.connect(dialog, SIGNAL("changeValues"), self.changeLightValues)
        parentWidget.connect(dialog, SIGNAL("acceptValues"), self.acceptLightValues)
        dialog.exec_()

    def changeLightValues(self, newValues):
        LicGLHelpers.setLightParameters(*newValues)
        self.update()

    def acceptLightValues(self, oldValues):
        action = ChangeLightingCommand(self.scene(), oldValues)
        self.scene().undoStack.push(action)

class TemplateCalloutArrow(TemplateLineItem, CalloutArrow):

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Format Border", lambda: self.formatBorder(self.brush().color()))
        menu.exec_(event.screenPos())

    def setPen(self, newPen):
        CalloutArrow.setPen(self, newPen)
        CalloutArrow.defaultPen = newPen

    def setBrush(self, newBrush):
        CalloutArrow.setBrush(self, newBrush)
        CalloutArrow.defaultBrush = newBrush
        
class TemplateCallout(TemplateRectItem, Callout):
    
    def setPen(self, newPen):
        Callout.setPen(self, newPen)
        Callout.defaultPen = newPen

    def setBrush(self, newBrush):
        Callout.setBrush(self, newBrush)
        Callout.defaultBrush = newBrush

    def setBorderFit(self, fit):
        Callout.defaultBorderFit = fit
        self.borderFit = fit

    def contextMenuEvent(self, event):
        stack = self.scene().undoStack
        menu = TemplateRectItem.getContextMenu(self)
        menu.addSeparator()
        arrowMenu = menu.addMenu("Border Shape")
        arrowMenu.addAction("Rectangle", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.RectangleBorder)))
        arrowMenu.addAction("Step Fit", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.StepBorder)))
        arrowMenu.addAction("Tight Fit", lambda: stack.push(CalloutBorderFitCommand(self, self.borderFit, Callout.TightBorder)))
        menu.exec_(event.screenPos())

class TemplateStep(Step):
    
    def postLoadInit(self):
        self.data = lambda index: "Template Step"
        self.setFlags(NoMoveFlags)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Disable PLIs" if self.hasPLI() else "Enable PLIs", self.togglePLIs)
        #menu.addSeparator()
        #menu.addAction("Format Background", self.formatBackground)  # TODO: implement step fills
        #arrowMenu = menu.addMenu("Format Background")
        #arrowMenu.addAction("Color", self.setBackgroundColor)
        #arrowMenu.addAction("Gradient", self.setBackgroundColor)
        #rrowMenu.addAction("Image", self.setBackgroundColor)
        menu.exec_(event.screenPos())

    def togglePLIs(self):
        self.scene().undoStack.push(TogglePLIs(self.getPage(), not self.hasPLI()))

    def formatBackground(self):
        pass

class TemplatePLIItem(PLIItem):
    
    def contextMenuEvent(self, event):
        event.ignore()

class TemplatePLI(TemplateRectItem, PLI, TemplateRotateScaleSignalItem):
    
    def contextMenuEvent(self, event):
        actions = [("Change Default PLI Rotation", self.rotateDefaultSignal),
                   ("Change Default PLI Scale", self.scaleDefaultSignal)]
        menu = TemplateRectItem.getContextMenu(self, actions)
        menu.exec_(event.screenPos())
    
    def setPen(self, newPen):
        PLI.setPen(self, newPen)
        PLI.defaultPen = newPen

    def setBrush(self, newBrush):
        PLI.setBrush(self, newBrush)
        PLI.defaultBrush = newBrush

class TemplateSubmodelPreview(TemplateRectItem, SubmodelPreview, TemplateRotateScaleSignalItem):

    def contextMenuEvent(self, event):
        actions = [("Change Default Submodel Rotation", self.rotateDefaultSignal),
                   ("Change Default Submodel Scale", self.scaleDefaultSignal)]
        menu = TemplateRectItem.getContextMenu(self, actions)
        menu.exec_(event.screenPos())
        
    def setPen(self, newPen):
        SubmodelPreview.setPen(self, newPen)
        SubmodelPreview.defaultPen = newPen

    def setBrush(self, newBrush):
        SubmodelPreview.setBrush(self, newBrush)
        SubmodelPreview.defaultBrush = newBrush

class TemplateCSI(CSI, TemplateRotateScaleSignalItem):
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Change Default CSI Rotation", self.rotateDefaultSignal)
        menu.addAction("Change Default CSI Scale", self.scaleDefaultSignal)

        text = "%sHighlight new Parts" % ("Don't " if CSI.highlightNewParts else "")
        menu.addAction(text, self.highlightNewPartsSignal)

        menu.exec_(event.screenPos())

    def highlightNewPartsSignal(self):
        self.scene().undoStack.push(ToggleCSIPartHighlightCommand(not CSI.highlightNewParts, CSI, self))

class TemplateCircleLabel(GraphicsCircleLabelItem, TemplateRectItem):
    
    def contextMenuEvent(self, event):
        actions = [("Set Font", self.setItemFont), ("Set Size", self.setItemDiameter)]
        menu = TemplateRectItem.getContextMenu(self, actions)
        menu.exec_(event.screenPos())
        
    def setPen(self, newPen):
        GraphicsCircleLabelItem.setPen(self, newPen)
        GraphicsCircleLabelItem.defaultPen = newPen

    def setBrush(self, newBrush):
        GraphicsCircleLabelItem.setBrush(self, newBrush)
        GraphicsCircleLabelItem.defaultBrush = newBrush

    def setDiameter(self, diameter):
        GraphicsCircleLabelItem.setDiameter(self, diameter)
        GraphicsCircleLabelItem.defaultDiameter = diameter

    def setItemFont(self):
        oldFont = self.font()
        newFont, ok = QFontDialog.getFont(oldFont)
        if ok:
            self.scene().undoStack.push(SetItemFontsCommand(self.getPage(), oldFont, newFont, "GraphicsCircleLabelItem"))

    def setItemDiameter(self):
        oldDiameter = self.rect().width()
        newDiameter, ok = QInputDialog.getInteger(self.scene().views()[0], "Get Circle Size", "New Circle Size:", oldDiameter, 0, 50)
        if ok:
            self.scene().undoStack.push(SetDefaultDiameterCommand(self, oldDiameter, newDiameter, True))

class TemplateRotateIcon(TemplateRectItem, GraphicsRotateArrowItem):
    
    def formatArrowPen(self):
        
        self.setSelected(False)  # Deselect to better see new border changes
        parentWidget = self.scene().views()[0]
        dialog = LicDialogs.PenDlg(parentWidget, self.arrowPen, False, None)

        parentWidget.connect(dialog, SIGNAL("changePen"), self.changeArrowPen)
        parentWidget.connect(dialog, SIGNAL("acceptPen"), self.acceptArrowPen)

        dialog.exec_()

    def setPen(self, newPen):
        GraphicsRotateArrowItem.setPen(self, newPen)
        GraphicsRotateArrowItem.defaultPen = newPen

    def setBrush(self, newBrush):
        GraphicsRotateArrowItem.setBrush(self, newBrush)
        GraphicsRotateArrowItem.defaultBrush = newBrush

    def changeArrowPen(self, newPen, newBrush = None):
        GraphicsRotateArrowItem.defaultArrowPen = newPen
        GraphicsRotateArrowItem.changeArrowPen(self, newPen)

    def acceptArrowPen(self, oldPen, oldBrush):
        self.scene().undoStack.push(SetPenCommand(self, oldPen, self.arrowPen, "changeArrowPen"))

    def contextMenuEvent(self, event):
        menu = TemplateRectItem.getContextMenu(self)
        menu.addAction("Format Arrow Pen", self.formatArrowPen)
        menu.exec_(event.screenPos())
