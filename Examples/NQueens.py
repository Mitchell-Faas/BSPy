import BSPy

N = 10
max_number = 10**2
counter = 0

def NQueens(BSP):
    def isSafe(N, board, row, col):
        # Check this row on the left side
        for i in range(col):
            if board[row][i]:
                return False

        # Check upper diagonal on left side
        i = row
        j = col
        while i >= 0 and j >= 0:
            if board[i][j]:
                return False
            i -= 1
            j -= 1

        # Check lower left diagonal
        i = row
        j = col
        while i < N and j >= 0:
            if board[i][j]:
                return False
            i += 1
            j -= 1

        return True

    def solveNQUtil(N, board, col, s):
        # Return true if all queens are placed
        if col == N:
            global counter
            counter += 1
            return True

        res = False
        for i in range(N):
            if isSafe(N, board, i, col):
                board[i][col] = 1
                res = solveNQUtil(N, board, col + 1, s) or res

                board[i][col] = 0

        return res

    def solveNQ(N, s, p):
        board = [[0] * N for x in range(N)]

        i = s
        while i < N:
            board[i][0] = 1
            solveNQUtil(N, board, 1, s)

            board[i][0] = 0

            i += p
        return

    tic = BSP.time()
    p = BSP.cores
    s = BSP.pid

    if s == 0:
        for i in range(p):
            BSP.send(N, i)

    BSP.sync()
    boardSize = BSP.move()

    solveNQ(boardSize, s, p)

    BSP.sync()

    for i in range(p):
        BSP.send(counter, i)

    BSP.sync()

    total = 0
    for i in range(p):
        total += BSP.move()

    toc = BSP.time()

    if s ==0:
        print("we found {} solutions in {} seconds.".format(total, toc - tic))


if __name__ == '__main__':
    BSPy.run(NQueens, 4)


