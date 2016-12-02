#!/usr/bin/env python

import base64
import os.path
import shelve
import threading
import Tkinter
import tkSimpleDialog
import time
import Tix
import ttk

import Tkx
import Twitch


DEFAULT_PREFERENCES = {
    'maxInputHistory':		100,
    'maxScratchWidth':		50,
    'userPaneVisible':		True,
}

EVENT_MSG = 0
EVENT_JOIN = 1
EVENT_LEAVE = 2

CHAT_POPULATE_INTERVAL = 0.1


class ChatCallbackFunctions(Twitch.ChatCallbacks):
    def __init__(self, master):
	self.master = master

    def userJoined(self, channel, user):
	if (not self.master.channels.has_key(channel)):
	    return
	if (self.master.channels[channel]['users'].has_key(user)):
	    return
	self.master.channels[channel]['userLock'].acquire()
	self.master.channels[channel]['users'][user] = {'display': user}
	self.master.channels[channel]['userLock'].release()
	self.master.channels[channel]['log'].append((EVENT_JOIN, user))
	if (channel != self.master.curChannel):
	    return
	userSort = self.master.getSortedUsers(channel)
	idx = userSort.index(user)
	self.master.userListLock.acquire()
	self.master.userList.insert(idx, user)
	self.master.userListLock.release()

    def usersJoined(self, channel, users):
	if (not self.master.channels.has_key(channel)):
	    return
	if (len(users) < len(self.master.channels[channel]['users']) / 2):
	    return Twitch.ChatCallbacks.usersJoined(self, channel, users)
	self.master.channels[channel]['userLock'].acquire()
	for user in users:
	    self.master.channels[channel]['users'][user] = {'display': user}
	    self.master.channels[channel]['log'].append((EVENT_JOIN, user))
	self.master.channels[channel]['userLock'].release()
	if (channel != self.master.curChannel):
	    return
	self.master.userListLock.acquire()
	self.master.userList.delete(0, Tkinter.END)
	for user in self.master.getSortedUsers(channel):
	    self.master.userList.insert(Tkinter.END, user)
	self.master.userListLock.release()

    def userLeft(self, channel, user):
	if (not self.master.channels.has_key(channel)):
	    return
	if (not self.master.channels[channel]['users'].has_key(user)):
	    return
	self.master.channels[channel]['log'].append((EVENT_LEAVE, user))
	if (channel == self.master.curChannel):
	    userSort = self.master.getSortedUsers(channel)
	    idx = userSort.index(user)
	    self.master.userListLock.acquire()
	    self.master.userList.delete(idx)
	    self.master.userListLock.release()
	self.master.channels[channel]['userLock'].acquire()
	del self.master.channels[channel]['users'][user]
	self.master.channels[channel]['userLock'].release()

    def chatMessage(self, channel, user, msg, userDisplay=None, userColor=None, userBadges=set(), emotes=[]):
	if (not self.master.channels.has_key(channel)):
	    return
	updateUserList = False
	if (not self.master.channels[channel].has_key(user)):
	    self.master.channels[channel]['userLock'].acquire()
	    self.master.channels[channel]['users'][user] = {'display': user}
	    self.master.channels[channel]['userLock'].release()
	    updateUserList = True
	if (not userDisplay):
	    userDisplay = self.master.channels[channel]['users'][user].get('display')
	if (self.master.channels[channel]['users'][user]['display'] != userDisplay):
	    if (channel == self.master.curChannel):
		self.master.userListLock.acquire()
		userSort = self.master.getSortedUsers(channel)
		idx = userSort.index(user)
		self.master.userList.delete(idx)
		self.master.userListLock.release()
	    self.master.channels[channel]['users'][user]['display'] = userDisplay
	    updateUserList = True
	if (not userColor):
	    userColor = self.master.channels[channel]['users'][user].get('color')
	self.master.channels[channel]['users'][user]['color'] = userColor
