import os
import gtk
import gtk.glade
import gtk.gtkgl
import gobject

import config
from Model import *
from GLHelpers import *

from OpenGL.GL import *
from OpenGL.GLU import *

# TODO: Fix OGL surface normals and BFC, so OGL rendering can look better.
gui_xml = gtk.glade.XML(os.path.join(os.getcwd(), 'LIC.glade'))

class DrawArea(gtk.DrawingArea, gtk.gtkgl.Widget):
	def __init__(self, window):
		gtk.DrawingArea.__init__(self)
		
		self.set_events(gtk.gdk.BUTTON_MOTION_MASK  | gtk.gdk.KEY_PRESS_MASK |
				gtk.gdk.KEY_RELEASE_MASK    | gtk.gdk.POINTER_MOTION_MASK |
				gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON_PRESS_MASK |
				gtk.gdk.SCROLL_MASK)
		
		self.containingWindow = window
		self.set_flags(gtk.CAN_FOCUS)
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

	def on_treeview_key_press(self, *args):
		return False
	
	def on_treeview_key_release(self, *args):
		return False
	
	def on_box_opengl_key_press(self, widget, event):
		if not self.currentSelection:
			return True
		
		key = gtk.gdk.keyval_name(event.keyval)
		d = 10 if event.state & gtk.gdk.SHIFT_MASK else 1
		if key == 'Up':
			self.currentSelection.moveBy(0, -d)
			self.on_draw_event()
		elif key == 'Down':
			self.currentSelection.moveBy(0, d)
			self.on_draw_event()
		elif key == 'Left':
			self.currentSelection.moveBy(-d, 0)
			self.on_draw_event()
		elif key == 'Right':
			self.currentSelection.moveBy(d, 0)
			self.on_draw_event()
		return True
	
	def on_button_press(self, widget, event):
		self.set_flags(gtk.HAS_FOCUS)
		self.grab_focus()
		
		x = event.x
		y = event.y
		prevSelection = self.currentSelection
		if self.currentPage:
			self.currentSelection = self.currentPage.select(x, y)
		if prevSelection is not self.currentSelection:
			self.on_draw_event()  # Selected a new instruction element - redraw

	def on_box_opengl_key_release(self, *args):
		return True

	def on_generate_images(self, data):
		self.instructions.generateImages()
	
	def on_translate_part(self, data):
		if self.currentSelection and isinstance(self.currentSelection , Step):
			self.currentSelection.parts[0].translate(0, 0, -10)
			self.on_draw_event()
	
	def on_exit(self, data):
		return False

	def file_browse(self, action, filename = ""):
		
		if action == gtk.FILE_CHOOSER_ACTION_OPEN:
			title = "Open Model..."
			buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK)
		else:
			title = "Save Model As..."
			buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK)
		
		chooser = gtk.FileChooserDialog(title, None, action, buttons)
		chooser.set_current_folder(os.path.join(config.LDrawPath, 'MODELS'))
		
		if action == gtk.FILE_CHOOSER_ACTION_SAVE:
			chooser.set_current_name(filename)
		
		filter = gtk.FileFilter()
		filter.set_name("LDraw Models...")
		filter.add_pattern("*.dat")
		filter.add_pattern("*.ldr")
		filter.add_pattern("*.mpd")
		chooser.add_filter(filter)
		filter = gtk.FileFilter()
		filter.set_name("All files...")
		filter.add_pattern("*")
		chooser.add_filter(filter)
		
		response = chooser.run()
		if response == gtk.RESPONSE_OK:
			filename = chooser.get_filename()
		chooser.destroy()
		
		return filename

	def on_open(self, widget):
		# TODO: Holy crap GTK's FileChooser is horrid - try desperately to either sanitize it, or get GTK to use native window manager's open dialog.
		# Why the heck would a toolkit like this create its own FileChooser without checking the underlying window manager first??
		filename = self.file_browse(gtk.FILE_CHOOSER_ACTION_OPEN)
		self.load_model(filename)
		self.containingWindow.set_title("%s - Lic 0.01 (pre-pre-Alpha)" % os.path.basename(filename))
	
	def on_save(self, data):
		self.instructions.save()

	def on_save_as(self, *args):
		# TODO: See on_open TODO - Save As is just as asstastic
		filename = self.file_browse(gtk.FILE_CHOOSER_ACTION_SAVE, self.instructions.filename)
		self.instructions.save(filename)
		self.containingWindow.set_title("%s - Lic 0.01 (pre-pre-Alpha)" % os.path.basename(filename))
	
	def on_destroy(self, widget, data=None):
		gtk.main_quit()

	def load_model(self, filename):
		
		glEnable(GL_DEPTH_TEST)
		glClearColor(1.0, 1.0, 1.0, 1.0)  # Draw clear white screen
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		print "*** Loading Model ***"
		try:
			self.instructions = Instructions(filename)
		except IOError:
			print "Could not find file %s" % (filename)
			return
		
		cr = self.window.cairo_create()
		self.instructions.initDraw(cr)
		self.currentSelection = self.instructions.getMainModel()
		self.initializeTree()

	def on_init(self, *args):
		""" Initialize the window. """
		
		glEnable(GL_LIGHTING)
		glEnable(GL_LIGHT0)
		glShadeModel(GL_SMOOTH)
		
		glEnable(GL_COLOR_MATERIAL)
		glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
		
		lightPos = [100.0, 100.0, 100.0]
		ambient = [0.2, 0.2, 0.2]
		diffuse = [0.8, 0.8, 0.8]
		specular = [0.5, 0.5, 0.5]
		
		glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
		glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
		glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
		glLightfv(GL_LIGHT0, GL_SPECULAR, specular)
		
		modelName = None
		#modelName = "pyramid.dat"
		#modelName = "Blaster.mpd"
		if modelName:
			self.load_model("c:\\ldrawparts\\models\\" + modelName)

	def on_resize_event(self, *args):
		""" Resize the window. """
		
		self.width = args[1].width
		self.height = args[1].height
		
		if (self.width < 5) or (self.height < 5):
			return  # ignore resize if window is basically invisible
		
		gldrawable = self.get_gl_drawable()
		glcontext = self.get_gl_context()
		gldrawable.gl_begin(glcontext)
		
		adjustGLViewport(0, 0, self.width, self.height)
		glLoadIdentity()	
		rotateToDefaultView()
		
		gldrawable.gl_end()
	
	def on_draw_event(self, *args):
		""" Draw the window. """
		
		# Create a fresh, blank cairo context attached to the window's display area
		# TODO: After draw debugging is done, double buffer this draw by drawing everything to a temp cairo surface,
		# then dump that surface to the window's context.  Drawing directly onto the window flickers something nasty.
		cr = self.window.cairo_create()
		cr.identity_matrix()
		cr.set_source_rgb(1, 1, 1)
		cr.paint()
		
		# Clear the window's current GL buffers
		glClearColor(1.0, 1.0, 1.0, 0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		
		# Draw the currently selected model / part / step / page / whatnot
		if self.currentPage:
			self.currentPage.draw(cr, self.width, self.height, self.currentSelection)
		elif self.currentSelection and isinstance(self.currentSelection, Part):
			self.currentSelection.draw(cr, self.width, self.height)
	
	def treeview_button_press(self, obj, event):
		treemodel, iter = self.tree.get_selection().get_selected()
		if iter:  # If nothing is selected, iter is None, and get_value crashes
			self.currentSelection = treemodel.get_value(iter, 1)
			self.currentPage = treemodel.get_value(iter, 2)
			self.on_draw_event()

	def initializeTree(self):
		print "*** Loading TreeView ***"
		root = self.insert_after(self.treemodel, None, None, self.currentSelection.name, self.currentSelection, None)
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
						subRoot = self.insert_before(self.treemodel, root, iterPage, "SubModel " + p.name, part, None)
						loadedSubModels.append(p.name)
						
						# Add this part's steps into this part in the tree.
						if p.pages != []:
							self.addPagesToTree(p.pages, subRoot)
					
					# Add this part (not partOGL) to tree, placed inside the current CSI node
					iterPart = self.insert_after(self.treemodel, iterCSI, iterPart, p.name, part, page)
				
				iterPart = None
			iterStep = iterPLI = iterCSI = None

def go():
	
	main = gui_xml.get_widget("main_window")
	
	area = DrawArea(main)
	box = gui_xml.get_widget("box_opengl")
	box.pack_start(area)
	
	sigs = {"on_menuGenerate_activate": area.on_generate_images,
			"on_open_activate": area.on_open,
			"on_save_activate": area.on_save,
			"on_save_as_activate": area.on_save_as,
			"on_quit_activate": area.on_destroy,
			"on_treeview_key_press_event": area.on_treeview_key_press,
			"on_treeview_key_release_event": area.on_treeview_key_release,
			"on_box_opengl_key_press_event": area.on_box_opengl_key_press,
			"on_box_opengl_key_release_event": area.on_box_opengl_key_release,
			"on_quit_activate": area.on_destroy,
			}
	
	gui_xml.signal_autoconnect(sigs)

	# Some example status bar code
	statusbar = gui_xml.get_widget("statusbar")
	context_id = statusbar.get_context_id("statusbar")
	message_id = statusbar.push(context_id, "Hello")
	
	#main.maximize()
	main.set_title("Lic 0.01 (pre-pre-Alpha)")
	main.show_all()
	
	gtk.main()

if __name__ == '__main__':
	go()
