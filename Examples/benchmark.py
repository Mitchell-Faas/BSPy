import BSPy
import sys

NITERS = 10 ** 3 # number of iterations
MAXN = 2**10 # Maximum length of DAXPY (from bspbench of Biss)
MAXH = 2 ** 8 # Maximum h-relation
MEGA = 10**6


def leastsqares(h0, h1, t):
    sumt=0
    sumth=0

    for h, timeh in enumerate(t):
        sumt += timeh
        sumth += timeh*h

    nh = h1-h0+1
    h00 = h0*(h0-1)
    h11 = h1*(h1+1)
    sumh = (h11-h00)/2
    sumhh = (h11*(2*h1+1) - h00*(2*h0-1))/6

    a = nh/sumh
    if abs(nh)>abs(sumh):
        g = (sumth - a*sumt) / (sumhh - a*sumh)
        l = (sumt - sumh*g) / nh
    else:
        g = (sumt - a*sumth) / (sumh - a*sumhh)
        l = (sumth - sumhh * g) / sumh

    return (g,l)


def bench(bsp: BSPy.BSPObject):
    p = bsp.cores
    s = bsp.pid

    times = []


    #################
    #  Determine r  #
    #################
    r = 0
    n = 1
    while n <= MAXN:
        # Initialize scalars and vectors
        alpha = 1 / 3
        beta = 4 / 9

        x = [x for x in range(n)]
        y = [x for x in range(n)]
        z = [x for x in range(n)]
        times = [0] * (MAXH+1)

        # Measure time of 2*NITERS DAXPY operations of length n
        tic = bsp.time()
        for iter in range(NITERS):
            for i in range(n):
                y[i] += alpha * x[i]
            for i in range(n):
                z[i] -= beta * x[i]
        toc = bsp.time()

        time = toc - tic

        bsp.send(time, 0)
        bsp.sync()

        # Proc 0 determines min, max, and avg computing rate
        if s == 0:
            time_list = [bsp.move() for x in range(p)]
            mintime = min(time_list)
            maxtime = max(time_list)

            # Workaround for bug
            if mintime == None:
                continue

            if mintime > 0:
                nflops = 4 * NITERS * n
                r = 0
                for time in time_list:
                    r += nflops / time
                r /= p

                print("n={}, min={}, max={}, av={} Mflop/s"
                      .format(n,
                              round(nflops / (maxtime*MEGA),3),
                              round(nflops / (mintime*MEGA),3),
                              round(r / MEGA),3))
            else:
                print("Minimum time is 0")

        # Increase n
        n *= 2


    #######################
    #  Determine g and l  #
    #######################

    for h in range(MAXH+1):
        # Initialize communication pattern
        src = [i for i in range(h)]

        if p == 1:
            destproc = [0 for _ in range(h)]
        else:
            destproc = [(s+1 + i%(p-1)) %p for i in range(h)]

        bsp.sync()

        tic = bsp.time()
        for iter in range(NITERS):
            # Send data
            for i in range(h):
                bsp.send(src[i], destproc[i])

            bsp.sync()
            # Receive data
            for i in range(h):
                bsp.move()
        toc = bsp.time()

        time = toc-tic

        # Compute the time for one h-relation
        if s == 0:
            times[h] = (time*r)/NITERS
            print("Time of %5d-relation= %lf sec= %8.0lf flops"%(h, time/NITERS, times[h]))

    if s==0:
        print('size of int = {} bytes'.format(sys.getsizeof(7)))
        (g,l) = leastsqares(0,p,times)
        print('Range h=0 to p  : g= {}, l={}'.format(g,l))
        (g, l) = leastsqares(p, MAXH, times)
        print('Range h=p to {}  : g= {}, l={}'.format(MAXH, g, l))

        print("The bottom line for this BSP computer is:")
        print("p= {}, r= {} Mflop/s, g= {}, l= {}".format(p, r / MEGA, g, l))


if __name__ == '__main__':
    BSPy.run(bench, 8)