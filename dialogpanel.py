#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog as fd
from re import findall

import model, transport


class Dialogpanel(ttk.Frame):
    
    def __init__(self, master, output1, output2):
        ttk.Frame.__init__(self, master)
        self.lock = False
        self.master = master
        self.info = output1
        self.status = output2
        self.ready = False
        self.filename = None
        self.path = None    # remember directory for next time
        
        self.portOpenbtn = ttk.Button(self, command=self.openComms, 
                                      text = 'Connect', width=10)
        self.fileOpenbtn = ttk.Button(self,command=self.getfile,
                                       text='Open File', width=10)
        self.motorsOffbtn = ttk.Button(self,command=self.powerDown,
                                       text='Motors Off', width=10)
        self.printbtn = ttk.Button(self,command=self.startPrint,
                                       text='Print', width=10)
        self.abortbtn = ttk.Button(self,command=self.stopPrint,
                                       text='Abort', width=10)

        self.portOpenbtn.grid(row=0, column=0, padx=2, pady=2)
        self.motorsOffbtn.grid(row=0, column=1, padx=2, pady=2)
        self.fileOpenbtn.grid(row=0, column=2, padx=2, pady=2)
        self.printbtn.grid(row=0, column=3, padx=2, pady=2)
        self.abortbtn.grid(row=0, column=4, padx=2, pady=2)

        self.enable((self.fileOpenbtn, self.portOpenbtn))
        self.disable((self.motorsOffbtn, self.printbtn, self.abortbtn))

    def openComms(self):
        ''' pop up the open comms window to setp serial ink.'''
        if model.connected: # close port if already open
            transport.kill = True   # abort communication thread
            model.ready = False     # reset transprt state
            model.connected = False
            model.homed = set()     # unhome all axes (needed??)
            self.portOpenbtn.configure(text='Connect')
            if model.gcodeFile:
                self.disable((self.printbtn, self.motorsOffbtn))
            return
        if self.lock:   # allow only one instance of subwindow
            return
        self.lock = True
        openport = tk.Toplevel(self, bg='black')
        openport.title('Open Serial Port')
        openport.protocol('WM_DELETE_WINDOW', lambda: self.shutdown(openport))

        label1 = ttk.Label(openport, text='Serial Port id: ')
        entry1 = ttk.Entry(openport, width=12)
        label2 = ttk.Label(openport, text='Baud rate: ')
        entry2 = ttk.Entry(openport, width=12)
        okBtn = ttk.Button(openport, width=8, 
                           command=lambda: self.setport(entry1.get(), 
                                            entry2.get(), openport), 
                           text='OK')
        entry1.insert(0, model.port)
        entry2.insert(0, str(model.baud))
        cancelBtn = ttk.Button(openport, width=8,
                               command=lambda: self.shutdown(openport), 
                               text='Cancel')
        
        label1.grid(row=0, column=0, columnspan=3, pady=10, padx=5, sticky='W')
        entry1.grid(row=0, column=2, columnspan=2, pady=10, padx=5, sticky='E')
        label2.grid(row=1, column=0, columnspan=3, pady=10, padx=5, sticky='W')
        entry2.grid(row=1, column=2, columnspan=2, pady=10, padx=5, sticky='E')
        okBtn.grid(row=2, column=1, pady=10, padx=5)
        cancelBtn.grid(row=2, column=2, pady=10, padx=5)
        okBtn.focus_set()
        
    def setport(self, id, baud, widget):
        ''' Save port specs and close widget. '''
        try:
            model.port = id
            model.baud = int(baud)
            # start transport threads:
            if transport.init(id, baud, self.info, self.status) < 0:
                messagebox.showerror('Error', 'Error opening {} at {} baud'.
                                     format(id, baud))
                return
            model.connected = True
            self.status.show('Printer online\n')
            self.portOpenbtn.configure(text='Close')
            self.enable((self.motorsOffbtn))
            if model.gcodeFile:
                self.enable(self.printbtn)
        except ValueError:
            print('Invalid baudrate')
        finally:
            self.shutdown(widget)
            self.lock = False
        
    def shutdown(self, widget):
        ''' Destroy the specified widget.'''
        self.lock = False
        widget.destroy()

    def getfile(self):
        try:
            if model.gcodeFile: # do we already have a file open?
                model.gcodeFile.close() # yes; close it!
                model.gcodeFile = None
            self.filename = fd.askopenfilename(filetypes=(('g-code','*.gcode'),
                                                          ('all files', '*.*')), 
                                               initialdir = self.path)
            if self.filename:
                # extract directory path and filename:
                path = findall('(.*\/).*$', self.filename)[0]
                self.path = path if path else None
                file = findall('.*\/(.*)$', self.filename)[0]
                self.status.show('Opening ' + file)
                # open the file for later use:
                model.gcodeFile = open(self.filename)
                model.filesize = len(model.gcodeFile.readlines())
                model.gcodeFile.seek(0)
                if model.connected:
                    self.enable(self.printbtn)
        except Exception as e:
            messagebox.showerror('I/O Error', e)
            model.gcodeFile = None
        finally:
            if self.filename:
                self.status.show(' Failed\n' if not model.gcodeFile
                             else ' ..Ok\n')  
            
    def powerDown(self):
        ''' Send M81 to turn motor power off. '''
        model.xmtQ.put('M81')
        
    def startPrint(self):
        if model.gcodeFile and model.ready and not model.printing:
            self.status.show('Printing {} lines\n'.format(model.filesize))
            model.curline = 0
            model.gcodeFile.seek(0)
            model.xmtQ.put('M110 N1')   # reset line number
            model.linenum = 1
            model.printing = True   # release the transmitter...
            self.enable(self.abortbtn)
            self.disable((self.motorsOffbtn, self.printbtn,
                    self.portOpenbtn, self.fileOpenbtn))

    def stopPrint(self):
        if model.printing:
            self.status.show('\nAbort\n')
            model.printing = False
            model.xmtQ.put('M110 N1')   # reset line number
            model.linenum = 1
            self.disable(self.abortbtn)
            self.enable((self.motorsOffbtn, self.portOpenbtn, 
                         self.fileOpenbtn, self.printbtn))
#            if model.gcodeFile:
#                self.enable(self.printbtn)
                
    def enable(self, btns):
        ''' Set state of specified buttons to 'normal'.'''
        try:    # if btns is iterable
            for btn in btns:
                btn.config(state = 'normal')
        except TypeError: # else single item
            btns.config(state = 'normal')
        
        
    def disable(self, btns):
        ''' Set state of specified buttons to 'disabled'.'''
        try:    # iterable?
            for btn in btns:
                btn.config(state = 'disabled')
        except TypeError: # else single item
            btns.config(state = 'disabled')






