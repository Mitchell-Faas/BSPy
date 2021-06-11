from collections import deque
import multiprocessing as mp
from sys import version_info
import itertools
import time
import os

RUNNING_ON_WINDOWS = os.name == 'nt'

if not RUNNING_ON_WINDOWS:
    mp.set_start_method("fork")


class BSPObject:
    """The main BSP object that enables use of BSP

    This class keeps track of communication lines, its pid and the total cores
    it also enables the use of BSP functions through these variables. This is
    a low level object which the end user should not need to call directly.

    Parameters
    ----------
    cores : int
        The total number of cores in this BSP instance.
    pid : int
        This processor's id. It always holds that 0 <= pid < cores.
    pipe_dict : dict of Pipeconnection
        A connection to every other processor. Should be given
        through the run() function.
    barrier : barrier
        The barrier object all processors adhere to.

    Attributes
    ----------
    cores : int
        The total number of cores in this BSP instance (run).
    pid : int
        This processor's id. It always holds that 0 <= pid < cores"""

    def __init__(self, cores, pid, pipe_dict, barrier):
        # Constants
        self.PIPE_TYPE = mp.connection.PipeConnection if RUNNING_ON_WINDOWS else mp.connection.Connection
        self.QUEUE_TYPE = mp.queues.Queue

        # These should be static
        self._pipe_dict = pipe_dict
        self._barrier = barrier

        self.cores = cores
        self.pid = pid

        # These are expected to be dynamic and change.
        self._to_send_dict = {}
        self._queue = deque()

    def _clear_to_send(self):
        """Clears the _to_send dictionary.

        Should not be used by the end user in normal operation.

        Returns
        -------
        out : None"""
        self._to_send_dict = {}

    def _is_empty(self, comm_line):
        """
        Tells you if the comm_line is empty

        Parameters
        ----------
        comm_line : Pipe or Queue
            The communication line you're asking about.

        Returns
        -------
        out : bool
            True if comm_line is empty, False otherwise.
        """
        if type(comm_line) == self.PIPE_TYPE:
            empty = not comm_line.poll()
        elif type(comm_line) == self.QUEUE_TYPE:
            empty = comm_line.empty()
        else:
            raise TypeError("comm_line is neither a queue, nor a pipe")

        return empty

    def sync(self):
        """sync()

        Starts the synchronisation defined in the BSP model. A synchronisation
        consists of 3 distinct steps:
        1) Wait for all processing nodes to finish computing
        2) Send all messages that have queued up since the last sync
        3) Receive all messages that have been sent in the previous step.
        After sync() has completed, every processor will have access to the data that
        has been sent to it.

        Returns
        -------
        out : None"""

        # Ensure every processor is done doing what it was doing before
        self._barrier.wait()

        # Send all data
        for key in self._to_send_dict:
            # Pick the right communication line
            comm_line = self._pipe_dict[key]
            send_queue = self._to_send_dict[key]

            # Until the send_queue is empty
            while send_queue:
                # Pop the first message in send_queue, and send it.
                message = send_queue.popleft()
                if type(comm_line) == self.PIPE_TYPE:
                    # comm_line is a Pipe object
                    comm_line.send(message)
                elif type(comm_line) == self.QUEUE_TYPE:
                    # comm_line is a Queue object, so use put
                    comm_line.put(message)
                else:
                    raise TypeError("comm_line is neither a queue, nor a pipe")

        # Clear _to_send_dict
        self._clear_to_send()

        # Ensure sending is done
        self._barrier.wait()

        # Clear the previous incoming _queue
        self._queue = deque()

        # Go through every pipe (to get data)
        for key in self._pipe_dict:
            comm_line = self._pipe_dict[key]

            while not self._is_empty(comm_line):
                if type(comm_line) == self.PIPE_TYPE:
                    # comm_line is a Pipe object
                    message = comm_line.recv()
                elif type(comm_line) == self.QUEUE_TYPE:
                    # comm_line is a Queue object, so use get

                    # Nothing can change in the size of the comm_line queue now;
                    # we've already sent everything in the previous step.
                    # Hence, we can reliably use the size of the queue to see if we can get.
                    message = comm_line.get()
                else:
                    raise TypeError("comm_line is neither a queue, nor a pipe")

                self._queue.append(message)

        # Ensure getting is done
        self._barrier.wait()
        # Everyone is released and the _barrier reset.

    def send(self, message, pid):
        """
        Sends a message to the processor identified with pid.

        Parameters
        ----------
        message : literally anything
            Whatever data you wish to transfer between processors
        pid : int
            The processor id to which you wish to send a message.

        Returns
        -------
        out : None"""

        # Add message to _queue
        if pid not in self._to_send_dict:
            self._to_send_dict[pid] = deque()
        self._to_send_dict[pid].append(message)

    def move(self):
        """
        Acquires the first message stored in the receiving queue.

        Used to grab data from the receiving queue. This is a pop-like function
        and previously returned data cannot be returned a second time.
        returns None if queue is empty.

        Returns
        -------
        out : queue data
            The first element in the processor's "receive" queue."""
        try:
            return self._queue.popleft()
        except IndexError:
            return None

    @staticmethod
    def time():
        """Records the current Unix time in seconds of the system as a float.

        Returns
        -------
        out : float
            Current Unix time in seconds"""

        if version_info >= (3, 7):
            return time.time_ns() / (10 ** 9)  # Convert to floating-point seconds
        else:
            return time.time()

    def nprocs(self):
        """Finds number of available processors in BSP instance.

        Returns
        -------
        out : int
            Number of processors participating in the current BSP instance."""
        return self.cores


