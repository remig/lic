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
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		print "*** Loading Model ***"
		self.instructions = Instructions(MODEL_NAME)
		self.instructions.initDraw()
		self.model = self.instructions.getMainModel()
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
		
		self.initializeTree()

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
	
		# Draw any 2D page elements, like borders, labels, etc, from a newly created cairo context
		cr = self.window.cairo_create()
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

def on_exit(widget, event):
	gtk.main_quit()

def NamedTuple(typename, s):
	"""Returns a new subclass of tuple with named fields.

	>>> Point = NamedTuple('Point', 'x y')
	>>> Point.__doc__           # docstring for the new class
	'Point(x, y)'
	>>> p = Point(11, y=22)     # instantiate with positional args or keywords
	>>> p[0] + p[1]             # works just like the tuple (11, 22)
	33
	>>> x, y = p                # unpacks just like a tuple
	>>> x, y
	(11, 22)
	>>> p.x + p.y               # fields also accessable by name
	33
	>>> p                       # readable __repr__ with name=value style 
	Point(x=11, y=22)
	>>> p.replace('x', 100)     # method like str.replace() but using a field name
	Point(x=100, y=22)
	"""

	field_names = s.split()
	if not ''.join(field_names).replace('_', '').isalnum():
		raise ValueError('Type names and field names can only contain alphanumeric characters and underscores')
	argtxt = ', '.join(field_names)
	reprtxt = ', '.join('%s=%%r' % name for name in field_names)
	arglist = repr(field_names)    
	template = '''class %(typename)s(tuple):
		'%(typename)s(%(argtxt)s)'
		__slots__ = ()
		def __new__(cls, %(argtxt)s):
			return tuple.__new__(cls, (%(argtxt)s,))
		def __repr__(self):
			return '%(typename)s(%(reprtxt)s)' %% self
		def replace(self, field, value):
			return %(typename)s(**dict((a, value if a==field else getattr(self, a)) for a in %(arglist)s))            
	''' % locals()
	for i, name in enumerate(field_names):
		template += '\n        %s = property(itemgetter(%d))\n' % (name, i)
	m = dict(itemgetter=itemgetter)
	exec template in m
	result = m[typename]
	if hasattr(sys, '_getframe'):
		result.__module__ = sys._getframe(1).f_globals['__name__']
	return result

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
