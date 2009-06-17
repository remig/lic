from Model import *

class TemplateRectItem(object):
    """ Encapsulates functionality common to all template GraphicItems, like formatting border & fill""" 

    def postLoadInit(self, dataText):
        self.data = lambda index: dataText
        self.setFlags(NoMoveFlags)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Format Border", self.formatBorder)
        menu.exec_(event.screenPos())

    def formatBorder(self):
        
        self.setSelected(False)  # Deselect to better see new border changes
        parentWidget = self.scene().views()[0]
        stack = self.scene().undoStack
        action = lambda newPen: stack.push(SetPenCommand(self.getPage(), self, self.pen(), newPen))
        dialog = LicDialogs.PenDlg(parentWidget, self.pen())
        parentWidget.connect(dialog, SIGNAL("changed"), action)
        
        stack.beginMacro("change Border")
        dialog.exec_()
        stack.endMacro()
    
    def changePen(self, newPen):
        self.setPen(newPen)
        self.update()

class TemplatePage(Page):

    def __init__(self, subModel, instructions):
        Page.__init__(self, subModel, instructions, 0, 0)
        self.__filename = None
        self.dataText = "Template Page"

    def __getFilename(self):
        return self.__filename
        
    def __setFilename(self, filename):
        self.__filename = filename
        self.dataText = "Template - " + os.path.basename(self.filename)
        
    filename = property(fget = __getFilename, fset = __setFilename)

    def postLoadInit(self, filename):
        # TemplatePages are rarely instantiated directly - instead, they're regular Page
        # instances promoted to TemplatePages by changing their __class__.  Doing that does
        # *not* call TemplatePage.__init__, so, can explicitly call postLoadInit instead. 

        self.filename = filename
        self.prevPage = lambda: None
        self.nextPage = lambda: None
        self.data = lambda index: self.dataText
        
        step = self.steps[0]
        
        # Promote page members to appropriate Template subclasses, and initialize if necessary
        step.__class__ = TemplateStep
        step.postLoadInit()
        step.callouts[0].__class__ = TemplateCallout
        step.pli.__class__ = TemplatePLI
                
        self.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Page'))
        step.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Step'))
        self.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, self.numberItem)
        step.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, step.numberItem)

        if step.hasPLI():
            for item in step.pli.pliItems:
                item.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'PLI Item'))
                item.numberItem.contextMenuEvent = lambda event, i = item: self.fontMenuEvent(event, i.numberItem)
        
        # Set all page elements so they can't move
        for item in self.getAllChildItems():
            item.setFlags(NoMoveFlags)

    def createBlankTemplate(self):
        step = Step(self, 0)
        step.data = lambda index: "Template Step"
        self.addStep(step)
        
        for part in self.subModel.parts[:5]:
            step.addPart(part.duplicate())
        
        step.csi.createOGLDisplayList()
        self.initCSIDimension()
        step.csi.createPixmap()
        
        self.initLayout()
        self.postLoadInit()

    def initCSIDimension(self):
        global GlobalGLContext
        GlobalGLContext.makeCurrent()

        csi = self.steps[0].csi
        sizes = [512, 1024, 2048]

        for size in sizes:

            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render CSI and calculate its size
            if csi.initSize(size, pBuffer):
                break

        GlobalGLContext.makeCurrent()
        
    def applyFullTemplate(self):
        
        originalPage = self.instructions.mainModel.pages[0]
        stack = self.scene().undoStack
        stack.beginMacro("Load Template")
        stack.push(SetPageBackgroundColorCommand(self, originalPage.color, self.color))
        stack.push(SetPageBackgroundBrushCommand(self, originalPage.brush, self.brush))
        
        stack.push(SetItemFontsCommand(self, originalPage.numberItem.font(), self.numberItem.font(), 'Page'))
        stack.push(SetItemFontsCommand(self, originalPage.steps[0].numberItem.font(), self.steps[0].numberItem.font(), 'Step'))
        stack.push(SetItemFontsCommand(self, originalPage.steps[0].pli.pliItems[0].numberItem.font(), self.steps[0].pli.pliItems[0].numberItem.font(), 'PLI Item'))
        stack.endMacro()

    def getStep(self, number):
        return self.steps[0] if number == 0 else None

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Background Color", self.setBackgroundColor)
        arrowMenu = menu.addMenu("Background Fill Effect")
        arrowMenu.addAction("Gradient", self.setBackgroundGradient)
        arrowMenu.addAction("Image", self.setBackgroundImage)
        arrowMenu.addAction("None", self.setBackgroundNone)
        #menu.addSeparator()
        menu.exec_(event.screenPos())
        
    def setBackgroundColor(self):
        color = QColorDialog.getColor(self.color, self.scene().views()[0])
        if color.isValid(): 
            self.scene().undoStack.push(SetPageBackgroundColorCommand(self, self.color, color))
    
    def setBackgroundNone(self):
        self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush, None))
        
    def setBackgroundGradient(self):
        g = self.brush.gradient() if self.brush else None
        dialog = GradientDialog.GradientDialog(self.scene().views()[0], Page.PageSize, g)
        if dialog.exec_():
            self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush, QBrush(dialog.getGradient())))
    
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
        dialog = LicDialogs.BackgroundImagePropertiesDlg(parentWidget, image, self.color, self.brush, Page.PageSize)
        action = lambda image: stack.push(SetPageBackgroundBrushCommand(self, self.brush, QBrush(image)))
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

class TemplateCallout(TemplateRectItem, Callout):
    pass

class TemplatePLI(TemplateRectItem, PLI):
    pass

class TemplateStep(Step):
    
    def postLoadInit(self):
        self.data = lambda index: "Template Step"
        self.setFlags(NoMoveFlags)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Disable PLIs" if self.hasPLI() else "Enable PLIs", self.togglePLIs)
        #menu.addSeparator()
        menu.addAction("Format Background", self.formatBackground)
        arrowMenu = menu.addMenu("Format Background")
        #arrowMenu.addAction("Color", self.setBackgroundColor)
        #arrowMenu.addAction("Gradient", self.setBackgroundColor)
        #rrowMenu.addAction("Image", self.setBackgroundColor)
        menu.exec_(event.screenPos())

    def togglePLIs(self):
        self.scene().undoStack.push(TogglePLIs(self, not self.hasPLI()))
    
    def formatBackground(self):
        pass
    