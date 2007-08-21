import gtk
import gtk.glade
import gtk.gtkgl
import gobject

from Model import *
from GLHelpers import *

from OpenGL.GL import *
from OpenGL.GLU import *

#MODEL_NAME = "pyramid.dat"
MODEL_NAME = "Blaster.mpd"

gui_xml = gtk.glade.XML( "c:\\LDraw\\LIC\\LIC.glade")

# TODO: Fix OGL surface normals and BFC, so OGL rendering can look better.

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
		
		self.tree = gui_xml.get_widget("treeview")
		self.treemodel = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
		self.tree.connect("button_release_event", self.treeview_button_press)
		
		self.tree.set_reorderable(True)
		self.tree.set_model(self.treemodel)
		
		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("Instructions", renderer, text=0)
		self.tree.append_column(column)
		
		self.model = None  # The currently selected Lego model, whether a single part, submodel, step, or main model
		self.cairo_context = None  # Drawing context for all 2D drawing, done through cairo
	
	def on_exit(self, widget, event):
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
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		
		if not gldrawable.gl_begin(glcontext):
			return
		
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
		
		print "*** Loading Model ***"
		self.instructions = Instructions(MODEL_NAME)
		self.instructions.initDraw(self.width, self.height)
		self.model = self.instructions.getMainModel()
		
		gldrawable.gl_end()
		
		self.initializeTree()
		self.cairo_context = self.window.cairo_create()

	def on_configure_event(self, *args):
		""" Resize the window. """
		
		self.width = args[1].width
		self.height = args[1].height
		
		if ((self.width < 5) or (self.height < 5)):
			return  # ignore resize if window is basically invisible
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
		
		# Create a new cairo context based on the new window size
		self.cairo_context = self.window.cairo_create()
	
	def on_expose_event(self, *args):
		""" Draw the window. """
		
		gldrawable = self.get_gl_drawable()
		glcontext  = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		glClearColor(1.0,1.0,1.0,1.0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		glFrontFace(GL_CW)
		glColor3f(0,0,0)
		#self.displayGrid()
		
		glPushMatrix()
		
		# Draw any 3D stuff first (swap buffer call below would hose any 2D draw calls)
		if (self.model):
			self.model.drawModel(width = self.width, height = self.height)
		
		glPopMatrix()
		glFlush()
		
		gldrawable.swap_buffers()
		gldrawable.gl_end()
		
		# Draw any 2D page elements, like borders, labels, etc.
		if (self.model and isinstance(self.model, Step)):
			self.model.drawPageElements(self.cairo_context)
		
		return

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

def on_exit(widget, event):
	gtk.main_quit()

def go():
	area = DrawArea()
	
	main = gui_xml.get_widget("main_window")
	main.connect( "delete_event", on_exit )
	
	box = gui_xml.get_widget("box_opengl")
	box.pack_start(area)  

	#main.maximize()
	main.set_title("First example")
	main.show_all()
	
	gtk.main()

go()

#import hotshot
#prof = hotshot.Profile("hotshot_stats_no_int")
#prof.runcall(gogo)
#prof.close()
