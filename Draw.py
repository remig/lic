from operator import itemgetter
import sys

import gtk
import gtk.glade
import gtk.gtkgl
import gobject

from Model import *
from GLHelpers import *

from OpenGL.GL import *
from OpenGL.GLU import *

#MODEL_NAME = "pyramid.dat"
#MODEL_NAME = "pyramid_bufs.dat"
#MODEL_NAME = "Blaster_shortened.mpd"
MODEL_NAME = "Blaster.mpd"
#MODEL_NAME = "2744.DAT"
#MODEL_NAME = "4286.DAT"

# TODO: Fix OGL surface normals and BFC, so OGL rendering can look better.

gui_xml = gtk.glade.XML( r"C:\LDraw\Lic\LIC.glade")

class DrawArea(gtk.DrawingArea, gtk.gtkgl.Widget):
	def __init__(self):
		gtk.DrawingArea.__init__(self)
		
		self.set_events(gtk.gdk.BUTTON_MOTION_MASK  | gtk.gdk.KEY_PRESS_MASK |
						gtk.gdk.KEY_RELEASE_MASK    | gtk.gdk.POINTER_MOTION_MASK |
						gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
						gtk.gdk.SCROLL_MASK)
		
		display_mode = (gtk.gdkgl.MODE_RGBA | gtk.gdkgl.MODE_DOUBLE)
		glconfig = gtk.gdkgl.Config(mode=display_mode)
		self.set_gl_capability(glconfig)
		
		self.set_events(gtk.gdk.BUTTON_MOTION_MASK  | gtk.gdk.KEY_PRESS_MASK |
						gtk.gdk.KEY_RELEASE_MASK    | gtk.gdk.POINTER_MOTION_MASK |
						gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
						gtk.gdk.SCROLL_MASK)
		
		self.connect( "realize", self.on_init )
		self.connect( "expose_event", self.on_draw_event )
		self.connect( "configure_event", self.on_resize_event )
		self.connect( "button_press_event", self.on_button_press )
		self.connect( "delete_event", self.on_exit )
		self.connect( "destroy", self.on_destroy )
		
		self.tree = gui_xml.get_widget("treeview")
		self.treemodel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)
		self.tree.connect("button_release_event", self.treeview_button_press)
		self.tree.set_reorderable(True)
		self.tree.set_model(self.treemodel)
		
		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Instructions", renderer, text=0)
		self.tree.append_column(column)
		
		self.instructions = None      # The complete Lego instructions book currently loaded
		self.currentSelection = None  # The currently selected item in the Instruction tree, whether a single part, submodel, step, or page
		self.currentPage = 	None      # The currently selected page
	
	def on_generate_images(self, data):
		print "Generating Images"
		self.instructions.generateImages()
	
	def on_translate_part(self, data):
		if self.currentSelection and isinstance(self.currentSelection , Step):
			self.currentSelection.parts[0].translate(0, 0, -10)
			self.on_draw_event()
	
	def on_exit(self, data):
		return False

	def on_save(self, data):
		self.instructions.getMainModel().partOGL.ldrawFile.saveFile()

	def on_destroy(self, widget, data=None):
		gtk.main_quit()

	def on_button_press(self, *args):
		pass

	def on_init(self, *args):
		""" Initialize the window. """
		
		specular = [1.0, 1.0, 1.0, 1.0]
		shininess = [50.0]
		lightPos = [1.0, 1.0, 1.0, 0.0]
		
		glShadeModel(GL_SMOOTH)
		
		glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, specular)
		glMaterialfv(GL_FRONT_AND_BACK, GL_SHININESS, shininess)
		glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
		
		glEnable(GL_LIGHTING)
		glEnable(GL_LIGHT0)
		
		glEnable(GL_DEPTH_TEST)
		#glCullFace(GL_BACK)
		#glFrontFace(GL_CCW)
		#glEnable(GL_CULL_FACE)
		glClearColor(1.0, 1.0, 1.0, 1.0)  # Draw clear white screen
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		print "*** Loading Model ***"
		cr = self.window.cairo_create()
		try:
			self.instructions = Instructions(MODEL_NAME)
		except IOError:
			print "Could not find file %s" % (MODEL_NAME)
			exit()
		
		self.instructions.resize(self.width, self.height)
		self.instructions.initDraw(cr)
		self.currentSelection = self.instructions.getMainModel()
		self.currentPage = self.currentSelection.partOGL.pages[0]
		
		self.initializeTree()

	def on_resize_event(self, *args):
		""" Resize the window. """
		
		self.width = args[1].width
		self.height = args[1].height
		
		if (self.width < 5) or (self.height < 5):
			return  # ignore resize if window is basically invisible
		
		if self.instructions:
			self.instructions.resize(self.width, self.height)
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
	
	def on_draw_event(self, *args):
		""" Draw the window. """
		
		# TODO: This all works, but slowly - have nasty flicker.  Need to double buffer or something
		# Create a fresh, blank cairo context attached to the window's display area
		cr = self.window.cairo_create()
		cr.identity_matrix()
		
		# Clear GL buffer
		glClearColor(1.0, 1.0, 1.0, 0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# Draw the currently selected model / part / step / page / whatnot to GL buffer
		if self.currentPage:
			self.currentPage.draw(cr, self.currentSelection)
	
	def treeview_button_press(self, obj, event):
		treemodel, iter = self.tree.get_selection().get_selected()
		if iter:  # If nothing is selected, iter is None, and get_value crashes
			self.currentSelection = treemodel.get_value(iter, 1)
			self.currentPage = treemodel.get_value(iter, 2)
			self.on_draw_event()

	def initializeTree(self):
		print "*** Loading TreeView ***"
		root = self.insert_after(self.treemodel, None, None, self.currentSelection.name, self.currentSelection, self.currentPage)
		self.addPagesToTree(self.currentSelection.partOGL.pages, root)

	def insert_after(self, model, parent, sibling, name, selection, page):
		iter = model.insert_after(parent, sibling)
		model.set_value(iter, 0, name)
		model.set_value(iter, 1, selection)
		model.set_value(iter, 2, page)
		return iter

	def insert_before(self, model, parent, sibling, name, selection, page):
		iter = model.insert_before(parent, sibling)
		model.set_value(iter, 0, name)
		model.set_value(iter, 1, selection)
		model.set_value(iter, 2, page)
		return iter
	
	def addPagesToTree(self, pages, root):
		loadedSubModels = []
		iterPage = iterStep = iterPart = iterPLI = iterCSI = None
		for page in pages:
			
			# Add each page to specified spot in tree
			iterPage = self.insert_after(self.treemodel, root, iterPage, "Page " + str(page.number), page, page)
			
			for step in page.steps:
				
				iterStep = self.insert_after(self.treemodel, iterPage, iterStep, "Step " + str(step.number), step, page)
				
				# Add all the parts in this PLI to the PLI tree node
				iterPLI  = self.insert_after(self.treemodel, iterStep, None, "PLI", step.pli, page)
				for item in step.pli.layout.values():
					self.insert_after(self.treemodel, iterPLI, None, item.partOGL.name, item, page)
				
				# Add all the parts in this step to the step's CSI tree node
				iterCSI  = self.insert_after(self.treemodel, iterStep, None, "CSI", step.csi, page)
				for part in step.parts:
					
					p = part.partOGL
					if (p.pages != []) and (p.name not in loadedSubModels):
						
						# This part has pages of its own, so add this part to specified root
						subRoot = self.insert_before(self.treemodel, root, iterPage, "SubModel " + p.name, p, page)
						loadedSubModels.append(p.name)
						
						# Add this part's steps into this part in the tree.
						if p.pages != []:
							self.addPagesToTree(p.pages, subRoot)
					
					# Add this part (not partOGL) to tree, placed inside the current CSI node
					iterPart = self.insert_after(self.treemodel, iterCSI, iterPart, p.name, part, page)
				
				iterPart = None
			iterStep = iterPLI = iterCSI = None
	
def go():
	
	area = DrawArea()
	main = gui_xml.get_widget("main_window")
	box = gui_xml.get_widget("box_opengl")
	box.pack_start(area)
	
	sigs = {"on_menuGenerate_activate": area.on_generate_images,
			"on_save_activate": area.on_save,
			"on_quit_activate": area.on_destroy }
	
	gui_xml.signal_autoconnect(sigs)

	# Some example status bar code
	statusbar = gui_xml.get_widget("statusbar")
	context_id = statusbar.get_context_id("statusbar")
	message_id = statusbar.push(context_id, "Hello")
	
	#main.maximize()
	main.set_title("Title Goes Here When Close To Done")
	main.show_all()
	
	gtk.main()

if __name__ == '__main__':
	go()

#import hotshot
#prof = hotshot.Profile("hotshot_stats_no_int")
#prof.runcall(gogo)
#prof.close()
