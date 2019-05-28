import BSPy

def hello_proc(bsp: BSPy.BSPObject):
    # Get the data we need about the BSP instance
    cores = bsp.cores
    pid = bsp.pid

    # Queue all messages for sending
    for destination in range(cores):
        bsp.send("Hello from proc %d to proc %d"%(pid, destination), pid=destination)

    # Synchronise the system
    bsp.sync()

    # Print the received messages
    for _ in range(cores):
        message = bsp.move()
        print(message)

if __name__ == '__main__':
    BSPy.run(hello_proc, 2)