#####
##
	#update self.master.channels[channel]['users'][user] badges
##
#####
	logLine = (EVENT_MSG, time.time(), user, msg, userDisplay, userColor, userBadges, emotes)
	self.master.channels[channel]['log'].append(logLine)
	if (channel != self.master.curChannel):
	    return
	if (updateUserList):
	    self.master.userListLock.acquire()
	    userSort = self.master.getSortedUsers(channel)
	    idx = userSort.index(user)
	    self.master.userList.insert(idx, self.master.channels[channel]['users'][user].get('display', user))
	    self.master.userListLock.release()
	if ((userColor) and (not self.master.chatTags.has_key(userColor))):
	    self.master.chatTags[userColor] = set([channel])
#####
##
	    #make sure background is reasonable
##
#####
	    self.master.chatBox.tag_configure(userColor, foreground=userColor)
	elif (userColor):
	    self.master.chatTags[userColor].add(channel)
#####
##
	#(timestamp and general tags should be set up elsewhere, but not coded yet)
	tsTags=None
	userTags=userColor #single tag or tuple of tags
	msgTags=None
	self.master.chatBoxLock.acquire()
	#if showing timestamps: self.master.chatBox.insert(Tkinter.END, timestamp_string, tsTags)
	#deal with badges
##
#####
	self.master.chatBox.insert(Tkinter.END, userDisplay, userTags)
#####
##
	#deal with emotes
	self.master.chatBox.insert(Tkinter.END, ": %s\n" % msg, msgTags)
##
#####
	self.master.chatBoxLock.release()


class MainGui(Tkinter.Frame):
    def __init__(self, master=None):
	Tkinter.Frame.__init__(self, master)

	self.loadPreferences()

	self.channels = {}
	self.channelOrder = []
	self.curChannel = None
	self.chat = None
	self.chatToPopulate = []
	self.chatPopulateThread = None
	self.chatTags = {}
	self.scratchMsgs = []
	self.inputHistory = []
	self.inputHistoryPos = 0
#####
##
	#stuff
##
#####

	self.chatBoxLock = threading.Lock()
	self.userListLock = threading.Lock()

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
##
#####

	# favorites menu
	self.favoritesMen = Tkinter.Menu(self.menuBar, tearoff=False)
	self.favoritesMen.add_command(label="Add Favorite", command=self.addFavorite)
	self.favoritesMen.add_command(label="Edit Favorites...", command=self.editFavorites)
	self.favoritesMen.add_separator()
	for channel in self.preferences.get('favorites', []):
	    self.favoritesMen.add_command(label=channel, command=lambda c=channel: self.doChannelOpen(c))
	self.menuBar.add_cascade(label="Favorites", menu=self.favoritesMen)

#####
##
	#macros menu (edit macros..., -, macro1, macro2, ...)
##
#####

	self.panes = Tkinter.PanedWindow(self, sashrelief=Tkinter.GROOVE)

	# chat pane
	self.chatPane = Tkinter.Frame(self.panes)
	self.channelTabs = Tkx.ClosableNotebook(self.chatPane, height=0)
	self.channelTabs.bind("<<NotebookTabChanged>>", self.channelTabChanged)
	self.channelTabs.onClose = self.channelTabClosed
	self.channelTabs.grid(row=0, column=0, columnspan=2, sticky=(Tkinter.W, Tkinter.E, Tkinter.S))
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
	self.chatInputBox.bind("<Return>", self.submitChatInput)
	self.chatInputBox.bind("<Up>", self.inputUpHistory)
	self.chatInputBox.bind("<Down>", self.inputDownHistory)
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
	self.userList = Tkinter.Listbox(self.userGrid, activestyle="none")
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
	#configure self.chatBox timestamp and message tags
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
	self.chatToPopulate = []
	if(self.chat):self.chat.disconnect()
##
#####
	self.preferences.close()
	self.master.destroy()

    def openChannel(self):
	self.doChannelOpen(tkSimpleDialog.askstring("Channel", "Enter channel to join"))

