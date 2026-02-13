# -*- coding: utf-8 -*-
"""Threading utilities for the Scanning Magnetometer application.

This module contains the Worker thread class, signals, and a base mixin for components
that need to execute long-running operations asynchronously to avoid blocking the UI.
"""

from PyQt6 import QtCore
import sys
import traceback


class WorkerSignals(QtCore.QObject):
    """Signals emitted by Worker threads."""
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    results = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(object)


class Worker(QtCore.QRunnable):
    """Worker thread for executing functions asynchronously."""

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
        # Add callback to kwargs for progress updates
        self.kwargs['progress_callback'] = self.signals.progress

    @QtCore.pyqtSlot()
    def run(self):
        """Execute the function and emit appropriate signals."""
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.results.emit(result)
        finally:
            self.signals.finished.emit()


class ThreadedComponent:
    """Mixin class for components that execute operations on worker threads.
    
    Provides a unified thread_function method that handles Worker creation,
    signal connection, and thread pool submission.
    """

    def thread_function(self, fn, *args, **kwargs):
        """Execute a function asynchronously on a worker thread.
        
        Args:
            fn: The function to execute asynchronously
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments. Special kwargs:
                - fin_fn: Function to call when execution finishes
                - prg_fn: Function to call for progress updates
                - err_fn: Function to call if an error occurs
                - progress_callback: Automatically added for progress updates
        
        The function will be executed in a worker thread, preventing UI blocking.
        Signals will be emitted for progress, completion, and errors.
        """
        self.worker = Worker(fn, args, kwargs)
        
        # Connect finish signal
        if 'fin_fn' in kwargs:
            self.worker.signals.results.connect(kwargs['fin_fn'])
        
        # Connect progress signal
        if 'prg_fn' in kwargs:
            self.worker.signals.progress.connect(kwargs['prg_fn'])
        
        # Connect error signal
        if 'err_fn' in kwargs:
            self.worker.signals.error.connect(kwargs['err_fn'])
        
        # Start the worker in the global threadpool
        QtCore.QThreadPool.globalInstance().start(self.worker)
