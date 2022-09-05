#!/usr/bin/python3
# -*- coding: utf-8 -*-

''' This is the transport module for the 3D-Gui program.
'''
import queue
import threading
import re
import time
from functools import reduce
from serial import Serial, SerialException, PARITY_ODD, PARITY_NONE

import data

class Transport():
    
    def __init__(self, status=None):
        self.BUFSIZE = 128      # Marlin config setting
        self.status = status    # status panel we report to
        self.resendFrom = -1    # resend request pending if > linenumber
        self.resending = False  # tells listen thread to ignore subsequent resend requests
        self.linenum = -1       # Nxx of current gcode line being printed
        self.gcode = []         # entire gcode file
        self.queueindex = 0     # index into gcode array; points to next cmd
        self.maxIndex = 0       # limit for queueindex
        self.sentLines = {}     # command history (used for resending)
        self.P_word = 0
        self.pending = 0        # number of commands sent but not yet ACK'ed
        self.lastLineSent = 0   # line number of last line sent
        self.lastLineAck  = 0   # line number for which marlin last sent an Ok (P-word in ok)
        self.buffAvailable = 5  # number of free line buffers in Marlin (B-word in ok response)
        
        self.prioQ = queue.Queue()  # priority queue for immediate commands
        self.rcvr = None     # thread: listens to the printer
        self.xmtr = None     # thread: xmtr when not printing
        self.print_thread = None    # thread: xmtr when printing
        self.printer = None         # printer device handle
        self.stop_xmtr = False      # (killer flags for threads.. 
        self.printing = False       # ...
        self.stop_rcvr = False      # ...)
        self.CRCflag = False # test
        
        
    def listen(self):
        ''' This is the receiver thread. It listens to the serial port
            and handles all incoming messages. Synchronization with the
            other program compoments occurs via two vars:
                pending     number of commands issued to Marlin's.
                            Pending is incremented upon transmission of
                            a command. It is decremented upon reception
                            of an ok response.
                            In order to solve the issue of missed Ok's 
                            we decrease pending by the difference of the 
                            N-word and lastLineAck; because if the N-word
                            of the ok-response minus the current value of
                            lastLineAck is > 1 we must have missed an Ok.
                resendFrom  linenumber (also index in thegcode array)
                            of the command that has to be resent.
            This thread is invoked as soon as the connection to the
            printer has been established - by connect().
        '''
        print("Starting receiver thread")
        resendExp = re.compile("(\d*)$")
        
        # thread loop starts here:
        while not self.stop_rcvr:
            if not self.printer.in_waiting:
                continue
            line = self.printer.readline().decode("ascii")
            # => resend:
            if not self.resending and line.lower().startswith(("resend", "rs")):
                self.resendFrom = int(re.search(resendExp, line).group(1))
            # => ok:
            if line.startswith("ok"): 
                m = re.search("ok N(\d+) P(\d+) B(\d+)\n", line)
                # this requires ADVANCED_OK in Marlin
                if m:   # all three of N, P and B words match:
                    N_word = int(m.group(1))        # line number of last acknowledge
                    self.P_word = int(m.group(2))   # free space in plan buffer
                    self.buffAvailable = int(m.group(3)) # number of free input buffers
                    self.pending = max(0,self.lastLineSent - N_word)
                    self.lastLineAck = N_word
                else:   # no N_word; decrement pending for each ok received
                    # NOTE: a resend request is followed by a single ok without N, B and P.
                    # so we need this part also when no "smart" buffer mgmt would be used
                    self.pending = max(0, self.pending - 1)
            # => info, busy, error, etc:
            if not line.startswith("ok") or "T0:" in line:
                data.rcvQ.put(line)
        print("Receiver thread killed")

    def start_print(self):
        ''' Setup things so the print thread can take over. Called from the 
            print button in de gui.
        '''
        if not(data.gcodeFile and data.ready and not self.printing):
            return False
        data.gcodeFile.seek(0)
        self.gcode = []
        self.gcode = data.gcodeFile.readlines() # <TODO> try reading line by line?
        if not self.gcode:  # no data in file
            self.status.show("*** gcode file is empty")
            return False
        while not self._send("M110", -1, True):   # reset line number
            time.sleep(0.001)
        self.maxIndex = len(self.gcode)
        self.linenum = 0
        self.resendFrom = -1
        self.resending = False
        self.queueindex = 0
        self.pending = 0
        self.printing = True   # release the print thread
        self.print_thread = threading.Thread(target = self.print, name = "print_thread")
        self.print_thread.start()
        return True
        
    def abort_print(self):
        print("Entering abort_print")
        self.printing = False
        if self.print_thread:
            self.print_thread.join()
        self.print_thread = None
        self.gcode = []

    def print(self):
        ''' This is the print xmitter thread. It calls sendNext() repeatedly
            as long as self.printing is True. This thread is started upon the 
            print command in the gui. Before entering its main loop it kills
            the sender thread because we don't want two threads sending
            on the same port.
        '''
        print("Starting print thread")
        self.stop_xmtr = True   # kill xmtr thread first
        if self.xmtr:
            self.xmtr.join()    # wait until xmtr is dead
        self.xmtr = None
        self.CRCflag = False
        while self.printing and self.printer:
            self.sendNext()
        print("Print thread killed")
        self.xmtr = threading.Thread(target = self.sender)
        self.stop_xmtr = False
        self.xmtr.start()

    def _checksum(self, command):
        return reduce(lambda x, y: x ^ y, map(ord, command))

    def _send(self, command, lineno = 0, calcCRC = False):
        ''' If specified by calcCRC wraps command in linenum and
            checksum. If command is not M110 (set linenumber) and
            it is wrapped then save a copy in sentLines so it can
            be retrieved when a resend request occurs.
            Then, wrapped or not, transmit the command to the printer.
        '''
        if calcCRC:
            prefix = "N" + str(lineno) + " " + command
            command = prefix + "*" + str(self._checksum(prefix))
            if not "M110" in command:
                self.sentLines[lineno] = command
        if self.buffAvailable <= self.pending:
            return False  # no buffers free; call again later