#####
##
    def openLog(self):
	pass

    def saveLog(self):
	pass

    def saveLogAs(self):
	pass

    def exportLog(self):
	pass
##
######

    def closeChannel(self):
	if (not self.curChannel):
	    return
	try:
	    idx = self.channelOrder.index(self.curChannel)
	except ValueError:
	    return
	self.channelTabs.forget(idx)

#####
##
    #other menu handlers
##
#####

    def addFavorite(self):
	if ((not self.curChannel) or (self.curChannel in self.preferences.get('favorites', []))):
	    return
	favorites = self.preferences.get('favorites', [])
	favorites.append(self.curChannel)
	favorites.sort(key=lambda c: c.lower())
	self.preferences['favorites'] = favorites
	self.preferences.sync()
	idx = self.preferences['favorites'].index(self.curChannel)
	cmd = lambda c=self.curChannel: self.doChannelOpen(c)
	self.favoritesMen.insert_command(idx + 3, label=self.curChannel, command=cmd)

    def editFavorites(self):
#####
##
	pass
##
#####

#####
##
    #macros menu handlers
##
######

    def channelTabChanged(self, e=None):
	tabId = self.channelTabs.select()
	if (not tabId):
	    return
	idx = self.channelTabs.index(tabId)
	if ((idx < 0) or (idx >= len(self.channelOrder)) or (self.channelOrder[idx] == self.curChannel)):
	    return
	self.curChannel = self.channelOrder[idx]
	self.populateChat(self.channels[self.curChannel]['log'])
	self.userListLock.acquire()
	self.userList.delete(0, Tkinter.END)
	for user in self.getSortedUsers(self.curChannel):
	    self.userList.insert(Tkinter.END, self.channels[self.curChannel]['users'][user].get('display',user))
	self.userListLock.release()

    def channelTabClosed(self, idx):
	if ((idx < 0) or (idx >= len(self.channelOrder))):
	    return
	channel = self.channelOrder[idx]
#####
##
	#maybe prompt to confirm leaving without saving log; return True to abort
##
######
	self.chat.leave(channel)
	self.channelOrder = self.channelOrder[:idx] + self.channelOrder[idx + 1:]
	del self.channels[channel]
	self.curChannel = None

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

    def scratchInput(self):
	s = self.chatInputBox.get()
	if ((not s) or (s in self.scratchMsgs)):
	    return
	self.scratchMsgs.append(s)
	maxWidth = self.preferences.get('maxScratchWidth', DEFAULT_PREFERENCES['maxScratchWidth'])
	if (len(s) <= maxWidth):
	    shortS = s
	else:
	    shortS = s[:maxWidth / 2 - 1] + "..." + s[-((maxWidth - 1) / 2 - 1):]
	self.scratchMen.add_command(label=shortS, command=lambda cmd=s: self.scratchCmd(cmd))
	self.chatInputBox.delete(0, Tkinter.END)

    def scratchCmd(self, s):
	if (not s):
	    return
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, s)
	try:
	    idx = self.scratchMsgs.index(s)
	except ValueError:
	    return
	self.scratchMsgs = self.scratchMsgs[:idx] + self.scratchMsgs[idx + 1:]
	self.scratchMen.delete(idx + 2)

    def submitChatInput(self, e=None):
	s = self.chatInputBox.get()
	if (not s):
	    return
	self.inputHistory.append(s)
	self.inputHistory = self.inputHistory[-self.preferences.get('maxInputHistory'):]
	self.inputHistoryPos = len(self.inputHistory)
	self.chatInputBox.delete(0, Tkinter.END)
	if ((not self.chat) or (not self.curChannel) or (not self.channels.has_key(self.curChannel))):
	    return
	self.chat.send(self.curChannel, s)

    def inputUpHistory(self, e=None):
	if (self.inputHistoryPos > len(self.inputHistory)):
	    self.inputHistoryPos = len(self.inputHistory)
	if (self.inputHistoryPos <= 0):
	    return
	self.inputHistoryPos -= 1
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, self.inputHistory[self.inputHistoryPos])

    def inputDownHistory(self, e=None):
	if (self.inputHistoryPos >= len(self.inputHistory)):
	    return
	self.inputHistoryPos += 1
	if (self.inputHistoryPos >= len(self.inputHistory)):
	    s = ""
	else:
	    s = self.inputHistory[self.inputHistoryPos]
	self.chatInputBox.delete(0, Tkinter.END)
	self.chatInputBox.insert(0, s)

