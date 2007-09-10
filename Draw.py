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
MODEL_NAME = "Blaster.mpd"
#MODEL_NAME = "Blaster_shortened.mpd"

# TODO: Fix OGL surface normals and BFC, so OGL rendering can look better.

gui_xml = gtk.glade.XML( r"C:\LDraw\LIC\LIC.glade")

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
		
		self.connect( "expose_event", self.on_expose_event ) # expose = OnDraw
		self.connect( "realize", self.on_realize )  # one shot initialization
		self.connect( "configure_event", self.on_configure_event ) # given a size and width, resized
		self.connect( "button_press_event", self.on_button_press )
		self.connect( "delete_event", self.on_exit )
		self.connect( "destroy", self.on_destroy )
		
		self.tree = gui_xml.get_widget("treeview")
		self.treemodel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
		self.tree.connect("button_release_event", self.treeview_button_press)
		
		self.tree.set_reorderable(True)
		self.tree.set_model(self.treemodel)
		
		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Instructions", renderer, text=0)
		self.tree.append_column(column)
		
		self.instructions = None # The complete Lego instructions book currently loaded
		self.model = None  # The currently selected Lego model, whether a single part, submodel, step, or main model
	
	def on_generate_images(self, data):
		print "Generating Images"
	
	def on_translate_part(self, data):
		if (self.model and isinstance(self.model, Step)):
			self.model.parts[0].translate(0, 0, -10)
			self.on_expose_event()
	
	def on_exit(self, data):
		return False

	def on_save(self, data):
		self.instructions.getMainModel().partOGL.ldrawFile.saveFile()

	def on_destroy(self, widget, data=None):
		gtk.main_quit()

	def on_button_press(self, *args):
		x = args[1].x
		y = args[1].y
		
		if (x < (self.width/3)):
			glRotatef( -10.0, 0.0, 1.0, 0.0,)
		elif (x > (self.width*2/3)):
			glRotatef( 10.0, 0.0, 1.0, 0.0,)
		elif (y < (self.height/3)):
			glRotatef( -10.0, 1.0, 0.0, 0.0,)
		elif (y > (self.height*2/3)):
			glRotatef( 10.0, 1.0, 0.0, 0.0,)
		
		self.on_expose_event()

	def on_realize(self, *args):
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
		self.model = self.instructions.getMainModel()
		
		self.initializeTree()

	def on_configure_event(self, *args):
		""" Resize the window. """
		
		self.width = args[1].width
		self.height = args[1].height
		
		if ((self.width < 5) or (self.height < 5)):
			return  # ignore resize if window is basically invisible
		
		if (self.instructions):
			self.instructions.resize(self.width, self.height)
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
	
	def on_expose_event(self, *args):
		""" Draw the window. """
		
		# TODO: This all works, but slowly - have nasty flicker.  Need to double buffer or something
		
		# Create a fresh, blank cairo context attached to the window's display area
		cr = self.window.cairo_create()
		cr.identity_matrix()
		
		# Draw the overall page frame
		# This leaves the cairo context translated to the top left corner of the page, but *NOT* scaled.
		# Instead, it returns the width and height of the page.  Scaling here messes up GL drawing.
		scaleWidth, scaleHeight = self.instructions.drawPage(cr, self.width, self.height)
		
		# Clear GL buffer
		glClearColor(1.0, 1.0, 1.0, 0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# Fully reset the viewport - necessary if we've mangled it while calculating part dimensions
		adjustGLViewport(0, 0, scaleWidth, scaleHeight)
		glLoadIdentity()	
		rotateToDefaultView()
		
		# Draw the currently selected model / part / step / whatnot to GL buffer
		if (self.model):
			self.model.drawModel()
		
		# Copy GL buffer to a new cairo surface, then dump that surface to the current context
		pixels = glReadPixels (0, 0, scaleWidth, scaleHeight, GL_RGBA,  GL_UNSIGNED_BYTE)
		surface = cairo.ImageSurface.create_for_data(pixels, cairo.FORMAT_ARGB32, scaleWidth, scaleHeight, scaleWidth * 4)
		#crTmp = cairo.Context(surface)
		cr.set_source_surface(surface)
		cr.paint()
		
		# Draw any remaining 2D page elements, like borders, labels, etc
		if (self.model and isinstance(self.model, Step)):
			self.model.drawPageElements(cr)
	
	def initializeTree(self):
		print "*** Loading TreeView ***"
		root = self.insert_row(self.treemodel, None, None, self.model.name, self.model)
		self.addStepsToTree(self.model.partOGL.steps, root)

	def treeview_button_press(self, obj, event):
		treemodel, iter = self.tree.get_selection().get_selected()
		self.model = treemodel.get_value(iter, 1)
		self.on_expose_event()

	def insert_row(self, model, parent, sibling, firstcol, secondcol):
		iter = model.insert_after(parent, sibling)
		model.set_value(iter, 0, firstcol)
		model.set_value(iter, 1, secondcol)
		return iter

	def insert_before(self, model, parent, sibling, firstcol, secondcol):
		iter = model.insert_before(parent, sibling)
		model.set_value(iter, 0, firstcol)
		model.set_value(iter, 1, secondcol)
		return iter
	
	def addStepsToTree(self, steps, root):
		loadedSubModels = []
		iterStep = iterPart = None
		for step in steps:
			
			# Add each step to specified spot in tree
			iterStep = self.insert_row(self.treemodel, root, iterStep, "Step " + str(step.number), step)
			
			for part in step.parts:
				p = part.partOGL
				if ((p.steps != []) and (p.name not in loadedSubModels)):
					# This part has steps of its own, so add this part to specified root.
					subRoot = self.insert_before(self.treemodel, root, iterStep, "SubModel " + p.name, p)
					loadedSubModels.append(p.name)
					# Add this part's steps into this part in the tree.
					if (p.steps != []):
						self.addStepsToTree(p.steps, subRoot)
				
				# Add this part to tree, placed inside the current step.
				iterPart = self.insert_row(self.treemodel, iterStep, iterPart, p.name, p)
			
			iterPart = None
	
	def displayGrid(self):
		glBegin( GL_LINES )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 1000, 0, 0 )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 0, 1000, 0 )
		glVertex3i( 0, 0, 0 )
		glVertex3i( 0, 0, 1000 )
		glEnd()

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
