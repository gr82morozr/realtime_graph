#!/apps/anaconda3/bin/python3

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import sys
import re
import time
import json
import multiprocessing
import collections
import serial
import socket

import py3toolbox as tb
import pyqtgraph as pg
from random import randint
from multiprocessing import Process, Pipe
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt, QTime, QTimer)
from collections import deque , defaultdict

module_name = 'GraphMonitor'

def get_config():
  return tb.load_json('./config.json')[module_name]


def get_config1():
  config = {
    'DATA_FEED_WAIT'  : True,
    'DROP_FRAME'      : True,
    'REFRESH_RATE'    : 20,


    'DATA_FILE'       : './sample.data',
    'LOG_FILE'        : '/tmp/1.log',
    'FILE_TEST'       : True,

   
    'DEBUG_MODE'      : False,
    'PEN_WIDTH'       : 0,
    'WIN_SIZE_X'      : 1400,
    'WIN_SIZE_Y'      : 800,
    'win_title'       : 'Realtime Data Visualizer',
    'CUSTOM_CONFIG'   : False,
    
    'layouts'          : {
      'win_layout'      : (5,3),
      'boards'          : { 
                            '1'   : { 'layout' : (1,1,1,1), 'max_entries' : 100 },
                            '2'   : { 'layout' : (1,2,1,1), 'max_entries' : 100 },
                            '3'   : { 'layout' : (1,3,1,1), 'max_entries' : 100 },       
                            
                            '4'   : { 'layout' : (2,1,1,1), 'max_entries' : 100 }, 
                            '5'   : { 'layout' : (2,2,1,1), 'max_entries' : 100 },
                            '6'   : { 'layout' : (2,3,1,1), 'max_entries' : 100 }, 
                            
                            '7'   : { 'layout' : (3,1,1,1), 'max_entries' : 100 }, 
                            '8'   : { 'layout' : (3,2,1,1), 'max_entries' : 100 },
                            '9'   : { 'layout' : (3,3,1,1), 'max_entries' : 100 }, 

                            '10'  : { 'layout' : (4,1,1,1), 'max_entries' : 100 }, 
                            '11'  : { 'layout' : (4,2,1,1), 'max_entries' : 100 },
                            '12'  : { 'layout' : (4,3,1,1), 'max_entries' : 100 }, 

                            '13'  : { 'layout' : (5,1,1,3), 'max_entries' : 400 }

                          }
    },

    'data_config'     : { 
                          'ax'      : { 'board_id'    : '1', 'color' : 'b'  },
                          'ay'      : { 'board_id'    : '2', 'color' : 'g'  },
                          'az'      : { 'board_id'    : '3', 'color' : 'r'  },

                          'gx'      : { 'board_id'    : '4', 'color' : 'c'  },
                          'gy'      : { 'board_id'    : '5', 'color' : 'm'  },
                          'gz'      : { 'board_id'    : '6', 'color' : 'y'  },
                          
                          'ax_raw'  : { 'board_id'    : '1', 'color' : (60,60,60)   },
                          'ay_raw'  : { 'board_id'    : '2', 'color' : (60,60,60)   },
                          'az_raw'  : { 'board_id'    : '3', 'color' : (60,60,60)   },

                          'gx_raw'  : { 'board_id'    : '4', 'color' : (60,60,60)   },
                          'gy_raw'  : { 'board_id'    : '5', 'color' : (60,60,60)   },
                          'gz_raw'  : { 'board_id'    : '6', 'color' : (60,60,60)   },
                          
                          'Pitch'   : { 'board_id'    : '7', 'color' : 'r'   },
                          'Yaw'     : { 'board_id'    : '8', 'color' : 'g'   },
                          'Roll'    : { 'board_id'    : '9', 'color' : 'b'   },

                          'err_P'   : { 'board_id'    :'10', 'color' : 'r'   },
                          'err_I'   : { 'board_id'    :'11', 'color' : 'g'   },
                          'err_D'   : { 'board_id'    :'12', 'color' : 'b'   },

                          'Error'     : { 'board_id'    :'13', 'color' : 'w'   },
                          'PID'       : { 'board_id'    :'13', 'color' : 'r'   },
                          'g_int'     : { 'board_id'    :'13', 'color' : 'g'   },
                          'g_pitch'   : { 'board_id'    :'13', 'color' : 'b'   }
                          
                        }
  }
  return config