#####
##
    #other handlers
##
#####

    def doChannelOpen(self, channel):
	if (not channel):
	    return
#####
##
	if (self.channels.has_key(channel)):
	    #maybe warn about already connected and/or raise channel tab
	    return
	#get oauth (logging in if necessary)
	oauth=base64.b64decode(self.preferences.get('token'))
##
######
	if (not self.chat):
	    self.chat = Twitch.Chat(ChatCallbackFunctions(self), oauth)
	self.channels[channel] = {'users': {}, 'log': [], 'userLock': threading.Lock()}
	self.channelOrder.append(channel)
	self.channels[channel]['frame'] = Tkinter.Frame(self.channelTabs)
	self.channelTabs.add(self.channels[channel]['frame'], text=channel)
	self.channelTabs.select(len(self.channelOrder) - 1)
	self.curChannel = channel
	self.chatBoxLock.acquire()
	self.chatBox.delete("1.0", Tkinter.END)
	self.chatBoxLock.release()
	self.userListLock.acquire()
	self.userList.delete(0, Tkinter.END)
	self.userListLock.release()
	self.chat.join(channel)

    def getSortedUsers(self, channel):
	if ((not channel) or (not self.channels.has_key(channel))):
	    return
	users = self.channels[channel]['users'].keys()
	users.sort(key=lambda u: self.channels[channel]['users'][u].get('display', u).lower())
	return users

    def populateChat(self, log):
	self.chatBoxLock.acquire()
	self.chatBox.delete("1.0", Tkinter.END)
	self.chatToPopulate = log[:]
	self.chatBoxLock.release()
	if (not self.chatPopulateThread):
	    self.chatPopulateThread = threading.Thread(target=self.populateChatThreadHandler)
	    self.chatPopulateThread.daemon = True
	    self.chatPopulateThread.start()

    def populateChatThreadHandler(self):
	while (True):
	    if (not self.chatToPopulate):
		time.sleep(CHAT_POPULATE_INTERVAL)
		continue
	    self.chatBoxLock.acquire()
	    if (not self.chatToPopulate):
		self.chatBoxLock.release()
		continue
	    logLine = self.chatToPopulate.pop()
	    if (logLine[0] != EVENT_MSG):
		self.chatBoxLock.release()
		continue
	    (e, ts, user, msg, userDisplay, userColor, userBadges, emotes) = logLine
	    if ((userColor) and (not self.chatTags.has_key(userColor))):
		self.chatTags[userColor] = set([self.curChannel])
#####
##
		#make sure background is reasonable
##
#####
		self.chatBox.tag_configure(userColor, foreground=userColor)
	    elif (userColor):
		self.chatTags[userColor].add(self.curChannel)
#####
##
	    tsTags=None
	    userTags=userColor #single tag or tuple of tags (make sure userColor is valid tag)
	    msgTags=None
	    #deal with emotes
	    self.chatBox.insert("1.0", ": %s\n" % msg, msgTags)
	    #deal with badges
	    self.chatBox.insert("1.0", userDisplay, userTags)
	    #if showing timestamps: self.chatBox.insert("1.0", timestamp_string, tsTags)
##
#####
	    self.chatBoxLock.release()


mainWin = MainGui(Tix.Tk())
mainWin.mainloop()