def _create_pipes(cores):
    """Creates all communication pipes between processors.

    Sets up pipes and queues for all processors by using a dict of dicts.
    Part of this dict of dicts will be sent to every processor for communication
    when the run() function is called.

    Parameters
    ----------
    cores : int
        The total number of cores you'll be running your BSP instance with.

    Returns
    -------
    out : dict of dicts
        A dictionary that connects each processor together."""
    # Create all combinations of channels
    channels = itertools.combinations(range(cores), 2)

    # This lists all graph edges.
    pipe_dict = {}
    # Add self references ((1,1), (2,2), etc)
    for core in range(cores):
        # Create a _queue
        self_queue = mp.Queue()
        pipe_dict[core] = {}
        pipe_dict[core][core] = self_queue

    for channel in channels:
        # Create the actual pipe
        end1, end2 = mp.Pipe()

        # Get processor numbers
        proc1, proc2 = channel

        # Every key already exists because we made self-relations.
        pipe_dict[proc1][proc2] = end1
        pipe_dict[proc2][proc1] = end2

    return pipe_dict


def run(function, cores=0, *args):
    """Execute function on number of cores specified.

    This is how a BSP program is launched. Function needs to be of the form func(BSP:BSPObject).
    run() needs to be nested in an if __name__ = '__main__' statement.

    Parameters
    ----------
    function : callable
        A callable function to run in BSP.
    cores : int, optional
        The amount of cores you wish to use
        Defaults to all available cores
    *args : optional
        Any arguments you wish to pass on to your function.

    Returns
    -------
    out : None"""
    try:
        # If cores isn't given or is 0, then set to maximum
        if not cores:
            cores = mp.cpu_count()
        # Core exception handling
        if type(cores) != int:
            raise TypeError("Cores must be an int")
        if cores < 0:
            raise ValueError("Cores must be positive")

        # Function exception handling
        if not callable(function):
            raise TypeError("Function must be callable")

        # First open all communication channels.
        # There will be be n(n-1)/2 channels.
        pipe_dict = _create_pipes(cores)

        # Then create a _barrier
        barrier = mp.Barrier(cores)

        # Start all processes one after the other.
        for i in range(cores):
            # Create a BSP data object
            bsp = BSPObject(cores=cores, pid=i, pipe_dict=pipe_dict[i], barrier=barrier)

            # Send BSP object
            p = mp.Process(target=function, args=(bsp, *args))
            p.start()
    except RuntimeError:
        raise RuntimeError('''
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
        
        This probably means that you tried to use the run function
        but have forgotten to use the proper safeguard:
        
            if __name__ == '__main__':
                run(function, cores)
        
        This is essential for the program to run properly.''')


def max_cores():
    """Finds number of available processors of the system.

    Returns
    ----------
    out : int
        Maximum number of available processors."""
    return mp.cpu_count()