#========================================================================
#        #resend test:
#        if not self.CRCflag and command.startswith("N10"):
#            command = "N10 GARBAGE*00" # bad command to trigger resend
#            self.CRCflag = True
#========================================================================
        self.pending += 1
        self.lastLineSent = lineno
#        print("Resending: {}; pending: {}; lastLine: {}; lastAck: {}; bufAvail: {}; P-word: {}".format( \
#            self.resending, self.pending, self.lastLineSent, self.lastLineAck, self.buffAvailable, self.P_word))
        try:
            self.printer.write((command + "\n").encode('ascii'))
        except SerialException:
            self.status.show("*** Error: Can't write to printer")
            self.printing = False # abort printing
        return True
        
        
    def sender(self):
        ''' This is the xmitter thread when not printing, such as for
            sending printer initialization commands or MDI from the gui.
            This thread is killed as soon as the print() thread starts.
        '''
        print("Starting transmitter thread")
        while not self.stop_xmtr:
            while data.xmtQ.empty():
                time.sleep(0.001)
                if self.stop_xmtr:
                    break
            else:
                command = data.xmtQ.get(True, 0.1)
                while not self._send(command) and not self.stop_xmtr:
                    time.sleep(0.001)
        print("Transmitter thread killed")
        
    def sendNext(self):
        ''' The workhorse for sending gcode data to the printer. It checks,
            in that order, either:
              - if we are still printing. If not, e.g. due to an abort,
                we return immediately. Also all waiting  loops check this.
              - if there is a resend request pending: if so it takes the
                next command from the history in the dictionary sentLines
              - if there is an entry in the priority queue (prioQ) it
                transmits that entry in front of any other command. 
                Currently not used.
              - otherwise it sends the next command from the gcode array
                in the main queue (gcode) and it appends the sent command
                to the sendLines dict.
                
        '''
        if not self.printer or not self.printing:
            return

        if self.resendFrom != -1 and self.resendFrom < self.linenum:
            self.resending = True   # tell listen thread to ignore subsequent resends
#            print("linenum: {}; resendFrom: {}".format(self.linenum, self.resendFrom))
            # we don't add linenum and CRC because line already has them
            while not self._send(self.sentLines[self.resendFrom], self.resendFrom, False):
                if not self.printing: # aborted..
                    return
                time.sleep(0.0005)
            self.resendFrom += 1    # resend all lines until linenum catches up
            return

        self.resendFrom = -1
        self.resending = False
        
        if not self.prioQ.empty():
            while not self._send(self.prioQ.get_nowait()):
                if not self.printing:
                    return
                time.sleep(0.0005)
            self.prioQ.task_done()
            return

        if self.queueindex < self.maxIndex:
            gline = self.gcode[self.queueindex]
            self.queueindex += 1
            # remove empty lines and comments:
            gline = gline[:gline.find(';')]
            if gline:
                while not self._send(gline, self.linenum, True):
                    # wait for space in Marlin's buffers
                    if not self.printing:
                        return  # avoid hang-up when aborted
                    time.sleep(0.0005)
                self.linenum += 1
        else:
            self.printing = False   # we're done (or aborted)...
            self.status.show( "\nPrinting Completed")
            self.print_thread = None
            self.linenum = 0
            self.queueindex = 0
        
    def connect(self, status=None):
        ''' The method to open the connection to the Marlin printer via
            the serial port. If the port could be opened successfully
            this method also starts the listen thread and the sender
            thread in order to be able to access the printer.
            This method is normally invoked from the Gui Connect button.
        '''
        try:
            self.printer = Serial(port = data.port,
                              baudrate = data.baud,
                              timeout = 0.25,
                              parity = PARITY_NONE)
            if not self.printer.isOpen():
                self.printer.open()
            self.printer.flush()
            self.printer.setDTR(1)  # hardware resets the machine
            self.printer.setDTR(0)
            data.connected = True
            status.show("printer is on-line\n")

        except SerialException as e:
            print("Could not connect to {} at baudrate {}:" \
                  .format(data.port, data.baud), e)
            return False   # error!
        self.rcvr = threading.Thread(target = self.listen)
        self.xmtr = threading.Thread(target = self.sender)
        self.stop_xmtr = False
        self.stop_rcvr = False
        self.rcvr.start()
        self.xmtr.start()
        return True

    def disconnect(self, status=None):
        ''' Disconnect the port, stop all running threads, clear
            status vars.
        '''
        if self.rcvr:
            self.stop_rcvr = True
            if threading.current_thread() != self.rcvr:
                self.rcvr.join()  # wait till thread is dead
            self.rcvr = None
        data.stop_decoder()
        if self.xmtr:
            self.stop_xmtr = True
            self.xmtr.join()
            self.xmtr = None
        if self.print_thread:
            self.stop_print_thread = True
            self.print_thread.join()
            self.print_thread = None
        if self.printer.isOpen():
            self.printer.close()
            self.printer = None
        data.ready = False     # reset transprt state
        data.connected = False
        data.homed = set()     # unhome all axes (needed??)
        status.show("printer off-line\n")
       