class GraphMonitor(multiprocessing.Process):
  def __init__(self,in_q=None):
    multiprocessing.Process.__init__(self)
    self.config     = get_config()
    self.in_q       = in_q
    self.trace_data = {}

    # data stuff
    self.fps = 0   

    # for FPS calculation
    self.last  = time.time()

  def init_plots(self):
    self.app = QtGui.QApplication([])
    self.win = pg.GraphicsWindow(title="Basic plotting")
    self.win.addLayout(row=self.config['layouts']['win_layout'][0], col=self.config['layouts']['win_layout'][1]) 
    self.win.resize(self.config['layouts']['win_size'][0],self.config['layouts']['win_size'][1])

    self.win.setWindowTitle(self.config['win_title'])
    pg.setConfigOptions(antialias=True)    
    self.boards = {}
    for b in self.config['layouts']['boards'].keys():
      cfg = self.config['layouts']['boards'][b]['layout']
      t_row     = cfg[0]
      t_col     = cfg[1]
      t_rowspan = cfg[2]
      t_colspan = cfg[3]      
      title     = None
      for d in self.config['data_config'].keys():
        if self.config['data_config'][d]['board_id'] == b :
          if title is None : title=d 
          else: title += ',' + d
      self.boards[b] =  self.win.addPlot(row=t_row, col=t_col, rowspan=t_rowspan, colspan=t_colspan, title=title) 
      


  def init_trace_data (self, key):
    max_entries =  self.config['layouts']['boards'][self.config['data_config'][key]['board_id']]['max_entries']
    self.trace_data[key] = {}
    self.trace_data[key]['color']   = self.config['data_config'][key]['color']
    self.trace_data[key]['x_data']  = np.arange(0,max_entries,1)
    self.trace_data[key]['y_data']  = deque ([0] * max_entries, maxlen = max_entries)
    self.trace_data[key]['plot']    = self.boards[self.config['data_config'][key]['board_id']].plot(pen=pg.mkPen(self.trace_data[key]['color'], width=1), name=key)
    
  
  # update FPS  
  def update_fps(self):
    self.fps = int(1.0/(time.time() - self.last + 0.00001 ))
    self.last = time.time()
    self.win.setWindowTitle(self.config['win_title'] + ' : ' + str(self.fps ) + ' FPS, Q = ' + str(self.in_q.qsize())  )
    #print (self.fps)

  # update data for charts  
  def update(self):
    
    # wait for data feed
    if self.config['data_feed_wait'] == True:
      #rawdata = self.in_q.get()
      #print (rawdata)
      data = self.in_q.get()
      #data = json.loads(self.in_q.recv())
      #if self.config['DROP_FRAME'] == True and self.config['FILE_TEST'] == False and self.in_q.qsize() > int(self.fps / 8) :
      #  return
      for k in data.keys():
        if k not in self.config['data_config']: continue
        if k not in self.trace_data :
          self.init_trace_data(k)
        self.trace_data[k]['y_data'].append(float(data[k]))
    else :
      # NOT wait for data feed
      try :
        data = json.loads(self.in_q.get(block=False, timeout=1))
        #data = json.loads(self.in_q.recv())
        for k in data.keys():
          if k not in self.config['data_config']: continue
          if k not in self.trace_data:
            self.init_trace_data(k)
          self.trace_data[k]['y_data'].append(float(data[k]))        
      except Exception:
        for k in self.trace_data.keys():
          self.trace_data[k]['y_data'].append( self.trace_data[k]['y_data'][-1] )  
      
    for k in self.trace_data.keys():
      self.trace_data[k]['plot'].setData(self.trace_data[k]['x_data'] ,self.trace_data[k]['y_data'])
     
    self.update_fps()

  def run(self):
    self.init_plots()
    # kick off the animation
 
    timer = QtCore.QTimer()
    timer.timeout.connect(self.update)

    if self.config['data_feed_wait'] == True:
      timer.start(0)
    else:
      timer.start(self.config['refresh_rate'])

    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
      QtGui.QApplication.instance().exec_() 
 



if __name__ == '__main__':
  g    = GraphMonitor()
  g.start()

  pass