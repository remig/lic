import cairo

UNINIT_PROP = -1

class Point():
	def __init__(self, x = 0, y = 0):
		self.x = x
		self.y = y
	def __repr__(self):
		return "Point(%d, %d)" % (self.x, self.y)

class Font():
	def __init__(self, size, face = "Arial", color = [0, 0, 0], bold = False, italic = False):
		self.size = size
		self.face = face
		self.color = color
		self.bold = bold
		self.italic = italic

	def passToCairo(self, context):
		""" 
		Set the specified cairo context's current font info to the info stored in this Font. 
		This overwrites any current cairo font settings - caller is responsible for caching, if needed.
		"""
		
		if self.bold:
			bold = cairo.FONT_WEIGHT_BOLD
		else:
			bold = cairo.FONT_WEIGHT_NORMAL
		
		if self.italic:
			italic = cairo.FONT_SLANT_ITALIC
		else:
			italic = cairo.FONT_SLANT_NORMAL
			
		context.select_font_face(self.face, italic, bold)
		context.set_font_size(self.size)
		context.set_source_rgb(*self.color)
	
class Line():
	"""
	Drawing properties for any given line an instruction book.
	"""

	# TODO: Define all members and their units in this class
	def __init__(self, red = 0, green = 0, blue = 0):
		self.color = [red, green, blue]  # [red, green, blue], 0.0 - 1.0
		self.thickness = 0
		self.dash = 0

class Fill():
# TODO: Define all members and their units in this class
	def __init__(self):
		self.color = [0.0, 0.0, 0.0]  # [red, green, blue], 0.0 - 1.0
		self.pattern = 0
		self.image = 0
	
class Box():
	"""
	Represents a border and fill drawn around a PLI / CSI / page,
	and the position and size info needed to draw the border.
	"""
	
	def __init__(self, x = UNINIT_PROP, y = UNINIT_PROP, width = UNINIT_PROP, height = UNINIT_PROP):
		self.line = Line(0, 0, 0)
		self.fill = Fill()
		
		# TODO: Convert all of these to relative values (from 0..1, % of overall width | height)
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		
		self.cornerRadius = 0 # Radius for rounded corners. 0 = square
		self.internalGap = 10  # Distance from inside edge of border to outside edge of contents

	def draw(self, context):
		# TODO: Remove this check once all is well
		if (self.x == UNINIT_PROP or self.y == UNINIT_PROP or self.width == UNINIT_PROP or self.height == UNINIT_PROP):
			print "ERROR: Trying to draw an uninitialized box!!"
			return
		
		context.set_source_rgb(*self.line.color)
		context.rectangle(self.x, self.y, self.width, self.height)
		context.stroke()
