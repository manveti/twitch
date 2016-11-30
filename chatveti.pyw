#!/usr/bin/env python

import base64
import os.path
import shelve
import Tkinter
import Tix
import ttk

import Tkx
import Twitch


DEFAULT_PREFERENCES = {'userPaneVisible': True}


class ChatCallbackFunctions(Twitch.ChatCallbacks):
    def __init__(self, master):
	self.master = master

#####
##
    def userJoined(self, channel, user):
	pass

    def userLeft(self, channel, user):
	pass

    def chatMessage(self, channel, user, msg):
	pass
	self.master.chatBox.insert(Tkinter.END, "%s: %s\n" % (user, msg), None)
##
#####


class MainGui(Tkinter.Frame):
    def __init__(self, master=None):
	Tkinter.Frame.__init__(self, master)

	self.loadPreferences()

	self.channels = {}
#####
##
	#stuff
##
#####

	self.master.title("ChatVeti")
	self.menuBar = Tkinter.Menu(self)
	master.config(menu=self.menuBar)

	# file menu
	self.fileMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.fileMen.add_command(label="Open Channel...", command=self.openChannel)
	self.fileMen.add_command(label="Open Log...", command=self.openLog)
	self.fileMen.add_separator()
	self.fileMen.add_command(label="Save Log", command=self.saveLog)
	self.fileMen.add_command(label="Save Log As...", command=self.saveLogAs)
	self.fileMen.add_command(label="Export Log...", command=self.exportLog)
	self.fileMen.add_separator()
	self.fileMen.add_command(label="Close Channel", command=self.closeChannel)
	self.fileMen.add_command(label="Exit", command=self.interceptExit)
	self.menuBar.add_cascade(label="File", menu=self.fileMen)

#####
##
	#other menus
	#  ?edit (cut, copy, paste, select all, -, find, preferences...)?
	#  ?view (show/hide timestamps; show/hide user list)?
	#  ?favorite channels (add favorite, edit favorites..., -, channel1, channel2, ...)?
	#  macros (edit macros..., -, macro1, macro2, ...)
##
#####

	self.panes = Tkinter.PanedWindow(self, sashrelief=Tkinter.GROOVE)

	# chat pane
	self.chatPane = Tkinter.Frame(self.panes)
	self.channelTabs = Tkx.ClosableNotebook(self.chatPane, height=0)
	self.channelTabs.grid(row=0, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.S))
#####
##
	fr1=Tkinter.Frame(self.channelTabs)
	self.channelTabs.add(fr1,text="twogirls1game")
	fr2=Tkinter.Frame(self.channelTabs)
	self.channelTabs.add(fr2,text="geekandsundry")
##
#####
	self.userPaneToggle = Tkinter.Button(self.chatPane, text=">", command=self.toggleUserPane)
	self.userPaneToggle.grid(row=0, column=2, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatGrid = Tkinter.Frame(self.chatPane)
	self.chatBox = Tkinter.Text(self.chatGrid, wrap=Tkinter.NONE)
#####
##
	#chat box keybindings
##
#####
	self.chatBox.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatVScroll = Tkinter.Scrollbar(self.chatGrid, command=self.chatBox.yview)
	self.chatVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatHScroll = Tkinter.Scrollbar(self.chatGrid, orient=Tkinter.HORIZONTAL, command=self.chatBox.xview)
	self.chatHScroll.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	self.chatGrid.columnconfigure(0, weight=1)
	self.chatGrid.rowconfigure(0, weight=1)
	self.chatGrid.grid(row=1, column=0, columnspan=3, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.scratchBut = Tkinter.Menubutton(self.chatPane, text="Scratch", relief=Tkinter.RAISED)
	self.scratchMen = Tkinter.Menu(self.scratchBut, tearoff=False)
	self.scratchMen.add_command(label="Scratch Input", command=self.scratchInput)
	self.scratchMen.add_separator()
	self.scratchBut.config(menu=self.scratchMen)
	self.scratchBut.grid(row=2, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.chatInputBox = Tkinter.Entry(self.chatPane)
#####
##
	#chat input box keybindings
##
#####
	self.chatInputBox.grid(row=2, column=1, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
#####
##
	#?emotes menu?
	#?macro buttons?
##
#####
	self.chatPane.columnconfigure(1, weight=1)
	self.chatPane.rowconfigure(1, weight=1)
	self.panes.add(self.chatPane, stretch="always")

	# users pane
	self.userPane = Tkinter.Frame(self.panes)
	self.userGrid = Tkinter.Frame(self.userPane)
	self.userList = Tkinter.Listbox(self.userGrid)
#####
##
	self.userList.insert(Tkinter.END, "Bob Dole")
	self.userList.insert(Tkinter.END, "manveti")
##
#####
	self.userList.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
	self.userVScroll = Tkinter.Scrollbar(self.userGrid, command=self.userList.yview)
	self.userVScroll.grid(row=0, column=1, sticky=(Tkinter.E, Tkinter.N, Tkinter.S))
	self.userHScroll = Tkinter.Scrollbar(self.userGrid, orient=Tkinter.HORIZONTAL, command=self.userList.xview)
	self.userHScroll.grid(row=1, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N))
	self.userGrid.columnconfigure(0, weight=1)
	self.userGrid.rowconfigure(0, weight=1)
	self.userGrid.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))
#####
##
	#optional user admin area
##
#####
	self.userPane.columnconfigure(0, weight=1)
	self.userPane.rowconfigure(0, weight=1)
	if (self.preferences.get('userPaneVisible')):
	    self.panes.add(self.userPane, stretch="always")

	self.panes.grid(row=0, column=0, sticky=(Tkinter.W, Tkinter.E, Tkinter.N, Tkinter.S))

#####
##
	#(maybe) minimizable macro area
##
#####

	self.columnconfigure(0, weight=1)
	self.rowconfigure(0, weight=1)
	self.pack(fill="both", expand=True)

#####
##
	#configure self.chatBox tags
##
#####

	self.master.protocol("WM_DELETE_WINDOW", self.interceptExit)

    def loadPreferences(self):
	self.preferences = shelve.open(os.path.join(os.path.dirname(__file__), ".config"), protocol=1)

	for pref in DEFAULT_PREFERENCES.keys():
	    if (not self.preferences.has_key(pref)):
		self.preferences[pref] = DEFAULT_PREFERENCES[pref]

    def savePreferences(self):
	self.preferences.sync()

    def interceptExit(self):
#####
##
	#prevent exit and return if necessary
	self.chat.disconnect()
##
#####
	self.preferences.close()
	self.master.destroy()

#####
##
    def openChannel(self):
	pass
	self.chat = Twitch.Chat(ChatCallbackFunctions(self), base64.b64decode(self.preferences.get('token')))
	self.chat.join("twogirls1game")

    def openLog(self):
	pass
	self.chat.leave("twogirls1game")

    def saveLog(self):
	pass

    def saveLogAs(self):
	pass

    def exportLog(self):
	pass

    def closeChannel(self):
	pass

    #other menu handlers
    #channelTabs handlers
##
######

    def toggleUserPane(self):
	if (self.preferences.get('userPaneVisible')):
	    self.panes.remove(self.userPane)
	    self.userPaneToggle.configure(text="<")
	    self.preferences['userPaneVisible'] = False
	else:
	    self.panes.add(self.userPane, stretch="always")
	    self.userPaneToggle.configure(text=">")
	    self.preferences['userPaneVisible'] = True
	self.savePreferences()

#####
##
    def scratchInput(self):
	pass
##
#####

#####
##
    #other handlers
##
#####


mainWin = MainGui(Tix.Tk())
mainWin.mainloop()
