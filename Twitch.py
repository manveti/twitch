import json
import re
import select
import socket
import ssl
import threading
import urllib
import webbrowser


CLIENT_ID = "8ttcvo44qr7774zw9hounn1bcx2lnk2"

REDIRECT_ADDR = ("localhost", 14425)
REDIRECT_URI = "http://%s:%s" % REDIRECT_ADDR

AUTH_URL_BASE = "https://api.twitch.tv/kraken/oauth2/authorize"
AUTH_ARGS = "?response_type=token&client_id=%(cid)s&redirect_uri=%(redirect)s&scope=%(scope)s"
AUTH_FORCE_ARG = "&force_verify=true"

DEFAULT_SCOPES = ["user_read", "chat_login"]

API_ADDR = ("api.twitch.tv", 443)
API_URL_BASE = "https://%s/kraken" % API_ADDR[0]

CHAT_ADDR = ("irc.chat.twitch.tv", 6667)

BUF_SIZE = 1024
READ_INTERVAL = 0.1

AUTH_HTML = """<html>
<head>
<title>Authorizing</title>
<script language="javascript"><!--
function getAuthInfo(){
    var req = new XMLHttpRequest();
    req.onreadystatechange = function(){
	if ((this.readyState != 4) || (this.status != 200)){
	    return;
	}
	var progBox = document.getElementById('authProgress');
	progBox.innerHTML = "<big>Authorized</big><br>\\n<small>You may now close this page.</small>";
    };
    req.open("POST", "%s", true);
    req.send(document.location.hash);
}
--></script>
</head>
<body onLoad="getAuthInfo()">
<div style="position: absolute; top: 50%%; left: 50%%; transform: translate(-50%%, -50%%)">
 <div id="authProgress" style="text-align: center">
  <big>Authorizing...</big><br>
  <small>Please do not close this page until authorization complete.</small>
 </div>
</div>
</body>
</html>""" % REDIRECT_URI

LENGTH_EXP = re.compile("^Content-Length:\s*(?P<len>\d+)\s*$", re.I + re.M)

exp = "^(:(?P<prefix>[^ \r\n]+) )?(?P<command>([a-zA-Z]+|[0-9]{3}))"
exp += "(?P<params>( [^: \r\n][^ \r\n]*){0,14})( :(?P<final>[^\r\n]+))?$"
IRC_MSG_EXP = re.compile(exp)
IRC_PREFIX_EXP = re.compile("[@!.]")


def getOauth(scopes=DEFAULT_SCOPES, force=False):
    args = {'cid':	urllib.quote(CLIENT_ID),
	    'redirect':	urllib.quote(REDIRECT_URI),
	    'scope':	urllib.quote(" ".join(scopes))}
    url = AUTH_URL_BASE + (AUTH_ARGS % args)
    if (force):
	url += AUTH_FORCE_ARG
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#####
##
    #timeout?
##
#####
    server.bind(REDIRECT_ADDR)
    server.listen(1)
    webbrowser.open(url)
    conn = server.accept()
    resp = ""
    while (True):
	s = conn[0].recv(BUF_SIZE)
	if (not s):
	    break
	resp += s
	if (resp.find("\r\n\r\n") >= 0):
	    break
#####
##
    #verify that resp is http request ("GET / HTTP/1.1\r\n")
##
#####
    msg = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %s\r\n\r\n%s"
    conn[0].send(msg % (len(AUTH_HTML), AUTH_HTML))
    if (not re.search("^Connection:\s*keep-alive\s*$", resp, re.I + re.M)):
	conn[0].close()
	conn = server.accept()
    resp = ""
    bodyStart = None
    bodyLength = None
    while (True):
	s = conn[0].recv(BUF_SIZE)
	if (not s):
	    break
	resp += s
	if (not bodyStart):
	    idx = resp.find("\r\n\r\n")
	    if (idx >= 0):
		bodyStart = idx + 4
	if ((bodyStart) and (not bodyLength)):
	    m = LENGTH_EXP.search(resp)
	    if (m):
		bodyLength = int(m.group('len'))
	if ((bodyLength) and (len(resp) >= bodyStart + bodyLength)):
	    break
    resp = resp[bodyStart : (bodyStart + bodyLength)]
    if (resp[0] == '#'):
	resp = resp[1:]
    conn[0].send("HTTP/1.1 200 OK\r\nContent-type: text/html\r\nContent-Length: 0\r\n\r\n")
    conn[0].close()
    server.close()
    respVars = {}
    for tok in resp.split("&"):
	(var, val) = tok.split("=", 1)
	respVars[var] = urllib.unquote_plus(val)
    return (respVars.get('access_token'), respVars.get('scope'))

