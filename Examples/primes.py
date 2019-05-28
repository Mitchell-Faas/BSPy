import BSPy
from math import *

def spmd(bsp: BSPy.BSPObject, n):
    p = bsp.cores
    s = bsp.pid

    if s == 0:
        for i in range(p):
            bsp.send(n, i)

    bsp.sync()

    max_n = bsp.move()
    sqrt_n = floor(sqrt(max_n))
    sieveList = Sieve(sqrt_n+1)

    # Generate list of primes this core has to do and comb them
    per_core = max_n / p
    start = max(2, s*per_core) # make sure we don't count 0 and 1
    end = min(max_n, (s+1)*per_core)
    primeList = Comb(sieveList, start = start, end = end)
    primeAmount = len(primeList)

    bsp.send(primeAmount, 0)
    #bsp.send(primeList, 0)
    bsp.sync()

    if s == 0:
        total = 0
        #total = []
        for i in range(p):
            total += bsp.move()

        print("Total line 34:", total)


def Sieve(n: int):
    # Initialize primes array
    primes = [1]*n
    for i in range(n):
        primes[i] = i

    # Start sieving
    foundPrimes = 0
    for i in range(2,n):
        # if i isn't sieved out, discard its multiples
        if primes[i] != 0:
            foundPrimes += 1
            for j in range(2*i, n, i):
                primes[j] = 0

    # Fill primeList
    primeList = []
    for i, x in enumerate(primes[2:]): # Discard the first 2 elements (0, 1)
        if x != 0:
            primeList.append(i+2)

    return primeList


def Comb(primesSieved: list, start: int, end: int):
    # Do some type cleanup
    start = int(start)
    end = int(end)
    # Initialize checklist
    numbers = [1]*(end-start)

    # comb out the non-primes
    for prime in primesSieved:
        # x*primeList[i] - start --> needs to be positive
        pSieveSqrd = prime**2

        # Ensure we we don't try to access weird indicies
        if start > pSieveSqrd:
            # If the start is larger than psquared, define jStart
            # at the next index to cross off
            if start % prime == 0:
                jStart = start
            else:
                jStart = start + (prime - start % prime)
        else:
            jStart = pSieveSqrd

        # Do the sieving
        for j in range(jStart, end, prime):
            numbers[j - start] = 0


    # Go through the sieved list
    primesList = []
    counter = 0
    for i, x in enumerate(numbers):
        if x != 0:
            primesList.append(start+i)

    return primesList


if __name__ == '__main__':
    n = 10**5#int(input("n="))
    BSPy.run(spmd, 12, n)