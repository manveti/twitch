import Tkinter
import ttk


class ClosableNotebook(ttk.Notebook):
    _initialized = False

    def __init__(self, *args, **kwargs):
	if (not self._initialized):
	    self.initImages()
	kwargs['style'] = "ClosableNotebook"
	ttk.Notebook.__init__(self, *args, **kwargs)
	self._active = None
	self.bind("<ButtonPress-1>", self.closePressed, True)
	self.bind("<ButtonRelease-1>", self.closeReleased)

    def initImages(self):
	self.images = (
		Tkinter.PhotoImage("img_cn_close", data='''
				R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
				d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
				5kEJADs='''),
		Tkinter.PhotoImage("img_cn_close_active", data='''
				R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH5BAEKAAQALAAA
				AAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU5kEJADs='''),
		Tkinter.PhotoImage("img_cn_close_pressed", data='''
				R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
				d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
				5kEJADs='''))
	style = ttk.Style()
	style.element_create("close", "image", "img_cn_close",
				    ("active", "pressed", "!disabled", "img_cn_close_pressed"),
				    ("active", "!disabled", "img_cn_close_active"), border=8, sticky="")
	style.layout("ClosableNotebook", [("ClosableNotebook.client", {'sticky': "nswe"})])
	focusSpec = {'side': "top",
		    'sticky': "nswe",
		    'children': [
			("ClosableNotebook.label", {'side': "left", 'sticky': ""}),
			("ClosableNotebook.close", {'side': "left", 'sticky': ""})
		    ]}
	paddingSpec = {'side': "top",
			'sticky': "nswe",
			'children': [("ClosableNotebook.focus", focusSpec)]}
	tabSpec = {'sticky': "nswe", 'children': [("ClosableNotebook.padding", paddingSpec)]}
	style.layout("ClosableNotebook.Tab", [("ClosableNotebook.tab", tabSpec)])

    def closePressed(self, event):
	element = self.identify(event.x, event.y)
	if ((not element) or ("close" not in element)):
	    return
	idx = self.index("@%d,%d" % (event.x, event.y))
	self.state(["pressed"])
	self._active = idx

    def closeReleased(self, event):
	if (not self.instate(["pressed"])):
	    return
	self.state(["!pressed"])
	active = self._active
	self._active = None

	element = self.identify(event.x, event.y)
	if ((not element) or ("close" not in element)):
	    return
	idx = self.index("@%d,%d" % (event.x, event.y))
	if (active != idx):
	    return
	self.forget(idx)

    def forget(self, idx):
	if (self.onClose(idx)):
	    return
	ttk.Notebook.forget(self, idx)

    def onClose(self, idx):
	pass