def getApi(path, oauth=None):
    if (not oauth):
	oauth = getOauth()
    if ((path) and (path[0] != "/")):
	path = "/" + path
    msg = "GET %s%s HTTP/1.1\r\nAccept: application/vnd.twitchtv.v5+json\r\nAuthorization: OAuth %s\r\n\r\n"
    msg = msg % (API_URL_BASE, path, oauth)
    conn = ssl.SSLSocket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    conn.connect(API_ADDR)
    conn.send(msg)
    resp = ""
    bodyStart = None
    bodyLength = None
    while (True):
	s = conn.recv(BUF_SIZE)
	if (not s):
	    break
	resp += s
	if (not bodyStart):
	    idx = resp.find("\r\n\r\n")
	    if (idx >= 0):
		bodyStart = idx + 4
	if ((bodyStart) and (not bodyLength)):
	    m = LENGTH_EXP.search(resp)
	    if (m):
		bodyLength = int(m.group('len'))
	if ((bodyLength) and (len(resp) >= bodyStart + bodyLength)):
	    break
    resp = resp[bodyStart : (bodyStart + bodyLength)]
    return json.loads(resp)

class ChatCallbacks:
    def userJoined(self, channel, user):
	pass

    def userLeft(self, channel, user):
	pass

    def chatMessage(self, channel, user, msg):
	pass

class Chat:
    def __init__(self, callbacks, oauth=None):
	if (not oauth):
	    oauth = getOauth()

	self.callbacks = callbacks
	self.oauth = oauth

	userInfo = getApi("/user", self.oauth)
	self.displayName = userInfo.get('display_name', userInfo.get('name'))

	self.socket = None
	self.running = False
	self.buf = ""
	self.channels = {}

    def connect(self):
	self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	self.socket.connect(CHAT_ADDR)
	self.socket.send("PASS oauth:%s\r\nNICK %s\r\n" % (self.oauth, self.displayName.lower()))
	self.channels = {}
	self.buf = ""
	self.running = True
	self.thread = threading.Thread(target=self.recvThread)
	self.thread.start()
	self.socket.send("CAP REQ :twitch.tv/membership\r\n")

    def disconnect(self):
	self.running = False

    def recvThread(self):
	while (self.running):
	    if (not select.select([self.socket], [], [], READ_INTERVAL)[0]):
		continue
	    self.buf += self.socket.recv(BUF_SIZE)
	    lines = self.buf.replace("\r\n", "\n").split("\n")
	    self.buf = lines.pop()
	    for line in lines:
		m = IRC_MSG_EXP.match(line)
		cmd = m.group('command')
		params = m.group('params').split(" ")[1:]
		if (m.group('final')):
		    params.append(m.group('final'))
		if (cmd == "PING"):
		    self.socket.send("PONG :%s\r\n" % params[-1])
		    continue
		if (cmd == "PRIVMSG"):
		    if ((not params) or (not params[0])):
			continue
		    channel = params[0]
		    if (channel[0] == "#"):
			channel = channel[1:]
		    user = "<anonymous>"
		    if (m.group('prefix')):
			splits = IRC_PREFIX_EXP.split(m.group('prefix'))
			if ((splits) and (splits[0])):
			    user = splits[0]
		    msg = " ".join(params[1:])
		    self.callbacks.chatMessage(channel, user, msg)
		    continue
#####
##
		#handle JOIN and PART commands at least
		#messages we can get:
		#  ":${server} \d{3} ${user} :${msg}"
		#  ":${user}!${user}@${user}.${server} JOIN ${channel}"
		#  ":${user}.${server} \d{3} ${user} = ${channel} :${user}" //353
		#  ":${user}.${server} \d{3} ${user} ${channel} :End of /NAMES list" //366
		#  ":${user}!${user}@${user}.${server} PRIVMSG ${channel} :${msg}"
		#  ":${user}!${user}@${user}.tmi.twitch.tv PRIVMSG ${channel} :${msg}\r\n"
		#in general:
		#  "(:${prefix} )?${command}( ${param}){0,15}"
		#  prefix is origin of message ("${server}" or "${nick}(!${user})?(@${host})?")
		#  command is irc command or 3-digit code
		#  only last param can begin with ':'; param not beginning with ':' cannot have space
##
#####
	self.socket.close()
	self.socket = None

    def join(self, channel):
	if (not self.socket):
	    self.connect()
	if (channel[0] == "#"):
	    channel = channel[1:]
	if (self.channels.has_key(channel)):
	    return
	self.channels[channel] = set()
	self.socket.send("JOIN #%s\r\n" % channel)

    def leave(self, channel):
	if (channel[0] == "#"):
	    channel = channel[1:]
	if ((not self.socket) or (not self.channels.has_key(channel))):
	    return
	self.socket.send("PART #%s\r\n" % channel)
	del self.channels[channel]
