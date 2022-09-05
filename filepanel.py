#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  3 16:03:11 2022

@author: hschulz
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd
import re


class Filepanel(ttk.Frame):
    
    def __init__(self, master):
        ttk.Frame.__init__(self, master)
        self.filename = None
        self.path = None    # remember directory for next time
        self.openBtn = ttk.Button(self, text='Open File', command=self.getfile)
        self.openBtn.grid(row=0, column=0)
        
    def getfile(self):
        self.filename = fd.askopenfilename(filetypes=(('g-code','*.gcode'),
                                                      ('all files', '*.*')),
                                           initialdir = self.path)
        if self.filename:
            path = re.findall('(.*\/).*$', self.filename)[0]
            self.path = path if path else None

