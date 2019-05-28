from collections import deque
import multiprocessing as mp
from sys import version_info
import itertools
import time

class BSPObject:
    # The main BSP class

    def __init__(self, cores, pid, pipe_dict, barrier):
        # These should be static
        self._pipe_dict = pipe_dict
        self._barrier = barrier

        self.cores = cores
        self.pid = pid

        # These are expected to be dynamic and change.
        self._to_send_dict = {}
        self._queue = deque()

    def _clear_to_send(self):
        self._to_send_dict = {}

    def _is_empty(self, comm_line):
        """Returns true if comm_line is empty.
        :comm_line: Pipe or Queue"""
        if type(comm_line) == mp.connection.PipeConnection:
            empty = not comm_line.poll()
        elif type(comm_line) == mp.queues.Queue:
            empty = comm_line.empty()
        else:
            raise TypeError("comm_line is neither a queue, nor a pipe")

        return empty

    def sync(self):
        """sync()

            Ensures all threads have stopped and parse
            all communication

            Returns
            ----------
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
                if type(comm_line) == mp.connection.PipeConnection:
                    # comm_line is a Pipe object
                    comm_line.send(message)
                elif type(comm_line) == mp.queues.Queue:
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
                if type(comm_line) == mp.connection.PipeConnection:
                    # comm_line is a Pipe object
                    message = comm_line.recv()
                elif type(comm_line) == mp.queues.Queue:
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

    def send(self, message, send_pid):
        """send(message, pid)

            Sends any object to the processor with a pid of send_pid.

            Parameters
            ----------
            message : literally anything
              Whatever data you wish to transfer
              between processors
            send_pid : int
              The processor id to which you wish
              to send a message.

            Returns
            ----------
            out : None"""

        # Add message to _queue
        if send_pid not in self._to_send_dict:
            self._to_send_dict[send_pid] = deque()
        self._to_send_dict[send_pid].append(message)

    def move(self):
        """"move()

        Acquires the first message stored in the receiving queue

        Returns
        ----------
        out : queue data
          The first element in the processor's "receive" queue."""
        if len(self._queue) > 0:
            message = self._queue.popleft()
        else:
            message = None
        return message

    @staticmethod
    def time():
        """time()

        Records the current Unix time in seconds of the system as a float.

        Returns
        ----------
        out : float
          Current Unix time in seconds"""

        if version_info >= (3, 7):
            return time.time_ns() / (10 ** 9) # Convert to floating-point seconds
        else:
            return time.time()

    def nprocs(self):
        """nprocs()

            Finds number of available processors.

            Returns
            ----------
            out : int
              Number of processors participating
                in the current BSP instance."""
        return self.cores


def _create_pipes(cores):
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
    """run(function, [cores], [*args])

        Execute function on number of cores specified.
        Needs to be nested in an if __name__ = '__main__' statement.

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
        ----------
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
        but have forgotten to use the proper safequard:
        
            if __name__ == '__main__':
                run(function, cores)
        
        This is essential for the program to run properly.''')


def max_cores():
    """max_cores()

        Finds number of available processors.

        Returns
        ----------
        out : int
          Maximum number of available processors."""
    return mp.cpu_count()
