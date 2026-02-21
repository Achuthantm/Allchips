# Naive Python can run about 10^6 operations and have an error of 0.1%
# MCCFR 10^6 reps -> ([0.332718325082334, 0.3332732584905663, 0.3340084164270996])
# CFR+ 10^6 reps -> 
# (0, 1, 2) -> (Rock, Paper, Scissor)
import numpy as np
import random
N: int = 3
RPS:int = 1000000
cumalative_regret: list[int] = [0]*N
strategy_sum: list[int] = [0]*N
def get_strategy(rep):
    strat: list[float] = [0]*N
    cm_regret:int = 0
    for i in range(N):
        if cumalative_regret[i] > 0:
            cm_regret = cm_regret + cumalative_regret[i]
            strat[i] = cumalative_regret[i]
    if(cm_regret == 0):
        return [1.0/N]*N
    for i in range(N):
        strat[i] = strat[i]/cm_regret
        strategy_sum[i] += strat[i]
    return strat

def get_action(strat: list[float]):
    rng: float = random.random()
    i: int = 0
    sm: int = 0
    while(True):
        sm = sm + strat[i]
        if sm > rng:
            return i
        i = i + 1
    assert(False)

def getAvgStrat():
    sm = 0
    for i in range(N):
        sm = sm + strategy_sum[i]
    ans = strategy_sum
    for i in range(N):
        ans[i] = ans[i]/sm
    return ans

for _ in range(RPS):
    s = get_strategy(_)
    P1 = get_action(s)
    P2 = get_action(s)
    ## We are optimising for P1 
    utility = [0]*N
    utility[P2] = 0
    utility[(P2 + 1)%N] = 1
    utility[(P2 + N - 1)%N] = -1
    for i in range(N):
        cumalative_regret[i] = cumalative_regret[i] + (utility[i] - utility[P1])

print(getAvgStrat())
