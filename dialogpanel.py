#!/usr/bin/env python2

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog as fd
from re import findall

import data as d

class Dialogpanel(ttk.Frame):
    
    def __init__(self, master, transport, info, status):
        ttk.Frame.__init__(self, master)
        self.lock = False
        self.master = master
        self.transport = transport
        self.info = info
        self.status = status
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
        self.abortbtn = ttk.Button(self,command=self.abortPrint,
                                       text='Abort', width=10)

        self.portOpenbtn.grid(row=0, column=0, padx=2, pady=2)
        self.motorsOffbtn.grid(row=0, column=1, padx=2, pady=2)
        self.fileOpenbtn.grid(row=0, column=2, padx=2, pady=2)
        self.printbtn.grid(row=0, column=3, padx=2, pady=2)
        self.abortbtn.grid(row=0, column=4, padx=2, pady=2)

        self.enable((self.fileOpenbtn, self.portOpenbtn))
        self.disable((self.motorsOffbtn, self.printbtn, self.abortbtn))

    def openComms(self):
        ''' pop up the open comms window to setp serial link.'''
        if d.connected: # close port if already open
            self.transport.disconnect(status = self.status)
            self.portOpenbtn.configure(text='Connect')
            if d.gcodeFile:
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
        entry1.insert(0, str(d.port))
        entry2.insert(0, str(d.baud))
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
        ''' Save port specs, connect to printer and close widget. '''
        try:
            d.port = id
            d.baud = int(baud)
            if self.transport.connect(status = self.status):
                self.portOpenbtn.configure(text='Disconnect')
                self.enable((self.motorsOffbtn))
                if d.gcodeFile:
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
            if d.gcodeFile: # do we already have a file open?
                d.gcodeFile.close() # yes; close it!
                d.gcodeFile = None
            self.filename = fd.askopenfilename(filetypes=(('g-code','*.gcode'),
                                                          ('all files', '*.*')), 
                                               initialdir = "./testdata")
            if self.filename:
                # extract directory path and filename:
                path = findall('(.*\/).*$', self.filename)[0]
                self.path = path if path else None
                file = findall('.*\/(.*)$', self.filename)[0]
                self.status.show('Opening ' + file)
                # open the file for later use:
                d.gcodeFile = open(self.filename)
                d.filesize = len(d.gcodeFile.readlines())
                if d.connected: # printer is online and gcode file is open
                    self.enable(self.printbtn)
        except Exception as e:
            messagebox.showerror('I/O Error', e)
            d.gcodeFile = None
        finally:
            if self.filename:
                self.status.show(' Failed\n' if not d.gcodeFile
                             else ' ..Ok\n')  
            
    def powerDown(self):
        ''' Send M81 to turn motor power off. '''
        d.xmtQ.put('M81')
        
    def startPrint(self):
        if self.transport.start_print():
            self.status.show('Printing {} lines\n'.format(d.filesize))
            self.enable(self.abortbtn)
            self.disable((self.motorsOffbtn, self.printbtn,
                    self.portOpenbtn, self.fileOpenbtn))
    
    def abortPrint(self):
        self.transport.abort_print()
        self.status.show('\nAbort\n')
        self.stopPrint()

    def stopPrint(self):
        self.disable(self.abortbtn)
        self.enable((self.motorsOffbtn, self.portOpenbtn, 
                     self.fileOpenbtn, self.printbtn))
                
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





